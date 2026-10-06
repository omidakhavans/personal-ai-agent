"""Storage-neutral read models for future operator and API interfaces.

These DTOs deliberately expose durable business history, not SQLAlchemy rows,
filesystem paths, raw artifacts, technical logs, or provider credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .domain import RunStatus
from .stages import StageStatus


@dataclass(frozen=True)
class RunListFilters:
    """The small, currently justified filter set for a run-history table."""

    status: RunStatus | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@dataclass(frozen=True)
class RunListItem:
    """One safe, compact row for a future run-history screen."""

    run_id: str
    workflow: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    current_step: str | None
    stage_attempt_count: int
    error_summary: str | None
    model: str | None


@dataclass(frozen=True)
class RunStageView:
    """Current durable checkpoint for one workflow stage."""

    name: str
    status: StageStatus
    artifact_name: str
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    message: str


@dataclass(frozen=True)
class RunEventView:
    """One immutable, deterministically ordered execution-history entry."""

    sequence: int
    event_type: str
    occurred_at: datetime
    stage_name: str | None
    schema_version: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunDetail:
    """Read model for one run without exposing ORM entities or private inputs."""

    run_id: str
    workflow: str
    subject: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    current_step: str | None
    input_summary: dict[str, Any]
    stages: tuple[RunStageView, ...]
    events: tuple[RunEventView, ...]


@dataclass(frozen=True)
class RunPage:
    """A keyset-paginated, newest-first run-history response."""

    items: tuple[RunListItem, ...]
    next_cursor: str | None


class RunQueryService(Protocol):
    """Application read boundary consumed later by HTTP and operator adapters."""

    def list_runs(
        self,
        *,
        filters: RunListFilters | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> RunPage:
        """Return a bounded, newest-first page of safe run summaries."""

    def get_run_detail(self, run_id: str) -> RunDetail | None:
        """Return safe durable history for one run, or ``None`` when absent."""
