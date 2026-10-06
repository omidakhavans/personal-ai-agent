"""Command-line interface for the minimal runtime."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .approval import SocialApprovalExecutor
from .evidence_context import EvidenceContextExecutor, EvidenceContextSettings
from .model_client import OpenAIResponsesClient
from .privacy import reference_label, repository_label
from .research_resources import ResearchResourcesSettings, ResourceResearchExecutor
from .research_work import ResearchWorkExecutor, ResearchWorkSettings
from .review_blog import BlogReviewerExecutor, BlogReviewerSettings
from .runtime import Orchestrator, RuntimeErrorWithContext
from .social_writing import (
    LinkedInWriterExecutor,
    SocialWriterSettings,
    XWriterExecutor,
)
from .stages import RoutedStageExecutor
from .state import StateError, paths_for_run, read_private_config, read_state
from .write_blog import BlogWriterExecutor, BlogWriterSettings

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_MAX_MODEL_ATTEMPTS = 3


@dataclass(frozen=True)
class ModelRuntimeOptions:
    """Operational limits shared by model-backed stages in one run."""

    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_MODEL_ATTEMPTS
    max_output_tokens: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        """Return JSON-safe values for resumable local configuration."""
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "max_output_tokens": self.max_output_tokens,
        }


def positive_int(value: str) -> int:
    """Accept only positive CLI limits, before a model request can start."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a whole number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI grammar for starting and operating local workflow runs."""
    parser = argparse.ArgumentParser(
        prog="personal-ai-agent",
        description="Minimal local agent runtime skeleton.",
    )
    parser.add_argument(
        "--runs-dir",
        default=str(DEFAULT_RUNS_DIR),
        help="Directory for run state and artifacts. Defaults to ./runs.",
    )
    parser.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help="Format run and validation summaries for a person or another tool.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=positive_int,
        help=f"Per-model-request timeout. Defaults to {DEFAULT_REQUEST_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--max-model-attempts",
        type=positive_int,
        help=f"Maximum retry attempts for retryable model API responses. Defaults to {DEFAULT_MAX_MODEL_ATTEMPTS}.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=positive_int,
        help="Override the output-token limit for every model-backed stage in this run.",
    )
    parser.add_argument("--version", action="version", version="personal-ai-agent 0.1.0")

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
        help="OpenAI model for all model-backed stages. Defaults to gpt-4.1-mini.",
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

    validate_parser = subparsers.add_parser(
        "validate", help="Check a run's persisted state and expected artifacts without invoking a model."
    )
    validate_parser.add_argument("run_id", help="Run id to validate.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI input, construct required capabilities, and run one command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)

    try:
        if args.command == "run":
            model_options = model_options_from_args(args)
            executor = build_content_executor(
                Path(args.repository), tuple(args.resource), args.model, model_options
            )
            state = Orchestrator(runs_dir=runs_dir, executor=executor).start(
                args.subject,
                inputs={
                    "repository": repository_label(Path(args.repository).expanduser().resolve()),
                    "resources": [reference_label(resource) for resource in args.resource],
                    "model": args.model,
                    "model_runtime": model_options.as_dict(),
                },
                private_inputs={
                    "repository": str(Path(args.repository).expanduser().resolve()),
                    "resources": args.resource,
                    "model": args.model,
                    "model_options": model_options.as_dict(),
                },
            )
            print_run_result(state, output_format=args.output_format)
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
            model_options = model_options_from_args(args, private_config)
            state = Orchestrator(
                runs_dir=runs_dir,
                executor=build_content_executor(
                    Path(repository), resources, model, model_options
                ),
            ).resume(args.run_id)
            print_run_result(state, output_format=args.output_format)
            return 0

        if args.command == "show-state":
            paths = paths_for_run(runs_dir, args.run_id)
            print(json.dumps(read_state(paths.state_path), indent=2, sort_keys=True))
            return 0

        if args.command == "validate":
            state = Orchestrator(runs_dir=runs_dir).validate_run(args.run_id)
            print_validation_result(state, output_format=args.output_format)
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
            model_options = model_options_from_args(args, private_config)
            state = Orchestrator(
                runs_dir=runs_dir,
                executor=build_content_executor(
                    Path(repository), resources, model, model_options
                ),
            ).approve_social(args.run_id, args.notes)
            print_run_result(state, output_format=args.output_format)
            return 0
    except (RuntimeErrorWithContext, StateError) as exc:
        parser.error(str(exc))

    parser.error(f"Unknown command: {args.command}")


def model_options_from_args(
    args: argparse.Namespace, private_config: dict[str, object] | None = None
) -> ModelRuntimeOptions:
    """Merge explicit CLI overrides with the values stored for a resumable run."""
    saved = private_config.get("model_options") if private_config else None
    saved_options = saved if isinstance(saved, dict) else {}
    timeout = args.request_timeout_seconds or saved_options.get(
        "timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    max_attempts = args.max_model_attempts or saved_options.get(
        "max_attempts", DEFAULT_MAX_MODEL_ATTEMPTS
    )
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else saved_options.get("max_output_tokens")
    )
    if not isinstance(timeout, int) or not isinstance(max_attempts, int):
        raise RuntimeErrorWithContext("Saved model runtime options are invalid.")
    if max_output_tokens is not None and not isinstance(max_output_tokens, int):
        raise RuntimeErrorWithContext("Saved model runtime options are invalid.")
    return ModelRuntimeOptions(timeout, max_attempts, max_output_tokens)


def print_run_result(state: dict, *, output_format: str) -> None:
    """Print a safe concise status summary for a newly advanced run."""
    run_id = state["run_id"]
    artifact_names = [
        stage["artifact"]
        for stage in state["stages"].values()
        if stage["status"] in {"completed", "skipped", "blocked", "awaiting_approval"}
    ]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": state["status"],
                    "current_stage": state["current_stage"],
                    "artifacts": artifact_names,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    print(f"run_id: {run_id}")
    print(f"status: {state['status']}")
    print("state artifact: state.json")
    print("artifact directory: this run's directory under the configured runs directory")


def print_validation_result(state: dict, *, output_format: str) -> None:
    """Print the outcome of the read-only state and artifact validation command."""
    validated = [
        name
        for name, stage in state["stages"].items()
        if stage["status"] in {"completed", "skipped", "blocked", "awaiting_approval"}
    ]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "run_id": state["run_id"],
                    "status": state["status"],
                    "validated_stages": validated,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    print(f"run_id: {state['run_id']}")
    print("validation: passed")
    print("validated stages: " + (", ".join(validated) or "none"))


def build_content_executor(
    repository: Path,
    resources: tuple[str, ...],
    model: str,
    model_options: ModelRuntimeOptions | None = None,
) -> RoutedStageExecutor:
    """Compose the concrete executors used by the Phase 2 CLI workflow."""
    options = model_options or ModelRuntimeOptions()

    def client(default_max_output_tokens: int) -> OpenAIResponsesClient:
        """Create a client that shares run limits and preserves stage defaults."""
        return OpenAIResponsesClient(
            timeout_seconds=options.timeout_seconds,
            max_attempts=options.max_attempts,
            max_output_tokens=options.max_output_tokens or default_max_output_tokens,
        )

    research_work = ResearchWorkExecutor(
        settings=ResearchWorkSettings(repository=repository, model=model),
        client=client(1_600),
    )
    research_resources = ResourceResearchExecutor(
        settings=ResearchResourcesSettings(references=resources, model=model),
        client=client(1_600),
    )
    evidence_context = EvidenceContextExecutor(
        settings=EvidenceContextSettings(model=model),
        client=client(1_600),
    )
    write_blog = BlogWriterExecutor(
        settings=BlogWriterSettings(model=model),
        client=client(2_400),
    )
    review_blog = BlogReviewerExecutor(
        settings=BlogReviewerSettings(model=model),
        client=client(2_400),
    )
    social_settings = SocialWriterSettings(model=model)
    return RoutedStageExecutor(
        research_work=research_work,
        research_resources=research_resources,
        evidence_context=evidence_context,
        write_blog=write_blog,
        review_blog=review_blog,
        approve_social=SocialApprovalExecutor(),
        write_linkedin=LinkedInWriterExecutor(settings=social_settings, client=client(1_600)),
        write_x=XWriterExecutor(settings=social_settings, client=client(1_600)),
    )




if __name__ == "__main__":
    raise SystemExit(main())
