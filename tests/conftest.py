"""Shared fixtures for repository integration tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ai_task_manager.db.base import Base
from ai_task_manager.db.session import create_engine_from_url
from ai_task_manager.models.task import Task  # noqa: F401  # registers the table in metadata
from ai_task_manager.repositories.task_repository import TaskRepository


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine_from_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db_session:
        yield db_session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def repository(session: Session) -> TaskRepository:
    return TaskRepository(session)
