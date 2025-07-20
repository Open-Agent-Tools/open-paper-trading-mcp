"""
E2E test configuration and fixtures.

Provides test database isolation, test client setup, and other fixtures
for end-to-end testing scenarios.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database.base import Base
from app.storage.database import get_async_session


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session for each test."""
    # Create test database engine
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///./test_e2e.db", echo=False, future=True
    )

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    TestingSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create session
    async with TestingSessionLocal() as session:
        yield session

    # Clean up
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture(scope="function")
async def test_client(test_async_session: AsyncSession):
    """Create a test client with isolated database."""

    # Override database dependency
    async def override_get_async_session():
        yield test_async_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Create async client
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up override
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_test_client():
    """Create a synchronous test client for simple tests."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
async def test_account_data():
    """Provide test account data for E2E tests."""
    return {
        "owner": "test_user_e2e",
        "cash_balance": 100000.0,
        "name": "E2E Test Account",
    }


@pytest.fixture(scope="function")
async def test_order_data():
    """Provide test order data for E2E tests."""
    return {
        "symbol": "AAPL",
        "order_type": "buy",
        "quantity": 100,
        "price": 150.0,
        "condition": "limit",
    }


@pytest.fixture(scope="function")
async def created_test_account(test_client: AsyncClient, test_account_data: dict):
    """Create a test account and return its ID."""
    response = await test_client.post("/api/v1/accounts", json=test_account_data)
    assert response.status_code == 201
    account = response.json()
    return account["id"]


@pytest.fixture(scope="session")
def test_symbols():
    """Provide a list of test symbols for E2E tests."""
    return ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]


@pytest.fixture(scope="function")
async def populated_test_account(
    test_client: AsyncClient, created_test_account: str, test_symbols: list
):
    """Create a test account with some initial positions."""
    account_id = created_test_account

    # Create some orders to establish positions
    orders = []
    for i, symbol in enumerate(test_symbols[:3]):  # Use first 3 symbols
        order_data = {
            "symbol": symbol,
            "order_type": "buy",
            "quantity": (i + 1) * 10,  # 10, 20, 30 shares
            "price": 100.0 + i * 50,  # $100, $150, $200
            "condition": "limit",
        }

        response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=order_data
        )
        assert response.status_code == 201
        order = response.json()
        orders.append(order)

        # Execute the order to create position
        execution_data = {"status": "filled"}
        exec_response = await test_client.patch(
            f"/api/v1/orders/{order['id']}", json=execution_data
        )
        assert exec_response.status_code == 200

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
            response = await client.get(f"/api/v1/orders/{order_id}")
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
        response = await client.get(f"/api/v1/accounts/{account_id}")
        assert response.status_code == 200
        account = response.json()
        return account["cash_balance"]

    @staticmethod
    async def get_position_count(client: AsyncClient, account_id: str) -> int:
        """Get number of positions in account."""
        response = await client.get(f"/api/v1/accounts/{account_id}/positions")
        assert response.status_code == 200
        positions = response.json()
        return len(positions)

    @staticmethod
    async def create_and_fill_order(
        client: AsyncClient, account_id: str, order_data: dict, fill_price: float = None
    ) -> dict:
        """Create an order and immediately fill it."""
        # Create order
        response = await client.post(
            f"/api/v1/accounts/{account_id}/orders", json=order_data
        )
        assert response.status_code == 201
        order = response.json()

        # Fill order
        fill_data = {
            "status": "filled",
            "filled_price": fill_price or order_data.get("price", 150.0),
        }
        fill_response = await client.patch(
            f"/api/v1/orders/{order['id']}", json=fill_data
        )
        assert fill_response.status_code == 200

        return order


@pytest.fixture(scope="function")
def e2e_helpers():
    """Provide E2E test helper methods."""
    return E2ETestHelpers()
