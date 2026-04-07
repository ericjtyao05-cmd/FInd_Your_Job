create extension if not exists "pgcrypto";

create table if not exists candidates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  target_titles text[] not null default '{}',
  preferred_locations text[] not null default '{}',
  skills text[] not null default '{}',
  years_experience integer not null default 0,
  resume_text text not null default '',
  resume_file_path text,
  created_at timestamptz not null default now()
);

create table if not exists workflow_runs (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references candidates(id) on delete cascade,
  status text not null default 'queued',
  live_research boolean not null default true,
  allow_submit boolean not null default false,
  visual_browser boolean not null default false,
  top_n integer not null default 3,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists workflow_events (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  event_type text not null,
  step text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists workflow_jobs (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  external_job_id text not null,
  title text not null,
  company text not null,
  location text not null default '',
  source text not null default '',
  url text not null default '',
  description text not null default '',
  category text not null default 'other',
  fit_score integer,
  fit_rationale text,
  strengths jsonb not null default '[]'::jsonb,
  gaps jsonb not null default '[]'::jsonb,
  review_status text,
  review_notes jsonb not null default '[]'::jsonb,
  browser_result jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists workflow_jobs_run_external_job_id_idx
on workflow_jobs(run_id, external_job_id);

create table if not exists application_packages (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  job_external_id text not null,
  resume_summary text not null default '',
  bullet_updates jsonb not null default '[]'::jsonb,
  highlighted_keywords jsonb not null default '[]'::jsonb,
  cover_letter text not null default '',
  qa_script jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists browser_artifacts (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  job_external_id text not null,
  artifact_type text not null,
  path text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
