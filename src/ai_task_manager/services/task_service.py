"""Business rules and coordination for tasks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from ai_task_manager import utc_now
from ai_task_manager.exceptions import DomainValidationError, NotFoundError
from ai_task_manager.models.task import Task, TaskPriority, TaskStatus
from ai_task_manager.repositories.task_repository import (
    DEFAULT_LIMIT,
    TaskRepository,
)

_STATUSES = frozenset(status.value for status in TaskStatus)
_PRIORITIES = frozenset(priority.value for priority in TaskPriority)
_UPDATABLE_FIELDS = frozenset({"title", "description", "status", "priority", "due_at"})
_COMPLETED = TaskStatus.COMPLETED.value
_MAX_TITLE_LENGTH = 200


def _normalize_title(value: object) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(
            "title must be a string", fields={"title": "must be a string"}
        )
    title = value.strip()
    if not title:
        raise DomainValidationError(
            "title must not be empty", fields={"title": "must not be empty"}
        )
    if len(title) > _MAX_TITLE_LENGTH:
        raise DomainValidationError(
            "title is too long",
            fields={"title": f"must be at most {_MAX_TITLE_LENGTH} characters"},
        )
    return title


def _normalize_description(value: object) -> str | None:
    if value is not None and not isinstance(value, str):
        raise DomainValidationError(
            "description must be a string or null",
            fields={"description": "must be a string or null"},
        )
    return value


def _validate_choice(name: str, value: object, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise DomainValidationError(
            f"Invalid {name}: {value!r}",
            fields={name: f"must be one of {', '.join(sorted(allowed))}"},
        )
    return value


def _normalize_due_at(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise DomainValidationError(
            "due_at must be a datetime or null",
            fields={"due_at": "must be a datetime or null"},
        )
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class TaskService:
    """Apply task business rules and delegate persistence to a repository."""

    def __init__(
        self,
        repository: TaskRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        status: str = TaskStatus.PENDING.value,
        priority: str = TaskPriority.MEDIUM.value,
        due_at: datetime | None = None,
    ) -> Task:
        clean_status = _validate_choice("status", status, _STATUSES)
        clean_priority = _validate_choice("priority", priority, _PRIORITIES)
        task = self._repository.create(
            title=_normalize_title(title),
            description=_normalize_description(description),
            status=clean_status,
            priority=clean_priority,
            due_at=_normalize_due_at(due_at),
        )
        if clean_status == _COMPLETED:
            task.completed_at = self._clock()
        return task

    def get(self, task_id: int) -> Task:
        task = self._repository.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task

    def list(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        sort: str = "created_at:desc",
    ) -> tuple[list[Task], int]:
        clean_status = (
            _validate_choice("status", status, _STATUSES) if status is not None else None
        )
        clean_priority = (
            _validate_choice("priority", priority, _PRIORITIES)
            if priority is not None
            else None
        )
        try:
            items = self._repository.list(
                status=clean_status,
                priority=clean_priority,
                limit=limit,
                offset=offset,
                sort=sort,
            )
            total = self._repository.count(status=clean_status, priority=clean_priority)
        except ValueError as exc:
            raise DomainValidationError(str(exc), code="invalid_query") from exc
        return items, total

    def update(self, task_id: int, changes: Mapping[str, object]) -> Task:
        task = self.get(task_id)
        unknown = set(changes) - _UPDATABLE_FIELDS
        if unknown:
            raise DomainValidationError(
                "Unsupported update fields",
                fields={name: "field is not updatable" for name in sorted(unknown)},
            )

        clean: dict[str, object] = {}
        if "title" in changes:
            clean["title"] = _normalize_title(changes["title"])
        if "description" in changes:
            clean["description"] = _normalize_description(changes["description"])
        if "status" in changes:
            clean["status"] = _validate_choice("status", changes["status"], _STATUSES)
        if "priority" in changes:
            clean["priority"] = _validate_choice("priority", changes["priority"], _PRIORITIES)
        if "due_at" in changes:
            clean["due_at"] = _normalize_due_at(changes["due_at"])

        self._apply_completion(task, clean)
        return self._repository.update(task, clean)

    def delete(self, task_id: int) -> None:
        self._repository.delete(self.get(task_id))

    def _apply_completion(self, task: Task, changes: dict[str, object]) -> None:
        if "status" not in changes:
            return
        new_status = changes["status"]
        if new_status == _COMPLETED and task.status != _COMPLETED:
            changes["completed_at"] = self._clock()
        elif task.status == _COMPLETED and new_status != _COMPLETED:
            changes["completed_at"] = None
