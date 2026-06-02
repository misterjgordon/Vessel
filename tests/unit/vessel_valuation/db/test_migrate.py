"""
Legacy SQLite bootstrap and Alembic upgrade behaviour.
uv run pytest tests/unit/vessel_valuation/db/test_migrate.py -v
"""

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import inspect

from vessel_valuation.db.connection import create_db_engine
from vessel_valuation.db.migrate import _current_alembic_revision
from vessel_valuation.db.migrate import _legacy_create_all_schema
from vessel_valuation.db.migrate import upgrade_database
from vessel_valuation.db.repository import init_schema

if TYPE_CHECKING:
    import pytest


def test_legacy_create_all_schema_detects_tables_without_alembic_version(tmp_path: Path) -> None:
    """init_schema-only databases are recognized as needing an Alembic stamp."""
    db_path = tmp_path / 'legacy.db'
    engine = create_db_engine(f'sqlite:///{db_path}')
    init_schema(engine)

    assert _legacy_create_all_schema(engine) is True


def test_legacy_create_all_schema_false_on_empty_database(tmp_path: Path) -> None:
    """An empty database is not treated as a legacy create_all bootstrap."""
    db_path = tmp_path / 'empty.db'
    engine = create_db_engine(f'sqlite:///{db_path}')

    assert _legacy_create_all_schema(engine) is False


def test_upgrade_database_stamps_legacy_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upgrade_database stamps head when schema exists but alembic_version is empty."""
    db_path = tmp_path / 'legacy.db'
    url = f'sqlite:///{db_path}'
    monkeypatch.setenv('DATABASE_URL', url)

    engine = create_db_engine(url)
    init_schema(engine)

    upgrade_database()

    assert _current_alembic_revision(create_db_engine(url)) == '9f2b93443d45'


def test_upgrade_database_applies_migrations_on_fresh_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upgrade_database runs migrations on a new file database."""
    db_path = tmp_path / 'fresh.db'
    url = f'sqlite:///{db_path}'
    monkeypatch.setenv('DATABASE_URL', url)

    upgrade_database()

    engine = create_db_engine(url)
    assert 'raw_vessel_submissions' in inspect(engine).get_table_names()
    assert _current_alembic_revision(engine) == '9f2b93443d45'
    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            'SELECT COUNT(*) FROM vessel_benchmarks',
        ).fetchone()[0]
    assert count == 4
