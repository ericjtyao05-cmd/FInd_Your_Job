from __future__ import annotations

import json
from html import unescape
import re
from collections import defaultdict
from urllib.parse import quote_plus
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .base import Agent, AgentResult
from find_your_job.models import CandidateProfile, JobCategory, JobPosting, ResearchResult, ResearchSource


class ResearchAgent(Agent):
    def __init__(self) -> None:
        super().__init__("research_agent")

    def run(
        self,
        jobs: list[JobPosting] | None = None,
        candidate: CandidateProfile | None = None,
        sources: list[ResearchSource] | None = None,
    ) -> AgentResult[ResearchResult]:
        normalized: dict[tuple[str, str, str], JobPosting] = {}
        discovered = list(jobs or [])
        source_errors: list[str] = []

        if sources:
            fetched_jobs, fetch_errors = self._fetch_live_jobs(candidate, sources)
            discovered.extend(fetched_jobs)
            source_errors.extend(fetch_errors)

        for job in discovered:
            job.category = self._categorize(job)
            key = self._dedupe_key(job)
            if key in normalized:
                job.duplicate_of = normalized[key].id
            else:
                normalized[key] = job

        deduplicated = list(normalized.values())
        categories: dict[JobCategory, list[JobPosting]] = defaultdict(list)
        for job in deduplicated:
            categories[job.category].append(job)

        return AgentResult(
            agent_name=self.name,
            payload=ResearchResult(
                discovered_jobs=discovered,
                deduplicated_jobs=deduplicated,
                categories=dict(categories),
                source_errors=source_errors,
            ),
        )

    def _fetch_live_jobs(
        self,
        candidate: CandidateProfile | None,
        sources: list[ResearchSource],
    ) -> tuple[list[JobPosting], list[str]]:
        jobs: list[JobPosting] = []
        errors: list[str] = []

        for source in sources:
            try:
                if source.kind == "lever":
                    jobs.extend(self._fetch_lever_jobs(source, candidate))
                elif source.kind == "greenhouse":
                    jobs.extend(self._fetch_greenhouse_jobs(source, candidate))
                elif source.kind == "linkedin":
                    jobs.extend(self._fetch_linkedin_jobs(source, candidate))
                else:
                    errors.append(f"Unsupported research source kind: {source.kind}")
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                errors.append(f"{source.company} ({source.kind}) fetch failed: {exc}")

        return jobs, errors

    def _fetch_lever_jobs(
        self,
        source: ResearchSource,
        candidate: CandidateProfile | None,
    ) -> list[JobPosting]:
        url = f"https://api.lever.co/v0/postings/{source.token}?mode=json"
        payload = self._load_json(url)
        jobs: list[JobPosting] = []

        for item in payload:
            description = self._strip_html(item.get("descriptionPlain") or item.get("description") or "")
            posting = JobPosting(
                id=f"lever-{source.token}-{item['id']}",
                title=item.get("text", "").strip(),
                company=source.company,
                location=(item.get("categories") or {}).get("location", "").strip(),
                source=source.source_label,
                url=item.get("hostedUrl", "").strip(),
                description=description,
            )
            if self._matches_candidate(posting, candidate, source):
                jobs.append(posting)

        return jobs

    def _fetch_linkedin_jobs(
        self,
        source: ResearchSource,
        candidate: CandidateProfile | None,
    ) -> list[JobPosting]:
        if not candidate or not candidate.target_titles:
            return []

        locations = candidate.preferred_locations or [""]
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()
        max_results = 12

        for title in candidate.target_titles[:4]:
            for location in locations[:4]:
                search_url = (
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={quote_plus(title)}&location={quote_plus(location)}&start=0"
                )
                html = self._load_text(search_url)
                for match in self._parse_linkedin_cards(html):
                    if len(jobs) >= max_results:
                        return jobs
                    job_id = f"linkedin-{match['job_id']}"
                    if job_id in seen_ids:
                        continue
                    posting = JobPosting(
                        id=job_id,
                        title=match["title"],
                        company=match["company"],
                        location=match["location"],
                        source=source.source_label,
                        url=match["url"],
                        description="",
                    )
                    if self._matches_candidate(posting, candidate, source):
                        jobs.append(posting)
                        seen_ids.add(job_id)

        return jobs

    def _fetch_greenhouse_jobs(
        self,
        source: ResearchSource,
        candidate: CandidateProfile | None,
    ) -> list[JobPosting]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{source.token}/jobs?content=true"
        payload = self._load_json(url)
        jobs: list[JobPosting] = []

        for item in payload.get("jobs", []):
            description = self._strip_html(item.get("content") or "")
            posting = JobPosting(
                id=f"greenhouse-{source.token}-{item['id']}",
                title=item.get("title", "").strip(),
                company=source.company,
                location=((item.get("location") or {}).get("name") or "").strip(),
                source=source.source_label,
                url=item.get("absolute_url", "").strip(),
                description=description,
            )
            if self._matches_candidate(posting, candidate, source):
                jobs.append(posting)

        return jobs

    def _matches_candidate(
        self,
        job: JobPosting,
        candidate: CandidateProfile | None,
        source: ResearchSource,
    ) -> bool:
        title_text = job.title.lower()
        location_text = job.location.lower()
        title_keywords = [item.lower() for item in source.title_keywords]
        source_location_keywords = [item.lower() for item in source.locations]

        if candidate:
            title_keywords.extend(title.lower() for title in candidate.target_titles)
            candidate_location_keywords = [
                location.lower() for location in candidate.preferred_locations if location.strip()
            ]
        else:
            candidate_location_keywords = []

        title_keywords = [keyword for keyword in title_keywords if keyword]
        location_keywords = candidate_location_keywords or [keyword for keyword in source_location_keywords if keyword]

        title_ok = True if not title_keywords else any(keyword in title_text for keyword in title_keywords)
        location_ok = True if not location_keywords else any(keyword in location_text for keyword in location_keywords)
        return title_ok and location_ok

    def _load_json(self, url: str) -> object:
        with urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_text(self, url: str) -> str:
        with urlopen(url, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")

    def _dedupe_key(self, job: JobPosting) -> tuple[str, str, str]:
        return (
            self._normalize(job.company),
            self._normalize(job.title),
            self._normalize(job.location),
        )

    def _categorize(self, job: JobPosting) -> JobCategory:
        title = job.title.lower()
        text = f"{job.title} {job.description}".lower()
        if any(token in title for token in ("software", "backend", "frontend", "full stack", "engineer", "developer")):
            return JobCategory.SOFTWARE
        if any(token in title for token in ("data", "analytics", "machine learning", "scientist")):
            return JobCategory.DATA
        if any(token in title for token in ("product manager", "product owner")):
            return JobCategory.PRODUCT
        if any(token in text for token in ("software", "backend", "frontend", "full stack", "engineer", "developer")):
            return JobCategory.SOFTWARE
        if any(token in text for token in ("data", "analytics", "machine learning", "scientist")):
            return JobCategory.DATA
        if any(token in text for token in ("product manager", "product owner", "roadmap", "product sense")):
            return JobCategory.PRODUCT
        if any(token in text for token in ("designer", "ux", "ui", "figma")):
            return JobCategory.DESIGN
        if any(token in text for token in ("operations", "ops", "support", "process")):
            return JobCategory.OPERATIONS
        return JobCategory.OTHER

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    def _strip_html(self, value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", unescape(value))
        return re.sub(r"\s+", " ", cleaned).strip()[:2500]

    def _parse_linkedin_cards(self, html: str) -> list[dict[str, str]]:
        cards = re.findall(r"<li>(.*?)</li>", html, flags=re.DOTALL)
        results: list[dict[str, str]] = []
        for card in cards:
            href_match = re.search(r'href="([^"]+/jobs/view/[^"]*?-(\d+)(?:\?[^"]*)?)"', card)
            title_match = re.search(r'base-search-card__title[^>]*>\s*(.*?)\s*</', card, flags=re.DOTALL)
            company_match = re.search(r'base-search-card__subtitle[^>]*>.*?<a[^>]*>\s*(.*?)\s*</a>', card, flags=re.DOTALL)
            location_match = re.search(r'job-search-card__location[^>]*>\s*(.*?)\s*</', card, flags=re.DOTALL)

            if not href_match or not title_match or not company_match or not location_match:
                continue

            results.append(
                {
                    "url": unescape(href_match.group(1).split("?")[0]),
                    "job_id": href_match.group(2),
                    "title": self._clean_text(title_match.group(1)),
                    "company": self._clean_text(company_match.group(1)),
                    "location": self._clean_text(location_match.group(1)),
                }
            )
        return results

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()
