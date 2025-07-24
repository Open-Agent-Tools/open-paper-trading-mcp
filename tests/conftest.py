import os
from collections.abc import AsyncGenerator
from typing import Any
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
    from app.services.trading_service import TradingService, _get_quote_adapter

    trading_service = TradingService(_get_quote_adapter())
    app.state.trading_service = trading_service

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
def mock_trading_service(mocker: Any) -> MagicMock:
    """Mock the trading service."""
    mock_service = mocker.patch("app.services.trading_service.trading_service")
    return mock_service


# Enhanced Test Fixtures for Integration Testing


@pytest_asyncio.fixture
async def test_account_data(async_db_session: AsyncSession) -> dict[str, Any]:
    """Create test account with sample data."""
    import uuid

    from app.models.database.trading import Account as DBAccount
    from app.models.database.trading import Position as DBPosition

    # Create test account
    account = DBAccount(
        id=str(uuid.uuid4()),
        owner="test_user",
        cash_balance=100000.0,
        buying_power=200000.0,
    )
    async_db_session.add(account)
    await async_db_session.commit()
    await async_db_session.refresh(account)

    # Create test positions
    positions = [
        DBPosition(
            id=str(uuid.uuid4()),
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
        ),
        DBPosition(
            id=str(uuid.uuid4()),
            account_id=account.id,
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0,
            current_price=2750.0,
            unrealized_pnl=-2500.0,
        ),
    ]

    for position in positions:
        async_db_session.add(position)

    await async_db_session.commit()

    return {
        "account": account,
        "positions": positions,
        "account_id": account.id,
        "owner": account.owner,
    }


@pytest.fixture
def sample_stock_quotes() -> dict[str, Any]:
    """Create sample stock quotes for testing."""
    from datetime import datetime

    from app.schemas.trading import StockQuote

    return {
        "AAPL": StockQuote(
            symbol="AAPL",
            price=155.0,
            change=5.0,
            change_percent=3.33,
            volume=1000000,
            last_updated=datetime.now(),
        ),
        "GOOGL": StockQuote(
            symbol="GOOGL",
            price=2750.0,
            change=-50.0,
            change_percent=-1.79,
            volume=500000,
            last_updated=datetime.now(),
        ),
        "MSFT": StockQuote(
            symbol="MSFT",
            price=380.0,
            change=2.5,
            change_percent=0.66,
            volume=800000,
            last_updated=datetime.now(),
        ),
    }


@pytest.fixture
def sample_order_data() -> dict[str, Any]:
    """Create sample order data for testing."""
    from app.schemas.orders import OrderCreate, OrderType

    from app.schemas.orders import OrderCondition
    
    return {
        "buy_market": OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=None,  # Market order
            condition=OrderCondition.MARKET,
        ),
        "sell_limit": OrderCreate(
            symbol="AAPL", 
            order_type=OrderType.SELL, 
            quantity=50, 
            price=160.0,
            condition=OrderCondition.LIMIT,
        ),
        "buy_limit": OrderCreate(
            symbol="GOOGL", 
            order_type=OrderType.BUY, 
            quantity=10, 
            price=2700.0,
            condition=OrderCondition.LIMIT,
        ),
    }


@pytest_asyncio.fixture
async def trading_service_with_data(
    async_db_session: AsyncSession, test_account_data: dict[str, Any]
) -> Any:
    """Create a TradingService instance with test data and mocked quote adapter."""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock

    from app.schemas.trading import StockQuote
    from app.services.trading_service import TradingService

    # Create trading service
    service = TradingService(account_owner=test_account_data["owner"])

    # Override the database session via dependency injection
    from unittest.mock import patch
    with patch.object(service, '_get_async_db_session', return_value=async_db_session):
        pass  # Service will use the mocked session

    # Mock quote adapter with realistic data
    mock_adapter = MagicMock()
    mock_adapter.get_quote = AsyncMock()
    mock_adapter.get_quote.side_effect = lambda symbol: StockQuote(
        symbol=symbol,
        price={"AAPL": 155.0, "GOOGL": 2750.0, "MSFT": 380.0}.get(symbol, 100.0),
        change=0.0,
        change_percent=0.0,
        volume=1000000,
        last_updated=datetime.now(),
    )

    service.quote_adapter = mock_adapter

    return service


@pytest.fixture
def mock_quote_adapter() -> MagicMock:
    """Create a mock quote adapter for testing."""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock

    from app.schemas.trading import StockQuote

    adapter = MagicMock()
    adapter.get_quote = AsyncMock()

    # Default quote response
    adapter.get_quote.return_value = StockQuote(
        symbol="TEST",
        price=100.0,
        change=0.0,
        change_percent=0.0,
        volume=1000000,
        last_updated=datetime.now(),
    )

    return adapter


@pytest_asyncio.fixture
async def integration_test_client(
    async_db_session: AsyncSession, test_account_data: dict[str, Any]
) -> TestClient:
    """Create a test client configured for integration testing."""
    from unittest.mock import AsyncMock

    from app.services.trading_service import TradingService

    # Override database session dependency
    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Create and configure trading service for integration testing
    trading_service = TradingService(account_owner=test_account_data["owner"])
    # Note: Database session will be overridden by FastAPI dependency injection

    # Store in app state
    app.state.trading_service = trading_service

    return TestClient(app)


@pytest.fixture
def test_scenarios() -> dict[str, Any]:
    """Create common test scenarios for integration testing."""
    return {
        "happy_path_order": {
            "symbol": "AAPL",
            "quantity": 100,
            "order_type": "buy",
            "expected_cost": 15500.0,  # 100 * 155.0
        },
        "insufficient_funds": {
            "symbol": "BERKB",  # Expensive stock
            "quantity": 1000,
            "order_type": "buy",
            "price": 500000.0,  # Would exceed account balance
        },
        "partial_sell": {
            "symbol": "AAPL",
            "quantity": 50,  # Sell half of existing position
            "order_type": "sell",
        },
    }


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Standard database session fixture - all tests should use this."""
    # Use the same logic as async_db_session but avoid circular reference
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


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
