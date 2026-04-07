from __future__ import annotations

from find_your_job.models import CandidateProfile, JobPosting, ResearchSource


def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        name="Alex Chen",
        target_titles=["Software Engineer", "Backend Engineer"],
        preferred_locations=["London", "Remote"],
        skills=["Python", "SQL", "AWS", "Docker", "Communication", "APIs"],
        years_experience=5,
        resume_text="Experienced engineer with backend and platform delivery experience.",
        resume_path="/Users/ericyao/Desktop/CV_2026_3_12.pdf",
        achievements=[
            "Reduced API latency by 43% after redesigning service boundaries and caching strategy.",
            "Led a migration to cloud-native deployment workflows across three services.",
        ],
    )


def sample_jobs() -> list[JobPosting]:
    return [
        JobPosting(
            id="job-001",
            title="Backend Software Engineer",
            company="Northstar",
            location="London",
            source="Lever",
            url="https://jobs.lever.co/northstar/backend-software-engineer",
            description="Build Python services, SQL data flows, Docker deployments, and AWS infrastructure.",
        ),
        JobPosting(
            id="job-002",
            title="Backend Software Engineer",
            company="Northstar",
            location="London",
            source="Lever",
            url="https://jobs.lever.co/northstar/backend-software-engineer?duplicate=1",
            description="Build Python services, SQL data flows, Docker deployments, and AWS infrastructure.",
        ),
        JobPosting(
            id="job-003",
            title="Data Analyst",
            company="Maple Insights",
            location="Remote",
            source="Greenhouse",
            url="https://boards.greenhouse.io/mapleinsights/jobs/4001002001",
            description="Own analytics, SQL reporting, stakeholder communication, and experimentation readouts.",
        ),
        JobPosting(
            id="job-004",
            title="Product Manager",
            company="Atlas",
            location="Berlin",
            source="Workday",
            url="https://atlas.wd5.myworkdayjobs.com/en-US/External/job/Berlin/Product-Manager_R-1001",
            description="Drive roadmap, product sense, communication, and analytics across a B2B SaaS product.",
        ),
    ]


def sample_research_sources() -> list[ResearchSource]:
    return [
        ResearchSource(
            kind="linkedin",
            token="",
            company="LinkedIn",
            source_label="LinkedIn",
        ),
        ResearchSource(
            kind="lever",
            token="encord",
            company="Encord",
            source_label="Lever",
            locations=["Remote", "London", "Europe", "Asia", "APAC"],
            title_keywords=["Software Engineer", "Backend Engineer", "Platform Engineer"],
        ),
        ResearchSource(
            kind="lever",
            token="zopa",
            company="Zopa",
            source_label="Lever",
            locations=["London", "Remote", "United Kingdom"],
            title_keywords=["Software Engineer", "Backend Engineer"],
        ),
        ResearchSource(
            kind="greenhouse",
            token="ebury",
            company="Ebury",
            source_label="Greenhouse",
            locations=["London", "Remote", "Europe", "APAC"],
            title_keywords=["Software Engineer", "Backend Engineer", "Staff Engineer"],
        ),
    ]
