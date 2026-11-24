"""AI Task Manager API package."""

from __future__ import annotations

from datetime import UTC, datetime

__version__ = "0.1.0"

__all__ = ["__version__", "utc_now"]


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime.

    SQLite stores naive UTC values in this MVP; callers add the ``Z`` suffix
    when serializing them in API responses.
    """
    return datetime.now(tz=UTC).replace(tzinfo=None)
