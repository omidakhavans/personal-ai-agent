"""Command-line interface for the minimal runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .evidence_context import EvidenceContextExecutor, EvidenceContextSettings
from .approval import SocialApprovalExecutor
from .model_client import OpenAIResponsesClient
from .privacy import reference_label, repository_label
from .research_resources import ResearchResourcesSettings, ResourceResearchExecutor
from .research_work import ResearchWorkExecutor, ResearchWorkSettings
from .runtime import Orchestrator, RuntimeErrorWithContext
from .state import StateError, paths_for_run, read_private_config, read_state
from .stages import RoutedStageExecutor
from .write_blog import BlogWriterExecutor, BlogWriterSettings
from .review_blog import BlogReviewerExecutor, BlogReviewerSettings
from .social_writing import LinkedInWriterExecutor, SocialWriterSettings, XWriterExecutor


DEFAULT_RUNS_DIR = Path("runs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-ai-agent",
        description="Minimal local agent runtime skeleton.",
    )
    parser.add_argument(
        "--runs-dir",
        default=str(DEFAULT_RUNS_DIR),
        help="Directory for run state and artifacts. Defaults to ./runs.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Start a new content workflow run.")
    run_parser.add_argument("subject", help="Subject for the workflow.")
    run_parser.add_argument(
        "--repository",
        required=True,
        help="Read-only local repository to research during the first stage.",
    )
    run_parser.add_argument(
        "--resource",
        action="append",
        default=[],
        help="Explicit local text path or http(s) URL for research-resources. Repeat as needed.",
    )
    run_parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model for research-work. Defaults to gpt-4.1-mini.",
    )

    resume_parser = subparsers.add_parser("resume", help="Resume an incomplete run.")
    resume_parser.add_argument("run_id", help="Run id to resume.")
    resume_parser.add_argument("--repository", help="Override the repository saved with the run.")
    resume_parser.add_argument("--model", help="Override the model saved with the run.")
    resume_parser.add_argument(
        "--resource",
        action="append",
        help="Override the resources saved with the run. Repeat as needed.",
    )

    approval_parser = subparsers.add_parser("approve-social", help="Approve a reviewed blog and create social drafts.")
    approval_parser.add_argument("run_id", help="Run id awaiting social-transformation approval.")
    approval_parser.add_argument("--notes", help="Optional approval notes recorded in approval.md.")
    approval_parser.add_argument("--repository", help="Override the repository saved with the run.")
    approval_parser.add_argument("--model", help="Override the model saved with the run.")
    approval_parser.add_argument("--resource", action="append", help="Override resources saved with the run.")

    state_parser = subparsers.add_parser("show-state", help="Print a run state.json.")
    state_parser.add_argument("run_id", help="Run id to inspect.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)

    try:
        if args.command == "run":
            executor = build_content_executor(Path(args.repository), tuple(args.resource), args.model)
            state = Orchestrator(runs_dir=runs_dir, executor=executor).start(
                args.subject,
                inputs={
                    "repository": repository_label(Path(args.repository).expanduser().resolve()),
                    "resources": [reference_label(resource) for resource in args.resource],
                    "model": args.model,
                },
                private_inputs={
                    "repository": str(Path(args.repository).expanduser().resolve()),
                    "resources": args.resource,
                    "model": args.model,
                },
            )
            print_run_result(state, runs_dir)
            return 0

        if args.command == "resume":
            read_state(paths_for_run(runs_dir, args.run_id).state_path)
            try:
                private_config = read_private_config(runs_dir, args.run_id)
            except StateError:
                if not args.repository or not args.model:
                    raise
                private_config = {
                    "repository": args.repository,
                    "resources": args.resource or [],
                    "model": args.model,
                }
            repository = args.repository or private_config.get("repository")
            model = args.model or private_config.get("model")
            resources = tuple(args.resource) if args.resource is not None else tuple(private_config.get("resources", []))
            if not repository or not model:
                raise RuntimeErrorWithContext(
                    "This run has no saved research configuration. Pass --repository and --model."
                )
            state = Orchestrator(
                runs_dir=runs_dir,
                executor=build_content_executor(Path(repository), resources, model),
            ).resume(args.run_id)
            print_run_result(state, runs_dir)
            return 0

        if args.command == "show-state":
            paths = paths_for_run(runs_dir, args.run_id)
            print(json.dumps(read_state(paths.state_path), indent=2, sort_keys=True))
            return 0

        if args.command == "approve-social":
            try:
                private_config = read_private_config(runs_dir, args.run_id)
            except StateError:
                if not args.repository or not args.model:
                    raise
                private_config = {
                    "repository": args.repository,
                    "resources": args.resource or [],
                    "model": args.model,
                }
            repository = args.repository or private_config.get("repository")
            model = args.model or private_config.get("model")
            resources = tuple(args.resource) if args.resource is not None else tuple(private_config.get("resources", []))
            if not repository or not model:
                raise RuntimeErrorWithContext("This run has no saved research configuration. Pass --repository and --model.")
            state = Orchestrator(
                runs_dir=runs_dir,
                executor=build_content_executor(Path(repository), resources, model),
            ).approve_social(args.run_id, args.notes)
            print_run_result(state, runs_dir)
            return 0
    except (RuntimeErrorWithContext, StateError) as exc:
        parser.error(str(exc))

    parser.error(f"Unknown command: {args.command}")
    return 2


def print_run_result(state: dict, runs_dir: Path) -> None:
    run_id = state["run_id"]
    print(f"run_id: {run_id}")
    print(f"status: {state['status']}")
    print("state artifact: state.json")
    print("artifact directory: this run's directory under the configured runs directory")


def build_content_executor(
    repository: Path,
    resources: tuple[str, ...],
    model: str,
) -> RoutedStageExecutor:
    research_work = ResearchWorkExecutor(
        settings=ResearchWorkSettings(repository=repository, model=model),
        client=OpenAIResponsesClient(),
    )
    research_resources = ResourceResearchExecutor(
        settings=ResearchResourcesSettings(references=resources, model=model),
        client=OpenAIResponsesClient(),
    )
    evidence_context = EvidenceContextExecutor(
        settings=EvidenceContextSettings(model=model),
        client=OpenAIResponsesClient(),
    )
    write_blog = BlogWriterExecutor(
        settings=BlogWriterSettings(model=model),
        client=OpenAIResponsesClient(max_output_tokens=2_400),
    )
    review_blog = BlogReviewerExecutor(
        settings=BlogReviewerSettings(model=model),
        client=OpenAIResponsesClient(max_output_tokens=2_400),
    )
    social_settings = SocialWriterSettings(model=model)
    return RoutedStageExecutor(
        research_work=research_work,
        research_resources=research_resources,
        evidence_context=evidence_context,
        write_blog=write_blog,
        review_blog=review_blog,
        approve_social=SocialApprovalExecutor(),
        write_linkedin=LinkedInWriterExecutor(settings=social_settings, client=OpenAIResponsesClient(max_output_tokens=1_600)),
        write_x=XWriterExecutor(settings=social_settings, client=OpenAIResponsesClient(max_output_tokens=1_600)),
    )


if __name__ == "__main__":
    raise SystemExit(main())
