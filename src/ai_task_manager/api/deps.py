"""Dependency composition: session -> repository -> service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from ai_task_manager.db.session import get_session
from ai_task_manager.repositories.task_repository import TaskRepository
from ai_task_manager.services.task_service import TaskService


def get_task_repository(
    session: Annotated[Session, Depends(get_session)],
) -> TaskRepository:
    """Build a repository bound to the request session."""
    return TaskRepository(session)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    """Build the task service used by the endpoints."""
    return TaskService(repository)


TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


__all__ = [
    "TaskRepositoryDep",
    "TaskServiceDep",
    "get_task_repository",
    "get_task_service",
]
