-- AI Excel Copilot - Phase 8: hardening, quotas, audit, and retention
-- Run after 0006_guide.sql.

-- Keep user-visible metadata bounded and free of control characters.
alter table public.workbooks
  add constraint workbooks_filename_safe
  check (char_length(btrim(filename)) between 1 and 255
         and filename !~ '[[:cntrl:]]');

-- A small, non-sensitive audit trail for security and product operations.
create table public.audit_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  workbook_id uuid references public.workbooks(id) on delete set null,
  action      text not null check (action in ('upload_registered', 'workbook_deleted', 'analysis_completed', 'analysis_failed')),
  metadata    jsonb not null default '{}',
  created_at  timestamptz not null default now()
);
create index audit_events_user_created_idx on public.audit_events (user_id, created_at desc);
alter table public.audit_events enable row level security;
create policy "audit: select own" on public.audit_events
  for select to authenticated using (user_id = auth.uid());

create or replace function public.write_workbook_audit() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' then
    insert into public.audit_events (user_id, workbook_id, action, metadata)
    values (new.user_id, new.id, 'upload_registered',
            jsonb_build_object('size_bytes', new.size_bytes));
    return new;
  end if;
  insert into public.audit_events (user_id, workbook_id, action)
  values (old.user_id, old.id, 'workbook_deleted');
  return old;
end $$;

create trigger workbooks_audit_insert after insert on public.workbooks
  for each row execute function public.write_workbook_audit();
create trigger workbooks_audit_delete after delete on public.workbooks
  for each row execute function public.write_workbook_audit();

-- Free-tier safety limits. Existing workbooks are not removed.
create or replace function public.enforce_workbook_quota() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  active_count int;
  recent_count int;
begin
  select count(*) into active_count
    from public.workbooks
   where user_id = new.user_id
     and created_at > now() - interval '30 days';
  if active_count >= 25 then
    raise exception 'workbook_quota_exceeded' using errcode = 'P0001';
  end if;

  select count(*) into recent_count
    from public.workbooks
   where user_id = new.user_id
     and created_at > now() - interval '1 day';
  if recent_count >= 10 then
    raise exception 'upload_rate_limited' using errcode = 'P0001';
  end if;
  return new;
end $$;

create trigger workbooks_quota before insert on public.workbooks
  for each row execute function public.enforce_workbook_quota();

-- Service-role maintenance can remove audit data after the retention window.
create or replace function public.purge_old_audit_events(retention interval default interval '180 days')
returns int language plpgsql security definer set search_path = public as $$
declare removed int;
begin
  delete from public.audit_events where created_at < now() - retention;
  get diagnostics removed = row_count;
  return removed;
end $$;
revoke execute on function public.purge_old_audit_events(interval) from public, anon, authenticated;
grant execute on function public.purge_old_audit_events(interval) to service_role;

alter table public.analysis_jobs alter column pipeline_version set default 'phase8';
