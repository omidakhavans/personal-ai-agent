"""Explicit composition and FastAPI dependencies for the HTTP adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import environ
from pathlib import Path
from secrets import compare_digest
from typing import cast

from fastapi import Request
from sqlalchemy import text

from ..application import (
    RunHistoryApplicationService,
    RuntimeMetadataApplicationService,
)
from ..configuration import ConfigurationApplicationService
from ..postgres import (
    SqlAlchemyConfigurationRepository,
    SqlAlchemyRunQueryService,
    SqlAlchemyRunRepository,
)
from ..run_queries import RunDetail, RunListFilters, RunPage, RunQueryService
from .errors import ApiDependencyUnavailableError


@dataclass(frozen=True)
class ApiSettings:
    """Non-secret API process settings read at composition time only."""

    database_url: str | None
    artifact_root: Path
    cors_origins: tuple[str, ...]
    admin_token: str | None = None

    @classmethod
    def from_environment(cls) -> ApiSettings:
        """Read optional local API settings without reflecting secret values."""
        origins = tuple(
            value.strip()
            for value in environ.get("PERSONAL_AI_AGENT_CORS_ORIGINS", "http://localhost:5173").split(",")
            if value.strip()
        )
        if "*" in origins:
            raise ValueError("PERSONAL_AI_AGENT_CORS_ORIGINS must not use a wildcard origin.")
        return cls(
            database_url=environ.get("PERSONAL_AI_AGENT_DATABASE_URL"),
            artifact_root=Path(environ.get("PERSONAL_AI_AGENT_ARTIFACT_ROOT", "runs")),
            cors_origins=origins,
            admin_token=environ.get("PERSONAL_AI_AGENT_ADMIN_TOKEN"),
        )


class UnavailableRunQueryService(RunQueryService):
    """Keep liveness available when durable query infrastructure is not configured."""

    def list_runs(
        self, *, filters: RunListFilters | None = None, limit: int = 25, cursor: str | None = None
    ) -> RunPage:
        """Report a safe service-unavailable state without fabricating run data."""
        raise ApiDependencyUnavailableError("Run history is not configured.")

    def get_run_detail(self, run_id: str) -> RunDetail | None:
        """Report a safe service-unavailable state without inspecting local files."""
        raise ApiDependencyUnavailableError("Run history is not configured.")


@dataclass(frozen=True)
class ApiServices:
    """Small explicit service container; routes receive these, not ORM sessions."""

    run_history: RunHistoryApplicationService
    runtime_metadata: RuntimeMetadataApplicationService
    readiness: Callable[[], bool]
    configuration: ConfigurationApplicationService | None = None


def build_services(settings: ApiSettings) -> ApiServices:
    """Compose infrastructure adapters once at process startup."""
    metadata = RuntimeMetadataApplicationService()
    if not settings.database_url:
        return ApiServices(
            run_history=RunHistoryApplicationService(UnavailableRunQueryService()),
            runtime_metadata=metadata,
            configuration=None,
            readiness=lambda: False,
        )
    repository = SqlAlchemyRunRepository(
        database_url=settings.database_url,
        artifact_root=settings.artifact_root,
    )
    return ApiServices(
        run_history=RunHistoryApplicationService(SqlAlchemyRunQueryService(repository)),
        runtime_metadata=metadata,
        configuration=ConfigurationApplicationService(SqlAlchemyConfigurationRepository(repository)),
        readiness=lambda: _database_ready(repository),
    )


def get_services(request: Request) -> ApiServices:
    """Retrieve application services placed on the app during composition."""
    return cast(ApiServices, request.app.state.services)


def require_configuration_write(request: Request) -> str:
    """Authorize local configuration writes without accepting provider secrets."""
    settings = cast(ApiSettings, request.app.state.settings)
    token = request.headers.get("X-Admin-Token")
    if not settings.admin_token:
        raise ApiDependencyUnavailableError("Configuration writes are disabled.")
    if not token or not compare_digest(token, settings.admin_token):
        from .errors import ApiAuthorizationError

        raise ApiAuthorizationError("A valid local admin token is required.")
    return "local-admin"


def _database_ready(repository: SqlAlchemyRunRepository) -> bool:
    """Use a short read-only connection check for readiness, not liveness."""
    try:
        with repository.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM runs LIMIT 1"))
    except Exception:
        return False
    return True
