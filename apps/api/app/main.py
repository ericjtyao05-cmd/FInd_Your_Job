from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import get_supabase
from .security import encrypt_secret
from .schemas import ResumeUploadResponse, RunCreateRequest, RunCreateResponse, RunDetailResponse


def _cors_origins() -> list[str]:
    extras = [value.strip() for value in settings.cors_extra_origins.split(",") if value.strip()]
    return [settings.cors_origin, settings.cors_origin_alt, "http://localhost:3000", "http://127.0.0.1:3000", *extras]

app = FastAPI(title="Find Your Job API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def ensure_storage_bucket(supabase) -> None:
    bucket_name = settings.supabase_storage_bucket
    try:
        supabase.storage.get_bucket(bucket_name)
        return
    except Exception:
        pass

    try:
        supabase.storage.create_bucket(bucket_name, bucket_name, {"public": True})
    except Exception as exc:
        try:
            supabase.storage.get_bucket(bucket_name)
            return
        except Exception:
            raise HTTPException(status_code=500, detail=f"Storage bucket setup failed: {exc}") from exc


@app.post("/api/uploads/resume", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)) -> ResumeUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded file name.")

    allowed_suffixes = {".pdf", ".doc", ".docx", ".txt"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Unsupported resume file type.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    supabase = get_supabase()
    ensure_storage_bucket(supabase)
    object_path = f"resumes/{uuid4().hex}-{Path(file.filename).name}"
    try:
        supabase.storage.from_(settings.supabase_storage_bucket).upload(
            object_path,
            content,
            file_options={
                "content-type": file.content_type or "application/octet-stream",
                "x-upsert": "false",
            },
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Resume upload failed: {exc}") from exc

    public_url = None
    try:
        public_url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(object_path)
    except Exception:
        public_url = None

    return ResumeUploadResponse(
        path=object_path,
        bucket=settings.supabase_storage_bucket,
        public_url=public_url,
    )


@app.post("/api/runs", response_model=RunCreateResponse)
def create_run(request: RunCreateRequest) -> RunCreateResponse:
    supabase = get_supabase()
    encrypted_openai_key = None
    if request.deepseek_api_key:
        if not settings.run_secret_encryption_key:
            raise HTTPException(status_code=500, detail="Run secret encryption key is not configured on the server.")
        encrypted_openai_key = encrypt_secret(request.deepseek_api_key, settings.run_secret_encryption_key)

    candidate_row = supabase.table("candidates").insert(
        {
            "name": request.candidate.name,
            "target_titles": request.candidate.target_titles,
            "preferred_locations": request.candidate.preferred_locations,
            "skills": request.candidate.skills,
            "years_experience": request.candidate.years_experience,
            "resume_text": request.candidate.resume_text,
            "resume_file_path": request.candidate.resume_file_path,
        }
    ).execute()
    candidate = candidate_row.data[0]

    run_row = supabase.table("workflow_runs").insert(
        {
            "candidate_id": candidate["id"],
            "status": "queued",
            "live_research": request.live_research,
            "allow_submit": request.allow_submit,
            "visual_browser": request.visual_browser,
            "top_n": request.top_n,
            "llm_api_key_ciphertext": encrypted_openai_key,
        }
    ).execute()
    run = run_row.data[0]

    supabase.table("workflow_events").insert(
        {
            "run_id": run["id"],
            "event_type": "log",
            "step": None,
            "payload": {"message": "Run created and queued."},
        }
    ).execute()

    return RunCreateResponse(run_id=run["id"], status=run["status"])


@app.get("/api/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str) -> RunDetailResponse:
    supabase = get_supabase()
    run_rows = supabase.table("workflow_runs").select("*").eq("id", run_id).limit(1).execute().data
    if not run_rows:
        raise HTTPException(status_code=404, detail="Run not found.")

    events = supabase.table("workflow_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    jobs = supabase.table("workflow_jobs").select("*").eq("run_id", run_id).order("created_at").execute().data
    applications = supabase.table("application_packages").select("*").eq("run_id", run_id).order("created_at").execute().data
    artifacts = supabase.table("browser_artifacts").select("*").eq("run_id", run_id).order("created_at").execute().data

    return RunDetailResponse(
        run=run_rows[0],
        events=events,
        jobs=jobs,
        applications=applications,
        artifacts=artifacts,
    )
