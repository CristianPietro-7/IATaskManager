"""Unit tests for TaskService with an in-memory fake repository."""

from datetime import datetime, timedelta, timezone

import pytest

from ai_task_manager.exceptions import DomainValidationError, NotFoundError
from ai_task_manager.models.task import Task, TaskStatus
from ai_task_manager.repositories.task_repository import DEFAULT_LIMIT
from ai_task_manager.services.task_service import TaskService


class _FakeTaskRepository:
    """Minimal in-memory stand-in implementing the repository interface."""

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self.list_calls: list[dict[str, object]] = []
        self.count_calls: list[dict[str, str | None]] = []
        self.list_error: Exception | None = None

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        status: str = TaskStatus.PENDING.value,
        priority: str = "medium",
        due_at: datetime | None = None,
    ) -> Task:
        task = Task(
            id=self._next_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_at=due_at,
        )
        self._tasks[task.id] = task
        self._next_id += 1
        return task

    def get_by_id(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def _filtered(self, status: str | None, priority: str | None) -> list[Task]:
        return [
            task
            for task in self._tasks.values()
            if (status is None or task.status == status)
            and (priority is None or task.priority == priority)
        ]

    def list(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        sort: str = "created_at:desc",
    ) -> list[Task]:
        self.list_calls.append(
            {
                "status": status,
                "priority": priority,
                "limit": limit,
                "offset": offset,
                "sort": sort,
            }
        )
        if self.list_error is not None:
            raise self.list_error
        return self._filtered(status, priority)[offset : offset + limit]

    def count(self, *, status: str | None = None, priority: str | None = None) -> int:
        self.count_calls.append({"status": status, "priority": priority})
        return len(self._filtered(status, priority))

    def update(self, task: Task, changes: dict[str, object]) -> Task:
        for name, value in changes.items():
            setattr(task, name, value)
        return task

    def delete(self, task: Task) -> None:
        self._tasks.pop(task.id, None)


def test_create_normalizes_title_and_applies_defaults() -> None:
    repository = _FakeTaskRepository()

    task = TaskService(repository).create(title="  Buy milk  ")

    assert task.id == 1
    assert task.title == "Buy milk"
    assert task.status == TaskStatus.PENDING.value
    assert task.priority == "medium"
    assert task.due_at is None
    assert task.completed_at is None


@pytest.mark.parametrize("title", ["", "   ", "x" * 201, 123])
def test_create_rejects_invalid_title(title: str | int) -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(DomainValidationError, match="title"):
        service.create(title=title)


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("priority", "urgent")],
)
def test_create_rejects_invalid_choices(field: str, value: str) -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(DomainValidationError, match=f"Invalid {field}"):
        service.create(title="task", **{field: value})


def test_create_rejects_invalid_description_and_due_at() -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(DomainValidationError, match="description"):
        service.create(title="task", description=123)
    with pytest.raises(DomainValidationError, match="due_at"):
        service.create(title="task", due_at="2026-01-01")


def test_create_converts_aware_due_at_to_naive_utc() -> None:
    service = TaskService(_FakeTaskRepository())
    aware = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2)))

    task = service.create(title="task", due_at=aware)

    assert task.due_at == datetime(2026, 1, 1, 10)
    assert task.due_at is not None and task.due_at.tzinfo is None


def test_create_completed_sets_completed_at_from_clock() -> None:
    fixed = datetime(2026, 1, 1, 12)
    service = TaskService(_FakeTaskRepository(), clock=lambda: fixed)

    task = service.create(title="task", status=TaskStatus.COMPLETED.value)

    assert task.completed_at == fixed


def test_get_returns_existing_task() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    service = TaskService(repository)

    assert service.get(task.id) is task


def test_get_raises_not_found_for_missing_task() -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(NotFoundError, match="Task 999 not found"):
        service.get(999)


def test_list_returns_items_and_total_with_filters() -> None:
    repository = _FakeTaskRepository()
    repository.create(title="a", status="pending")
    repository.create(title="b", status="completed")
    service = TaskService(repository)

    items, total = service.list(status="pending", limit=1, offset=0)

    assert [task.title for task in items] == ["a"]
    assert total == 1
    assert repository.list_calls[0]["status"] == "pending"
    assert repository.count_calls[0] == {"status": "pending", "priority": None}


def test_list_rejects_invalid_status() -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(DomainValidationError, match="Invalid status"):
        service.list(status="unknown")


def test_list_wraps_repository_value_error() -> None:
    repository = _FakeTaskRepository()
    repository.list_error = ValueError("limit must be an integer between 1 and 100")
    service = TaskService(repository)

    with pytest.raises(DomainValidationError, match="limit must be") as error:
        service.list()

    assert error.value.code == "invalid_query"


def test_update_normalizes_title_and_keeps_untouched_fields() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="old", description="keep")
    service = TaskService(repository)

    updated = service.update(task.id, {"title": "  new  "})

    assert updated.title == "new"
    assert updated.description == "keep"


def test_update_marks_completed_at_when_completing() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    fixed = datetime(2026, 2, 1)
    service = TaskService(repository, clock=lambda: fixed)

    updated = service.update(task.id, {"status": TaskStatus.COMPLETED.value})

    assert updated.completed_at == fixed


def test_update_clears_completed_at_when_reverting() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task", status=TaskStatus.COMPLETED.value)
    original = datetime(2026, 1, 1)
    task.completed_at = original
    service = TaskService(repository, clock=lambda: datetime(2026, 3, 1))

    updated = service.update(task.id, {"status": TaskStatus.IN_PROGRESS.value})

    assert updated.completed_at is None


def test_update_keeps_completed_at_when_status_is_unchanged() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task", status=TaskStatus.COMPLETED.value)
    original = datetime(2026, 1, 1)
    task.completed_at = original
    service = TaskService(repository, clock=lambda: datetime(2026, 3, 1))

    updated = service.update(task.id, {"status": TaskStatus.COMPLETED.value})

    assert updated.completed_at == original


@pytest.mark.parametrize(
    "changes",
    [
        {"completed_at": datetime(2026, 1, 1)},
        {"unknown": 1},
    ],
)
def test_update_rejects_unsupported_fields(changes: dict[str, object]) -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    service = TaskService(repository)

    with pytest.raises(DomainValidationError, match="Unsupported update fields"):
        service.update(task.id, changes)


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("priority", "urgent")],
)
def test_update_rejects_invalid_choices(field: str, value: str) -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    service = TaskService(repository)

    with pytest.raises(DomainValidationError, match=f"Invalid {field}"):
        service.update(task.id, {field: value})


def test_update_rejects_blank_title() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    service = TaskService(repository)

    with pytest.raises(DomainValidationError, match="title must not be empty"):
        service.update(task.id, {"title": "   "})


def test_update_raises_not_found_for_missing_task() -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(NotFoundError, match="Task 999 not found"):
        service.update(999, {"title": "new"})


def test_delete_removes_existing_task() -> None:
    repository = _FakeTaskRepository()
    task = repository.create(title="task")
    service = TaskService(repository)

    service.delete(task.id)

    assert repository.get_by_id(task.id) is None


def test_delete_raises_not_found_for_missing_task() -> None:
    service = TaskService(_FakeTaskRepository())

    with pytest.raises(NotFoundError, match="Task 999 not found"):
        service.delete(999)
