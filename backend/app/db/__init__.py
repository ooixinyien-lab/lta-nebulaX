"""Production-ready PS1 persistence layer.

The legacy JSON/SQLite store remains in :mod:`backend.app.database` for the
transition API. This package stores immutable PS1 input revisions and runs in
PostgreSQL (or SQLite for tests and local development).
"""

from .engine import DatabaseSession, create_engine_and_session, create_schema
from .models import Base

__all__ = ["Base", "DatabaseSession", "create_engine_and_session", "create_schema"]
