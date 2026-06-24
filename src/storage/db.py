from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    from config.settings import get_settings

    url = get_settings().database_url

    kwargs: dict = {}
    if url.startswith("sqlite"):
        # Resolve relative path and create parent directory
        db_path = url.replace("sqlite:///", "").replace("sqlite://", "")
        if db_path:
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_engine(url, echo=False, **kwargs)

    # Enable WAL mode for SQLite — better read concurrency
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _set_wal(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    logger.info("Database engine created: %s", url)
    return _engine


def init_db() -> None:
    """Create all tables if they do not exist."""
    from .models import Base

    Base.metadata.create_all(get_engine())
    logger.info("Database schema synchronised")


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _SessionFactory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    factory = _get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
