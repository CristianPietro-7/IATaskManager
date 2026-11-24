"""Shared response envelopes for errors and pagination."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Uniform JSON body for every API error."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    code: str | None = None
    fields: dict[str, str | list[str]] | None = None


class Page[T](BaseModel):
    """Offset-based pagination envelope."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    items: list[T]
    total: int
    limit: int
    offset: int


__all__ = ["ErrorResponse", "Page"]
