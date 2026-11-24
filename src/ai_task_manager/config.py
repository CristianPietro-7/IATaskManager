"""Application configuration read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_DATABASE_URL = "sqlite:///./ai_task_manager.db"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_API_PREFIX = "/api/v1"
VALID_ENVIRONMENTS = frozenset({"development", "testing", "production"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off", ""})


def _parse_bool(name: str, raw_value: str) -> bool:
    value = raw_value.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise ValueError(f"{name} must be a boolean value, got {raw_value!r}")


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings used to build the application."""

    database_url: str
    environment: str
    api_prefix: str
    create_tables_on_startup: bool

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from a mapping, defaulting to ``os.environ``."""
        env = os.environ if environ is None else environ

        database_url = env.get("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
        if not database_url.startswith("sqlite://"):
            raise ValueError("DATABASE_URL must use SQLite, e.g. sqlite:///./ai_task_manager.db")

        environment = env.get("ENV", DEFAULT_ENVIRONMENT).strip().lower()
        if environment not in VALID_ENVIRONMENTS:
            allowed = ", ".join(sorted(VALID_ENVIRONMENTS))
            raise ValueError(f"ENV must be one of: {allowed}")

        api_prefix = env.get("API_PREFIX", DEFAULT_API_PREFIX).strip()
        if not api_prefix.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        api_prefix = api_prefix.rstrip("/") or "/"

        raw_flag = env.get("CREATE_TABLES_ON_STARTUP")
        create_tables = (
            environment == "development"
            if raw_flag is None
            else _parse_bool("CREATE_TABLES_ON_STARTUP", raw_flag)
        )

        return cls(
            database_url=database_url,
            environment=environment,
            api_prefix=api_prefix,
            create_tables_on_startup=create_tables,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings; tests may clear this cache."""
    return Settings.from_env()


__all__ = [
    "DEFAULT_API_PREFIX",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_ENVIRONMENT",
    "VALID_ENVIRONMENTS",
    "Settings",
    "get_settings",
]
