from __future__ import annotations

from .base import Agent, AgentResult
from find_your_job.models import (
    ApplicationPackage,
    ApplicationStatus,
    BrowserExecutionResult,
    FitScore,
    ReviewDecision,
)


class ReviewGateAgent(Agent):
    def __init__(self) -> None:
        super().__init__("review_gate_agent")

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
