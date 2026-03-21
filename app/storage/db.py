"""Otomoto Parser – Database engine and session factory."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.schema import Table

from app.storage.models import Base, Listing

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def init_db(db_url: str) -> Engine:
    """Create the SQLite engine, enable WAL mode, and create all tables."""
    global _engine, _SessionFactory

    _engine = create_engine(db_url, echo=False, future=True)

    # Enable WAL journal mode for better concurrent read performance
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    _ensure_columns(_engine)
    _ensure_indexes(_engine)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)

    logger.info(f"Database initialised: {db_url}")
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


def _ensure_indexes(engine: Engine) -> None:
    """Create any missing indexes for existing SQLite tables."""
    inspector = inspect(engine)
    existing = {index["name"] for index in inspector.get_indexes(Listing.__tablename__)}

    listing_table = Listing.__table__
    if not isinstance(listing_table, Table):
        raise RuntimeError("Listing table metadata is not available")

    for index in listing_table.indexes:
        if index.name in existing:
            continue
        logger.info("Creating missing index: %s", index.name)
        index.create(bind=engine, checkfirst=True)


def _ensure_columns(engine: Engine) -> None:
    """Add missing columns for existing SQLite tables."""
    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns(Listing.__tablename__)}
    column_defs = {
        "published_at": "DATETIME",
        "photos_json": "TEXT NOT NULL DEFAULT ''",
        "source_category": "VARCHAR(256) NOT NULL DEFAULT ''",
        "raw_attributes_json": "TEXT NOT NULL DEFAULT ''",
    }
    with engine.begin() as conn:
        for name, ddl in column_defs.items():
            if name in existing_columns:
                continue
            logger.info("Adding missing column: %s", name)
            conn.execute(text(f"ALTER TABLE {Listing.__tablename__} ADD COLUMN {name} {ddl}"))


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
