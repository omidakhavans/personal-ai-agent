"""Small, explicit workflow runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .stages import (
    STAGE_BLOCKED,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_PENDING,
    STAGE_RUNNING,
    STAGE_SKIPPED,
    TERMINAL_STAGE_STATUSES,
    WORKFLOW_STAGES,
    PlaceholderStageExecutor,
    StageExecutor,
)
from .state import (
    RUN_BLOCKED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_RUNNING,
    initial_state,
    new_run_id,
    paths_for_run,
    read_state,
    utc_now,
    write_state,
)


class RuntimeErrorWithContext(RuntimeError):
    """Runtime-level error with a user-facing message."""


class Orchestrator:
    def __init__(
        self,
        *,
        runs_dir: Path,
        executor: StageExecutor | None = None,
    ) -> None:
        self.runs_dir = runs_dir
        self.executor = executor or PlaceholderStageExecutor()

    def start(self, subject: str) -> dict[str, Any]:
        run_id = new_run_id()
        paths = paths_for_run(self.runs_dir, run_id)
        paths.run_dir.mkdir(parents=True, exist_ok=False)
        state = initial_state(run_id=run_id, subject=subject)
        write_state(paths.state_path, state)
        return self._advance(state=state, state_path=paths.state_path, run_dir=paths.run_dir)

    def resume(self, run_id: str) -> dict[str, Any]:
        paths = paths_for_run(self.runs_dir, run_id)
        if not paths.state_path.exists():
            raise RuntimeErrorWithContext(f"Run not found: {run_id}")
        state = read_state(paths.state_path)

        if state["status"] in {RUN_COMPLETED, RUN_BLOCKED, RUN_FAILED}:
            return state

        self._reset_interrupted_stage(state)
        return self._advance(state=state, state_path=paths.state_path, run_dir=paths.run_dir)

    def _reset_interrupted_stage(self, state: dict[str, Any]) -> None:
        for stage in WORKFLOW_STAGES:
            stage_state = state["stages"][stage.name]
            if stage_state["status"] == STAGE_RUNNING:
                stage_state["status"] = STAGE_PENDING
                stage_state["message"] = "Reset from interrupted running state."
                stage_state["finished_at"] = None
                return

    def _advance(
        self,
        *,
        state: dict[str, Any],
        state_path: Path,
        run_dir: Path,
    ) -> dict[str, Any]:
        state["status"] = RUN_RUNNING
        write_state(state_path, state)

        for stage in WORKFLOW_STAGES:
            stage_state = state["stages"][stage.name]
            status = stage_state["status"]

            if status in {STAGE_COMPLETED, STAGE_SKIPPED}:
                continue
            if status == STAGE_BLOCKED:
                state["status"] = RUN_BLOCKED
                state["current_stage"] = stage.name
                write_state(state_path, state)
                return state
            if status == STAGE_FAILED:
                state["status"] = RUN_FAILED
                state["current_stage"] = stage.name
                write_state(state_path, state)
                return state
            if status != STAGE_PENDING:
                raise RuntimeErrorWithContext(
                    f"Cannot resume stage {stage.name!r} from status {status!r}."
                )

            state["current_stage"] = stage.name
            stage_state["status"] = STAGE_RUNNING
            stage_state["started_at"] = utc_now()
            write_state(state_path, state)

            try:
                result = self.executor.execute(
                    stage=stage,
                    subject=state["subject"],
                    run_dir=run_dir,
                )
            except Exception as exc:  # pragma: no cover - exact exception is stage-specific
                stage_state["status"] = STAGE_FAILED
                stage_state["message"] = f"{type(exc).__name__}: {exc}"
                stage_state["finished_at"] = utc_now()
                state["status"] = RUN_FAILED
                write_state(state_path, state)
                return state

            if result.status not in TERMINAL_STAGE_STATUSES:
                stage_state["status"] = STAGE_FAILED
                stage_state["message"] = f"Invalid stage result status: {result.status}"
                stage_state["finished_at"] = utc_now()
                state["status"] = RUN_FAILED
                write_state(state_path, state)
                return state

            stage_state["status"] = result.status
            stage_state["message"] = result.message
            stage_state["finished_at"] = utc_now()
            if result.artifact:
                stage_state["artifact"] = result.artifact
            write_state(state_path, state)

            if result.status == STAGE_BLOCKED:
                state["status"] = RUN_BLOCKED
                write_state(state_path, state)
                return state
            if result.status == STAGE_FAILED:
                state["status"] = RUN_FAILED
                write_state(state_path, state)
                return state

        state["status"] = RUN_COMPLETED
        state["current_stage"] = None
        write_state(state_path, state)
        return state
