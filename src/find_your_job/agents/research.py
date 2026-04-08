from __future__ import annotations

import json
from html import unescape
import re
import time
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .base import Agent, AgentResult
from find_your_job.models import CandidateProfile, JobCategory, JobPosting, ResearchResult, ResearchSource


TITLE_SYNONYMS: dict[str, list[str]] = {
    "software engineer": [
        "software developer",
        "application engineer",
        "software engineer",
        "software developer",
        "软件工程师",
    ],
    "backend engineer": [
        "backend developer",
        "backend software engineer",
        "platform engineer",
        "server-side engineer",
        "后端工程师",
        "后端开发",
    ],
    "frontend engineer": [
        "frontend developer",
        "ui engineer",
        "web engineer",
        "前端工程师",
    ],
    "data engineer": [
        "analytics engineer",
        "etl engineer",
        "big data engineer",
        "数据工程师",
    ],
    "product manager": [
        "product owner",
        "product lead",
        "产品经理",
    ],
}

LOCATION_ALIASES: dict[str, list[str]] = {
    "london": ["london", "greater london", "united kingdom", "uk", "england", "remote uk", "emea"],
    "berlin": ["berlin", "germany", "deutschland", "remote germany", "emea"],
    "new york": ["new york", "nyc", "new york city", "united states", "usa", "us", "remote us", "north america"],
    "san francisco": ["san francisco", "bay area", "sf", "california", "united states", "usa", "us", "remote us", "north america"],
    "shanghai": ["shanghai", "上海", "pudong", "china", "中国", "apac", "asia", "remote china"],
    "beijing": ["beijing", "北京", "china", "中国", "apac", "asia", "remote china"],
    "singapore": ["singapore", "sg", "apac", "asia", "remote singapore"],
    "tokyo": ["tokyo", "東京", "japan", "日本", "apac", "asia"],
    "hong kong": ["hong kong", "香港", "apac", "asia"],
    "remote": ["remote", "worldwide", "global", "distributed", "hybrid"],
}

LINKEDIN_MAX_RESULTS = 12
LINKEDIN_MAX_QUERY_PAIRS = 4
LINKEDIN_MAX_SEARCH_TITLES = 3
LINKEDIN_MAX_SEARCH_LOCATIONS = 3


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

        ordered_sources = sorted(sources, key=lambda source: 1 if source.kind == "linkedin" else 0)

        for source in ordered_sources:
            try:
                if source.kind == "lever":
                    jobs.extend(self._fetch_lever_jobs(source, candidate))
                elif source.kind == "greenhouse":
                    jobs.extend(self._fetch_greenhouse_jobs(source, candidate))
                elif source.kind == "linkedin":
                    jobs.extend(self._fetch_linkedin_jobs(source, candidate))
                else:
                    errors.append(f"Unsupported research source kind: {source.kind}")
            except HTTPError as exc:
                if source.kind == "linkedin" and exc.code in {403, 429}:
                    errors.append(f"{source.company} ({source.kind}) guest search was rate limited; continuing with official sources.")
                else:
                    errors.append(f"{source.company} ({source.kind}) fetch failed: {exc}")
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
        search_titles = self._linkedin_search_titles(candidate, source)
        search_locations = self._linkedin_search_locations(candidate, source)
        if not search_titles:
            return []

        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()
        query_pairs = 0

        for title in search_titles:
            for location in search_locations:
                query_pairs += 1
                if query_pairs > LINKEDIN_MAX_QUERY_PAIRS:
                    return jobs
                if query_pairs > 1:
                    time.sleep(0.4)
                search_url = (
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={quote_plus(title)}&location={quote_plus(location)}&start=0"
                )
                html = self._load_text(search_url)
                for match in self._parse_linkedin_cards(html):
                    if len(jobs) >= LINKEDIN_MAX_RESULTS:
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

    def _linkedin_search_titles(
        self,
        candidate: CandidateProfile | None,
        source: ResearchSource,
    ) -> list[str]:
        prioritized = self._unique_preserve(list(candidate.target_titles) if candidate else [])
        if not prioritized:
            prioritized = self._expanded_titles(candidate, source)
        return prioritized[:LINKEDIN_MAX_SEARCH_TITLES]

    def _linkedin_search_locations(
        self,
        candidate: CandidateProfile | None,
        source: ResearchSource,
    ) -> list[str]:
        prioritized = self._unique_preserve(list(candidate.preferred_locations) if candidate and candidate.preferred_locations else [])
        if not prioritized:
            prioritized = self._expanded_locations(candidate, source)
        return (prioritized[:LINKEDIN_MAX_SEARCH_LOCATIONS] or [""])

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
        title_text = self._normalize(job.title)
        location_text = self._normalize(job.location)
        title_keywords = self._expanded_titles(candidate, source)
        location_keywords = self._expanded_locations(candidate, source)

        title_ok = True if not title_keywords else any(self._normalize(keyword) in title_text for keyword in title_keywords)
        location_ok = True if not location_keywords else any(self._normalize(keyword) in location_text for keyword in location_keywords)
        return title_ok and location_ok

    def _expanded_titles(
        self,
        candidate: CandidateProfile | None,
        source: ResearchSource,
    ) -> list[str]:
        raw_titles: list[str] = []
        raw_titles.extend(source.title_keywords)
        if candidate:
            raw_titles.extend(candidate.target_titles)

        expanded: list[str] = []
        for title in raw_titles:
            normalized = self._normalize(title)
            if not normalized:
                continue
            expanded.append(title.strip())
            for root, variants in TITLE_SYNONYMS.items():
                if root in normalized:
                    expanded.extend(variants)
                elif any(variant in normalized for variant in variants):
                    expanded.append(root)
                    expanded.extend(variants)

        return self._unique_preserve(expanded)

    def _expanded_locations(
        self,
        candidate: CandidateProfile | None,
        source: ResearchSource,
    ) -> list[str]:
        raw_locations: list[str] = []
        if candidate and candidate.preferred_locations:
            raw_locations.extend(candidate.preferred_locations)
        else:
            raw_locations.extend(source.locations)

        expanded: list[str] = []
        for location in raw_locations:
            normalized = self._normalize(location)
            if not normalized:
                continue
            expanded.append(location.strip())
            for root, variants in LOCATION_ALIASES.items():
                if root in normalized or any(variant in normalized for variant in variants):
                    expanded.append(root)
                    expanded.extend(variants)

        return self._unique_preserve(expanded)

    def _unique_preserve(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            key = self._normalize(value)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(value)
        return ordered

    def _load_json(self, url: str) -> object:
        request = Request(url, headers=self._request_headers())
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_text(self, url: str) -> str:
        request = Request(url, headers=self._request_headers())
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")

    def _request_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

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
