"""Config resolution — database URL provenance."""

import pytest

from vessel_valuation.config import DEFAULT_APP_DATABASE_URL
from vessel_valuation.config import DEFAULT_MIGRATION_DATABASE_URL
from vessel_valuation.config import DEFAULT_RUNTIME_DATABASE_URL
from vessel_valuation.config import DatabaseUrl
from vessel_valuation.config import DatabaseUrlSource
from vessel_valuation.config import get_app_database_url
from vessel_valuation.config import get_database_url
from vessel_valuation.config import get_migration_database_url


@pytest.fixture
def clear_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove DATABASE_URL so defaults apply."""
    monkeypatch.delenv('DATABASE_URL', raising=False)


def test_runtime_url_uses_in_memory_default_when_env_unset(clear_database_url: None) -> None:
    """Runtime getter falls back to in-memory SQLite when DATABASE_URL is absent."""
    resolved = get_database_url()

    assert resolved == DatabaseUrl(
        url=DEFAULT_RUNTIME_DATABASE_URL,
        source=DatabaseUrlSource.DEFAULT_RUNTIME,
    )


def test_migration_url_uses_file_default_when_env_unset(clear_database_url: None) -> None:
    """Migration getter falls back to file SQLite when DATABASE_URL is absent."""
    resolved = get_migration_database_url()

    assert resolved == DatabaseUrl(
        url=DEFAULT_MIGRATION_DATABASE_URL,
        source=DatabaseUrlSource.DEFAULT_MIGRATION,
    )


def test_app_url_uses_file_default_when_env_unset(clear_database_url: None) -> None:
    """Dash app getter falls back to file SQLite when DATABASE_URL is absent."""
    resolved = get_app_database_url()

    assert resolved == DatabaseUrl(
        url=DEFAULT_APP_DATABASE_URL,
        source=DatabaseUrlSource.DEFAULT_APP,
    )


def test_database_url_from_env_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both getters use DATABASE_URL from the environment when it is set."""
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/vessel')

    runtime = get_database_url()
    migration = get_migration_database_url()

    assert runtime.url == 'postgresql://localhost/vessel'
    assert runtime.source is DatabaseUrlSource.ENV
    assert migration == runtime


def test_database_url_repr_redacts_password() -> None:
    """Repr masks credentials while preserving source for error diagnosis."""
    resolved = DatabaseUrl(
        url='postgresql://app:secret@db.example/vessel',
        source=DatabaseUrlSource.ENV,
    )

    text = repr(resolved)

    assert 'secret' not in text
    assert 'app:****@db.example' in text
    assert 'source=' in text


def test_database_url_repr_keeps_sqlite_url(clear_database_url: None) -> None:
    """SQLite URLs without credentials appear unchanged in repr."""
    resolved = get_database_url()

    assert repr(resolved) == (
        f"DatabaseUrl(url='{DEFAULT_RUNTIME_DATABASE_URL}', "
        f'source={DatabaseUrlSource.DEFAULT_RUNTIME!r})'
    )


def test_empty_database_url_env_is_not_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty DATABASE_URL is still env-sourced, not replaced by defaults."""
    monkeypatch.setenv('DATABASE_URL', '')

    assert get_database_url().source is DatabaseUrlSource.ENV
    assert get_database_url().url == ''
