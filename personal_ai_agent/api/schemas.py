"""Pydantic transport schemas kept separate from application read models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Shared API serialization policy for explicit, stable response shapes."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    """Liveness or readiness status without exposing implementation details."""

    status: Literal["ok", "not_ready"]


class RunListItemResponse(ApiModel):
    """HTTP form of the safe, compact application run-list item."""

    run_id: str
    workflow: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    current_step: str | None
    stage_attempt_count: int
    error_summary: str | None
    model: str | None


class RunListResponse(ApiModel):
    """Keyset-paginated run history response."""

    items: list[RunListItemResponse]
    next_cursor: str | None


class RunStageResponse(ApiModel):
    """Safe view of one stage's current checkpoint."""

    name: str
    status: str
    artifact_name: str
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    message: str


class RunEventResponse(ApiModel):
    """One immutable timeline entry without technical log detail."""

    sequence: int
    event_type: str
    occurred_at: datetime
    stage_name: str | None
    schema_version: int
    payload: dict[str, Any]


class RunDetailResponse(ApiModel):
    """HTTP view of safe run metadata, checkpoints, and ordered events."""

    run_id: str
    workflow: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    current_step: str | None
    input_summary: dict[str, Any]
    stages: list[RunStageResponse]
    events: list[RunEventResponse]


class WorkflowStageResponse(ApiModel):
    """Read-only description of one currently fixed workflow stage."""

    name: str
    artifact_name: str
    capability: str


class WorkflowResponse(ApiModel):
    """Read-only workflow metadata for the first control-plane navigation."""

    workflow_id: str
    display_name: str
    stages: list[WorkflowStageResponse]


class WorkflowListResponse(ApiModel):
    """Response wrapper for the current fixed workflow set."""

    items: list[WorkflowResponse]


class ErrorResponse(ApiModel):
    """Stable generic error envelope that never contains exception internals."""

    code: str
    message: str
