"""Task DTOs; enums are re-exported from the persistence model."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ai_task_manager.models.task import TaskPriority, TaskStatus
from ai_task_manager.schemas.common import Page


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class TaskCreate(BaseModel):
    """Payload accepted by ``POST /tasks``."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    """Partial payload accepted by ``PATCH /tasks/{task_id}``."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None


class TaskRead(BaseModel):
    """Task representation returned by every successful endpoint."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @field_serializer("due_at", "created_at", "updated_at", "completed_at")
    def serialize_utc_timestamps(self, value: datetime | None) -> str | None:
        """Render naive UTC storage as ISO-8601 with a ``Z`` suffix."""
        return _serialize_utc(value)


class TaskPage(Page[TaskRead]):
    """Pagination envelope returned by ``GET /tasks``."""


__all__ = [
    "TaskCreate",
    "TaskPage",
    "TaskPriority",
    "TaskRead",
    "TaskStatus",
    "TaskUpdate",
]
