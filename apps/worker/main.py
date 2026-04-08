from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from supabase import create_client

from config import settings
from find_your_job.agents import ApplicationWriterAgent, BrowserExecutorAgent, FitScoringAgent, ResearchAgent, ReviewGateAgent
from find_your_job.browser_adapters import BrowserTaskBuilder
from find_your_job.models import BrowserExecutionResult, CandidateProfile, ResearchSource
from find_your_job.sample_data import sample_research_sources
from security import decrypt_secret


def main() -> None:
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    browser_builder = BrowserTaskBuilder()
    _stdout("worker booted")

    while True:
        try:
            queued = (
                supabase.table("workflow_runs")
                .select("*, candidates(*)")
                .eq("status", "queued")
                .order("created_at")
                .limit(1)
                .execute()
                .data
            )
        except Exception as exc:  # pragma: no cover
            _stdout(f"queue poll failed: {exc}")
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        if not queued:
            _stdout("no queued runs")
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        run = queued[0]
        run_id = run["id"]
        _stdout(f"picked queued run {run_id}")
        candidate_row = run["candidates"]
        candidate = CandidateProfile(
            name=candidate_row["name"],
            target_titles=candidate_row["target_titles"],
            preferred_locations=candidate_row["preferred_locations"],
            skills=candidate_row["skills"],
            years_experience=candidate_row["years_experience"],
            resume_text=candidate_row["resume_text"],
            resume_path=candidate_row["resume_file_path"],
        )

        supabase.table("workflow_runs").update({"status": "running"}).eq("id", run_id).execute()
        _stdout(f"set run {run_id} to running")

        def log(event_type: str, step: str | None, payload: dict) -> None:
            supabase.table("workflow_events").insert(
                {"run_id": run_id, "event_type": event_type, "step": step, "payload": payload}
            ).execute()

        try:
            with tempfile.TemporaryDirectory(prefix="find-your-job-worker-") as temp_dir:
                local_resume_path = _materialize_resume_file(
                    supabase=supabase,
                    resume_path=candidate.resume_path,
                    temp_dir=temp_dir,
                )
                if local_resume_path:
                    candidate.resume_path = local_resume_path
                    log("log", None, {"message": f"Resume materialized for browser upload: {Path(local_resume_path).name}"})

                research_sources = sample_research_sources()
                research = ResearchAgent().run(jobs=[], candidate=candidate, sources=research_sources if run["live_research"] else None).payload
                log("step", "research", {"message": f"Research found {len(research.deduplicated_jobs)} jobs."})
                if research.source_errors:
                    log("log", "research", {"message": "Research source errors detected.", "source_errors": research.source_errors})
                _stdout(f"run {run_id}: research found {len(research.deduplicated_jobs)} jobs")

                run_openai_key = _resolve_run_openai_key(run, log)

                fit_scores = FitScoringAgent(api_key=run_openai_key).run(candidate, research.deduplicated_jobs).payload
                log("step", "fit_scoring", {"message": f"Scored {len(fit_scores)} jobs."})
                _stdout(f"run {run_id}: scored {len(fit_scores)} jobs")

                applications = ApplicationWriterAgent(api_key=run_openai_key).run(candidate, research.deduplicated_jobs, fit_scores, top_n=run["top_n"]).payload
                log("step", "application_writer", {"message": f"Generated {len(applications)} application packages."})
                _stdout(f"run {run_id}: generated {len(applications)} application packages")

                for job in research.deduplicated_jobs:
                    fit = next((item for item in fit_scores if item.job_id == job.id), None)
                    supabase.table("workflow_jobs").upsert(
                        {
                            "run_id": run_id,
                            "external_job_id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "source": job.source,
                            "url": job.url,
                            "description": job.description,
                            "category": job.category.value,
                            "fit_score": fit.score if fit else None,
                            "fit_rationale": fit.rationale if fit else None,
                            "strengths": fit.strengths if fit else [],
                            "gaps": fit.gaps if fit else [],
                            "review_status": None,
                            "review_notes": [],
                            "browser_result": None,
                        },
                        on_conflict="run_id,external_job_id",
                    ).execute()

                for package in applications:
                    supabase.table("application_packages").insert(
                        {
                            "run_id": run_id,
                            "job_external_id": package.job_id,
                            "resume_summary": package.tailored_resume.summary,
                            "bullet_updates": package.tailored_resume.bullet_updates,
                            "highlighted_keywords": package.tailored_resume.highlighted_keywords,
                            "cover_letter": package.cover_letter,
                            "qa_script": package.qa_script,
                        }
                    ).execute()

                log("step", "application_writer", {"message": "Persisted jobs and draft application packages."})

                job_lookup = {job.id: job for job in research.deduplicated_jobs}
                browser_tasks = []
                browser_results: list[BrowserExecutionResult] = []
                for package in applications:
                    job = job_lookup[package.job_id]
                    if _should_skip_browser(job):
                        message = f"Skipped browser automation for {job.source} job; page is not a supported direct application form."
                        log("browser", "browser_executor", {"kind": "task", "job_id": job.id, "code": "task_skipped", "data": {"source": job.source, "url": job.url}, "message": message})
                        browser_results.append(
                            BrowserExecutionResult(
                                job_id=job.id,
                                success=True,
                                screenshots=[],
                                mistakes=[],
                                submitted=False,
                            )
                        )
                        continue
                    browser_tasks.append(browser_builder.build(candidate, job, package))

                browser_agent = BrowserExecutorAgent(
                    headless=settings.playwright_headless and not run["visual_browser"],
                    event_sink=lambda event: log("browser", "browser_executor", event),
                )
                if browser_tasks:
                    browser_results.extend(browser_agent.run(browser_tasks, submit=run["allow_submit"]).payload)
                log("step", "browser_executor", {"message": f"Executed {len(browser_tasks)} browser tasks and skipped {len(applications) - len(browser_tasks)} unsupported jobs."})
                _stdout(f"run {run_id}: executed {len(browser_tasks)} browser tasks, skipped {len(applications) - len(browser_tasks)}")

                reviews = ReviewGateAgent(api_key=run_openai_key).run(applications, fit_scores, browser_results).payload
                log("step", "review_gate", {"message": "Review gate complete."})
                _stdout(f"run {run_id}: review gate complete")

                for job in research.deduplicated_jobs:
                    fit = next((item for item in fit_scores if item.job_id == job.id), None)
                    review = next((item for item in reviews if item.job_id == job.id), None)
                    browser = next((item for item in browser_results if item.job_id == job.id), None)
                    supabase.table("workflow_jobs").upsert(
                        {
                            "run_id": run_id,
                            "external_job_id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "source": job.source,
                            "url": job.url,
                            "description": job.description,
                            "category": job.category.value,
                            "fit_score": fit.score if fit else None,
                            "fit_rationale": fit.rationale if fit else None,
                            "strengths": fit.strengths if fit else [],
                            "gaps": fit.gaps if fit else [],
                            "review_status": review.status.value if review else None,
                            "review_notes": review.notes if review else [],
                            "browser_result": asdict(browser) if browser else None,
                        },
                        on_conflict="run_id,external_job_id",
                    ).execute()

                for result in browser_results:
                    for path in result.screenshots:
                        artifact_metadata = _upload_browser_artifact(
                            supabase=supabase,
                            run_id=run_id,
                            job_id=result.job_id,
                            local_path=path,
                        )
                        supabase.table("browser_artifacts").insert(
                            {
                                "run_id": run_id,
                                "job_external_id": result.job_id,
                                "artifact_type": "screenshot",
                                "path": artifact_metadata["object_path"],
                                "metadata": {
                                    **json.loads(json.dumps(asdict(result))),
                                    **artifact_metadata,
                                },
                            }
                        ).execute()

                supabase.table("workflow_runs").update({"status": "completed"}).eq("id", run_id).execute()
                _stdout(f"run {run_id}: completed")
        except Exception as exc:  # pragma: no cover
            supabase.table("workflow_runs").update({"status": "failed", "error_message": str(exc)}).eq("id", run_id).execute()
            log("error", None, {"message": str(exc)})
            _stdout(f"run {run_id}: failed with {exc}")


def _materialize_resume_file(supabase, resume_path: str | None, temp_dir: str) -> str | None:
    if not resume_path:
        return None

    candidate_path = Path(resume_path)
    if candidate_path.exists():
        return str(candidate_path.resolve())

    object_path = resume_path.lstrip("/")
    binary = supabase.storage.from_(settings.supabase_storage_bucket).download(object_path)
    target_name = Path(object_path).name or "resume"
    target_path = Path(temp_dir) / target_name

    if isinstance(binary, bytes):
        payload = binary
    elif hasattr(binary, "read"):
        payload = binary.read()
    else:
        raise ValueError("Unexpected Supabase Storage download response type.")

    target_path.write_bytes(payload)
    return str(target_path.resolve())


def _resolve_run_openai_key(run: dict, log) -> str | None:
    ciphertext = run.get("llm_api_key_ciphertext")
    if not ciphertext:
        return None
    if not settings.run_secret_encryption_key:
        log("log", None, {"message": "Encrypted run-scoped OpenAI key was present but worker decryption key is not configured."})
        return None
    try:
        return decrypt_secret(ciphertext, settings.run_secret_encryption_key)
    except Exception as exc:  # pragma: no cover
        log("log", None, {"message": f"Failed to decrypt run-scoped OpenAI key: {exc}"})
        return None


def _upload_browser_artifact(supabase, run_id: str, job_id: str, local_path: str) -> dict[str, str]:
    artifact_path = Path(local_path)
    object_path = f"artifacts/{run_id}/{job_id}/{artifact_path.name}"
    payload = artifact_path.read_bytes()
    supabase.storage.from_(settings.supabase_storage_bucket).upload(
        object_path,
        payload,
        file_options={
            "content-type": "image/png",
            "x-upsert": "true",
        },
    )
    public_url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(object_path)
    return {
        "object_path": object_path,
        "public_url": public_url,
        "local_path": str(artifact_path.resolve()),
    }


def _should_skip_browser(job) -> bool:
    source = job.source.lower()
    url = job.url.lower()
    return "linkedin" in source or "linkedin.com" in url


def _stdout(message: str) -> None:
    print(f"[worker] {message}", flush=True)


if __name__ == "__main__":
    main()
