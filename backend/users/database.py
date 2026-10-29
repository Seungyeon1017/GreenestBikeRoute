"""Connection to the users database: the engine, sessions and the base class for tables."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.users.config import get_settings


class Base(DeclarativeBase):
    """Every table class (models.py) inherits from this; Alembic reads Base.metadata."""


@lru_cache
def get_engine() -> Engine:
    """Created on first use, not on import, so the rest of the backend starts even without a database."""
    # pool_pre_ping checks a pooled connection before using it, e.g. after the database restarted.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Tests replace it with app.dependency_overrides[get_db] to use a test database.
    """
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()