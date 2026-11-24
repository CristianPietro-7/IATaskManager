"""ORM model for the tasks table."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_task_manager.db.base import Base, TimestampMixin


class TaskStatus(StrEnum):
    """Allowed values for ``tasks.status``."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    """Allowed values for ``tasks.priority``."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in TaskStatus)
_PRIORITY_VALUES = ", ".join(f"'{priority.value}'" for priority in TaskPriority)


class Task(TimestampMixin, Base):
    """Task entity; payload validation belongs to schemas and services."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.PENDING.value
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default=TaskPriority.MEDIUM.value
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="status"),
        CheckConstraint(f"priority IN ({_PRIORITY_VALUES})", name="priority"),
    )


Index("ix_tasks_status", Task.status)
Index("ix_tasks_created_at_desc", Task.created_at.desc())


__all__ = ["Task", "TaskPriority", "TaskStatus"]
