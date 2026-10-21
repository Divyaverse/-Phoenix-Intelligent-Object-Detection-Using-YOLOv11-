"""
SQLAlchemy Database Engine, Session Factory, and Initialization for PHOENIX.
Provides unified support for SQLite and PostgreSQL with connection pooling,
foreign key enforcement, and thread safety.
"""

from contextlib import contextmanager
import logging
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger("phoenix.db")

_current_engine = None
_current_session_factory = None
_last_engine_url = None


def get_engine():
    """Retrieve or create the singleton SQLAlchemy engine matching settings.database_url."""
    global _current_engine, _current_session_factory, _last_engine_url

    url = settings.database_url
    if _current_engine is not None and _last_engine_url == url:
        return _current_engine

    is_sqlite = url.startswith("sqlite")
    connect_args = {}
    engine_kwargs = {"echo": False}

    if is_sqlite:
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args
    else:
        # PostgreSQL / MySQL connection pool configuration
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 1800

    engine = create_engine(url, **engine_kwargs)

    # Enforce foreign key constraints for SQLite
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    _current_engine = engine
    _current_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _last_engine_url = url
    return _current_engine


def get_session_factory() -> sessionmaker:
    """Retrieve the session factory for the current engine."""
    get_engine()
    return _current_session_factory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager providing an isolated transactional database session."""
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """
    Initialize all database tables from metadata without dropping existing data.
    Preserves existing records in SQLite and PostgreSQL.
    """
    engine = get_engine()
    # Create all tables defined in models if they do not already exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized and verified.")


# Module-level engine reference for direct access
engine = get_engine()

