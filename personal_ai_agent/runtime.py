"""Small, explicit workflow runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import (
    RUN_AWAITING_APPROVAL,
    RUN_BLOCKED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_RUNNING,
    ArtifactReference,
    RunSnapshot,
    new_run_id,
    utc_now,
)
from .persistence import (
    ArtifactStore,
    FileArtifactStore,
    FileRunRepository,
    RunRepository,
    RunWorkspace,
)
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
from .state import StateError


class RuntimeErrorWithContext(RuntimeError):
    """Runtime-level error with a user-facing message."""


class Orchestrator:
    """Own deterministic state transitions for one sequential content workflow."""

    def __init__(
        self,
        *,
        runs_dir: Path,
        executor: StageExecutor | None = None,
        repository: RunRepository | None = None,
        artifacts: ArtifactStore | None = None,
    ) -> None:
        """Set capability and persistence adapters for one workflow application."""
        self.runs_dir = runs_dir
        self.executor = executor or PlaceholderStageExecutor()
        self.repository = repository or FileRunRepository(runs_dir)
        self.artifacts = artifacts or FileArtifactStore()

    def start(
        self,
        subject: str,
        *,
        inputs: dict[str, Any] | None = None,
        private_inputs: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """Create a checkpointed run and advance it until it stops or completes."""
        try:
            snapshot = RunSnapshot.create(
                run_id=new_run_id(),
                subject=subject,
                inputs=inputs,
            )
            workspace = self.repository.create(snapshot)
            with self.repository.lock(workspace):
                self.repository.save(workspace, snapshot)
                if private_inputs is not None:
                    self.repository.save_private_config(workspace, private_inputs)
                return self._advance(snapshot=snapshot, workspace=workspace)
        except (StateError, ValueError) as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def resume(self, run_id: str) -> dict[str, Any]:
        """Continue an unfinished run after validating its prior artifacts."""
        try:
            workspace = self.repository.open(run_id)
            with self.repository.lock(workspace):
                snapshot = self.repository.load(workspace)

                if snapshot.status in {RUN_COMPLETED, RUN_BLOCKED, RUN_FAILED, RUN_AWAITING_APPROVAL}:
                    return snapshot.to_dict()

                self._verify_prior_artifacts(snapshot, workspace)
                self._reset_interrupted_stage(snapshot)
                return self._advance(snapshot=snapshot, workspace=workspace)
        except (StateError, ValueError) as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def validate_run(self, run_id: str) -> dict[str, Any]:
        """Check persisted state and the artifacts it claims are available.

        This is intentionally read-only. It gives an operator or CI job a way
        to detect a moved, deleted, or tampered artifact without resuming a
        model-backed workflow or spending tokens.
        """
        try:
            workspace = self.repository.open(run_id)
            with self.repository.lock(workspace):
                snapshot = self.repository.load(workspace)
                self._verify_prior_artifacts(snapshot, workspace)
                return snapshot.to_dict()
        except (StateError, ValueError) as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def _reset_interrupted_stage(self, snapshot: RunSnapshot) -> None:
        """Make one interrupted running stage eligible for an explicit retry."""
        for stage in WORKFLOW_STAGES:
            stage_state = snapshot.stages[stage.name]
            if stage_state.status == STAGE_RUNNING:
                stage_state.status = STAGE_PENDING
                stage_state.message = "Interrupted attempt will be retried on explicit resume."
                stage_state.finished_at = None
                return

    def approve_social(self, run_id: str, notes: str | None = None) -> dict[str, Any]:
        """Record an explicit owner decision, then continue the social-draft stages."""
        try:
            workspace = self.repository.open(run_id)
            with self.repository.lock(workspace):
                snapshot = self.repository.load(workspace)
                stage_name = "approve-social"
                stage_state = snapshot.stages[stage_name]
                if snapshot.status != RUN_AWAITING_APPROVAL or stage_state.status != STAGE_AWAITING_APPROVAL:
                    raise RuntimeErrorWithContext("This run is not awaiting social-transformation approval.")
                from .approval import render_approved_social_transformations
                from .content_artifacts import (
                    ArtifactInputError,
                    collect_reviewed_article_inputs,
                )

                try:
                    article = collect_reviewed_article_inputs(workspace.run_dir).article
                except ArtifactInputError as exc:
                    raise RuntimeErrorWithContext(
                        f"Social approval cannot use the current artifacts: {exc}"
                    ) from exc

                self.artifacts.write_text(
                    workspace,
                    "approval.md",
                    render_approved_social_transformations(
                        snapshot.subject,
                        notes,
                        article.blog_sha256,
                    ),
                )
                stage_state.status = STAGE_COMPLETED
                stage_state.message = "Social transformation approved explicitly by the run owner."
                stage_state.finished_at = utc_now()
                snapshot.status = RUN_RUNNING
                self.repository.save(workspace, snapshot)
                return self._advance(snapshot=snapshot, workspace=workspace)
        except (StateError, ValueError) as exc:
            raise RuntimeErrorWithContext(str(exc)) from exc

    def _advance(self, *, snapshot: RunSnapshot, workspace: RunWorkspace) -> dict[str, Any]:
        """Advance pending stages in order until a terminal workflow outcome."""
        snapshot.status = RUN_RUNNING
        self.repository.save(workspace, snapshot)

        for stage in WORKFLOW_STAGES:
            stage_state = snapshot.stages[stage.name]
            status = stage_state.status

            if status in {STAGE_COMPLETED, STAGE_SKIPPED}:
                continue
            if status == STAGE_BLOCKED:
                snapshot.status = RUN_BLOCKED
                snapshot.current_stage = stage.name
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()
            if status == STAGE_FAILED:
                snapshot.status = RUN_FAILED
                snapshot.current_stage = stage.name
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()
            if status != STAGE_PENDING:
                raise RuntimeErrorWithContext(
                    f"Cannot resume stage {stage.name!r} from status {status!r}."
                )

            snapshot.current_stage = stage.name
            stage_state.status = STAGE_RUNNING
            stage_state.attempts += 1
            stage_state.started_at = utc_now()
            self.repository.save(workspace, snapshot)

            try:
                result = self.executor.execute(
                    stage=stage,
                    subject=snapshot.subject,
                    run_dir=workspace.run_dir,
                )
            except Exception as exc:  # pragma: no cover - exact exception is stage-specific
                stage_state.status = STAGE_FAILED
                stage_state.message = f"{type(exc).__name__}: {exc}"
                stage_state.finished_at = utc_now()
                snapshot.status = RUN_FAILED
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()

            if result.status not in TERMINAL_STAGE_STATUSES:
                stage_state.status = STAGE_FAILED
                stage_state.message = f"Invalid stage result status: {result.status}"
                stage_state.finished_at = utc_now()
                snapshot.status = RUN_FAILED
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()

            artifact_error = self._validate_stage_artifact(
                status=result.status,
                artifact=result.artifact,
                stage_name=stage.name,
                expected_artifact=stage.artifact,
                workspace=workspace,
            )
            if artifact_error:
                stage_state.status = STAGE_FAILED
                stage_state.message = artifact_error
                stage_state.finished_at = utc_now()
                snapshot.status = RUN_FAILED
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()

            stage_state.status = result.status
            stage_state.message = result.message
            stage_state.finished_at = utc_now()
            if result.artifact:
                stage_state.artifact = ArtifactReference(result.artifact)
            self.repository.save(workspace, snapshot)

            if result.status == STAGE_BLOCKED:
                snapshot.status = RUN_BLOCKED
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()
            if result.status == STAGE_AWAITING_APPROVAL:
                snapshot.status = RUN_AWAITING_APPROVAL
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()
            if result.status == STAGE_FAILED:
                snapshot.status = RUN_FAILED
                self.repository.save(workspace, snapshot)
                return snapshot.to_dict()

        snapshot.status = RUN_COMPLETED
        snapshot.current_stage = None
        self.repository.save(workspace, snapshot)
        return snapshot.to_dict()

    def _validate_stage_artifact(
        self,
        *,
        status: str,
        artifact: str | None,
        stage_name: str,
        expected_artifact: str,
        workspace: RunWorkspace,
    ) -> str | None:
        """Return an error when a reported artifact violates the stage contract."""
        if status == STAGE_FAILED:
            return None
        if artifact != expected_artifact:
            return f"Stage {stage_name!r} did not return its expected artifact."
        try:
            error = self.artifacts.validation_error(workspace, expected_artifact)
        except ValueError:
            return f"Stage {stage_name!r} produced an unsafe artifact path."
        if error:
            return f"Stage {stage_name!r} {error}"
        return None

    def _verify_prior_artifacts(self, snapshot: RunSnapshot, workspace: RunWorkspace) -> None:
        """Ensure saved terminal stages still have the artifacts later stages trust."""
        for stage in WORKFLOW_STAGES:
            stage_state = snapshot.stages[stage.name]
            if stage_state.status in {
                STAGE_COMPLETED,
                STAGE_SKIPPED,
                STAGE_BLOCKED,
                STAGE_AWAITING_APPROVAL,
            }:
                error = self._validate_stage_artifact(
                    status=stage_state.status,
                    artifact=stage_state.artifact.name,
                    stage_name=stage.name,
                    expected_artifact=stage.artifact,
                    workspace=workspace,
                )
                if error:
                    raise RuntimeErrorWithContext(f"Cannot resume: {error}")
