"""Shared dependency injection for database sessions and Redis."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


def _build_engine(settings: Settings):
    """Create SQLAlchemy engine from settings."""
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def _build_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Create session factory bound to the engine."""
    engine = _build_engine(settings)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


_session_factory: sessionmaker[Session] | None = None


def get_session_factory(settings: Settings = None) -> sessionmaker[Session]:
    """Get or create the session factory singleton."""
    global _session_factory
    if _session_factory is None:
        if settings is None:
            settings = get_settings()
        _session_factory = _build_session_factory(settings)
    return _session_factory


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Session:
    """FastAPI dependency that yields a database session."""
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
    finally:
        session.close()


# Type alias for use in route signatures
DBSession = Annotated[Session, Depends(get_db)]
