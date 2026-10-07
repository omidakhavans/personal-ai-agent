"""Small application services shared by future CLI and HTTP adapters."""

from __future__ import annotations

from dataclasses import dataclass

from .run_queries import RunDetail, RunListFilters, RunPage, RunQueryService
from .stages import WORKFLOW_STAGES


class RunNotFoundError(LookupError):
    """A requested logical run does not exist in the configured history store."""


@dataclass(frozen=True)
class WorkflowStageMetadata:
    """One current, read-only workflow stage safe for an operator to inspect."""

    name: str
    artifact_name: str
    capability: str


@dataclass(frozen=True)
class WorkflowMetadata:
    """Read-only description of the single workflow the runtime currently owns."""

    workflow_id: str
    display_name: str
    stages: tuple[WorkflowStageMetadata, ...]


class RunHistoryApplicationService:
    """Application read boundary that translates query absence into a domain error."""

    def __init__(self, query_service: RunQueryService) -> None:
        """Depend on the storage-neutral query protocol, never ORM rows."""
        self._query_service = query_service

    def list_runs(
        self, *, filters: RunListFilters | None = None, limit: int = 25, cursor: str | None = None
    ) -> RunPage:
        """Return a history page using the existing keyset query semantics."""
        return self._query_service.list_runs(filters=filters, limit=limit, cursor=cursor)

    def get_run(self, run_id: str) -> RunDetail:
        """Return one run detail or a domain-level absence error."""
        detail = self._query_service.get_run_detail(run_id)
        if detail is None:
            raise RunNotFoundError(f"Run {run_id!r} was not found.")
        return detail


class RuntimeMetadataApplicationService:
    """Expose only existing, fixed runtime concepts without mutable configuration."""

    def workflows(self) -> tuple[WorkflowMetadata, ...]:
        """Describe the current content workflow from its domain stage contract."""
        return (
            WorkflowMetadata(
                workflow_id="content",
                display_name="Content workflow",
                stages=tuple(
                    WorkflowStageMetadata(
                        name=stage.name,
                        artifact_name=stage.artifact,
                        capability=stage.phase1_skill,
                    )
                    for stage in WORKFLOW_STAGES
                ),
            ),
        )
