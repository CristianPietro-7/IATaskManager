"""Shared fixtures for API tests using the real app with a test session."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_task_manager.config import Settings
from ai_task_manager.db.session import get_session
from ai_task_manager.main import create_app

TEST_SETTINGS = Settings(
    database_url="sqlite:///:memory:",
    environment="testing",
    api_prefix="/api/v1",
    create_tables_on_startup=False,
)


@pytest.fixture
def settings() -> Settings:
    """Settings isolated from the real environment."""
    return TEST_SETTINGS


@pytest.fixture
def app(settings: Settings, session: Session) -> Iterator[FastAPI]:
    """Build the app and inject the per-test in-memory session."""
    application = create_app(settings)
    application.dependency_overrides[get_session] = lambda: session
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """HTTP client bound to the configured test app."""
    with TestClient(app) as test_client:
        yield test_client
