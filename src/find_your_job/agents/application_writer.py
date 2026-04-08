from __future__ import annotations

import json
import os

from .base import Agent, AgentResult
from find_your_job.models import (
    ApplicationPackage,
    CandidateProfile,
    FitScore,
    JobPosting,
    ResumeEdit,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


APPLICATION_PACKAGE_SCHEMA = {
    "type": "json_schema",
    "name": "application_package",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "bullet_updates": {
                "type": "array",
                "items": {"type": "string"},
            },
            "highlighted_keywords": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cover_letter": {"type": "string"},
            "qa_script": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "summary",
            "bullet_updates",
            "highlighted_keywords",
            "cover_letter",
            "qa_script",
        ],
        "additionalProperties": False,
    },
}


class ApplicationWriterAgent(Agent):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__("application_writer_agent")
        self.api_key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip() or None
        self.model = (model or os.getenv("DEEPSEEK_APPLICATION_WRITER_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
        self.base_url = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key and OpenAI is not None else None

    def run(
        self,
        candidate: CandidateProfile,
        jobs: list[JobPosting],
        fit_scores: list[FitScore],
        top_n: int = 3,
    ) -> AgentResult[list[ApplicationPackage]]:
        score_lookup = {score.job_id: score for score in fit_scores}
        ranked_jobs = sorted(jobs, key=lambda job: score_lookup[job.id].score, reverse=True)[:top_n]
        packages = [self._build_package(candidate, job, score_lookup[job.id]) for job in ranked_jobs]
        return AgentResult(agent_name=self.name, payload=packages)

    def _build_package(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        fit_score: FitScore,
    ) -> ApplicationPackage:
        if self._client is not None:
            llm_package = self._build_package_with_llm(candidate, job, fit_score)
            if llm_package is not None:
                return llm_package

        return self._build_package_fallback(candidate, job, fit_score)

    def _build_package_fallback(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        fit_score: FitScore,
    ) -> ApplicationPackage:
        keywords = fit_score.matched_skills[:6]
        summary = (
            f"{candidate.name} is a {candidate.years_experience}-year candidate targeting {job.title} "
            f"roles with strengths in {', '.join(keywords) if keywords else 'transferable delivery and communication'}."
        )
        bullet_updates = [
            f"Reorder bullets to foreground impact tied to {job.company}'s priorities.",
            f"Add measurable outcome related to {keywords[0] if keywords else 'execution quality'}.",
            "Trim unrelated content that does not support this target role.",
        ]
        cover_letter = (
            f"Dear {job.company} hiring team,\n\n"
            f"I am applying for the {job.title} role in {job.location}. My background includes "
            f"{candidate.years_experience} years of experience and hands-on work across {', '.join(candidate.skills[:5])}. "
            f"I am especially interested in this role because the job description emphasizes "
            f"{', '.join(fit_score.matched_skills[:3]) if fit_score.matched_skills else 'cross-functional execution'}.\n\n"
            f"One area I would immediately bring is {candidate.achievements[0] if candidate.achievements else 'clear ownership and delivery discipline'}. "
            f"I would welcome the chance to explain how that experience maps to your team.\n\n"
            f"Sincerely,\n{candidate.name}"
        )
        qa_script = [
            f"Why do you want to join {job.company}? -> Tie motivation to the team mission and role scope.",
            f"Why are you a fit for {job.title}? -> Lead with matched skills: {', '.join(fit_score.matched_skills[:4]) or 'adaptability and execution'}.",
            f"What is your biggest gap? -> Acknowledge {fit_score.gaps[0] if fit_score.gaps else 'the steepest learning area'} and describe the ramp plan.",
        ]
        return ApplicationPackage(
            job_id=job.id,
            tailored_resume=ResumeEdit(
                summary=summary,
                bullet_updates=bullet_updates,
                highlighted_keywords=keywords,
            ),
            cover_letter=cover_letter,
            qa_script=qa_script,
        )

    def _build_package_with_llm(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        fit_score: FitScore,
    ) -> ApplicationPackage | None:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write grounded job application materials. Return valid json only. "
                            "Do not fabricate candidate experience, credentials, employers, or metrics. "
                            "If job details are thin, stay conservative and use only the provided evidence. "
                            "Keep bullet updates specific and actionable. Keep the cover letter concise. "
                            "Output json matching the requested structure."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(candidate, job, fit_score),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=1800,
            )
            content = json.loads(response.choices[0].message.content or "{}")
            return ApplicationPackage(
                job_id=job.id,
                tailored_resume=ResumeEdit(
                    summary=content["summary"].strip(),
                    bullet_updates=self._limit_strings(content["bullet_updates"], limit=4),
                    highlighted_keywords=self._limit_strings(content["highlighted_keywords"], limit=8),
                ),
                cover_letter=content["cover_letter"].strip(),
                qa_script=self._limit_strings(content["qa_script"], limit=5),
            )
        except Exception:  # pragma: no cover
            return None

    def _build_prompt(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        fit_score: FitScore,
    ) -> str:
        return (
            "Create tailored application materials from the structured context below.\n\n"
            "Candidate:\n"
            f"- Name: {candidate.name}\n"
            f"- Years of experience: {candidate.years_experience}\n"
            f"- Target titles: {', '.join(candidate.target_titles) or 'N/A'}\n"
            f"- Preferred locations: {', '.join(candidate.preferred_locations) or 'N/A'}\n"
            f"- Skills: {', '.join(candidate.skills) or 'N/A'}\n"
            f"- Resume summary: {candidate.resume_text or 'N/A'}\n"
            f"- Achievements: {', '.join(candidate.achievements) or 'N/A'}\n\n"
            "Job:\n"
            f"- Title: {job.title}\n"
            f"- Company: {job.company}\n"
            f"- Location: {job.location}\n"
            f"- Source: {job.source}\n"
            f"- URL: {job.url}\n"
            f"- Description: {job.description or 'No detailed description available.'}\n\n"
            "Fit analysis:\n"
            f"- Score: {fit_score.score}\n"
            f"- Matched skills: {', '.join(fit_score.matched_skills) or 'N/A'}\n"
            f"- Strengths: {', '.join(fit_score.strengths) or 'N/A'}\n"
            f"- Gaps: {', '.join(fit_score.gaps) or 'N/A'}\n"
            f"- Rationale: {fit_score.rationale}\n\n"
            "Return JSON with:\n"
            "- summary: 1-2 sentences for the tailored resume summary\n"
            "- bullet_updates: 3 or 4 concrete resume bullet rewrite instructions\n"
            "- highlighted_keywords: 4 to 8 role-relevant keywords\n"
            "- cover_letter: concise, specific, and evidence-based\n"
            "- qa_script: 3 to 5 interview prep prompts with concise answer guidance\n\n"
            "JSON example:\n"
            "{\n"
            '  "summary": "Candidate summary",\n'
            '  "bullet_updates": ["Update 1", "Update 2", "Update 3"],\n'
            '  "highlighted_keywords": ["keyword1", "keyword2"],\n'
            '  "cover_letter": "Letter text",\n'
            '  "qa_script": ["Question -> answer guidance"]\n'
            "}"
        )

    def _limit_strings(self, values: list[str], limit: int) -> list[str]:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        return cleaned[:limit]
