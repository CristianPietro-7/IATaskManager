"""Unit tests for SQLite engine creation and session handling."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.pool import StaticPool

from ai_task_manager.db import session as session_module
from ai_task_manager.db.session import create_engine_from_url, get_session


def test_create_engine_from_url_builds_sqlite_engine() -> None:
    engine = create_engine_from_url("sqlite:///./unit_test.db")

    assert engine.url.drivername == "sqlite"
    assert not isinstance(engine.pool, StaticPool)
    engine.dispose()


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "sqlite://"])
def test_create_engine_from_url_uses_static_pool_for_in_memory(url: str) -> None:
    engine = create_engine_from_url(url)

    assert isinstance(engine.pool, StaticPool)
    engine.dispose()


def test_create_engine_from_url_allows_connection_from_another_thread() -> None:
    engine = create_engine_from_url("sqlite:///:memory:")

    with (
        engine.connect() as connection,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        value = executor.submit(
            lambda: connection.exec_driver_sql("SELECT 1").scalar_one()
        ).result()

    assert value == 1
    engine.dispose()


def test_create_engine_from_url_rejects_non_sqlite_url() -> None:
    with pytest.raises(ValueError, match="Only SQLite"):
        create_engine_from_url("postgresql://localhost/db")


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _replace_session_factory(monkeypatch: pytest.MonkeyPatch, fake: _FakeSession) -> None:
    def factory() -> _FakeSession:
        return fake

    monkeypatch.setattr(session_module, "SessionLocal", factory)


def test_get_session_commits_and_closes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSession()
    _replace_session_factory(monkeypatch, fake)

    generator = get_session()
    assert next(generator) is fake
    with pytest.raises(StopIteration):
        next(generator)

    assert fake.committed is True
    assert fake.rolled_back is False
    assert fake.closed is True


def test_get_session_rolls_back_and_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSession()
    _replace_session_factory(monkeypatch, fake)

    generator = get_session()
    assert next(generator) is fake
    with pytest.raises(RuntimeError, match="boom"):
        generator.throw(RuntimeError("boom"))

    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True
