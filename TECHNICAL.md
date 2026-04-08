# Technical Guide

This file contains the implementation and deployment details for Find Your Job `v1.0`.

Deployment note: use the latest `main` commit for Railway services rather than redeploying an older cached deployment snapshot.

## Architecture

```text
apps/
  api/       FastAPI service for frontend consumption, persisted via Supabase
  web/       Next.js app for Vercel
  worker/    Queue-polling worker that executes the agent workflow
src/find_your_job/
  agents/    Shared research, scoring, writing, browser, and review logic
supabase/
  migrations/ Database schema for candidates, workflow runs, jobs, events, and artifacts
```

## Deployment Split

### Vercel Frontend

The frontend in `apps/web` is a Next.js app that:

- collects candidate inputs
- uploads a resume file reference
- starts workflow runs through the Railway API
- polls run state and renders jobs, progress, and review outcomes

Set:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-railway-api.up.railway.app
```

Deploy on Vercel:

1. Import this repository into Vercel
2. Set the project root to `apps/web`
3. Add the environment variable `NEXT_PUBLIC_API_BASE_URL`
4. Point it to your Railway API URL
5. Deploy

### Railway Backend

The backend in `apps/api` is a FastAPI service that:

- creates candidates and workflow runs
- queues work in Supabase
- returns run state, events, jobs, applications, and artifacts to the frontend

Run locally:

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Deploy on Railway:

1. Create a new Railway service from this repository
2. Preferred: set the service root directory to `apps/api`
3. Set these environment variables in Railway:
   `SUPABASE_URL`
   `SUPABASE_SERVICE_ROLE_KEY`
   `SUPABASE_STORAGE_BUCKET`
   `RUN_SECRET_ENCRYPTION_KEY`
4. Start command:
   `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

If you deploy from the repo root instead of `apps/api`, this repo includes a root-level [nixpacks.toml](/Users/ericyao/agent_projects/Find_Your_Job/nixpacks.toml) fallback that installs `apps/api/requirements.txt` and starts the API from `apps/api`.

### Worker Service

The worker in `apps/worker` polls queued runs from Supabase and executes the shared Python pipeline. It writes:

- workflow events
- discovered jobs
- application packages
- browser artifacts

Run locally:

```bash
cd apps/worker
pip install -r requirements.txt
PYTHONPATH=../../src python main.py
```

Deploy on Railway:

1. Create a new Railway service from this repository
2. Leave the service root directory empty so the full repo is available during build
3. Switch the builder to `Dockerfile`
4. Set the Dockerfile path to:
   `apps/worker/Dockerfile`
5. Set these environment variables in Railway:
   `SUPABASE_URL`
   `SUPABASE_SERVICE_ROLE_KEY`
   `SUPABASE_STORAGE_BUCKET`
   `WORKER_POLL_INTERVAL_SECONDS`
   `PLAYWRIGHT_HEADLESS`
   `RUN_SECRET_ENCRYPTION_KEY`
   `DEEPSEEK_API_KEY`
   `DEEPSEEK_BASE_URL`
   `DEEPSEEK_APPLICATION_WRITER_MODEL`
   `DEEPSEEK_FIT_SCORING_MODEL`
   `DEEPSEEK_REVIEW_GATE_MODEL`
   `DEEPSEEK_TIMEOUT_SECONDS`

This is the recommended worker deployment path. The command-based Railway Python builder can fail to install both the worker dependencies and the shared `src/find_your_job` package into the same runtime environment.

### Supabase

Apply the schema in:

- [001_init.sql](/Users/ericyao/agent_projects/Find_Your_Job/supabase/migrations/001_init.sql)
- [002_add_llm_api_key_to_workflow_runs.sql](/Users/ericyao/agent_projects/Find_Your_Job/supabase/migrations/002_add_llm_api_key_to_workflow_runs.sql)

It creates tables for:

- `candidates`
- `workflow_runs`
- `workflow_events`
- `workflow_jobs`
- `application_packages`
- `browser_artifacts`

## Shared Python Workflow

The shared Python workflow remains under `src/find_your_job/` and can still run standalone:

```bash
PYTHONPATH=src python -m find_your_job.cli
```

Research-only:

```bash
PYTHONPATH=src python -m find_your_job.cli --live-research --research-only
```

## Environment

Copy:

```bash
.env.example
```

and provide:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `RUN_SECRET_ENCRYPTION_KEY` shared by the API and worker for encrypting run-scoped user API keys
- `DEEPSEEK_API_KEY` for hosted LLM-backed agents
- `DEEPSEEK_BASE_URL` if you need to override the default DeepSeek API endpoint
- `DEEPSEEK_MODEL`, `DEEPSEEK_APPLICATION_WRITER_MODEL`, `DEEPSEEK_FIT_SCORING_MODEL`, or `DEEPSEEK_REVIEW_GATE_MODEL` to override agent models
- `DEEPSEEK_TIMEOUT_SECONDS` to limit hosted model-call wait time
- `NEXT_PUBLIC_API_BASE_URL`

## Hosted vs Local Key Model

The current public hosted deployment is intended to use the server-side `DEEPSEEK_API_KEY` configured on the worker.

The encrypted run-scoped user-key path remains in the codebase for a later self-hosted or local edition, where users can run the system in their own environment and provide their own key without routing prompts through the public hosted service.

## Implementation Notes

What is implemented in `v1.0`:

- shared Python agent workflow
- Next.js frontend
- FastAPI backend
- queue-driven worker
- Supabase schema and persistence model
- public Vercel frontend deployment
- public Railway API deployment
- Docker-based Railway worker deployment
