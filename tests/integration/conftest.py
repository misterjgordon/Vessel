"""Integration test database fixtures."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from vessel_valuation.db.repository import create_test_session_factory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    """In-memory SQLite with schema and seed benchmarks."""
    return create_test_session_factory()


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session]:
    """Transactional session rolled back after each test."""
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.rollback()
        session.close()
