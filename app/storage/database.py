import os
import threading
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
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_size=5,  # Maximum number of permanent connections
    max_overflow=10,  # Maximum number of overflow connections
    pool_timeout=30,  # Timeout for getting connection from pool
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before use
    echo=False,  # Set to True for SQL query debugging
)

# Async engine - lazy initialization to avoid MissingGreenlet error
if "+asyncpg" not in database_url:
    ASYNC_DATABASE_URL = database_url.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = database_url

# Thread-local storage for async database components
_thread_local = threading.local()


def get_async_engine():
    """Get or create the async engine (thread-local lazy initialization)."""
    if not hasattr(_thread_local, "async_engine") or _thread_local.async_engine is None:
        _thread_local.async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            pool_size=5,  # Maximum number of permanent connections
            max_overflow=10,  # Maximum number of overflow connections
            pool_timeout=30,  # Timeout for getting connection from pool
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Verify connections before use
            echo=False,  # Set to True for SQL query debugging
        )
    return _thread_local.async_engine


def get_async_session_factory():
    """Get or create the async session factory (thread-local lazy initialization)."""
    if (
        not hasattr(_thread_local, "async_session_factory")
        or _thread_local.async_session_factory is None
    ):
        engine = get_async_engine()
        _thread_local.async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _thread_local.async_session_factory


# For backward compatibility, create module-level variables that get initialized lazily
async_engine = None
AsyncSessionLocal = None

# Create sync session factory (this is safe at module level)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Export both sync and async engines and sessions
__all__ = [
    "AsyncSessionLocal",
    "SessionLocal",
    "async_engine",
    "get_async_db",
    "get_async_engine",
    "get_async_session",
    "get_async_session_factory",
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
    session_factory = get_async_session_factory()
    session = session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Alias for FastAPI dependency injection
get_async_db = get_async_session


async def init_db() -> None:
    """
    Initialize the database (create tables, etc.).
    """
    from app.models.database.base import Base

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
