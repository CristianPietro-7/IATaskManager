"""API tests for the version 1 task endpoints."""

from __future__ import annotations

import json
import pathlib

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_task_manager.config import Settings
from ai_task_manager.main import create_app
from ai_task_manager.models.task import TaskPriority, TaskStatus
from ai_task_manager.repositories.task_repository import TaskRepository

_PREFIX = "/api/v1/tasks"


def test_create_task_returns_201_location_and_utc_timestamps(client: TestClient) -> None:
    response = client.post(
        _PREFIX,
        json={
            "title": "  Buy milk  ",
            "description": "today",
            "due_at": "2026-12-31T23:59:00Z",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == TaskStatus.PENDING.value
    assert body["priority"] == TaskPriority.MEDIUM.value
    assert body["due_at"] == "2026-12-31T23:59:00Z"
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    assert body["completed_at"] is None
    assert response.headers["location"] == f"http://testserver{_PREFIX}/{body['id']}"


def test_create_task_rejects_blank_title_with_domain_error(client: TestClient) -> None:
    response = client.post(_PREFIX, json={"title": "   "})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {
        "detail": "title must not be empty",
        "code": "validation_error",
        "fields": {"title": "must not be empty"},
    }


def test_create_task_rejects_missing_title_with_validation_error(
    client: TestClient,
) -> None:
    response = client.post(_PREFIX, json={"description": "without title"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    body = response.json()
    assert body["detail"] == "Invalid request."
    assert body["code"] == "validation_error"
    assert "title" in body["fields"]


def test_list_returns_pagination_envelope(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    repository.create(title="first")
    repository.create(title="second")
    session.commit()

    response = client.get(_PREFIX)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert sorted(item["title"] for item in body["items"]) == ["first", "second"]
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_list_filters_priority_and_paginates(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    repository.create(
        title="target",
        status=TaskStatus.COMPLETED.value,
        priority=TaskPriority.HIGH.value,
    )
    repository.create(title="other")
    session.commit()

    response = client.get(
        _PREFIX,
        params={
            "status": TaskStatus.COMPLETED.value,
            "priority": TaskPriority.HIGH.value,
            "limit": 1,
            "offset": 0,
            "sort": "created_at:asc",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert [item["title"] for item in body["items"]] == ["target"]


@pytest.mark.parametrize(
    ("params", "field"),
    [({"limit": 0}, "limit"), ({"limit": 101}, "limit"), ({"offset": -1}, "offset")],
)
def test_list_rejects_invalid_pagination(
    client: TestClient, params: dict[str, int], field: str
) -> None:
    response = client.get(_PREFIX, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert field in response.json()["fields"]


def test_list_rejects_invalid_status(client: TestClient) -> None:
    response = client.get(_PREFIX, params={"status": "unknown"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "status" in response.json()["fields"]


def test_get_task_returns_200(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="found")
    session.commit()

    response = client.get(f"{_PREFIX}/{task.id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "found"


def test_get_task_returns_404_with_error_envelope(client: TestClient) -> None:
    response = client.get(f"{_PREFIX}/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "Task 999 not found",
        "code": "not_found",
    }


def test_get_task_rejects_non_integer_id(client: TestClient) -> None:
    response = client.get(f"{_PREFIX}/abc")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "task_id" in response.json()["fields"]


def test_patch_updates_only_provided_fields(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="old", description="keep")
    session.commit()

    response = client.patch(f"{_PREFIX}/{task.id}", json={"title": "  new  "})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["title"] == "new"
    assert body["description"] == "keep"
    assert body["status"] == TaskStatus.PENDING.value
    assert body["completed_at"] is None


def test_patch_marks_completed_at(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="task")
    session.commit()

    response = client.patch(
        f"{_PREFIX}/{task.id}", json={"status": TaskStatus.COMPLETED.value}
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == TaskStatus.COMPLETED.value
    assert body["completed_at"] is not None
    assert body["completed_at"].endswith("Z")


def test_patch_rejects_unknown_field(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="task")
    session.commit()

    response = client.patch(f"{_PREFIX}/{task.id}", json={"unknown": 1})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "unknown" in response.json()["fields"]


def test_patch_returns_404_for_missing_task(client: TestClient) -> None:
    response = client.patch(f"{_PREFIX}/999", json={"title": "new"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "not_found"


def test_delete_returns_204_without_body(
    client: TestClient, repository: TaskRepository, session: Session
) -> None:
    task = repository.create(title="to delete")
    session.commit()

    response = client.delete(f"{_PREFIX}/{task.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    assert repository.get_by_id(task.id) is None


def test_delete_returns_404_for_missing_task(client: TestClient) -> None:
    response = client.delete(f"{_PREFIX}/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "not_found"


def test_openapi_documents_contract(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    assert "/api/v1/tasks" in schema["paths"]
    assert "/api/v1/tasks/{task_id}" in schema["paths"]
    assert "/health" in schema["paths"]
    schemas = schema["components"]["schemas"]
    assert {"TaskCreate", "TaskUpdate", "TaskRead", "TaskPage", "ErrorResponse"} <= set(
        schemas
    )
    create_responses = schema["paths"]["/api/v1/tasks"]["post"]["responses"]
    assert "Location" in create_responses["201"]["headers"]


def test_versioned_openapi_matches_generated_contract(settings: Settings) -> None:
    versioned = json.loads(pathlib.Path("docs/openapi.json").read_text(encoding="utf-8"))

    assert versioned == create_app(settings).openapi()
