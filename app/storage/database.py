import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Check for a testing environment
TESTING = os.getenv("TESTING", "False").lower() == "true"

if TESTING:
    # For testing, use async SQLite with aiosqlite driver
    ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
    )
else:
    # Production: Use async PostgreSQL with asyncpg driver
    database_url = settings.DATABASE_URL
    if "+asyncpg" not in database_url:
        ASYNC_DATABASE_URL = database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    else:
        ASYNC_DATABASE_URL = database_url
    async_engine = create_async_engine(ASYNC_DATABASE_URL)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Export async engine and session for direct access
__all__ = ["AsyncSessionLocal", "async_engine", "get_async_session", "get_async_db", "init_db"]


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
