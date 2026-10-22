-- AI Excel Copilot — Phase 2: Excel engine output (report §13: Sheet, ColumnProfile, Finding)
-- Run after 0001_init.sql.

-- ---------------------------------------------------------------- statuses
alter table public.workbooks drop constraint if exists workbooks_status_check;
alter table public.workbooks add constraint workbooks_status_check
  check (status in ('uploaded','validating','validated','analyzing','profiled','rejected','failed'));
alter table public.analysis_jobs alter column pipeline_version set default 'phase2';

-- ---------------------------------------------------------------- sheets
create table public.sheets (
  id              uuid primary key default gen_random_uuid(),
  workbook_id     uuid not null references public.workbooks(id) on delete cascade,
  user_id         uuid not null references auth.users(id) on delete cascade,
  position        int  not null,
  name            text not null,
  hidden          boolean not null default false,
  row_count       int  not null default 0,
  column_count    int  not null default 0,
  cell_count      int  not null default 0,
  formula_count   int  not null default 0,
  error_count     int  not null default 0,
  merged_count    int  not null default 0,
  hyperlink_count int  not null default 0,
  is_empty        boolean not null default false,
  notes           jsonb not null default '[]'
);
create index sheets_workbook_idx on public.sheets (workbook_id, position);

-- ---------------------------------------------------------------- tables found inside sheets
create table public.data_tables (
  id               uuid primary key default gen_random_uuid(),
  workbook_id      uuid not null references public.workbooks(id) on delete cascade,
  user_id          uuid not null references auth.users(id) on delete cascade,
  sheet_id         uuid not null references public.sheets(id) on delete cascade,
  position         int  not null,
  name             text not null,
  source           text not null check (source in ('detected','excel_table')),
  cell_range       text not null,
  header_row       int,
  first_data_row   int  not null,
  last_data_row    int  not null,
  row_count        int  not null,
  column_count     int  not null,
  confidence       real not null,
  header_confidence real,
  total_rows       int[] not null default '{}',
  blank_rows       int  not null default 0,
  truncated        boolean not null default false,
  artifact_path    text,                       -- cleaned table (Parquet) in the 'artifacts' bucket
  created_at       timestamptz not null default now()
);
create index data_tables_workbook_idx on public.data_tables (workbook_id, position);

-- ---------------------------------------------------------------- ColumnProfile
create table public.column_profiles (
  id               uuid primary key default gen_random_uuid(),
  workbook_id      uuid not null references public.workbooks(id) on delete cascade,
  user_id          uuid not null references auth.users(id) on delete cascade,
  table_id         uuid not null references public.data_tables(id) on delete cascade,
  position         int  not null,
  col_letter       text,
  name             text not null,
  original_label   text,
  data_type        text not null,
  base_type        text,
  type_confidence  real,
  role             text not null,
  role_subtype     text,
  role_confidence  real,
  currency         text,
  unit             text,
  number_format    text,
  formula_share    real,
  missing_count    int,
  missing_rate     real,
  distinct_count   int,
  uniqueness       real,
  stats            jsonb not null default '{}'
);
create index column_profiles_table_idx on public.column_profiles (table_id, position);

-- ---------------------------------------------------------------- Finding
create table public.findings (
  id            uuid primary key default gen_random_uuid(),
  workbook_id   uuid not null references public.workbooks(id) on delete cascade,
  user_id       uuid not null references auth.users(id) on delete cascade,
  sheet_id      uuid references public.sheets(id) on delete cascade,
  table_id      uuid references public.data_tables(id) on delete cascade,
  column_id     uuid references public.column_profiles(id) on delete cascade,
  code          text not null,
  severity      text not null check (severity in ('info','low','medium','high')),
  title         text not null,
  detail        text,
  affected_count int,
  total_count   int,
  sample_rows   int[] not null default '{}',
  evidence      jsonb not null default '{}',
  created_at    timestamptz not null default now()
);
create index findings_workbook_idx on public.findings (workbook_id, severity);

-- ---------------------------------------------------------------- workbook-level profile
create table public.workbook_profiles (
  workbook_id     uuid primary key references public.workbooks(id) on delete cascade,
  user_id         uuid not null references auth.users(id) on delete cascade,
  profile_version int  not null,
  summary         jsonb not null default '{}',
  relationships   jsonb not null default '[]',
  engine_ms       int,
  created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------- RLS: read own, write via worker only
alter table public.sheets            enable row level security;
alter table public.data_tables       enable row level security;
alter table public.column_profiles   enable row level security;
alter table public.findings          enable row level security;
alter table public.workbook_profiles enable row level security;

create policy "sheets: select own"            on public.sheets            for select to authenticated using (user_id = auth.uid());
create policy "data_tables: select own"       on public.data_tables       for select to authenticated using (user_id = auth.uid());
create policy "column_profiles: select own"   on public.column_profiles   for select to authenticated using (user_id = auth.uid());
create policy "findings: select own"          on public.findings          for select to authenticated using (user_id = auth.uid());
create policy "workbook_profiles: select own" on public.workbook_profiles for select to authenticated using (user_id = auth.uid());

-- ---------------------------------------------------------------- derived artifacts bucket
-- Cleaned tables (Parquet). Only the worker can write; users can read and delete their own folder.
insert into storage.buckets (id, name, public, file_size_limit)
values ('artifacts', 'artifacts', false, 52428800)
on conflict (id) do nothing;

create policy "artifacts bucket: read own folder" on storage.objects
  for select to authenticated
  using (bucket_id = 'artifacts' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "artifacts bucket: delete own folder" on storage.objects
  for delete to authenticated
  using (bucket_id = 'artifacts' and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------- re-profile files uploaded during Phase 1
insert into public.analysis_jobs (workbook_id, user_id)
select id, user_id from public.workbooks where status = 'validated';
