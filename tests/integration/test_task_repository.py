"""Integration tests for TaskRepository against in-memory SQLite."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_task_manager.models.task import Task, TaskPriority, TaskStatus
from ai_task_manager.repositories.task_repository import MAX_LIMIT, TaskRepository


def _seed(repository: TaskRepository) -> None:
    repository.create(
        title="A", status=TaskStatus.PENDING.value, priority=TaskPriority.LOW.value
    )
    repository.create(
        title="B", status=TaskStatus.COMPLETED.value, priority=TaskPriority.HIGH.value
    )
    repository.create(
        title="C", status=TaskStatus.COMPLETED.value, priority=TaskPriority.MEDIUM.value
    )


def test_create_persists_task_with_defaults(
    repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="  Write docs  ")
    session.commit()

    assert task.id is not None
    assert task.title == "  Write docs  "
    assert task.status == TaskStatus.PENDING.value
    assert task.priority == TaskPriority.MEDIUM.value
    assert task.created_at is not None
    assert task.updated_at is not None
    assert task.description is None
    assert task.due_at is None
    assert task.completed_at is None


def test_create_persists_explicit_optional_fields(
    repository: TaskRepository, session: Session
) -> None:
    due_at = datetime(2026, 12, 31, 23, 59)
    task = repository.create(
        title="Pay invoices",
        description="Before year end",
        status=TaskStatus.IN_PROGRESS.value,
        priority=TaskPriority.HIGH.value,
        due_at=due_at,
    )
    session.commit()

    loaded = repository.get_by_id(task.id)
    assert loaded is not None
    assert loaded.description == "Before year end"
    assert loaded.status == "in_progress"
    assert loaded.priority == "high"
    assert loaded.due_at == due_at


def test_get_by_id_returns_none_for_missing_task(repository: TaskRepository) -> None:
    assert repository.get_by_id(999) is None


def test_list_filters_by_status_and_priority(
    repository: TaskRepository, session: Session
) -> None:
    _seed(repository)
    session.commit()

    items = repository.list(
        status=TaskStatus.COMPLETED.value, priority=TaskPriority.HIGH.value
    )

    assert [task.title for task in items] == ["B"]
    assert (
        repository.count(
            status=TaskStatus.COMPLETED.value, priority=TaskPriority.HIGH.value
        )
        == 1
    )
    assert repository.count() == 3


def test_list_orders_by_created_at_in_both_directions(
    repository: TaskRepository, session: Session
) -> None:
    first = repository.create(title="old")
    first.created_at = datetime(2026, 1, 1)
    second = repository.create(title="new")
    second.created_at = datetime(2026, 2, 1)
    session.commit()

    assert [task.title for task in repository.list()] == ["new", "old"]
    assert [task.title for task in repository.list(sort="created_at:asc")] == [
        "old",
        "new",
    ]


def test_list_uses_id_as_deterministic_tiebreaker(
    repository: TaskRepository, session: Session
) -> None:
    for title in ("first", "second", "third"):
        task = repository.create(title=title)
        task.created_at = datetime(2026, 5, 1)
    session.commit()

    assert [task.title for task in repository.list()] == ["third", "second", "first"]
    assert [task.title for task in repository.list(sort="created_at:asc")] == [
        "third",
        "second",
        "first",
    ]


def test_list_applies_limit_and_offset(
    repository: TaskRepository, session: Session
) -> None:
    for index in range(5):
        task = repository.create(title=f"task-{index}")
        task.created_at = datetime(2026, 1, 1) + timedelta(days=index)
    session.commit()

    items = repository.list(limit=2, offset=1, sort="created_at:asc")

    assert [task.title for task in items] == ["task-1", "task-2"]
    assert [task.title for task in repository.list(limit=1, offset=4, sort="created_at:asc")] == [
        "task-4"
    ]


def test_list_returns_empty_when_offset_beyond_total(
    repository: TaskRepository, session: Session
) -> None:
    _seed(repository)
    session.commit()

    assert repository.list(offset=3) == []
    assert repository.list(offset=100) == []


def test_list_accepts_maximum_limit(
    repository: TaskRepository, session: Session
) -> None:
    for index in range(3):
        repository.create(title=f"task-{index}")
    session.commit()

    assert len(repository.list(limit=MAX_LIMIT)) == 3


@pytest.mark.parametrize("limit", [0, -1, MAX_LIMIT + 1, "10"])
def test_list_rejects_invalid_limit(repository: TaskRepository, limit: int | str) -> None:
    with pytest.raises(ValueError, match="limit must be"):
        repository.list(limit=limit)


@pytest.mark.parametrize("offset", [-1, "0"])
def test_list_rejects_invalid_offset(
    repository: TaskRepository, offset: int | str
) -> None:
    with pytest.raises(ValueError, match="offset must be"):
        repository.list(offset=offset)


def test_list_rejects_unsupported_sort(repository: TaskRepository) -> None:
    with pytest.raises(ValueError, match="Unsupported sort"):
        repository.list(sort="title:asc")


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("priority", "urgent")],
)
def test_create_rejects_invalid_status_and_priority(
    repository: TaskRepository, field: str, value: str
) -> None:
    with pytest.raises(ValueError, match=f"Unsupported {field}"):
        repository.create(title="task", **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("priority", "urgent")],
)
def test_update_rejects_invalid_status_and_priority(
    repository: TaskRepository, session: Session, field: str, value: str
) -> None:
    task = repository.create(title="task")
    session.commit()

    with pytest.raises(ValueError, match=f"Unsupported {field}"):
        repository.update(task, {field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("priority", "urgent")],
)
def test_count_rejects_invalid_filter(
    repository: TaskRepository, field: str, value: str
) -> None:
    with pytest.raises(ValueError, match=f"Unsupported {field}"):
        repository.count(**{field: value})


def test_update_applies_only_requested_fields(
    repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="old", description="keep me")
    session.commit()

    updated = repository.update(
        task, {"title": "new", "completed_at": datetime(2026, 3, 1)}
    )
    session.commit()

    assert updated.title == "new"
    assert updated.description == "keep me"
    assert updated.completed_at == datetime(2026, 3, 1)


def test_update_changes_updated_at(
    repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="old")
    old_timestamp = datetime(2000, 1, 1)
    task.updated_at = old_timestamp
    session.commit()

    repository.update(task, {"title": "new"})
    session.commit()

    assert task.updated_at > old_timestamp


def test_update_rejects_unknown_fields(
    repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="task")
    session.commit()

    with pytest.raises(ValueError, match="Unsupported fields"):
        repository.update(task, {"unknown": 1})


def test_delete_removes_task(repository: TaskRepository, session: Session) -> None:
    task = repository.create(title="to delete")
    session.commit()
    task_id = task.id

    repository.delete(task)
    session.commit()

    assert repository.get_by_id(task_id) is None
    assert repository.count() == 0


def test_database_rejects_invalid_status(session: Session) -> None:
    session.add(Task(title="bad", status="unknown"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_database_rejects_invalid_priority(session: Session) -> None:
    session.add(Task(title="bad", priority="urgent"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_database_rejects_missing_title(session: Session) -> None:
    session.add(Task(description="no title"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
