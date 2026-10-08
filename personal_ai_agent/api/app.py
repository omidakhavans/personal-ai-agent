"""FastAPI application factory for the versioned, read-only runtime API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import ApiServices, ApiSettings, build_services
from .errors import install_error_handlers
from .routes import router


def create_app(
    *, settings: ApiSettings | None = None, services: ApiServices | None = None
) -> FastAPI:
    """Compose FastAPI around application services without route-level wiring."""
    resolved_settings = settings or ApiSettings.from_environment()
    app = FastAPI(
        title="Personal AI Agent API",
        version="0.1.0",
        description="Read-only runtime history API for the future operator control plane.",
    )
    app.state.services = services or build_services(resolved_settings)
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "PUT"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
