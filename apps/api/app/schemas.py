from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    name: str
    target_titles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    years_experience: int = 0
    resume_text: str = ""
    resume_file_path: str | None = None


class RunCreateRequest(BaseModel):
    candidate: CandidateIn
    live_research: bool = True
    allow_submit: bool = False
    visual_browser: bool = False
    top_n: int = 3
    deepseek_api_key: str | None = None


class RunCreateResponse(BaseModel):
    run_id: str
    status: str


class ResumeUploadResponse(BaseModel):
    path: str
    bucket: str
    public_url: str | None = None


class RunDetailResponse(BaseModel):
    run: dict[str, Any]
    events: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    applications: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
