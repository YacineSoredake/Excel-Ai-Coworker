-- AI Excel Copilot — Phase 6: guided analysis (report §7)
-- Run after 0005_ai.sql.

alter table public.workbook_profiles add column if not exists guide jsonb not null default '{}';
alter table public.analysis_jobs alter column pipeline_version set default 'phase6';

-- re-run profiled files so they get their guide
insert into public.analysis_jobs (workbook_id, user_id)
select id, user_id from public.workbooks w
 where status = 'profiled'
   and not exists (select 1 from public.analysis_jobs j where j.workbook_id = w.id and j.status in ('queued','running'));
