-- AI Excel Copilot — Phase 5: AI layer (report §4.3, §6, §8, §15)
-- Run after 0004_charts.sql.

alter table public.analysis_jobs alter column pipeline_version set default 'phase5';
alter table public.workbook_profiles add column if not exists context jsonb not null default '{}';

-- ---------------------------------------------------------------- consent: AI is opt-in, per user
create table public.user_settings (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  ai_enabled     boolean not null default false,
  ai_consent_at  timestamptz,
  updated_at     timestamptz not null default now()
);
alter table public.user_settings enable row level security;
create policy "settings: select own" on public.user_settings for select to authenticated using (user_id = auth.uid());
create policy "settings: insert own" on public.user_settings for insert to authenticated with check (user_id = auth.uid());
create policy "settings: update own" on public.user_settings for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ---------------------------------------------------------------- insights
create table public.insights (
  id             uuid primary key default gen_random_uuid(),
  workbook_id    uuid not null references public.workbooks(id) on delete cascade,
  user_id        uuid not null references auth.users(id) on delete cascade,
  table_id       uuid references public.data_tables(id) on delete cascade,
  key            text not null,
  category       text not null,
  priority       int  not null,
  statement      text not null,                  -- what the data shows (numbers verified)
  interpretation text not null default '',       -- optional, hedged, no numbers
  next_check     text not null default '',
  next_plan      jsonb,                          -- ready plan for "Ask": answered without AI
  fact_keys      jsonb not null default '[]',
  finding_codes  jsonb not null default '[]',
  caveats        jsonb not null default '[]',
  source         text not null check (source in ('template','ai')),
  created_at     timestamptz not null default now(),
  unique (workbook_id, key)
);
create index insights_workbook_idx on public.insights (workbook_id, priority);
alter table public.insights enable row level security;
create policy "insights: select own" on public.insights for select to authenticated using (user_id = auth.uid());

-- ---------------------------------------------------------------- questions ("Ask your Excel"), answered by the worker
create table public.questions (
  id           uuid primary key default gen_random_uuid(),
  workbook_id  uuid not null references public.workbooks(id) on delete cascade,
  user_id      uuid not null default auth.uid() references auth.users(id) on delete cascade,
  text         text not null check (char_length(text) between 1 and 500),
  plan         jsonb,                            -- set by suggested questions; always re-validated by the worker
  status       text not null default 'queued' check (status in ('queued','answering','answered','failed')),
  answer       jsonb,
  error        text,
  attempts     int  not null default 0,
  created_at   timestamptz not null default now(),
  started_at   timestamptz,
  answered_at  timestamptz
);
create index questions_queue_idx on public.questions (status, created_at);
create index questions_workbook_idx on public.questions (workbook_id, created_at desc);
alter table public.questions enable row level security;
create policy "questions: select own" on public.questions for select to authenticated using (user_id = auth.uid());
create policy "questions: delete own" on public.questions for delete to authenticated using (user_id = auth.uid());
create policy "questions: insert own" on public.questions for insert to authenticated
  with check (user_id = auth.uid() and status = 'queued' and answer is null
              and exists (select 1 from public.workbooks w where w.id = workbook_id and w.user_id = auth.uid()));

-- at most 60 questions per user per hour (protects free AI quotas)
create or replace function public.limit_question_rate() returns trigger language plpgsql as $$
begin
  if (select count(*) from public.questions q where q.user_id = new.user_id and q.created_at > now() - interval '1 hour') >= 60 then
    raise exception 'rate_limited' using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger questions_rate_limit before insert on public.questions for each row execute function public.limit_question_rate();

create or replace function public.claim_next_question(stale_after interval default '2 minutes')
returns table (q_id uuid, wb_id uuid, owner_id uuid, q_text text, q_plan jsonb, q_attempts int)
language plpgsql security definer set search_path = public as $$
declare q public.questions;
begin
  update public.questions set status = 'failed', error = 'timeout', answered_at = now()
   where status = 'answering' and started_at < now() - stale_after and questions.attempts >= 2;
  select * into q from public.questions
   where (status = 'queued' or (status = 'answering' and started_at < now() - stale_after)) and questions.attempts < 2
   order by created_at for update skip locked limit 1;
  if not found then return; end if;
  update public.questions set status = 'answering', attempts = questions.attempts + 1, started_at = now() where id = q.id;
  return query select q.id, q.workbook_id, q.user_id, q.text, q.plan, q.attempts + 1;
end $$;
revoke execute on function public.claim_next_question(interval) from public, anon, authenticated;
grant  execute on function public.claim_next_question(interval) to service_role;

-- ---------------------------------------------------------------- let a user ask for their own workbook to be re-analysed
create or replace function public.request_reanalysis(p_workbook uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.workbooks w where w.id = p_workbook and w.user_id = auth.uid()) then
    raise exception 'not_found' using errcode = 'P0002';
  end if;
  if exists (select 1 from public.analysis_jobs j where j.workbook_id = p_workbook and j.status in ('queued','running')) then
    return;
  end if;
  insert into public.analysis_jobs (workbook_id, user_id) values (p_workbook, auth.uid());
end $$;
revoke execute on function public.request_reanalysis(uuid) from public, anon;
grant  execute on function public.request_reanalysis(uuid) to authenticated;

-- re-run profiled files so they get context and insights
insert into public.analysis_jobs (workbook_id, user_id)
select id, user_id from public.workbooks w
 where status = 'profiled' and not exists (select 1 from public.analysis_jobs j where j.workbook_id = w.id and j.status in ('queued','running'));
