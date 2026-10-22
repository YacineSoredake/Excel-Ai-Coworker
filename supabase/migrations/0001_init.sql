-- AI Excel Copilot — Phase 1 foundation
-- Run in the Supabase SQL editor (or `supabase db push`).

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- tables

create table public.workbooks (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users(id) on delete cascade,
  filename         text not null,
  size_bytes       bigint not null check (size_bytes > 0 and size_bytes <= 10485760),
  storage_path     text not null unique,
  sha256           text,
  sheet_count      int,
  hidden_sheets    int,
  has_external_links boolean,
  status           text not null default 'uploaded'
                   check (status in ('uploaded','validating','validated','rejected','failed')),
  rejection_reason text,
  created_at       timestamptz not null default now(),
  -- the file must live inside the owner's own folder
  constraint workbooks_path_owner check (storage_path like user_id::text || '/%')
);
create index workbooks_user_created_idx on public.workbooks (user_id, created_at desc);

create table public.analysis_jobs (
  id               uuid primary key default gen_random_uuid(),
  workbook_id      uuid not null references public.workbooks(id) on delete cascade,
  user_id          uuid not null references auth.users(id) on delete cascade,
  status           text not null default 'queued'
                   check (status in ('queued','running','done','failed')),
  attempts         int  not null default 0,
  error            text,
  pipeline_version text not null default 'phase1',
  created_at       timestamptz not null default now(),
  started_at       timestamptz,
  finished_at      timestamptz
);
create index analysis_jobs_queue_idx on public.analysis_jobs (status, created_at);

-- ---------------------------------------------------------------- RLS
-- Users can read their own rows. All writes to jobs, and all status updates
-- on workbooks, are done by the worker with the service role (bypasses RLS).

alter table public.workbooks     enable row level security;
alter table public.analysis_jobs enable row level security;

create policy "workbooks: select own" on public.workbooks
  for select to authenticated using (user_id = auth.uid());
create policy "workbooks: insert own" on public.workbooks
  for insert to authenticated with check (user_id = auth.uid());
create policy "workbooks: delete own" on public.workbooks
  for delete to authenticated using (user_id = auth.uid());

create policy "jobs: select own" on public.analysis_jobs
  for select to authenticated using (user_id = auth.uid());

-- ---------------------------------------------------------------- auto-enqueue

create or replace function public.enqueue_analysis_job()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.analysis_jobs (workbook_id, user_id)
  values (new.id, new.user_id);
  return new;
end;
$$;

create trigger workbooks_enqueue_job
  after insert on public.workbooks
  for each row execute function public.enqueue_analysis_job();

-- ---------------------------------------------------------------- queue claim
-- Postgres-as-queue: FOR UPDATE SKIP LOCKED lets several workers run safely.

create or replace function public.claim_next_job(stale_after interval default '10 minutes')
returns table (job_id uuid, wb_id uuid, owner_id uuid, path text, name text, attempts int)
language plpgsql
security definer
set search_path = public
as $$
declare
  j public.analysis_jobs;
begin
  -- jobs stuck "running" that already used all attempts are failed for good
  update public.analysis_jobs
     set status = 'failed', error = 'timeout', finished_at = now()
   where status = 'running'
     and started_at < now() - stale_after
     and analysis_jobs.attempts >= 3;

  select * into j
    from public.analysis_jobs
   where (status = 'queued'
          or (status = 'running' and started_at < now() - stale_after))
     and analysis_jobs.attempts < 3
   order by created_at
   for update skip locked
   limit 1;

  if not found then
    return;
  end if;

  update public.analysis_jobs
     set status = 'running',
         attempts = analysis_jobs.attempts + 1,
         started_at = now(),
         error = null
   where id = j.id;

  return query
    select j.id, w.id, w.user_id, w.storage_path, w.filename, j.attempts + 1
      from public.workbooks w
     where w.id = j.workbook_id;
end;
$$;

revoke execute on function public.claim_next_job(interval) from public, anon, authenticated;
grant  execute on function public.claim_next_job(interval) to service_role;

-- ---------------------------------------------------------------- storage

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'workbooks', 'workbooks', false, 10485760,
  array['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
)
on conflict (id) do nothing;

-- Objects live at  <user_id>/<workbook_id>/original.xlsx
create policy "workbooks bucket: insert own folder" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'workbooks' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "workbooks bucket: read own folder" on storage.objects
  for select to authenticated
  using (bucket_id = 'workbooks' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "workbooks bucket: delete own folder" on storage.objects
  for delete to authenticated
  using (bucket_id = 'workbooks' and (storage.foldername(name))[1] = auth.uid()::text);
