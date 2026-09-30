"""
database/session.py

SQLAlchemy database engine configuration for FabFlow AI.

Reads DATABASE_URL from the environment. Falls back to a local
SQLite file (`fabflow_dev.db`) when the variable is absent, so the
project works without Docker for local development and testing.

Usage:
    from database.session import engine, get_db, Base

    # In FastAPI lifespan / startup:
    Base.metadata.create_all(bind=engine)

    # In endpoint dependency injection:
    def some_endpoint(db: Session = Depends(get_db)):
        ...
"""

from __future__ import annotations 

import logging
import os   
from collections.abc import Generator
from typing import Any 

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection URL resolution
# ---------------------------------------------------------------------------
_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./fabflow_dev.db",
)
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def _build_engine(url: str) -> Engine:
    """
    Create a SQLAlchemy engine with sensible defaults for the detected
    database dialect.

    SQLite:
      - ``check_same_thread=False`` is required because FastAPI shares
        the engine across multiple threads.
      - A connection-level listener enables WAL mode and foreign-key
        enforcement on every new connection.

    PostgreSQL / others:
      - A connection pool with pre-ping keeps idle connections healthy.
    """
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn: Any, _connection_record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info("FabFlow AI — SQLite engine initialised: %s", url)
    else:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),

            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
        logger.info("FabFlow AI — PostgreSQL engine initialised: %s", url)

    return engine


engine: Engine = _build_engine(_DATABASE_URL)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Declarative base — shared by all ORM model classes
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Project-wide declarative base.

    All ORM model classes inherit from this; it owns the metadata
    registry used by ``Base.metadata.create_all()``.
    """


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session and guarantee cleanup.

    Designed for use as a FastAPI dependency::

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    The session is rolled back automatically on any exception so that
    a failed request never leaves uncommitted writes in the database.
    """
    
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health-check helper (used by /health endpoint)
# ---------------------------------------------------------------------------


def ping_db() -> bool:
    """Return *True* if a simple SELECT can be executed against the database."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health-check failed: %s", exc)
        return False