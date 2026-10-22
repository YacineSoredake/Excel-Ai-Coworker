-- AI Excel Copilot — Phase 3: verified analytics facts (report §6.1, §14 phases F-H)
-- Run after 0002_profile.sql.

alter table public.workbook_profiles add column if not exists analytics jsonb not null default '{}';
alter table public.analysis_jobs alter column pipeline_version set default 'phase3';

create table public.facts (
  id          uuid primary key default gen_random_uuid(),
  workbook_id uuid not null references public.workbooks(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  table_id    uuid references public.data_tables(id) on delete cascade,
  kind        text not null,
  key         text not null,
  rank        int  not null,              -- 1 = highest score
  title       text not null,              -- the question the fact answers
  headline    text not null,              -- one deterministic, non-causal sentence
  definition  text not null,              -- how it was computed
  measure     text,
  dimension   text,
  time_column text,
  agg         text,
  payload     jsonb not null,             -- the numbers (series, groups, ...)
  spec        jsonb not null,             -- enough to recompute it (also used for drill-down later)
  source      jsonb not null default '{}',
  caveats     jsonb not null default '[]',
  sample_rows int[] not null default '{}',
  usefulness  real not null,
  reliability real not null,
  score       real not null,
  verified    boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (workbook_id, key)
);
create index facts_workbook_rank_idx on public.facts (workbook_id, rank);

alter table public.facts enable row level security;
create policy "facts: select own" on public.facts for select to authenticated using (user_id = auth.uid());

-- re-run files already profiled so they get their facts
insert into public.analysis_jobs (workbook_id, user_id)
select id, user_id from public.workbooks where status = 'profiled';
