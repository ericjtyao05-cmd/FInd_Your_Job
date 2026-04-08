from __future__ import annotations

import json
import os
import re

from .base import Agent, AgentResult
from find_your_job.models import CandidateProfile, FitScore, JobPosting

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


FIT_SCORE_SCHEMA = {
    "type": "json_schema",
    "name": "fit_score",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "matched_skills": {
                "type": "array",
                "items": {"type": "string"},
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rationale": {"type": "string"},
        },
        "required": ["score", "matched_skills", "strengths", "gaps", "rationale"],
        "additionalProperties": False,
    },
}


class FitScoringAgent(Agent):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__("fit_scoring_agent")
        self.api_key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip() or None
        self.model = (model or os.getenv("DEEPSEEK_FIT_SCORING_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
        self.base_url = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key and OpenAI is not None else None

    def run(self, candidate: CandidateProfile, jobs: list[JobPosting]) -> AgentResult[list[FitScore]]:
        scores = [self._score_one(candidate, job) for job in jobs]
        scores.sort(key=lambda item: item.score, reverse=True)
        return AgentResult(agent_name=self.name, payload=scores)

    def _score_one(self, candidate: CandidateProfile, job: JobPosting) -> FitScore:
        if self._client is not None:
            llm_score = self._score_one_with_llm(candidate, job)
            if llm_score is not None:
                return llm_score

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

    def _score_one_with_llm(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
    ) -> FitScore | None:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You evaluate candidate-job fit conservatively. Return valid json only. "
                            "Do not invent qualifications, employers, credentials, or experience. "
                            "Base the score only on the provided candidate profile and job text. "
                            "A score above 85 requires strong direct evidence. "
                            "Keep strengths and gaps specific. Output json matching the requested structure."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(candidate, job),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=1200,
            )
            content = json.loads(response.choices[0].message.content or "{}")
            return FitScore(
                job_id=job.id,
                score=int(content["score"]),
                matched_skills=self._limit_strings(content["matched_skills"], limit=8),
                strengths=self._limit_strings(content["strengths"], limit=4),
                gaps=self._limit_strings(content["gaps"], limit=5),
                rationale=content["rationale"].strip(),
            )
        except Exception:  # pragma: no cover
            return None

    def _build_prompt(self, candidate: CandidateProfile, job: JobPosting) -> str:
        return (
            "Score the candidate's fit for the job from 0 to 100.\n\n"
            "Candidate:\n"
            f"- Name: {candidate.name}\n"
            f"- Target titles: {', '.join(candidate.target_titles) or 'N/A'}\n"
            f"- Preferred locations: {', '.join(candidate.preferred_locations) or 'N/A'}\n"
            f"- Years of experience: {candidate.years_experience}\n"
            f"- Skills: {', '.join(candidate.skills) or 'N/A'}\n"
            f"- Resume summary: {candidate.resume_text or 'N/A'}\n"
            f"- Achievements: {', '.join(candidate.achievements) or 'N/A'}\n\n"
            "Job:\n"
            f"- Title: {job.title}\n"
            f"- Company: {job.company}\n"
            f"- Location: {job.location}\n"
            f"- Source: {job.source}\n"
            f"- Description: {job.description or 'No detailed description available.'}\n\n"
            "Return JSON with:\n"
            "- score: integer 0-100\n"
            "- matched_skills: concrete matched skills or evidence\n"
            "- strengths: 2 to 4 strengths\n"
            "- gaps: up to 5 material gaps\n"
            "- rationale: concise explanation of the score\n\n"
            "JSON example:\n"
            "{\n"
            '  "score": 78,\n'
            '  "matched_skills": ["Python", "AWS"],\n'
            '  "strengths": ["Strong backend overlap"],\n'
            '  "gaps": ["Kubernetes"],\n'
            '  "rationale": "Short explanation"\n'
            "}"
        )

    def _limit_strings(self, values: list[str], limit: int) -> list[str]:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        return cleaned[:limit]

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
