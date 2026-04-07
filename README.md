# Find Your Job

`Find Your Job` is now scaffolded as a deployable multi-service platform:

- Frontend on Vercel: `apps/web`
- Backend API on Railway: `apps/api`
- Agent worker on a worker process: `apps/worker`
- Database on Supabase: `supabase/migrations`
- Shared Python agent logic: `src/find_your_job`

The platform still implements the five agents:

1. `ResearchAgent`
2. `FitScoringAgent`
3. `ApplicationWriterAgent`
4. `BrowserExecutorAgent`
5. `ReviewGateAgent`

## Architecture

```text
apps/
  api/       FastAPI service for Vercel frontend consumption, persisted via Supabase
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
4. Point it to your Railway API URL, for example `https://your-api.up.railway.app`
5. Deploy

If `NEXT_PUBLIC_API_BASE_URL` is missing, the frontend now shows a configuration error instead of trying to call `localhost` in production.

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
4. Start command:
   `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

If you deploy from the repo root instead of `apps/api`, this repo now includes a root-level [nixpacks.toml](/Users/ericyao/agent_projects/Find_Your_Job/nixpacks.toml) fallback that installs `apps/api/requirements.txt` and starts the API from `apps/api`.

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

This is the recommended worker deployment path. The command-based Railway Python builder can fail to install both the worker dependencies and the shared `src/find_your_job` package into the same runtime environment.

### Supabase

Apply the schema in:

- [001_init.sql](/Users/ericyao/agent_projects/Find_Your_Job/supabase/migrations/001_init.sql)

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
- `OPENAI_API_KEY` if you later add LLM-backed prompts
- `NEXT_PUBLIC_API_BASE_URL`

## Current Status

What is implemented now:

- shared Python agent workflow
- Next.js frontend scaffold for Vercel
- FastAPI backend scaffold for Railway
- worker scaffold that consumes queued runs
- Supabase schema and persistence model

What still needs environment-level deployment work:

- install app dependencies in each service
- set platform environment variables
- configure Supabase project credentials
- deploy the three services
- optionally add Supabase Storage-backed resume upload instead of placeholder file references in the Vercel frontend
