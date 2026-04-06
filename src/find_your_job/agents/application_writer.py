from __future__ import annotations

from .base import Agent, AgentResult
from find_your_job.models import (
    ApplicationPackage,
    CandidateProfile,
    FitScore,
    JobPosting,
    ResumeEdit,
)


class ApplicationWriterAgent(Agent):
    def __init__(self) -> None:
        super().__init__("application_writer_agent")

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
