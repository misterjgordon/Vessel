"""Application configuration loaded from environment variables.

Loads a project ``.env`` file on import (see D-018 in ``docs/decisions.md``).
Environment-specific values (database URL, app port, debug flags) belong here —
not scattered ``os.environ`` reads in feature modules.

Database URL behaviour
----------------------
``DATABASE_URL`` selects the SQLAlchemy backend. When unset, defaults differ by
use case:

- **Runtime** (``get_database_url()``): ``sqlite:///:memory:`` — zero-config
  fallback for tests and scripts.
- **Migrations** (``get_migration_database_url()``): ``sqlite:///vessel_valuation.db``
  — file-backed SQLite so ``alembic upgrade`` persists schema between CLI runs.
- **Dash app** (``get_app_database_url()``): same file default as migrations so
  saved vessels persist across HTTP requests.
- Override any of the above with ``DATABASE_URL`` (see ``.env.example``).
"""

import os
from dataclasses import dataclass
from enum import StrEnum

from dotenv import load_dotenv

load_dotenv()

# Runtime when DATABASE_URL is unset (see module docstring).
DEFAULT_RUNTIME_DATABASE_URL = 'sqlite:///:memory:'

# Alembic CLI when DATABASE_URL is unset (file persists across invocations).
DEFAULT_MIGRATION_DATABASE_URL = 'sqlite:///vessel_valuation.db'

# Dash / local app when DATABASE_URL is unset (file persists across HTTP requests).
DEFAULT_APP_DATABASE_URL = DEFAULT_MIGRATION_DATABASE_URL

_DATABASE_URL_ENV = 'DATABASE_URL'


class DatabaseUrlSource(StrEnum):
    """How a resolved database URL was chosen."""

    ENV = 'env'
    DEFAULT_RUNTIME = 'default_runtime'
    DEFAULT_MIGRATION = 'default_migration'
    DEFAULT_APP = 'default_app'


@dataclass(frozen=True)
class DatabaseUrl:
    """Resolved SQLAlchemy database URL with provenance for logging and errors."""

    url: str
    source: DatabaseUrlSource

    def __repr__(self) -> str:
        return f'DatabaseUrl(url={_redact_url(self.url)!r}, source={self.source!r})'


def _redact_url(url: str) -> str:
    """Mask credentials in a database URL for safe logging."""
    if '://' not in url or '@' not in url:
        return url
    scheme, rest = url.split('://', 1)
    credentials, host_part = rest.rsplit('@', 1)
    if ':' in credentials:
        user, _password = credentials.split(':', 1)
        return f'{scheme}://{user}:****@{host_part}'
    return f'{scheme}://****@{host_part}'


def _resolve_database_url(*, default: str, default_source: DatabaseUrlSource) -> DatabaseUrl:
    if _DATABASE_URL_ENV in os.environ:
        return DatabaseUrl(url=os.environ[_DATABASE_URL_ENV], source=DatabaseUrlSource.ENV)
    return DatabaseUrl(url=default, source=default_source)


def get_database_url() -> DatabaseUrl:
    """Return the runtime database URL from ``DATABASE_URL`` or the in-memory SQLite default."""
    return _resolve_database_url(
        default=DEFAULT_RUNTIME_DATABASE_URL,
        default_source=DatabaseUrlSource.DEFAULT_RUNTIME,
    )


def get_migration_database_url() -> DatabaseUrl:
    """Return the database URL for Alembic from ``DATABASE_URL`` or the file SQLite default."""
    return _resolve_database_url(
        default=DEFAULT_MIGRATION_DATABASE_URL,
        default_source=DatabaseUrlSource.DEFAULT_MIGRATION,
    )


def get_app_database_url() -> DatabaseUrl:
    """Return the database URL for the Dash app.

    Uses ``DATABASE_URL`` when set; otherwise file-backed SQLite so submissions
    persist across requests. Tests and scripts should keep using
    ``get_database_url()`` (in-memory default).
    """
    return _resolve_database_url(
        default=DEFAULT_APP_DATABASE_URL,
        default_source=DatabaseUrlSource.DEFAULT_APP,
    )
