"""Application factory, lifespan, routers and healthcheck."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ai_task_manager import __version__
from ai_task_manager.api.deps import TaskRepositoryDep
from ai_task_manager.api.v1.router import router as v1_router
from ai_task_manager.config import Settings, get_settings
from ai_task_manager.db.base import Base
from ai_task_manager.db.session import engine
from ai_task_manager.exceptions import register_exception_handlers
from ai_task_manager.models.task import Task  # noqa: F401  # registers the table in metadata
from ai_task_manager.schemas.common import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured application instance."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if settings.create_tables_on_startup:
            Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="AI Task Manager API",
        version=__version__,
        description="REST API para administrar tareas (MVP sin autenticación).",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(v1_router, prefix=settings.api_prefix)

    @app.get(
        "/health",
        response_model=None,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
        tags=["Health"],
    )
    def health(repository: TaskRepositoryDep) -> dict[str, str] | JSONResponse:
        """Report readiness by issuing a real database query."""
        try:
            repository.count()
        except SQLAlchemyError:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Database unavailable.", "code": "service_unavailable"},
            )
        return {"status": "ok"}

    return app


app = create_app()


__all__ = ["app", "create_app"]
