"""Reusable domain errors and their translation to HTTP responses."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Base class for errors raised by the business layer.

    Instances carry no HTTP information: the API layer decides the status code.
    """

    code = "domain_error"
    detail = "Unexpected domain error."

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        fields: Mapping[str, object] | None = None,
    ) -> None:
        self.detail = detail or self.detail
        self.code = code or self.code
        self.fields = fields
        super().__init__(self.detail)


class NotFoundError(DomainError):
    """A requested resource does not exist."""

    code = "not_found"
    detail = "Resource not found."


class ConflictError(DomainError):
    """The requested operation conflicts with the current state."""

    code = "conflict"
    detail = "Resource conflict."


class InvalidStateError(DomainError):
    """A state transition is not allowed."""

    code = "invalid_state"
    detail = "Invalid state transition."


class DomainValidationError(DomainError):
    """Input does not satisfy a domain rule."""

    code = "validation_error"
    detail = "Invalid input."


_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidStateError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DomainValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DomainError: status.HTTP_400_BAD_REQUEST,
}


def _status_for(exc: DomainError) -> int:
    for error_type in type(exc).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return status.HTTP_400_BAD_REQUEST


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    """Render every domain error with the shared error envelope."""
    payload: dict[str, object] = {"detail": exc.detail, "code": exc.code}
    if exc.fields is not None:
        payload["fields"] = dict(exc.fields)
    return JSONResponse(status_code=_status_for(exc), content=payload)


def request_validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render Pydantic/FastAPI validation failures with the shared envelope."""
    fields: dict[str, list[str]] = {}
    for error in exc.errors():
        location = [
            str(part)
            for part in error.get("loc", ())
            if part not in {"body", "query", "path", "header", "cookie"}
        ]
        name = ".".join(location) or "body"
        fields.setdefault(name, []).append(str(error.get("msg", "Invalid value.")))
    payload: dict[str, object] = {
        "detail": "Invalid request.",
        "code": DomainValidationError.code,
    }
    if fields:
        payload["fields"] = fields
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=payload
    )


def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render framework HTTP errors with the shared envelope."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": "http_error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every error handler to a FastAPI application."""
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)


__all__ = [
    "ConflictError",
    "DomainError",
    "DomainValidationError",
    "InvalidStateError",
    "NotFoundError",
    "domain_error_handler",
    "http_error_handler",
    "register_exception_handlers",
    "request_validation_error_handler",
]
