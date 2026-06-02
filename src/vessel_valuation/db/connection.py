"""SQLAlchemy engine and session factory."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from vessel_valuation.config import get_database_url

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def create_db_engine(url: str | None = None, *, for_tests: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the given URL.

    Parameters
    ----------
    url
        Database URL. Defaults to ``get_database_url()``.
    for_tests
        When True and the URL is SQLite, use ``StaticPool`` so in-memory
        databases survive across connections in the same process.
    """
    resolved = url if url is not None else get_database_url().url
    if resolved.startswith('sqlite'):
        connect_args = {'check_same_thread': False, 'timeout': 30}
        if for_tests:
            return create_engine(
                resolved,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(resolved, connect_args=connect_args)
    return create_engine(resolved)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Bind a session factory to ``engine``."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
