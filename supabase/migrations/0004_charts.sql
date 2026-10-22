-- AI Excel Copilot — Phase 4: visualization specs (report §13 'Visualization', §14 phases F-G, I)
-- Run after 0003_facts.sql.

alter table public.analysis_jobs alter column pipeline_version set default 'phase4';

create table public.charts (
  id          uuid primary key default gen_random_uuid(),
  workbook_id uuid not null references public.workbooks(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  table_id    uuid references public.data_tables(id) on delete cascade,
  key         text not null,
  kind        text not null,                       -- kpi line multi_line hbar stacked_bar target scatter histogram
  role        text not null,                       -- kpi trend comparison breakdown target relationship distribution
  placement   text not null check (placement in ('kpi','primary','secondary','explore')),
  position    int  not null default 0,
  title       text not null,                       -- the analytical question
  why         text not null,                       -- why this visualization exists
  fact_keys   jsonb not null default '[]',         -- the verified facts it comes from
  encoding    jsonb not null default '{}',
  data        jsonb not null,                      -- numbers to draw it, no query needed
  query       jsonb,                               -- re-runnable in the browser when filters change (null = not filterable)
  options     jsonb not null default '{}',
  usefulness  real not null,
  reliability real not null,
  readability real not null,
  score       real not null,
  caveats     jsonb not null default '[]',
  created_at  timestamptz not null default now(),
  unique (workbook_id, key)
);
create index charts_workbook_placement_idx on public.charts (workbook_id, placement, position);

alter table public.charts enable row level security;
create policy "charts: select own" on public.charts for select to authenticated using (user_id = auth.uid());

-- re-run profiled files so they get charts, and cleaned tables are rewritten in the browser-readable format
insert into public.analysis_jobs (workbook_id, user_id)
select id, user_id from public.workbooks where status = 'profiled';
