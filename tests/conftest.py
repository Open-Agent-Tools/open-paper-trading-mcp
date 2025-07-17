import os
import pytest
from fastapi.testclient import TestClient
from typing import Generator, Any, AsyncGenerator
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

# Set the TESTING environment variable BEFORE importing the app
os.environ["TESTING"] = "True"

from app.main import app
from app.storage.database import get_async_session, AsyncSessionLocal, async_engine
from app.models.database.base import Base


@pytest.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a new async database session for a test and handle setup/teardown."""
    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
    
    # Clean up tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client(async_db_session: AsyncSession) -> TestClient:
    """Create a test client that uses the test database session."""

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer testuser"}


@pytest.fixture
def mock_trading_service(mocker: MagicMock) -> MagicMock:
    """Mock the trading service."""
    mock_service = mocker.patch("app.services.trading_service.trading_service")
    return mock_service  # type: ignore
