"""
E2E test configuration and fixtures.

Provides test database isolation, test client setup, and other fixtures
for end-to-end testing scenarios.
"""

import asyncio

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app

# Import models to ensure they're registered with Base
from app.models.database import trading  # noqa: F401
from app.models.database.base import Base
from app.storage.database import get_async_session


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    yield loop

    # Clean up pending tasks and close loop properly
    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if pending_tasks:
        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))

    if not loop.is_closed():
        loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_async_session() -> AsyncSession:
    """Create a test database session for each test with isolated engine."""
    import os

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    # Create a new engine for this test to avoid event loop conflicts
    test_engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )

    try:
        # Create all tables (idempotent)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Clean up any existing test data first
            await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
            await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
            await conn.commit()

        # Create session factory for this test engine
        TestSessionLocal = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create session
        async with TestSessionLocal() as session:
            try:
                yield session
                # Try to commit any pending transactions
                await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except:
                    pass
                raise
            finally:
                await session.close()

        # Clean up test data for isolation
        try:
            async with test_engine.begin() as conn:
                await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
                await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
                await conn.commit()
        except Exception as e:
            print(f"Test cleanup warning: {e}")

    finally:
        # Properly dispose of the test engine
        await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_client():
    """Create a test client with shared database session."""
    # Import shared fixtures
    from tests.conftest import get_async_session as shared_get_async_session

    # Override database dependency to use shared session management
    app.dependency_overrides[get_async_session] = shared_get_async_session

    # Initialize TradingService for testing and store in app state
    from app.mcp.tools import set_mcp_trading_service
    from app.services.trading_service import TradingService, _get_quote_adapter

    trading_service = TradingService(_get_quote_adapter())
    app.state.trading_service = trading_service
    set_mcp_trading_service(trading_service)

    try:
        # Create async client with ASGI transport
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        # Clean up override and state
        app.dependency_overrides.clear()
        # Clean up app state
        if hasattr(app.state, "trading_service"):
            delattr(app.state, "trading_service")


@pytest.fixture(scope="function")
def sync_test_client():
    """Create a synchronous test client for simple tests."""
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def test_account_data():
    """Provide test account data for E2E tests."""
    return {
        "owner": "test_user_e2e",
        "cash_balance": 100000.0,
        "name": "E2E Test Account",
    }


@pytest_asyncio.fixture(scope="function")
async def test_order_data():
    """Provide test order data for E2E tests."""
    return {
        "symbol": "AAPL",
        "order_type": "buy",
        "quantity": 100,
        "price": 150.0,
        "condition": "limit",
    }


@pytest_asyncio.fixture(scope="function")
async def created_test_account(test_client: AsyncClient, test_account_data: dict):
    """Return a placeholder account ID since accounts are auto-created."""
    # In the current API design, accounts are created automatically by TradingService
    # when first accessed, so we just return a test account identifier
    return "default"


@pytest.fixture(scope="session")
def test_symbols():
    """Provide a list of test symbols for E2E tests."""
    return ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]


@pytest_asyncio.fixture(scope="function")
async def populated_test_account(
    test_client: AsyncClient, created_test_account: str, test_symbols: list
):
    """Create a test account with some initial positions."""
    account_id = created_test_account

    # Create some orders (they won't be automatically filled in current system)
    orders = []
    for i, symbol in enumerate(test_symbols[:3]):  # Use first 3 symbols
        order_data = {
            "symbol": symbol,
            "order_type": "buy",
            "quantity": (i + 1) * 10,  # 10, 20, 30 shares
            "price": 100.0 + i * 50,  # $100, $150, $200
            "condition": "limit",
        }

        response = await test_client.post("/api/v1/trading/order", json=order_data)
        assert response.status_code == 200
        order = response.json()
        orders.append(order)

    return {"account_id": account_id, "orders": orders, "symbols": test_symbols[:3]}


class E2ETestHelpers:
    """Helper methods for E2E testing."""

    @staticmethod
    async def wait_for_order_fill(
        client: AsyncClient, order_id: str, timeout: int = 5, status: str = "filled"
    ) -> dict:
        """Wait for an order to reach specified status."""
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            response = await client.get(f"/api/v1/trading/order/{order_id}")
            assert response.status_code == 200
            order = response.json()

            if order["status"] == status:
                return order

            await asyncio.sleep(0.1)

        raise TimeoutError(
            f"Order {order_id} did not reach status {status} within {timeout}s"
        )

    @staticmethod
    async def get_account_balance(client: AsyncClient, account_id: str) -> float:
        """Get current account balance."""
        response = await client.get("/api/v1/portfolio/")
        assert response.status_code == 200
        portfolio = response.json()
        return portfolio["cash_balance"]

    @staticmethod
    async def get_position_count(client: AsyncClient, account_id: str) -> int:
        """Get number of positions in account."""
        response = await client.get("/api/v1/portfolio/positions")
        assert response.status_code == 200
        positions = response.json()
        return len(positions)

    @staticmethod
    async def create_and_fill_order(
        client: AsyncClient,
        account_id: str,
        order_data: dict,
        fill_price: float | None = None,
    ) -> dict:
        """Create an order (note: immediate filling not supported in current API)."""
        # Create order
        response = await client.post("/api/v1/trading/order", json=order_data)
        assert response.status_code == 200
        order = response.json()

        # Note: Current API doesn't support immediate order execution/filling
        # Orders remain in pending status until executed by the trading engine

        return order


@pytest.fixture(scope="function")
def e2e_helpers():
    """Provide E2E test helper methods."""
    return E2ETestHelpers()
