"""Database engine and session management (Neon serverless PostgreSQL friendly).

Connection strategy
-------------------
* On Vercel (serverless) we use ``NullPool``: every function invocation opens a
  short-lived connection and closes it immediately. Pair this with Neon's
  *pooled* connection string (host contains ``-pooler``) so PgBouncer on Neon's
  side multiplexes connections and they never pile up.
* For a long-running server (local dev / container) we use a small
  ``QueuePool`` with ``pool_pre_ping`` so idle connections dropped by Neon's
  auto-suspend are transparently replaced.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from .config import get_settings

log = logging.getLogger("ayaka.db")

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


class DatabaseNotConfigured(RuntimeError):
    pass


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")

    connect_args = {"connect_timeout": 10, "application_name": "ayaka-sync-api"}
    if settings.is_serverless:
        _engine = create_engine(
            settings.database_url, poolclass=NullPool, connect_args=connect_args, future=True
        )
    else:
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=280,  # below Neon's idle suspend window
            connect_args=connect_args,
            future=True,
        )
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Dispose the engine (used by tests and after config changes)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def session_factory() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session."""
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def standalone_session() -> Iterator[Session]:
    """Independent session/transaction (used for usage logging and audit writes)."""
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ping() -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
        migrated = conn.execute(
            text("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
        ).scalar_one()
        applied = []
        if migrated:
            applied = [r[0] for r in conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))]
    return {"server": version.split(",")[0], "migrations": applied}
