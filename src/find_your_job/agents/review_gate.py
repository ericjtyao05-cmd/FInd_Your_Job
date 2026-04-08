from __future__ import annotations

import json
import os

from .base import Agent, AgentResult
from find_your_job.models import (
    ApplicationPackage,
    ApplicationStatus,
    BrowserExecutionResult,
    FitScore,
    ReviewDecision,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


REVIEW_GATE_SCHEMA = {
    "type": "json_schema",
    "name": "review_decision",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["ready", "needs_review", "blocked"],
            },
            "risky_paragraphs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "confirmation_required": {"type": "boolean"},
            "notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["status", "risky_paragraphs", "confirmation_required", "notes"],
        "additionalProperties": False,
    },
}


class ReviewGateAgent(Agent):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__("review_gate_agent")
        self.api_key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip() or None
        self.model = (model or os.getenv("DEEPSEEK_REVIEW_GATE_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
        self.base_url = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key and OpenAI is not None else None

    def run(
        self,
        applications: list[ApplicationPackage],
        fit_scores: list[FitScore],
        browser_results: list[BrowserExecutionResult],
    ) -> AgentResult[list[ReviewDecision]]:
        fit_lookup = {score.job_id: score for score in fit_scores}
        browser_lookup = {result.job_id: result for result in browser_results}
        decisions = [self._review_one(pkg, fit_lookup[pkg.job_id], browser_lookup[pkg.job_id]) for pkg in applications]
        return AgentResult(agent_name=self.name, payload=decisions)

    def _review_one(
        self,
        application: ApplicationPackage,
        fit_score: FitScore,
        browser_result: BrowserExecutionResult,
    ) -> ReviewDecision:
        if browser_result.mistakes:
            return ReviewDecision(
                job_id=application.job_id,
                status=ApplicationStatus.BLOCKED,
                risky_paragraphs=[],
                confirmation_required=True,
                notes=browser_result.mistakes,
            )

        if self._client is not None:
            llm_review = self._review_one_with_llm(application, fit_score, browser_result)
            if llm_review is not None:
                return llm_review

        return self._review_one_fallback(application, fit_score, browser_result)

    def _review_one_fallback(
        self,
        application: ApplicationPackage,
        fit_score: FitScore,
        browser_result: BrowserExecutionResult,
    ) -> ReviewDecision:
        risky_paragraphs: list[str] = []
        notes: list[str] = []
        status = ApplicationStatus.READY

        if fit_score.gaps:
            risky_paragraphs.append(
                f"Candidate should confirm any claim about missing area: {fit_score.gaps[0]}"
            )
            notes.append("Gap-based claims need explicit user review before submission.")
            status = ApplicationStatus.NEEDS_REVIEW

        if "I would immediately bring" in application.cover_letter:
            risky_paragraphs.append("Cover letter contains assertive impact language that should be user-verified.")
            status = ApplicationStatus.NEEDS_REVIEW

        if browser_result.mistakes:
            notes.extend(browser_result.mistakes)
            status = ApplicationStatus.BLOCKED

        return ReviewDecision(
            job_id=application.job_id,
            status=status,
            risky_paragraphs=risky_paragraphs,
            confirmation_required=True,
            notes=notes or ["Final user confirmation is required before apply."],
        )

    def _review_one_with_llm(
        self,
        application: ApplicationPackage,
        fit_score: FitScore,
        browser_result: BrowserExecutionResult,
    ) -> ReviewDecision | None:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a conservative application review gate. Return valid json only. "
                            "Flag unsupported claims, overconfident language, weak evidence, and risky gap statements. "
                            "Do not approve questionable claims just because they sound plausible. "
                            "If browser automation reported mistakes, the status must be blocked. "
                            "Output json matching the requested structure."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(application, fit_score, browser_result),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=1200,
            )
            content = json.loads(response.choices[0].message.content or "{}")
            status = ApplicationStatus(content["status"])
            if browser_result.mistakes:
                status = ApplicationStatus.BLOCKED
            return ReviewDecision(
                job_id=application.job_id,
                status=status,
                risky_paragraphs=self._limit_strings(content["risky_paragraphs"], limit=5),
                confirmation_required=bool(content["confirmation_required"]),
                notes=self._limit_strings(content["notes"], limit=5) or ["Final user confirmation is required before apply."],
            )
        except Exception:  # pragma: no cover
            return None

    def _build_prompt(
        self,
        application: ApplicationPackage,
        fit_score: FitScore,
        browser_result: BrowserExecutionResult,
    ) -> str:
        return (
            "Review whether the application package is safe to proceed.\n\n"
            "Fit analysis:\n"
            f"- Score: {fit_score.score}\n"
            f"- Matched skills: {', '.join(fit_score.matched_skills) or 'N/A'}\n"
            f"- Strengths: {', '.join(fit_score.strengths) or 'N/A'}\n"
            f"- Gaps: {', '.join(fit_score.gaps) or 'N/A'}\n"
            f"- Rationale: {fit_score.rationale}\n\n"
            "Application package:\n"
            f"- Resume summary: {application.tailored_resume.summary}\n"
            f"- Resume bullet updates: {' | '.join(application.tailored_resume.bullet_updates) or 'N/A'}\n"
            f"- Highlighted keywords: {', '.join(application.tailored_resume.highlighted_keywords) or 'N/A'}\n"
            f"- Cover letter: {application.cover_letter}\n"
            f"- QA script: {' | '.join(application.qa_script) or 'N/A'}\n\n"
            "Browser execution:\n"
            f"- Success: {browser_result.success}\n"
            f"- Mistakes: {', '.join(browser_result.mistakes) or 'None'}\n"
            f"- Submitted: {browser_result.submitted}\n\n"
            "Return JSON with:\n"
            "- status: ready, needs_review, or blocked\n"
            "- risky_paragraphs: exact passages or concise issue labels requiring user review\n"
            "- confirmation_required: boolean\n"
            "- notes: concise review notes\n\n"
            "JSON example:\n"
            "{\n"
            '  "status": "needs_review",\n'
            '  "risky_paragraphs": ["Gap claim needs review"],\n'
            '  "confirmation_required": true,\n'
            '  "notes": ["Final user confirmation is required before apply."]\n'
            "}"
        )

    def _limit_strings(self, values: list[str], limit: int) -> list[str]:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        return cleaned[:limit]
