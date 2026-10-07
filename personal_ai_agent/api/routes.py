"""Versioned, read-only HTTP routes that delegate to application services."""
# ruff: noqa: B008 -- FastAPI declares dependencies and request metadata in signatures.

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..application import (
    RunHistoryApplicationService,
    RuntimeMetadataApplicationService,
)
from ..domain import RunStatus
from ..run_queries import RunListFilters
from .dependencies import ApiServices, get_services
from .errors import ApiDependencyUnavailableError
from .schemas import (
    HealthResponse,
    RunDetailResponse,
    RunEventResponse,
    RunListItemResponse,
    RunListResponse,
    RunStageResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStageResponse,
)

router = APIRouter(prefix="/api/v1", tags=["runtime"])


@router.get("/health", response_model=HealthResponse, summary="Process liveness")
def health() -> HealthResponse:
    """Report whether the API process can answer requests without checking dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, summary="Dependency readiness")
def ready(services: ApiServices = Depends(get_services)) -> HealthResponse:
    """Report whether the required run-history dependency can serve normal reads."""
    if not services.readiness():
        raise ApiDependencyUnavailableError("Run history is not ready.")
    return HealthResponse(status="ok")


@router.get("/runs", response_model=RunListResponse, summary="List durable run history")
def list_runs(
    status: RunStatus | None = Query(default=None, description="Existing run status filter."),
    created_after: datetime | None = Query(default=None, description="Inclusive UTC creation lower bound."),
    created_before: datetime | None = Query(default=None, description="Inclusive UTC creation upper bound."),
    cursor: str | None = Query(default=None, description="Opaque newest-first keyset cursor."),
    limit: int = Query(default=25, ge=1, le=100, description="Maximum history rows to return."),
    services: ApiServices = Depends(get_services),
) -> RunListResponse:
    """Translate HTTP query values into the existing application keyset query."""
    page = _history(services).list_runs(
        filters=RunListFilters(status=status, created_after=created_after, created_before=created_before),
        limit=limit,
        cursor=cursor,
    )
    return RunListResponse(
        items=[
            RunListItemResponse(
                run_id=item.run_id,
                workflow=item.workflow,
                status=item.status,
                created_at=item.created_at,
                started_at=item.started_at,
                finished_at=item.finished_at,
                duration_seconds=item.duration_seconds,
                current_step=item.current_step,
                stage_attempt_count=item.stage_attempt_count,
                error_summary=item.error_summary,
                model=item.model,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse, summary="Read one run timeline")
def get_run(run_id: str, services: ApiServices = Depends(get_services)) -> RunDetailResponse:
    """Return an application detail view without filesystem or ORM exposure."""
    detail = _history(services).get_run(run_id)
    return RunDetailResponse(
        run_id=detail.run_id,
        workflow=detail.workflow,
        subject=detail.subject,
        status=detail.status,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        current_step=detail.current_step,
        input_summary=detail.input_summary,
        stages=[
            RunStageResponse(
                name=stage.name,
                status=stage.status,
                artifact_name=stage.artifact_name,
                attempts=stage.attempts,
                started_at=stage.started_at,
                finished_at=stage.finished_at,
                message=stage.message,
            )
            for stage in detail.stages
        ],
        events=[
            RunEventResponse(
                sequence=event.sequence,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                stage_name=event.stage_name,
                schema_version=event.schema_version,
                payload=event.payload,
            )
            for event in detail.events
        ],
    )


@router.get("/workflows", response_model=WorkflowListResponse, summary="List fixed workflow metadata")
def workflows(services: ApiServices = Depends(get_services)) -> WorkflowListResponse:
    """Return only the workflow metadata the current runtime actually defines."""
    metadata = _metadata(services).workflows()
    return WorkflowListResponse(
        items=[
            WorkflowResponse(
                workflow_id=workflow.workflow_id,
                display_name=workflow.display_name,
                stages=[
                    WorkflowStageResponse(
                        name=stage.name,
                        artifact_name=stage.artifact_name,
                        capability=stage.capability,
                    )
                    for stage in workflow.stages
                ],
            )
            for workflow in metadata
        ]
    )


def _history(services: ApiServices) -> RunHistoryApplicationService:
    """Keep routes visibly dependent on an application service, not persistence."""
    return services.run_history


def _metadata(services: ApiServices) -> RuntimeMetadataApplicationService:
    """Keep fixed runtime metadata behind the same application boundary."""
    return services.runtime_metadata
