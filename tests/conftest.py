"""Test fixtures: in-memory SQLite engine and session with rollback."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Import all models so Base.metadata is fully populated
from lineaf.models import Base, Product, PriceSnapshot, ScrapeRun  # noqa: F401


# Use TEST_DATABASE_URL if set (PostgreSQL), otherwise fall back to SQLite
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///:memory:"
)


@pytest.fixture(scope="session")
def db_engine():
    """Create engine, set up all tables, tear down after all tests."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Yield a session that rolls back after each test."""
    with Session(bind=db_engine) as session:
        yield session
        session.rollback()
