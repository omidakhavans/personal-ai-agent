"""Framework-independent records for the content workflow lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, TypeAlias, cast
from uuid import uuid4

from .stages import STAGE_PENDING, WORKFLOW_STAGES, StageStatus

RunStatus: TypeAlias = Literal[
    "pending", "running", "completed", "blocked", "failed", "awaiting_approval"
]

RUN_PENDING: RunStatus = "pending"
RUN_RUNNING: RunStatus = "running"
RUN_COMPLETED: RunStatus = "completed"
RUN_BLOCKED: RunStatus = "blocked"
RUN_FAILED: RunStatus = "failed"
RUN_AWAITING_APPROVAL: RunStatus = "awaiting_approval"
RUN_STATE_VERSION = 3
RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RUN_PENDING,
        RUN_RUNNING,
        RUN_COMPLETED,
        RUN_BLOCKED,
        RUN_FAILED,
        RUN_AWAITING_APPROVAL,
    }
)


def utc_now() -> str:
    """Return the current UTC timestamp for workflow records."""
    return datetime.now(UTC).isoformat()


def new_run_id() -> str:
    """Create a sortable identifier independent of a storage implementation."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid4().hex[:8]}"


@dataclass(frozen=True)
class ArtifactReference:
    """The expected named artifact that a stage makes available to later work."""

    name: str


@dataclass
class StageSnapshot:
    """Mutable checkpoint data for one workflow stage."""

    status: StageStatus
    artifact: ArtifactReference
    message: str
    attempts: int
    started_at: str | None
    finished_at: str | None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StageSnapshot:
        """Adapt validated legacy state data into a typed stage snapshot."""
        return cls(
            status=cast(StageStatus, value["status"]),
            artifact=ArtifactReference(name=cast(str, value["artifact"])),
            message=cast(str, value["message"]),
            attempts=cast(int, value["attempts"]),
            started_at=cast(str | None, value["started_at"]),
            finished_at=cast(str | None, value["finished_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the stable JSON shape used by the current file adapter."""
        return {
            "status": self.status,
            "artifact": self.artifact.name,
            "message": self.message,
            "attempts": self.attempts,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class RunSnapshot:
    """Typed workflow checkpoint independent of JSON files or database rows."""

    state_version: int
    run_id: str
    subject: str
    inputs: dict[str, Any]
    status: RunStatus
    current_stage: str | None
    created_at: str
    updated_at: str
    stages: dict[str, StageSnapshot]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        subject: str,
        inputs: dict[str, Any] | None = None,
    ) -> RunSnapshot:
        """Create the initial in-memory snapshot for a new workflow run."""
        if not subject.strip():
            raise ValueError("Run subject must not be empty.")
        timestamp = utc_now()
        return cls(
            state_version=RUN_STATE_VERSION,
            run_id=run_id,
            subject=subject,
            inputs=inputs or {},
            status=RUN_PENDING,
            current_stage=WORKFLOW_STAGES[0].name,
            created_at=timestamp,
            updated_at=timestamp,
            stages={
                stage.name: StageSnapshot(
                    status=STAGE_PENDING,
                    artifact=ArtifactReference(stage.artifact),
                    message="",
                    attempts=0,
                    started_at=None,
                    finished_at=None,
                )
                for stage in WORKFLOW_STAGES
            },
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RunSnapshot:
        """Adapt validated JSON state into the domain checkpoint record."""
        stages = cast(dict[str, dict[str, Any]], value["stages"])
        return cls(
            state_version=cast(int, value["state_version"]),
            run_id=cast(str, value["run_id"]),
            subject=cast(str, value["subject"]),
            inputs=cast(dict[str, Any], value["inputs"]),
            status=cast(RunStatus, value["status"]),
            current_stage=cast(str | None, value["current_stage"]),
            created_at=cast(str, value["created_at"]),
            updated_at=cast(str, value["updated_at"]),
            stages={name: StageSnapshot.from_dict(stage) for name, stage in stages.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the current shareable checkpoint contract without storage logic."""
        return {
            "state_version": self.state_version,
            "run_id": self.run_id,
            "subject": self.subject,
            "inputs": self.inputs,
            "status": self.status,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stages": {name: stage.to_dict() for name, stage in self.stages.items()},
        }


@dataclass(frozen=True)
class RunEvent:
    """Future append-only lifecycle event contract, not persisted in Phase 3.2."""

    kind: str
    occurred_at: str
    message: str
    stage_name: str | None = None
