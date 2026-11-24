"""Unit tests for domain errors and their HTTP translation."""

import asyncio
import json
from collections.abc import Mapping

import pytest
from fastapi import FastAPI, Request, status
from starlette.responses import JSONResponse

from ai_task_manager.exceptions import (
    ConflictError,
    DomainError,
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
    domain_error_handler,
    register_exception_handlers,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


def _handle(exc: DomainError) -> tuple[int, Mapping[str, object]]:
    response = asyncio.run(domain_error_handler(_request(), exc))
    assert isinstance(response, JSONResponse)
    payload = json.loads(response.body)
    assert isinstance(payload, dict)
    return response.status_code, payload


@pytest.mark.parametrize(
    ("exc", "expected_code", "expected_status"),
    [
        (NotFoundError(), "not_found", status.HTTP_404_NOT_FOUND),
        (ConflictError(), "conflict", status.HTTP_409_CONFLICT),
        (InvalidStateError(), "invalid_state", status.HTTP_422_UNPROCESSABLE_CONTENT),
        (DomainValidationError(), "validation_error", status.HTTP_422_UNPROCESSABLE_CONTENT),
        (DomainError(), "domain_error", status.HTTP_400_BAD_REQUEST),
    ],
)
def test_domain_errors_map_to_status_and_code(
    exc: DomainError, expected_code: str, expected_status: int
) -> None:
    actual_status, payload = _handle(exc)

    assert actual_status == expected_status
    assert payload == {"detail": exc.detail, "code": expected_code}


def test_handler_includes_fields_when_present() -> None:
    exc = DomainValidationError("Invalid title", fields={"title": "must not be empty"})

    actual_status, payload = _handle(exc)

    assert actual_status == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert payload["fields"] == {"title": "must not be empty"}


def test_handler_honors_custom_detail_and_code() -> None:
    exc = DomainError("Custom detail", code="custom_code")

    _, payload = _handle(exc)

    assert payload == {"detail": "Custom detail", "code": "custom_code"}


def test_status_resolution_uses_parent_mapping() -> None:
    class TaskNotFoundError(NotFoundError):
        code = "task_not_found"

    actual_status, payload = _handle(TaskNotFoundError())

    assert actual_status == status.HTTP_404_NOT_FOUND
    assert payload["code"] == "task_not_found"


def test_register_exception_handlers_attaches_domain_handler() -> None:
    app = FastAPI()

    register_exception_handlers(app)

    assert app.exception_handlers[DomainError] is domain_error_handler
