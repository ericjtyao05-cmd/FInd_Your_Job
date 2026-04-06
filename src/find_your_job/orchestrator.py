from __future__ import annotations

from dataclasses import dataclass

from find_your_job.agents import (
    ApplicationWriterAgent,
    BrowserExecutorAgent,
    FitScoringAgent,
    ResearchAgent,
    ReviewGateAgent,
)
from find_your_job.browser_adapters import BrowserTaskBuilder
from find_your_job.models import (
    CandidateProfile,
    JobPosting,
    ResearchSource,
    WorkflowResult,
)


@dataclass(slots=True)
class WorkflowConfig:
    top_n_applications: int = 3
    allow_submit: bool = False
    live_research: bool = False
    research_sources: list[ResearchSource] | None = None


class JobMatchSystem:
    def __init__(
        self,
        research_agent: ResearchAgent | None = None,
        fit_agent: FitScoringAgent | None = None,
        writer_agent: ApplicationWriterAgent | None = None,
        browser_agent: BrowserExecutorAgent | None = None,
        review_agent: ReviewGateAgent | None = None,
        browser_task_builder: BrowserTaskBuilder | None = None,
    ) -> None:
        self.research_agent = research_agent or ResearchAgent()
        self.fit_agent = fit_agent or FitScoringAgent()
        self.writer_agent = writer_agent or ApplicationWriterAgent()
        self.browser_agent = browser_agent or BrowserExecutorAgent()
        self.review_agent = review_agent or ReviewGateAgent()
        self.browser_task_builder = browser_task_builder or BrowserTaskBuilder()

    def run(
        self,
        candidate: CandidateProfile,
        jobs: list[JobPosting],
        config: WorkflowConfig | None = None,
    ) -> WorkflowResult:
        config = config or WorkflowConfig()

        research = self.research_agent.run(
            jobs=jobs,
            candidate=candidate,
            sources=config.research_sources if config.live_research else None,
        ).payload
        fit_scores = self.fit_agent.run(candidate, research.deduplicated_jobs).payload
        applications = self.writer_agent.run(
            candidate,
            research.deduplicated_jobs,
            fit_scores,
            top_n=config.top_n_applications,
        ).payload
        job_lookup = {job.id: job for job in research.deduplicated_jobs}
        browser_tasks = [
            self.browser_task_builder.build(candidate, job_lookup[application.job_id], application)
            for application in applications
        ]
        browser_results = self.browser_agent.run(browser_tasks, submit=config.allow_submit).payload
        reviews = self.review_agent.run(applications, fit_scores, browser_results).payload

        return WorkflowResult(
            research=research,
            fit_scores=fit_scores,
            application_packages=applications,
            browser_results=browser_results,
            reviews=reviews,
        )
