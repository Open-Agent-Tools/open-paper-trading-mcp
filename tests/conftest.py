import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Set testing environment variables BEFORE importing the app
os.environ["TESTING"] = "True"
# Use Docker PostgreSQL database for all tests
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
)
os.environ["TEST_DATABASE_URL"] = (
    "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
)
os.environ["QUOTE_ADAPTER_TYPE"] = "test"  # Use test data adapter

from app.main import app

# Import models to ensure they're registered with Base
from app.models.database import trading  # noqa: F401
from app.models.database.base import Base
from app.storage.database import async_engine, get_async_session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Set up test database once per test session."""
    # Ensure tables exist in test database
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Optional: Clean up after all tests (keep tables for debugging)
    # async with async_engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a new async database session for a test and handle setup/teardown."""
    # Use a separate engine for each test to avoid event loop conflicts
    import os

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    test_engine = create_async_engine(database_url, echo=False, future=True)
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        # Ensure tables exist (idempotent)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Clean up any existing test data BEFORE test runs
            await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
            await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
            await conn.commit()

        # Create session
        async with TestSessionLocal() as session:
            try:
                yield session
                # Commit any pending transactions
                await session.commit()
            except Exception:
                # Rollback on error
                await session.rollback()
                raise
            finally:
                await session.close()

        # Clean up data (not tables) for test isolation AFTER test runs
        try:
            async with test_engine.begin() as conn:
                # Truncate all tables to clean up test data
                await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
                await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
                await conn.commit()
        except Exception as e:
            print(f"Test cleanup warning: {e}")

    finally:
        # Always dispose the engine
        await test_engine.dispose()


@pytest.fixture
def client(async_db_session: AsyncSession) -> TestClient:
    """Create a test client that uses the test database session."""

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Initialize TradingService for testing and store in app state
    from app.services.trading_service import (
        TradingService,
        _get_quote_adapter,
        set_global_trading_service,
    )

    trading_service = TradingService(_get_quote_adapter())
    app.state.trading_service = trading_service
    set_global_trading_service(trading_service)

    return TestClient(app)


@pytest_asyncio.fixture
async def test_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a new async database session for a test - alias for async_db_session."""
    # Create a separate engine to avoid event loop conflicts
    import os

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    test_engine = create_async_engine(database_url, echo=False, future=True)
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        # Ensure tables exist and clean up
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
            await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
            await conn.commit()

        # Create session
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    finally:
        await test_engine.dispose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer testuser"}


@pytest.fixture
def mock_trading_service(mocker: MagicMock) -> MagicMock:
    """Mock the trading service."""
    mock_service = mocker.patch("app.services.trading_service.trading_service")
    return mock_service  # type: ignore


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Standard database session fixture - all tests should use this."""
    async for session in async_db_session():
        yield session
