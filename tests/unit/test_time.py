"""Unit tests for the shared UTC time helper."""

from datetime import UTC, datetime

from ai_task_manager import utc_now


def test_utc_now_returns_naive_utc_datetime() -> None:
    before = datetime.now(tz=UTC).replace(tzinfo=None)

    result = utc_now()

    after = datetime.now(tz=UTC).replace(tzinfo=None)
    assert result.tzinfo is None
    assert result.utcoffset() is None
    assert before <= result <= after
