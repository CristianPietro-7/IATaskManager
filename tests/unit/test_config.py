"""Unit tests for environment-based configuration."""

import pytest

from ai_task_manager.config import (
    DEFAULT_API_PREFIX,
    DEFAULT_DATABASE_URL,
    Settings,
    get_settings,
)

_ENV_KEYS = ("DATABASE_URL", "ENV", "API_PREFIX", "CREATE_TABLES_ON_STARTUP")


def test_settings_from_empty_env_uses_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.environment == "development"
    assert settings.api_prefix == DEFAULT_API_PREFIX
    assert settings.create_tables_on_startup is True


def test_settings_from_env_reads_and_normalizes_values() -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite:///:memory:",
            "ENV": " TESTING ",
            "API_PREFIX": "/api/v2/",
            "CREATE_TABLES_ON_STARTUP": "false",
        }
    )

    assert settings.database_url == "sqlite:///:memory:"
    assert settings.environment == "testing"
    assert settings.api_prefix == "/api/v2"
    assert settings.create_tables_on_startup is False


@pytest.mark.parametrize("raw_flag", ["1", "true", "YES", "on"])
def test_settings_accepts_truthy_create_tables_flags(raw_flag: str) -> None:
    settings = Settings.from_env({"CREATE_TABLES_ON_STARTUP": raw_flag})

    assert settings.create_tables_on_startup is True


@pytest.mark.parametrize("raw_flag", ["0", "false", "NO", "off", ""])
def test_settings_accepts_falsy_create_tables_flags(raw_flag: str) -> None:
    settings = Settings.from_env({"CREATE_TABLES_ON_STARTUP": raw_flag})

    assert settings.create_tables_on_startup is False


def test_settings_disables_table_creation_in_production_by_default() -> None:
    settings = Settings.from_env({"ENV": "production"})

    assert settings.create_tables_on_startup is False


@pytest.mark.parametrize(
    ("environ", "expected_message"),
    [
        ({"DATABASE_URL": "postgresql://localhost/db"}, "DATABASE_URL must use SQLite"),
        ({"ENV": "staging"}, "ENV must be one of"),
        ({"API_PREFIX": "api/v1"}, "API_PREFIX must start"),
        ({"CREATE_TABLES_ON_STARTUP": "maybe"}, "must be a boolean value"),
    ],
)
def test_settings_rejects_invalid_environment_values(
    environ: dict[str, str], expected_message: str
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        Settings.from_env(environ)


def test_get_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    try:
        first = get_settings()

        assert first is get_settings()
        assert first == Settings.from_env({})
    finally:
        get_settings.cache_clear()
