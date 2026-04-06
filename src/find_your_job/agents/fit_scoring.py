from __future__ import annotations

import re

from .base import Agent, AgentResult
from find_your_job.models import CandidateProfile, FitScore, JobPosting


class FitScoringAgent(Agent):
    def __init__(self) -> None:
        super().__init__("fit_scoring_agent")

    def run(self, candidate: CandidateProfile, jobs: list[JobPosting]) -> AgentResult[list[FitScore]]:
        scores = [self._score_one(candidate, job) for job in jobs]
        scores.sort(key=lambda item: item.score, reverse=True)
        return AgentResult(agent_name=self.name, payload=scores)

    def _score_one(self, candidate: CandidateProfile, job: JobPosting) -> FitScore:
        description = job.description.lower()
        candidate_skills = {skill.lower(): skill for skill in candidate.skills}
        matched = [original for key, original in candidate_skills.items() if key in description]

        target_title_bonus = 10 if any(title.lower() in job.title.lower() for title in candidate.target_titles) else 0
        location_bonus = 8 if any(location.lower() in job.location.lower() for location in candidate.preferred_locations) else 0
        experience_bonus = min(candidate.years_experience * 4, 20)
        match_bonus = min(len(matched) * 8, 40)

        required_keywords = self._extract_keywords(description)
        gaps = [keyword for keyword in required_keywords if keyword not in candidate_skills]
        gap_penalty = min(len(gaps) * 4, 20)

        score = max(0, min(100, target_title_bonus + location_bonus + experience_bonus + match_bonus - gap_penalty + 20))
        strengths = self._build_strengths(candidate, job, matched, location_bonus)
        rationale = self._build_rationale(score, matched, gaps, candidate, job)

        return FitScore(
            job_id=job.id,
            score=score,
            matched_skills=matched,
            strengths=strengths,
            gaps=gaps[:5],
            rationale=rationale,
        )

    def _extract_keywords(self, description: str) -> list[str]:
        tracked = [
            "python",
            "java",
            "javascript",
            "typescript",
            "react",
            "sql",
            "aws",
            "docker",
            "kubernetes",
            "machine learning",
            "analytics",
            "product sense",
            "communication",
        ]
        return [keyword for keyword in tracked if keyword in description]

    def _build_strengths(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        matched: list[str],
        location_bonus: int,
    ) -> list[str]:
        strengths: list[str] = []
        if matched:
            strengths.append(f"Strong direct overlap with job skills: {', '.join(matched[:4])}.")
        if location_bonus:
            strengths.append(f"Role location aligns with preferred markets for {candidate.name}.")
        if any(title.lower() in job.title.lower() for title in candidate.target_titles):
            strengths.append("Job title is close to the candidate's target search.")
        if candidate.achievements:
            strengths.append(f"Relevant achievement to feature: {candidate.achievements[0]}")
        return strengths or ["General profile alignment exists, but the evidence is weaker than higher-ranked roles."]

    def _build_rationale(
        self,
        score: int,
        matched: list[str],
        gaps: list[str],
        candidate: CandidateProfile,
        job: JobPosting,
    ) -> str:
        matched_text = ", ".join(matched[:4]) if matched else "limited direct skill overlap"
        gap_text = ", ".join(gaps[:3]) if gaps else "no major missing keywords"
        return (
            f"{candidate.name} scored {score}/100 for {job.title} at {job.company} because of "
            f"{matched_text}; main gaps: {gap_text}."
        )
