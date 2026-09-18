"""SQLAlchemy engine and session lifecycle for the PS1 database."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


class DatabaseSession:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def create_engine_and_session(database_url: str, *, echo: bool = False) -> DatabaseSession:
    kwargs = {"echo": echo, "future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return DatabaseSession(create_engine(database_url, **kwargs))


def create_schema(database: DatabaseSession) -> None:
    """Create tables for local development and tests.

    Production deployments should use Alembic migrations instead.
    """
    Base.metadata.create_all(database.engine)
