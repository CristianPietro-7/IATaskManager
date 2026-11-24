"""API tests for the healthcheck."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from ai_task_manager.api.deps import get_task_repository
from ai_task_manager.config import Settings
from ai_task_manager.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_fails(settings: Settings) -> None:
    app = create_app(settings)

    class BrokenRepository:
        def count(self) -> int:
            raise SQLAlchemyError("boom")

    app.dependency_overrides[get_task_repository] = lambda: BrokenRepository()
    with TestClient(app) as health_client:
        response = health_client.get("/health")
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database unavailable.",
        "code": "service_unavailable",
    }
