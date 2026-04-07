from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from find_your_job.agents.research import ResearchAgent
from find_your_job.orchestrator import JobMatchSystem, WorkflowConfig
from find_your_job.sample_data import sample_candidate, sample_jobs, sample_research_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Find Your Job multi-agent workflow.")
    parser.add_argument("--top-n", type=int, default=3, help="How many applications to draft.")
    parser.add_argument(
        "--allow-submit",
        action="store_true",
        help="If enabled, the browser executor will mark valid applications as submitted.",
    )
    parser.add_argument(
        "--live-research",
        action="store_true",
        help="Fetch live jobs from the configured live sources, including LinkedIn guest search plus official Lever and Greenhouse boards.",
    )
    parser.add_argument(
        "--research-only",
        action="store_true",
        help="Run only the research agent and print discovered jobs.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    candidate = sample_candidate()
    jobs = [] if args.live_research else sample_jobs()
    sources = sample_research_sources()

    if args.research_only:
        research = ResearchAgent().run(
            jobs=jobs,
            candidate=candidate,
            sources=sources if args.live_research else None,
        ).payload
        print(json.dumps(asdict(research), indent=2))
        return

    system = JobMatchSystem()
    result = system.run(
        candidate=candidate,
        jobs=jobs,
        config=WorkflowConfig(
            top_n_applications=args.top_n,
            allow_submit=args.allow_submit,
            live_research=args.live_research,
            research_sources=sources,
        ),
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
