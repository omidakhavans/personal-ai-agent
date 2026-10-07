"""Central transport mapping for expected application and infrastructure errors."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..application import RunNotFoundError
from ..run_queries import InvalidRunCursorError

logger = logging.getLogger(__name__)


class ApiDependencyUnavailableError(RuntimeError):
    """A required API dependency has not been configured or is unreachable."""


def install_error_handlers(app: FastAPI) -> None:
    """Translate application failures once instead of scattering HTTP exceptions."""

    @app.exception_handler(RunNotFoundError)
    async def run_not_found(_: Request, __: RunNotFoundError) -> JSONResponse:
        return _error_response(404, "run_not_found", "The requested run was not found.")

    @app.exception_handler(InvalidRunCursorError)
    async def invalid_cursor(_: Request, __: InvalidRunCursorError) -> JSONResponse:
        return _error_response(400, "invalid_cursor", "The run-history cursor is invalid.")

    @app.exception_handler(ApiDependencyUnavailableError)
    async def dependency_unavailable(_: Request, __: ApiDependencyUnavailableError) -> JSONResponse:
        return _error_response(503, "dependency_unavailable", "The requested service is unavailable.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error for %s", request.url.path)
        return _error_response(500, "internal_error", "An unexpected server error occurred.")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Return a deliberately small public error payload."""
    return JSONResponse(status_code=status_code, content={"code": code, "message": message})
