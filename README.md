# Find Your Job

`Find Your Job` is a Python MVP for a multi-agent job matching workflow. It implements the five agents you asked for:

1. `ResearchAgent`
2. `FitScoringAgent`
3. `ApplicationWriterAgent`
4. `BrowserExecutorAgent`
5. `ReviewGateAgent`

## What It Does

- Searches from a provided job list, deduplicates repeated postings, and categorizes them.
- Scores each role against a candidate profile, explains the reasoning, and highlights skill gaps.
- Drafts resume edits, a cover letter, and interview/application Q&A prompts for top matches.
- Prepares browser application runs and records screenshots plus mistakes.
- Blocks or flags risky applications and requires explicit user confirmation before final submission.

## Project Structure

```text
src/find_your_job/
  agents/
  browser_adapters.py
  cli.py
  models.py
  orchestrator.py
  sample_data.py
examples/
  resume.txt
```

## Run

Use the built-in demo data:

```bash
PYTHONPATH=src python -m find_your_job.cli
```

If you want the browser executor to mark valid applications as submitted:

```bash
PYTHONPATH=src python -m find_your_job.cli --allow-submit
```

## Web UI

Run the built-in web interface:

```bash
PYTHONPATH=src python -m find_your_job.web --port 8000
```

Or, after installing the package:

```bash
find-your-job-web --port 8000
```

Open `http://127.0.0.1:8000`.

The UI shows:

- live agent step status
- a feed of progress messages
- discovered jobs and fit scores
- review blockers and browser execution outcomes

## Notes On The Browser Agent

The browser executor now uses Playwright when the optional dependency is installed. It can:

- Open the target application page
- Wait for a page marker
- Fill configured form fields
- Upload configured files
- Save screenshots before and after the submit step
- Return mistakes when selectors or files are missing

Install the browser dependency and browser binaries:

```bash
pip install -e ".[browser]"
playwright install
```

The default sample data still points to placeholder URLs and selectors. For real automation, provide valid `application_url`, `field_selectors`, `upload_selectors`, and `submit_selector` values for each `BrowserTask`.

The project now includes a simple adapter layer in [browser_adapters.py](/Users/ericyao/agent_projects/Find_Your_Job/src/find_your_job/browser_adapters.py) that emits selectors for:

- Greenhouse
- Lever
- Workday
- Generic fallback forms

These adapters are intentionally conservative. They give the browser agent a real starting point, but Workday in particular usually needs company-specific overrides.

## Extension Points

- Replace `sample_data.py` with inputs from a database, job board scraper, or API.
- Replace deterministic heuristics inside the agents with LLM-backed prompts.
- Expand `ReviewGateAgent` with policy rules for risky claims, visa status, salary expectations, or compliance checks.
- Upgrade `BrowserExecutorAgent` to fill real application forms and upload real files with Playwright.
