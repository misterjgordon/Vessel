"""Apply Alembic migrations for the configured database URL.

Handles local SQLite databases that were bootstrapped with ``init_schema``
(``create_all``) before Alembic versioning was recorded.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy import inspect
from sqlalchemy import text

from vessel_valuation.config import get_migration_database_url
from vessel_valuation.db.connection import create_db_engine

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / 'alembic.ini'
_SCHEMA_MARKER_TABLE = 'raw_vessel_submissions'


def _alembic_config() -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option('sqlalchemy.url', get_migration_database_url().url)
    return cfg


def _current_alembic_revision(engine: Engine) -> str | None:
    inspector = inspect(engine)
    if 'alembic_version' not in inspector.get_table_names():
        return None
    with engine.connect() as connection:
        row = connection.execute(
            text('SELECT version_num FROM alembic_version LIMIT 1'),
        ).first()
    if row is None:
        return None
    return str(row[0])


def _legacy_create_all_schema(engine: Engine) -> bool:
    """Return whether ``init_schema`` created tables but Alembic was never stamped."""
    inspector = inspect(engine)
    if _SCHEMA_MARKER_TABLE not in inspector.get_table_names():
        return False
    return _current_alembic_revision(engine) is None


def upgrade_database() -> None:
    """Upgrade to head, or stamp head when a legacy ``create_all`` database is detected."""
    db_url = get_migration_database_url().url
    engine = create_db_engine(db_url)
    cfg = _alembic_config()

    if _legacy_create_all_schema(engine):
        head = ScriptDirectory.from_config(cfg).get_current_head()
        if head is None:
            msg = 'No Alembic revisions found; cannot stamp legacy database.'
            raise RuntimeError(msg)
        command.stamp(cfg, head)
        return

    command.upgrade(cfg, 'head')


def main() -> None:
    """CLI entry point used by ``make run`` / ``make dev``."""
    upgrade_database()


if __name__ == '__main__':
    main()
