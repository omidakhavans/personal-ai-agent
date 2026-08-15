"""Command-line interface for the minimal runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .runtime import Orchestrator, RuntimeErrorWithContext
from .state import paths_for_run, read_state


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

    resume_parser = subparsers.add_parser("resume", help="Resume an incomplete run.")
    resume_parser.add_argument("run_id", help="Run id to resume.")

    state_parser = subparsers.add_parser("show-state", help="Print a run state.json.")
    state_parser.add_argument("run_id", help="Run id to inspect.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)

    try:
        if args.command == "run":
            state = Orchestrator(runs_dir=runs_dir).start(args.subject)
            print_run_result(state, runs_dir)
            return 0

        if args.command == "resume":
            state = Orchestrator(runs_dir=runs_dir).resume(args.run_id)
            print_run_result(state, runs_dir)
            return 0

        if args.command == "show-state":
            paths = paths_for_run(runs_dir, args.run_id)
            print(json.dumps(read_state(paths.state_path), indent=2, sort_keys=True))
            return 0
    except RuntimeErrorWithContext as exc:
        parser.error(str(exc))

    parser.error(f"Unknown command: {args.command}")
    return 2


def print_run_result(state: dict, runs_dir: Path) -> None:
    run_id = state["run_id"]
    paths = paths_for_run(runs_dir, run_id)
    print(f"run_id: {run_id}")
    print(f"status: {state['status']}")
    print(f"state: {paths.state_path}")
    print(f"artifacts: {paths.run_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
