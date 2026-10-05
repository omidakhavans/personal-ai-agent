"""Small, explicit workflow runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .stages import (
    STAGE_AWAITING_APPROVAL,
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
    RUN_AWAITING_APPROVAL,
    initial_state,
    new_run_id,
    paths_for_run,
    read_state,
    run_lock,
    StateError,
    utc_now,
    write_private_config,
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

    def start(
        self,
        subject: str,
        *,
        inputs: dict[str, Any] | None = None,
        private_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = new_run_id()
        paths = paths_for_run(self.runs_dir, run_id)
        paths.run_dir.mkdir(parents=True, exist_ok=False)
        state = initial_state(run_id=run_id, subject=subject, inputs=inputs)
        try:
            with run_lock(paths.run_dir):
                write_state(paths.state_path, state)
                if private_inputs is not None:
                    write_private_config(self.runs_dir, run_id, private_inputs)
                return self._advance(state=state, state_path=paths.state_path, run_dir=paths.run_dir)
        except StateError as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def resume(self, run_id: str) -> dict[str, Any]:
        try:
            paths = paths_for_run(self.runs_dir, run_id)
            with run_lock(paths.run_dir):
                state = read_state(paths.state_path)

                if state["status"] in {RUN_COMPLETED, RUN_BLOCKED, RUN_FAILED, RUN_AWAITING_APPROVAL}:
                    return state

                self._verify_prior_artifacts(state, paths.run_dir)
                self._reset_interrupted_stage(state)
                return self._advance(state=state, state_path=paths.state_path, run_dir=paths.run_dir)
        except StateError as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def _reset_interrupted_stage(self, state: dict[str, Any]) -> None:
        for stage in WORKFLOW_STAGES:
            stage_state = state["stages"][stage.name]
            if stage_state["status"] == STAGE_RUNNING:
                stage_state["status"] = STAGE_PENDING
                stage_state["message"] = "Interrupted attempt will be retried on explicit resume."
                stage_state["finished_at"] = None
                return

    def approve_social(self, run_id: str, notes: str | None = None) -> dict[str, Any]:
        """Record an explicit owner decision, then continue the social-draft stages."""
        try:
            paths = paths_for_run(self.runs_dir, run_id)
            with run_lock(paths.run_dir):
                state = read_state(paths.state_path)
                stage_name = "approve-social"
                stage_state = state["stages"][stage_name]
                if state["status"] != RUN_AWAITING_APPROVAL or stage_state["status"] != STAGE_AWAITING_APPROVAL:
                    raise RuntimeErrorWithContext("This run is not awaiting social-transformation approval.")
                from .approval import render_approved_social_transformations
                from .content_artifacts import ArtifactInputError, collect_reviewed_article_inputs

                try:
                    article = collect_reviewed_article_inputs(paths.run_dir).article
                except ArtifactInputError as exc:
                    raise RuntimeErrorWithContext(
                        f"Social approval cannot use the current artifacts: {exc}"
                    ) from exc

                (paths.run_dir / "approval.md").write_text(
                    render_approved_social_transformations(
                        state["subject"], notes, article.blog_sha256
                    ),
                    encoding="utf-8",
                )
                stage_state["status"] = STAGE_COMPLETED
                stage_state["message"] = "Social transformation approved explicitly by the run owner."
                stage_state["finished_at"] = utc_now()
                state["status"] = RUN_RUNNING
                write_state(paths.state_path, state)
                return self._advance(state=state, state_path=paths.state_path, run_dir=paths.run_dir)
        except StateError as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

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
            stage_state["attempts"] += 1
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

            artifact_error = self._validate_stage_artifact(
                status=result.status,
                artifact=result.artifact,
                stage_name=stage.name,
                expected_artifact=stage.artifact,
                run_dir=run_dir,
            )
            if artifact_error:
                stage_state["status"] = STAGE_FAILED
                stage_state["message"] = artifact_error
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
            if result.status == STAGE_AWAITING_APPROVAL:
                state["status"] = RUN_AWAITING_APPROVAL
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

    @staticmethod
    def _validate_stage_artifact(
        *,
        status: str,
        artifact: str | None,
        stage_name: str,
        expected_artifact: str,
        run_dir: Path,
    ) -> str | None:
        if status == STAGE_FAILED:
            return None
        if artifact != expected_artifact:
            return f"Stage {stage_name!r} did not return its expected artifact."
        artifact_path = (run_dir / expected_artifact).resolve()
        if artifact_path.parent != run_dir.resolve():
            return f"Stage {stage_name!r} produced an unsafe artifact path."
        if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
            return f"Stage {stage_name!r} reported success without a readable artifact."
        return None

    def _verify_prior_artifacts(self, state: dict[str, Any], run_dir: Path) -> None:
        for stage in WORKFLOW_STAGES:
            stage_state = state["stages"][stage.name]
            if stage_state["status"] in {STAGE_COMPLETED, STAGE_SKIPPED, STAGE_BLOCKED}:
                error = self._validate_stage_artifact(
                    status=stage_state["status"],
                    artifact=stage_state["artifact"],
                    stage_name=stage.name,
                    expected_artifact=stage.artifact,
                    run_dir=run_dir,
                )
                if error:
                    raise RuntimeErrorWithContext(f"Cannot resume: {error}")
