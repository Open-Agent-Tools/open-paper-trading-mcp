import os
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Always use PostgreSQL - whether production, development, or testing
database_url = settings.DATABASE_URL

# For testing, use test database if TEST_DATABASE_URL is set
if os.getenv("TESTING", "False").lower() == "true":
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if test_db_url:
        database_url = test_db_url

# Sync engine (for legacy compatibility)
SYNC_DATABASE_URL = database_url
sync_engine = create_engine(SYNC_DATABASE_URL)

# Async engine
if "+asyncpg" not in database_url:
    ASYNC_DATABASE_URL = database_url.replace("postgresql://", "postgresql+asyncpg://")
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
