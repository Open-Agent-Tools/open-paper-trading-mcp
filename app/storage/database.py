import os
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Check for a testing environment
TESTING = os.getenv("TESTING", "False").lower() == "true"

if TESTING:
    # For testing, use SQLite for both sync and async
    SYNC_DATABASE_URL = "sqlite:///:memory:"
    ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

    sync_engine = create_engine(
        SYNC_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
    )
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
    )
else:
    # Production: Use PostgreSQL for both sync and async
    database_url = settings.DATABASE_URL

    # Sync engine (for legacy compatibility)
    SYNC_DATABASE_URL = database_url
    sync_engine = create_engine(SYNC_DATABASE_URL)

    # Async engine
    if "+asyncpg" not in database_url:
        ASYNC_DATABASE_URL = database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    else:
        ASYNC_DATABASE_URL = database_url
    async_engine = create_async_engine(ASYNC_DATABASE_URL)

# Create session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Export both sync and async engines and sessions
__all__ = [
    "AsyncSessionLocal",
    "SessionLocal",
    "async_engine",
    "get_async_db",
    "get_async_session",
    "get_sync_session",
    "init_db",
    "sync_engine",
]


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """
    Get a synchronous database session for legacy compatibility.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session using asyncpg (production) or aiosqlite (testing).
    """
    async with AsyncSessionLocal() as session:
        yield session


# Alias for FastAPI dependency injection
get_async_db = get_async_session


async def init_db() -> None:
    """
    Initialize the database (create tables, etc.).
    """
    from app.models.database.base import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
