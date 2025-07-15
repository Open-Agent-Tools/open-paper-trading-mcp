import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from typing import Generator

# Check for a testing environment
TESTING = os.getenv("TESTING", "False").lower() == "true"

if TESTING:
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Convert asyncpg URL to sync psycopg2 URL for synchronous operations
    database_url = settings.DATABASE_URL
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    engine = create_engine(database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Export engine for direct access (needed by main.py)
__all__ = ["engine", "SessionLocal", "get_db", "get_async_session", "init_db"]


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session():
    """
    Get an async database session (placeholder for async functionality).
    Note: This is a placeholder implementation. For true async support,
    you would need to use SQLAlchemy's async engine and session.
    """
    # For now, this just wraps the sync session
    # In a real async implementation, you'd use create_async_engine
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """
    Initialize the database (create tables, etc.).
    """
    from app.models.database.base import Base
    Base.metadata.create_all(bind=engine)
