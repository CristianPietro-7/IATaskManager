"""Persistence operations for tasks; the only module building task queries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ai_task_manager.models.task import Task, TaskPriority, TaskStatus

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
_SORT_EXPRESSIONS: dict[str, ColumnElement[object]] = {
    "created_at:asc": Task.created_at.asc(),
    "created_at:desc": Task.created_at.desc(),
}
_UPDATABLE_FIELDS = frozenset(
    {"title", "description", "status", "priority", "due_at", "completed_at"}
)
_VALID_STATUSES = frozenset(status.value for status in TaskStatus)
_VALID_PRIORITIES = frozenset(priority.value for priority in TaskPriority)


def _validate_choice(name: str, value: str, allowed: frozenset[str]) -> str:
    if value not in allowed:
        raise ValueError(f"Unsupported {name}: {value!r}")
    return value


def _validate_pagination(limit: int, offset: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")


def _apply_filters[QueryT](
    query: QueryT, *, status: str | None, priority: str | None
) -> QueryT:
    if status is not None:
        query = query.where(Task.status == _validate_choice("status", status, _VALID_STATUSES))
    if priority is not None:
        query = query.where(
            Task.priority == _validate_choice("priority", priority, _VALID_PRIORITIES)
        )
    return query


def _validate_update_choice(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {value!r}")
    allowed = _VALID_STATUSES if name == "status" else _VALID_PRIORITIES
    return _validate_choice(name, value, allowed)


class TaskRepository:
    """CRUD, filtering, ordering and pagination for ``Task`` entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        status: str = TaskStatus.PENDING.value,
        priority: str = TaskPriority.MEDIUM.value,
        due_at: datetime | None = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            status=_validate_choice("status", status, _VALID_STATUSES),
            priority=_validate_choice("priority", priority, _VALID_PRIORITIES),
            due_at=due_at,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def get_by_id(self, task_id: int) -> Task | None:
        return self._session.get(Task, task_id)

    def list(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        sort: str = "created_at:desc",
    ) -> list[Task]:
        _validate_pagination(limit, offset)
        expression = _SORT_EXPRESSIONS.get(sort)
        if expression is None:
            raise ValueError(f"Unsupported sort: {sort}")
        query = _apply_filters(select(Task), status=status, priority=priority)
        query = query.order_by(expression, Task.id.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(query).all())

    def count(self, *, status: str | None = None, priority: str | None = None) -> int:
        query = _apply_filters(
            select(func.count()).select_from(Task), status=status, priority=priority
        )
        return int(self._session.scalar(query) or 0)

    def update(self, task: Task, changes: Mapping[str, object]) -> Task:
        unknown = set(changes) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown))}")
        for name, value in changes.items():
            if name in {"status", "priority"}:
                value = _validate_update_choice(name, value)
            setattr(task, name, value)
        self._session.flush()
        return task

    def delete(self, task: Task) -> None:
        self._session.delete(task)
        self._session.flush()
