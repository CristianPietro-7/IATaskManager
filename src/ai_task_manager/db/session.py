"""SQLAlchemy engine, session factory and FastAPI session dependency."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ai_task_manager.config import get_settings

_SQLITE_PREFIX = "sqlite:"


def _is_memory_sqlite(url: str) -> bool:
    return url == "sqlite://" or ":memory:" in url or "mode=memory" in url


def create_engine_from_url(url: str, *, echo: bool = False) -> Engine:
    """Create a SQLite engine with the connection options this MVP needs."""
    if not url.startswith(_SQLITE_PREFIX):
        raise ValueError("Only SQLite database URLs are supported in the MVP.")

    connect_args = {"check_same_thread": False}
    if _is_memory_sqlite(url):
        return create_engine(
            url, connect_args=connect_args, poolclass=StaticPool, echo=echo
        )
    return create_engine(url, connect_args=connect_args, echo=echo)


settings = get_settings()
engine = create_engine_from_url(settings.database_url)
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)


def get_session() -> Iterator[Session]:
    """Yield a session, commit on success and roll back on failure."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["SessionLocal", "create_engine_from_url", "engine", "get_session", "settings"]
