"""
Comprehensive test coverage for OptimizedOrderQueries class.

This module provides complete test coverage for the performance-optimized
database queries used in order management operations, covering all query patterns,
optimization features, and edge cases.

Test Coverage Areas:
- Trigger condition filtering and monitoring
- Status and type-based order filtering
- Symbol-based order queries
- Account summary and aggregation
- Performance metrics and execution analysis
- Stop loss and trailing stop logic
- Queue depth and frequency analysis
- Bulk operations and cleanup functionality
- Database session handling and async patterns
- Performance optimization validation
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.schemas.orders import OrderCondition, OrderStatus, OrderType
from app.services.query_optimization import (
    OptimizedOrderQueries,
    get_optimized_order_queries,
)


async def create_test_account(db_session: AsyncSession, account_id: str) -> DBAccount:
    """Helper function to create a test account for order tests."""
    # Check if account already exists
    stmt = select(DBAccount).where(DBAccount.id == account_id)
    result = await db_session.execute(stmt)
    existing_account = result.scalar_one_or_none()

    if existing_account:
        return existing_account

    account = DBAccount(
        id=account_id,
        owner=f"test_user_{account_id[:8]}",
        cash_balance=100000.0,
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest.mark.database
class TestOptimizedOrderQueriesInitialization:
    """Test OptimizedOrderQueries class initialization and factory function."""

    def test_optimized_order_queries_initialization(self):
        """Test creating OptimizedOrderQueries instance with session."""
        mock_session = MagicMock()
        queries = OptimizedOrderQueries(mock_session)

        assert queries.session == mock_session
        assert isinstance(queries, OptimizedOrderQueries)

    def test_get_optimized_order_queries_factory(self):
        """Test factory function for creating OptimizedOrderQueries."""
        mock_session = MagicMock()
        queries = get_optimized_order_queries(mock_session)

        assert isinstance(queries, OptimizedOrderQueries)
        assert queries.session == mock_session


@pytest.mark.database
class TestGetPendingTriggeredOrders:
    """Test get_pending_triggered_orders method."""

    @pytest.mark.asyncio
    async def test_get_pending_triggered_orders_success(self, db_session: AsyncSession):
        """Test retrieving pending orders with trigger conditions."""
        # Create test account
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with trigger conditions
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.PENDING,
                "condition": OrderCondition.STOP,
                "stop_price": 150.0,  # Has stop price (trigger condition)
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
                "condition": OrderCondition.MARKET,
                "trail_percent": 5.0,  # Has trailing percent (trigger condition)
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
                "condition": OrderCondition.MARKET,
                # No trigger conditions - should not be returned
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        # Create queries instance
        queries = OptimizedOrderQueries(db_session)

        # Get pending triggered orders
        result = await queries.get_pending_triggered_orders(limit=10)

        # Verify results
        assert len(result) == 2  # Two orders with trigger conditions

        symbols = {order.symbol for order in result}
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "MSFT" not in symbols  # No trigger conditions

        # Verify all returned orders have trigger conditions
        for order in result:
            assert order.status == OrderStatus.PENDING
            has_trigger = (
                order.stop_price is not None
                or order.trail_percent is not None
                or order.trail_amount is not None
            )
            assert has_trigger

    @pytest.mark.asyncio
    async def test_get_pending_triggered_orders_limit(self, db_session: AsyncSession):
        """Test limit parameter for pending triggered orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create more orders than limit
        for i in range(5):
            order = DBOrder(
                id=f"order_{i}_{uuid.uuid4().hex[:8]}",
                account_id=account_id,
                symbol=f"STOCK{i}",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                condition=OrderCondition.STOP,
                stop_price=150.0 + i,
            )
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Test with limit of 3
        result = await queries.get_pending_triggered_orders(limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_pending_triggered_orders_empty_result(
        self, db_session: AsyncSession
    ):
        """Test get_pending_triggered_orders with no matching orders."""
        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_pending_triggered_orders()

        assert result == []


@pytest.mark.database
class TestGetOrdersByStatusAndType:
    """Test get_orders_by_status_and_type method."""

    @pytest.mark.asyncio
    async def test_get_orders_by_status_only(self, db_session: AsyncSession):
        """Test filtering orders by status only."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different statuses and types
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get filled orders only
        result = await queries.get_orders_by_status_and_type(status=OrderStatus.FILLED)

        assert len(result) == 2
        for order in result:
            assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_orders_by_status_and_type(self, db_session: AsyncSession):
        """Test filtering orders by both status and type."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different combinations
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get filled BUY orders only
        result = await queries.get_orders_by_status_and_type(
            status=OrderStatus.FILLED, order_type=OrderType.BUY
        )

        assert len(result) == 1
        assert result[0].status == OrderStatus.FILLED
        assert result[0].order_type == OrderType.BUY
        assert result[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_orders_by_status_and_type_ordering(
        self, db_session: AsyncSession
    ):
        """Test that results are ordered by created_at desc."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with specific timestamps
        base_time = datetime.now(UTC).replace(tzinfo=None)

        orders_data = [
            {
                "id": f"order_1_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(hours=2),
            },
            {
                "id": f"order_2_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.BUY,
                "quantity": 50,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(hours=1),
            },
            {
                "id": f"order_3_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.FILLED,
                "created_at": base_time,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_orders_by_status_and_type(status=OrderStatus.FILLED)

        # Should be ordered by created_at desc (newest first)
        assert len(result) == 3
        assert result[0].symbol == "MSFT"  # Most recent
        assert result[1].symbol == "GOOGL"  # Middle
        assert result[2].symbol == "AAPL"  # Oldest


@pytest.mark.database
class TestGetOrdersForSymbol:
    """Test get_orders_for_symbol method."""

    @pytest.mark.asyncio
    async def test_get_orders_for_symbol_all_statuses(self, db_session: AsyncSession):
        """Test getting all orders for a specific symbol."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders for different symbols
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.FILLED,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get all AAPL orders
        result = await queries.get_orders_for_symbol("AAPL")

        assert len(result) == 2
        for order in result:
            assert order.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_orders_for_symbol_with_status(self, db_session: AsyncSession):
        """Test getting orders for symbol filtered by status."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create AAPL orders with different statuses
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 25,
                "status": OrderStatus.CANCELLED,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get only FILLED AAPL orders
        result = await queries.get_orders_for_symbol("AAPL", status=OrderStatus.FILLED)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_orders_for_symbol_limit(self, db_session: AsyncSession):
        """Test limit parameter for symbol orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create more orders than limit
        for i in range(5):
            order = DBOrder(
                id=f"order_{i}_{uuid.uuid4().hex[:8]}",
                account_id=account_id,
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.FILLED,
            )
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Test with limit of 3
        result = await queries.get_orders_for_symbol("AAPL", limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_orders_for_symbol_nonexistent(self, db_session: AsyncSession):
        """Test getting orders for non-existent symbol."""
        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_orders_for_symbol("NONEXISTENT")

        assert result == []


@pytest.mark.database
class TestGetAccountOrdersSummary:
    """Test get_account_orders_summary method."""

    @pytest.mark.asyncio
    async def test_get_account_orders_summary_basic(self, db_session: AsyncSession):
        """Test basic account orders summary."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different statuses and types
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "TSLA",
                "order_type": OrderType.SELL,
                "quantity": 25,
                "status": OrderStatus.CANCELLED,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_account_orders_summary(account_id)

        # Verify summary structure
        assert "status_counts" in result
        assert "type_counts" in result
        assert "total_orders" in result

        # Verify status counts
        assert result["status_counts"][OrderStatus.FILLED] == 2
        assert result["status_counts"][OrderStatus.PENDING] == 1
        assert result["status_counts"][OrderStatus.CANCELLED] == 1

        # Verify type counts
        assert result["type_counts"][OrderType.BUY] == 2
        assert result["type_counts"][OrderType.SELL] == 2

        # Verify total
        assert result["total_orders"] == 4

    @pytest.mark.asyncio
    async def test_get_account_orders_summary_with_date_range(
        self, db_session: AsyncSession
    ):
        """Test account orders summary with date filtering."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different timestamps
        base_time = datetime.now(UTC).replace(tzinfo=None)

        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(days=10),  # Outside range
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(days=5),  # In range
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
                "created_at": base_time - timedelta(days=2),  # In range
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Filter to last 7 days
        start_date = base_time - timedelta(days=7)
        end_date = base_time

        result = await queries.get_account_orders_summary(
            account_id, start_date=start_date, end_date=end_date
        )

        # Should only include 2 orders in date range
        assert result["total_orders"] == 2
        assert result["status_counts"][OrderStatus.FILLED] == 1
        assert result["status_counts"][OrderStatus.PENDING] == 1

    @pytest.mark.asyncio
    async def test_get_account_orders_summary_empty_account(
        self, db_session: AsyncSession
    ):
        """Test account orders summary for account with no orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_account_orders_summary(account_id)

        assert result["status_counts"] == {}
        assert result["type_counts"] == {}
        assert result["total_orders"] == 0


@pytest.mark.database
class TestGetRecentFilledOrders:
    """Test get_recent_filled_orders method."""

    @pytest.mark.asyncio
    async def test_get_recent_filled_orders_success(self, db_session: AsyncSession):
        """Test getting recent filled orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different statuses and fill times
        base_time = datetime.now(UTC).replace(tzinfo=None)

        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(hours=2),  # Recent
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(days=2),  # Too old
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
                "filled_at": None,  # Not filled
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "TSLA",
                "order_type": OrderType.SELL,
                "quantity": 25,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(hours=12),  # Recent
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get orders filled in last 24 hours
        result = await queries.get_recent_filled_orders(hours=24)

        # Should return 2 recent filled orders
        assert len(result) == 2

        symbols = {order.symbol for order in result}
        assert "AAPL" in symbols
        assert "TSLA" in symbols
        assert "GOOGL" not in symbols  # Too old
        assert "MSFT" not in symbols  # Not filled

        # Verify all are filled
        for order in result:
            assert order.status == OrderStatus.FILLED
            assert order.filled_at is not None

    @pytest.mark.asyncio
    async def test_get_recent_filled_orders_custom_timeframe(
        self, db_session: AsyncSession
    ):
        """Test get_recent_filled_orders with custom timeframe."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create filled order 6 hours ago
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.FILLED,
            filled_at=base_time - timedelta(hours=6),
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Should find order with 12 hour window
        result_12h = await queries.get_recent_filled_orders(hours=12)
        assert len(result_12h) == 1

        # Should not find order with 4 hour window
        result_4h = await queries.get_recent_filled_orders(hours=4)
        assert len(result_4h) == 0

    @pytest.mark.asyncio
    async def test_get_recent_filled_orders_ordering(self, db_session: AsyncSession):
        """Test that recent filled orders are ordered by filled_at desc."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create multiple filled orders
        orders_data = [
            {
                "id": f"order_1_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(hours=3),
            },
            {
                "id": f"order_2_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(hours=1),  # Most recent
            },
            {
                "id": f"order_3_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.FILLED,
                "filled_at": base_time - timedelta(hours=2),
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_recent_filled_orders(hours=24)

        # Should be ordered by filled_at desc (most recent first)
        assert len(result) == 3
        assert result[0].symbol == "GOOGL"  # Most recent (1 hour ago)
        assert result[1].symbol == "MSFT"  # Middle (2 hours ago)
        assert result[2].symbol == "AAPL"  # Oldest (3 hours ago)


@pytest.mark.database
class TestGetOrderExecutionMetrics:
    """Test get_order_execution_metrics method."""

    @pytest.mark.asyncio
    async def test_get_order_execution_metrics_success(self, db_session: AsyncSession):
        """Test order execution metrics calculation."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create filled orders with known execution times
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(minutes=10),
                "filled_at": base_time - timedelta(minutes=8),  # 2 min execution
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(minutes=20),
                "filled_at": base_time - timedelta(minutes=16),  # 4 min execution
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,  # Not filled
                "created_at": base_time - timedelta(minutes=5),
                "filled_at": None,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get metrics for date range covering all orders
        start_date = base_time - timedelta(hours=1)
        end_date = base_time

        result = await queries.get_order_execution_metrics(start_date, end_date)

        # Verify metrics structure
        assert "avg_execution_time_seconds" in result
        assert "fill_rates_by_type" in result

        # Average execution time should be (120 + 240) / 2 = 180 seconds
        expected_avg = 180.0
        actual_avg = float(result["avg_execution_time_seconds"])
        assert abs(actual_avg - expected_avg) < 1.0

        # Verify fill rates
        fill_rates = result["fill_rates_by_type"]
        assert OrderType.BUY in fill_rates
        assert OrderType.SELL in fill_rates

        # BUY: 1 filled out of 2 total = 50%
        buy_rate = fill_rates[OrderType.BUY]
        assert buy_rate["total"] == 2
        assert buy_rate["filled"] == 1
        assert buy_rate["rate"] == 0.5

        # SELL: 1 filled out of 1 total = 100%
        sell_rate = fill_rates[OrderType.SELL]
        assert sell_rate["total"] == 1
        assert sell_rate["filled"] == 1
        assert sell_rate["rate"] == 1.0

    @pytest.mark.asyncio
    async def test_get_order_execution_metrics_no_filled_orders(
        self, db_session: AsyncSession
    ):
        """Test execution metrics with no filled orders."""
        queries = OptimizedOrderQueries(db_session)

        start_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        end_date = datetime.now(UTC).replace(tzinfo=None)

        result = await queries.get_order_execution_metrics(start_date, end_date)

        assert result["avg_execution_time_seconds"] == 0
        assert result["fill_rates_by_type"] == {}


@pytest.mark.database
class TestGetStopLossCandidates:
    """Test get_stop_loss_candidates method."""

    @pytest.mark.asyncio
    async def test_get_stop_loss_candidates_buy_trigger(self, db_session: AsyncSession):
        """Test stop loss candidates for BUY orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create BUY order with stop price
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            stop_price=150.0,  # Buy when price >= 150
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Test with current price above stop price (should trigger)
        current_prices = {"AAPL": 155.0}
        result = await queries.get_stop_loss_candidates(current_prices)

        assert len(result) == 1
        order_result, price = result[0]
        assert order_result.symbol == "AAPL"
        assert price == 155.0

    @pytest.mark.asyncio
    async def test_get_stop_loss_candidates_sell_trigger(
        self, db_session: AsyncSession
    ):
        """Test stop loss candidates for SELL orders."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create SELL order with stop price
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            status=OrderStatus.PENDING,
            stop_price=140.0,  # Sell when price <= 140
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Test with current price below stop price (should trigger)
        current_prices = {"AAPL": 135.0}
        result = await queries.get_stop_loss_candidates(current_prices)

        assert len(result) == 1
        order_result, price = result[0]
        assert order_result.symbol == "AAPL"
        assert price == 135.0

    @pytest.mark.asyncio
    async def test_get_stop_loss_candidates_no_trigger(self, db_session: AsyncSession):
        """Test stop loss candidates when conditions not met."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders that shouldn't trigger
        orders_data = [
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.PENDING,
                "stop_price": 150.0,  # Buy when >= 150, current is 145
            },
            {
                "id": f"order_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
                "stop_price": 140.0,  # Sell when <= 140, current is 145
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Current prices don't meet trigger conditions
        current_prices = {"AAPL": 145.0, "GOOGL": 145.0}
        result = await queries.get_stop_loss_candidates(current_prices)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_stop_loss_candidates_missing_prices(
        self, db_session: AsyncSession
    ):
        """Test stop loss candidates when prices not available."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            stop_price=150.0,
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # No current prices provided
        current_prices = {"GOOGL": 145.0}  # Different symbol
        result = await queries.get_stop_loss_candidates(current_prices)

        assert len(result) == 0


@pytest.mark.database
class TestGetTrailingStopCandidates:
    """Test get_trailing_stop_candidates method."""

    @pytest.mark.asyncio
    async def test_get_trailing_stop_candidates_percent(self, db_session: AsyncSession):
        """Test trailing stop candidates with percentage trailing."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create SELL order with trailing percent
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            status=OrderStatus.PENDING,
            trail_percent=5.0,  # 5% trailing
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        current_prices = {"AAPL": 150.0}
        result = await queries.get_trailing_stop_candidates(current_prices)

        assert len(result) == 1
        order_result, current_price, new_stop = result[0]
        assert order_result.symbol == "AAPL"
        assert current_price == 150.0
        # For SELL order: new_stop = current_price - trail_amount
        # trail_amount = 150.0 * (5.0 / 100) = 7.5
        # new_stop = 150.0 - 7.5 = 142.5
        assert abs(new_stop - 142.5) < 0.01

    @pytest.mark.asyncio
    async def test_get_trailing_stop_candidates_amount(self, db_session: AsyncSession):
        """Test trailing stop candidates with fixed amount trailing."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create BUY order with trailing amount
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            trail_amount=10.0,  # $10 trailing
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        current_prices = {"AAPL": 150.0}
        result = await queries.get_trailing_stop_candidates(current_prices)

        assert len(result) == 1
        order_result, current_price, new_stop = result[0]
        assert order_result.symbol == "AAPL"
        assert current_price == 150.0
        # For BUY order: new_stop = current_price + trail_amount
        # new_stop = 150.0 + 10.0 = 160.0
        assert new_stop == 160.0

    @pytest.mark.asyncio
    async def test_get_trailing_stop_candidates_no_trailing(
        self, db_session: AsyncSession
    ):
        """Test trailing stop candidates with no trailing conditions."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create order without trailing stops
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            stop_price=150.0,  # Regular stop, not trailing
        )
        db_session.add(order)
        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        current_prices = {"AAPL": 155.0}
        result = await queries.get_trailing_stop_candidates(current_prices)

        assert len(result) == 0


@pytest.mark.database
class TestGetOrderQueueDepth:
    """Test get_order_queue_depth method."""

    @pytest.mark.asyncio
    async def test_get_order_queue_depth_success(self, db_session: AsyncSession):
        """Test order queue depth calculation."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders with different statuses
        orders_data = [
            # 3 PENDING orders
            {
                "id": f"order_1_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.PENDING,
            },
            {
                "id": f"order_2_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
            },
            {
                "id": f"order_3_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.PENDING,
            },
            # 2 FILLED orders
            {
                "id": f"order_4_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "TSLA",
                "order_type": OrderType.SELL,
                "quantity": 25,
                "status": OrderStatus.FILLED,
            },
            {
                "id": f"order_5_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "NVDA",
                "order_type": OrderType.BUY,
                "quantity": 10,
                "status": OrderStatus.FILLED,
            },
            # 1 CANCELLED order
            {
                "id": f"order_6_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AMD",
                "order_type": OrderType.SELL,
                "quantity": 30,
                "status": OrderStatus.CANCELLED,
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_order_queue_depth()

        # Verify queue depth counts
        assert result[OrderStatus.PENDING] == 3
        assert result[OrderStatus.FILLED] == 2
        assert result[OrderStatus.CANCELLED] == 1

    @pytest.mark.asyncio
    async def test_get_order_queue_depth_empty(self, db_session: AsyncSession):
        """Test order queue depth with no orders."""
        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_order_queue_depth()

        assert result == {}


@pytest.mark.database
class TestGetHighFrequencySymbols:
    """Test get_high_frequency_symbols method."""

    @pytest.mark.asyncio
    async def test_get_high_frequency_symbols_success(self, db_session: AsyncSession):
        """Test high frequency symbols identification."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create orders for different symbols with varying frequencies
        symbol_counts = {"AAPL": 15, "GOOGL": 8, "MSFT": 12, "TSLA": 5}

        for symbol, count in symbol_counts.items():
            for i in range(count):
                order = DBOrder(
                    id=f"order_{symbol}_{i}_{uuid.uuid4().hex[:8]}",
                    account_id=account_id,
                    symbol=symbol,
                    order_type=OrderType.BUY,
                    quantity=100,
                    status=OrderStatus.FILLED,
                    created_at=base_time - timedelta(hours=i),  # Within 24h
                )
                db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get symbols with at least 10 orders in 24 hours
        result = await queries.get_high_frequency_symbols(hours=24, min_orders=10)

        # Should return symbols with >= 10 orders, ordered by count desc
        assert len(result) == 2

        # Verify ordering (highest count first)
        assert result[0][0] == "AAPL"
        assert result[0][1] == 15
        assert result[1][0] == "MSFT"
        assert result[1][1] == 12

    @pytest.mark.asyncio
    async def test_get_high_frequency_symbols_time_filter(
        self, db_session: AsyncSession
    ):
        """Test high frequency symbols with time filtering."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create orders: some recent, some old
        orders_data = [
            # Recent orders (within 12 hours)
            *[
                {
                    "id": f"order_recent_{i}_{uuid.uuid4().hex[:8]}",
                    "account_id": account_id,
                    "symbol": "AAPL",
                    "order_type": OrderType.BUY,
                    "quantity": 100,
                    "status": OrderStatus.FILLED,
                    "created_at": base_time - timedelta(hours=i),
                }
                for i in range(12)  # 12 recent orders
            ],
            # Old orders (outside 12 hour window)
            *[
                {
                    "id": f"order_old_{i}_{uuid.uuid4().hex[:8]}",
                    "account_id": account_id,
                    "symbol": "AAPL",
                    "order_type": OrderType.BUY,
                    "quantity": 100,
                    "status": OrderStatus.FILLED,
                    "created_at": base_time - timedelta(hours=24 + i),
                }
                for i in range(10)  # 10 old orders
            ],
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Get symbols with at least 10 orders in last 12 hours
        result = await queries.get_high_frequency_symbols(hours=12, min_orders=10)

        # Should find AAPL with 12 orders (only recent ones counted)
        assert len(result) == 1
        assert result[0][0] == "AAPL"
        assert result[0][1] == 12

    @pytest.mark.asyncio
    async def test_get_high_frequency_symbols_min_threshold(
        self, db_session: AsyncSession
    ):
        """Test high frequency symbols minimum threshold."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create symbols with counts below threshold
        for i in range(5):  # Only 5 orders, below min_orders=10
            order = DBOrder(
                id=f"order_{i}_{uuid.uuid4().hex[:8]}",
                account_id=account_id,
                symbol="LOWVOL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.FILLED,
            )
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        result = await queries.get_high_frequency_symbols(min_orders=10)

        # Should return empty list (no symbols meet threshold)
        assert result == []


@pytest.mark.database
class TestBulkUpdateOrderStatus:
    """Test bulk_update_order_status method."""

    @pytest.mark.asyncio
    async def test_bulk_update_order_status_without_filled_at(
        self, db_session: AsyncSession
    ):
        """Test bulk updating order status without filled_at."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders to update
        order_ids = []
        for i in range(3):
            order_id = f"order_{i}_{uuid.uuid4().hex[:8]}"
            order_ids.append(order_id)
            order = DBOrder(
                id=order_id,
                account_id=account_id,
                symbol=f"STOCK{i}",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
            )
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Update to FILLED status
        updated_count = await queries.bulk_update_order_status(
            order_ids, OrderStatus.FILLED
        )

        await db_session.commit()

        # Verify update count
        assert updated_count == 3

        # Verify orders were updated
        for order_id in order_ids:
            stmt = select(DBOrder).where(DBOrder.id == order_id)
            result = await db_session.execute(stmt)
            order = result.scalar_one()
            assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_bulk_update_order_status_with_filled_at(
        self, db_session: AsyncSession
    ):
        """Test bulk updating order status with filled_at timestamp."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)

        # Create orders to update
        order_ids = []
        for i in range(2):
            order_id = f"order_{i}_{uuid.uuid4().hex[:8]}"
            order_ids.append(order_id)
            order = DBOrder(
                id=order_id,
                account_id=account_id,
                symbol=f"STOCK{i}",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
            )
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Update to FILLED status with filled_at
        filled_time = datetime.now(UTC).replace(tzinfo=None)
        updated_count = await queries.bulk_update_order_status(
            order_ids, OrderStatus.FILLED, filled_at=filled_time
        )

        await db_session.commit()

        # Verify update count
        assert updated_count == 2

        # Verify orders were updated with filled_at
        for order_id in order_ids:
            stmt = select(DBOrder).where(DBOrder.id == order_id)
            result = await db_session.execute(stmt)
            order = result.scalar_one()
            assert order.status == OrderStatus.FILLED
            assert order.filled_at is not None
            # Check that filled_at is close to our timestamp (within 1 second)
            assert abs((order.filled_at - filled_time).total_seconds()) < 1.0

    @pytest.mark.asyncio
    async def test_bulk_update_order_status_nonexistent_orders(
        self, db_session: AsyncSession
    ):
        """Test bulk updating non-existent order IDs."""
        queries = OptimizedOrderQueries(db_session)

        # Try to update non-existent orders
        nonexistent_ids = [f"fake_{i}" for i in range(3)]
        updated_count = await queries.bulk_update_order_status(
            nonexistent_ids, OrderStatus.FILLED
        )

        # Should return 0 updated count
        assert updated_count == 0


@pytest.mark.database
class TestCleanupOldCompletedOrders:
    """Test cleanup_old_completed_orders method."""

    @pytest.mark.asyncio
    async def test_cleanup_old_completed_orders_count(self, db_session: AsyncSession):
        """Test counting old completed orders for cleanup."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create mix of old and recent orders with different statuses
        orders_data = [
            # Old completed orders (should be counted)
            {
                "id": f"order_old_filled_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(days=100),  # Old
            },
            {
                "id": f"order_old_cancelled_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.CANCELLED,
                "created_at": base_time - timedelta(days=120),  # Old
            },
            # Recent completed orders (should not be counted)
            {
                "id": f"order_recent_filled_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.BUY,
                "quantity": 75,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(days=30),  # Recent
            },
            # Old pending orders (should not be counted)
            {
                "id": f"order_old_pending_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "TSLA",
                "order_type": OrderType.SELL,
                "quantity": 25,
                "status": OrderStatus.PENDING,
                "created_at": base_time - timedelta(days=100),  # Old but pending
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Count orders older than 90 days
        count = await queries.cleanup_old_completed_orders(days_old=90)

        # Should count 2 old completed orders (1 filled + 1 cancelled)
        assert count == 2

    @pytest.mark.asyncio
    async def test_cleanup_old_completed_orders_no_old_orders(
        self, db_session: AsyncSession
    ):
        """Test cleanup count with no old orders."""
        queries = OptimizedOrderQueries(db_session)

        count = await queries.cleanup_old_completed_orders(days_old=90)

        assert count == 0


@pytest.mark.database
class TestOptimizedOrderQueriesErrorHandling:
    """Test error handling in OptimizedOrderQueries methods."""

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test handling of database errors."""
        # Create mock session that raises database error
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Database connection failed")

        queries = OptimizedOrderQueries(mock_session)

        # Should propagate database errors
        with pytest.raises(Exception, match="Database connection failed"):
            await queries.get_pending_triggered_orders()


@pytest.mark.database
class TestOptimizedOrderQueriesIntegration:
    """Test integration scenarios for OptimizedOrderQueries."""

    @pytest.mark.asyncio
    async def test_comprehensive_order_management_workflow(
        self, db_session: AsyncSession
    ):
        """Test comprehensive workflow using multiple query methods."""
        account_id = str(uuid.uuid4())
        await create_test_account(db_session, account_id)
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create diverse set of orders
        orders_data = [
            # Pending orders with various conditions
            {
                "id": f"order_pending_1_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 100,
                "status": OrderStatus.PENDING,
                "stop_price": 150.0,
                "created_at": base_time - timedelta(hours=1),
            },
            {
                "id": f"order_pending_2_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "GOOGL",
                "order_type": OrderType.SELL,
                "quantity": 50,
                "status": OrderStatus.PENDING,
                "trail_percent": 5.0,
                "created_at": base_time - timedelta(hours=2),
            },
            # Recently filled orders
            {
                "id": f"order_filled_1_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "AAPL",
                "order_type": OrderType.BUY,
                "quantity": 200,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(hours=3),
                "filled_at": base_time - timedelta(hours=2, minutes=58),
            },
            {
                "id": f"order_filled_2_{uuid.uuid4().hex[:8]}",
                "account_id": account_id,
                "symbol": "MSFT",
                "order_type": OrderType.SELL,
                "quantity": 75,
                "status": OrderStatus.FILLED,
                "created_at": base_time - timedelta(hours=4),
                "filled_at": base_time - timedelta(hours=3, minutes=55),
            },
        ]

        for order_data in orders_data:
            order = DBOrder(**order_data)
            db_session.add(order)

        await db_session.commit()

        queries = OptimizedOrderQueries(db_session)

        # Test 1: Get pending triggered orders
        pending_triggered = await queries.get_pending_triggered_orders()
        assert len(pending_triggered) == 2

        # Test 2: Get account summary
        summary = await queries.get_account_orders_summary(account_id)
        assert summary["total_orders"] == 4
        assert summary["status_counts"][OrderStatus.PENDING] == 2
        assert summary["status_counts"][OrderStatus.FILLED] == 2

        # Test 3: Get recent filled orders
        recent_filled = await queries.get_recent_filled_orders(hours=24)
        assert len(recent_filled) == 2

        # Test 4: Get orders for specific symbol
        aapl_orders = await queries.get_orders_for_symbol("AAPL")
        assert len(aapl_orders) == 2

        # Test 5: Get queue depth
        queue_depth = await queries.get_order_queue_depth()
        assert queue_depth[OrderStatus.PENDING] == 2
        assert queue_depth[OrderStatus.FILLED] == 2

        # Test 6: Test stop loss candidates
        current_prices = {"AAPL": 155.0, "GOOGL": 2800.0}  # AAPL should trigger
        stop_candidates = await queries.get_stop_loss_candidates(current_prices)
        assert len(stop_candidates) == 1  # Only AAPL BUY order triggers

        # Test 7: Test trailing stop candidates
        trailing_candidates = await queries.get_trailing_stop_candidates(current_prices)
        assert len(trailing_candidates) == 1  # Only GOOGL has trailing stop


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
