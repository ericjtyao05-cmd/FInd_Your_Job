from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class JobCategory(StrEnum):
    SOFTWARE = "software"
    DATA = "data"
    PRODUCT = "product"
    DESIGN = "design"
    OPERATIONS = "operations"
    OTHER = "other"


class ApplicationStatus(StrEnum):
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


@dataclass(slots=True)
class CandidateProfile:
    name: str
    target_titles: list[str]
    preferred_locations: list[str]
    skills: list[str]
    years_experience: int
    resume_text: str
    resume_path: str | None = None
    achievements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResearchSource:
    kind: str
    token: str
    company: str
    source_label: str
    locations: list[str] = field(default_factory=list)
    title_keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class JobPosting:
    id: str
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    category: JobCategory = JobCategory.OTHER
    duplicate_of: str | None = None


@dataclass(slots=True)
class ResearchResult:
    discovered_jobs: list[JobPosting]
    deduplicated_jobs: list[JobPosting]
    categories: dict[JobCategory, list[JobPosting]]
    source_errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FitScore:
    job_id: str
    score: int
    matched_skills: list[str]
    strengths: list[str]
    gaps: list[str]
    rationale: str


@dataclass(slots=True)
class ResumeEdit:
    summary: str
    bullet_updates: list[str]
    highlighted_keywords: list[str]


@dataclass(slots=True)
class ApplicationPackage:
    job_id: str
    tailored_resume: ResumeEdit
    cover_letter: str
    qa_script: list[str]


@dataclass(slots=True)
class BrowserTask:
    job_id: str
    application_url: str
    form_fields: dict[str, str]
    files_to_upload: dict[str, str]
    field_selectors: dict[str, str] = field(default_factory=dict)
    upload_selectors: dict[str, str] = field(default_factory=dict)
    submit_selector: str | None = None
    wait_for_selector: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BrowserExecutionResult:
    job_id: str
    success: bool
    screenshots: list[str]
    mistakes: list[str]
    submitted: bool


@dataclass(slots=True)
class ReviewDecision:
    job_id: str
    status: ApplicationStatus
    risky_paragraphs: list[str]
    confirmation_required: bool
    notes: list[str]


@dataclass(slots=True)
class WorkflowResult:
    research: ResearchResult
    fit_scores: list[FitScore]
    application_packages: list[ApplicationPackage]
    browser_results: list[BrowserExecutionResult]
    reviews: list[ReviewDecision]
