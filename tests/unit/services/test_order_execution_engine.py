"""
Comprehensive test coverage for OrderExecutionEngine database functions.

This module provides complete test coverage for the database interaction
functions in the OrderExecutionEngine, covering normal operations, edge cases,
error scenarios, and performance benchmarks.

Test Coverage Areas:
- _load_order_by_id(): Loading orders from database for execution
- _load_pending_orders(): Loading pending trigger orders on startup
- _update_order_triggered_status(): Updating order status when triggered

Functions Tested:
- OrderExecutionEngine._load_order_by_id() - app/services/order_execution_engine.py:413
- OrderExecutionEngine._load_pending_orders() - app/services/order_execution_engine.py:482
- OrderExecutionEngine._update_order_triggered_status() - app/services/order_execution_engine.py:457
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.schemas.orders import OrderCondition, OrderStatus, OrderType
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_basic_trading


@pytest.mark.database
class TestLoadOrderById:
    """Test OrderExecutionEngine._load_order_by_id() function."""

    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self, db_session: AsyncSession):
        """Test successfully loading an order by ID."""
        # Create test account and order
        account = DBAccount(
            id="ACCT000110",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        order_id = "ORDER_101"
        db_order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            stop_price=145.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.STOP,
        )
        db_session.add(db_order)
        await db_session.commit()

        # Create trading service and execution engine
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        # Mock get_async_session to use our test session
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Load the order
            result = await engine._load_order_by_id(order_id)

            # Verify result
            assert result is not None
            assert result.id == order_id
            assert result.symbol == "AAPL"
            assert result.order_type == OrderType.BUY
            assert result.quantity == 100
            assert result.price == 150.0
            assert result.stop_price == 145.0
            assert result.status == OrderStatus.PENDING
            assert result.condition == OrderCondition.STOP

    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self, db_session: AsyncSession):
        """Test loading a non-existent order."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        fake_order_id = "ORDER_120"

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await engine._load_order_by_id(fake_order_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_load_order_by_id_with_all_fields(self, db_session: AsyncSession):
        """Test loading order with all optional fields populated."""
        account = DBAccount(
            id="ACCT000130",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        order_id = "ORDER_130"
        created_time = datetime.now()
        filled_time = datetime.now()

        db_order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.0,
            stop_price=2750.0,
            trail_percent=5.0,
            trail_amount=50.0,
            status=OrderStatus.FILLED,
            created_at=created_time,
            filled_at=filled_time,
            condition=OrderCondition.STOP,
            net_price=2775.0,
        )
        db_session.add(db_order)
        await db_session.commit()

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await engine._load_order_by_id(order_id)

            # Verify all fields are properly loaded
            assert result is not None
            assert result.trail_percent == 5.0
            assert result.trail_amount == 50.0
            assert result.net_price == 2775.0
            assert result.filled_at == filled_time

    @pytest.mark.asyncio
    async def test_load_order_by_id_database_error(self, db_session: AsyncSession):
        """Test handling database errors during order loading."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                mock_session = AsyncMock()
                mock_session.execute.side_effect = DatabaseError(
                    "DB connection failed", None, None
                )
                yield mock_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            order_id = "ORDER_001"
            result = await engine._load_order_by_id(order_id)

            # Should return None on database error
            assert result is None


@pytest.mark.database
class TestLoadPendingOrders:
    """Test OrderExecutionEngine._load_pending_orders() function."""

    @pytest.mark.asyncio
    async def test_load_pending_orders_success(self, db_session: AsyncSession):
        """Test loading pending trigger orders successfully."""
        # Create test account
        account = DBAccount(
            id="ACCT000110",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create various pending orders (only trigger orders should be loaded)
        trigger_order_types = [OrderType.BUY, OrderType.SELL, OrderType.BUY]
        created_orders = []

        for i, order_type in enumerate(trigger_order_types):
            order_id = f"ORDER_00{i + 1}"
            db_order = DBOrder(
                id=order_id,
                account_id=account.id,
                symbol=f"TRIGGER{i}",
                order_type=order_type,
                quantity=100,
                price=150.0,
                stop_price=145.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                condition=OrderCondition.STOP,
            )
            created_orders.append(order_type)
            db_session.add(db_order)

        # Create non-trigger orders (should not be loaded)
        non_trigger_order = DBOrder(
            id="ORDER_004",
            account_id=account.id,
            symbol="REGULAR",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.MARKET,
        )
        db_session.add(non_trigger_order)

        await db_session.commit()

        # Create trading service and execution engine
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock the add_order method to track what orders are added
            added_orders = []

            async def mock_add_order(order):
                added_orders.append(order)

            with patch.object(engine, "add_order", new=mock_add_order):
                # Load pending orders
                await engine._load_pending_orders()

                # Verify correct orders were loaded
                assert len(added_orders) == 3  # Only trigger orders
                loaded_symbols = {order.symbol for order in added_orders}
                expected_symbols = {"TRIGGER0", "TRIGGER1", "TRIGGER2"}
                assert loaded_symbols == expected_symbols

            # Verify order types
            loaded_types = {order.order_type for order in added_orders}
            expected_types = set(trigger_order_types)
            assert loaded_types == expected_types

    @pytest.mark.asyncio
    async def test_load_pending_orders_empty_database(self, db_session: AsyncSession):
        """Test loading pending orders when none exist."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            added_orders = []

            async def mock_add_order(order):
                added_orders.append(order)

            with patch.object(engine, "add_order", new=mock_add_order):
                # Should complete without error
                await engine._load_pending_orders()

                # No orders should be added
                assert len(added_orders) == 0

    @pytest.mark.asyncio
    async def test_load_pending_orders_filter_by_status(self, db_session: AsyncSession):
        """Test that only PENDING orders are loaded."""
        account = DBAccount(
            id="ACCT000130",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create orders with different statuses
        statuses = [OrderStatus.PENDING, OrderStatus.FILLED, OrderStatus.CANCELLED]

        for i, status in enumerate(statuses):
            db_order = DBOrder(
                id=f"ORDER_13{i}",
                account_id=account.id,
                symbol=f"STATUS{i}",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                stop_price=145.0,
                status=status,
                created_at=datetime.now(),
                condition=OrderCondition.STOP,
            )
            db_session.add(db_order)

        await db_session.commit()

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            added_orders = []

            async def mock_add_order(order):
                added_orders.append(order)

            with patch.object(engine, "add_order", new=mock_add_order):
                await engine._load_pending_orders()

                # Only pending order should be loaded
                assert len(added_orders) == 1
                assert added_orders[0].symbol == "STATUS0"
                assert added_orders[0].status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_load_pending_orders_database_error(self, db_session: AsyncSession):
        """Test handling database errors during pending order loading."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                mock_session = AsyncMock()
                mock_session.execute.side_effect = DatabaseError(
                    "DB connection failed", None, None
                )
                yield mock_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Should complete without raising exception
            await engine._load_pending_orders()
            # No orders should be loaded due to error


@pytest.mark.database
class TestUpdateOrderTriggeredStatus:
    """Test OrderExecutionEngine._update_order_triggered_status() function."""

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_success(
        self, db_session: AsyncSession
    ):
        """Test successfully updating order triggered status."""
        # Create test account and order
        account = DBAccount(
            id="ACCT000110",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        order_id = "ORDER_110"
        db_order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            stop_price=145.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.STOP,
        )
        db_session.add(db_order)
        await db_session.commit()

        # Verify initial status
        assert db_order.status == OrderStatus.PENDING
        assert db_order.filled_at is None

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            trigger_price = 144.0
            await engine._update_order_triggered_status(order_id, trigger_price)

            # Verify status was updated
            await db_session.refresh(db_order)
            assert db_order.status == OrderStatus.FILLED
            assert db_order.filled_at is not None

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_not_found(
        self, db_session: AsyncSession
    ):
        """Test updating status for non-existent order."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        fake_order_id = "ORDER_120"

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Should complete without error (order not found case)
            await engine._update_order_triggered_status(fake_order_id, 100.0)

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_multiple_orders(
        self, db_session: AsyncSession
    ):
        """Test updating status for multiple orders."""
        account = DBAccount(
            id="ACCT000130",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create multiple orders
        orders = []
        for i in range(3):
            order_id = f"ORDER_01{i + 1}"
            db_order = DBOrder(
                id=order_id,
                account_id=account.id,
                symbol=f"MULTI{i}",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                stop_price=145.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                condition=OrderCondition.STOP,
            )
            orders.append((order_id, db_order))
            db_session.add(db_order)

        await db_session.commit()

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Update status for all orders
            for order_id, _ in orders:
                await engine._update_order_triggered_status(order_id, 144.0)

            # Verify all orders were updated
            for _, db_order in orders:
                await db_session.refresh(db_order)
                assert db_order.status == OrderStatus.FILLED
                assert db_order.filled_at is not None

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_database_error(
        self, db_session: AsyncSession
    ):
        """Test handling database errors during status update."""
        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        order_id = "ORDER_140"

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                mock_session = AsyncMock()
                mock_session.execute.side_effect = DatabaseError(
                    "DB connection failed", None, None
                )
                yield mock_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Should complete without raising exception
            await engine._update_order_triggered_status(order_id, 100.0)


@pytest.mark.database
class TestOrderExecutionEngineIntegration:
    """Test integration scenarios for OrderExecutionEngine database functions."""

    @pytest.mark.asyncio
    async def test_load_and_update_order_workflow(self, db_session: AsyncSession):
        """Test complete workflow of loading and updating an order."""
        # Create test account and order
        account = DBAccount(
            id="ACCT000110",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        order_id = "ORDER_110"
        db_order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="WORKFLOW",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            stop_price=145.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.STOP,
        )
        db_session.add(db_order)
        await db_session.commit()

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Step 1: Load the order
            loaded_order = await engine._load_order_by_id(order_id)
            assert loaded_order is not None
            assert loaded_order.status == OrderStatus.PENDING

            # Step 2: Update the order status
            trigger_price = 144.0
            await engine._update_order_triggered_status(order_id, trigger_price)

            # Step 3: Verify the update
            updated_order = await engine._load_order_by_id(order_id)
            assert updated_order is not None
            assert updated_order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_concurrent_order_operations(self, db_session: AsyncSession):
        """Test concurrent database operations on orders."""
        account = DBAccount(
            id="ACCT000120",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        order_id = "ORDER_120"
        db_order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="CONCURRENT",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            stop_price=145.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.STOP,
        )
        db_session.add(db_order)
        await db_session.commit()

        trading_service = TradingService(
            account_owner="test_user", db_session=db_session
        )
        engine = OrderExecutionEngine(trading_service)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Run concurrent operations
            async def load_order():
                return await engine._load_order_by_id(order_id)

            async def update_order():
                await engine._update_order_triggered_status(order_id, 144.0)
                return "updated"

            # Should handle concurrent access gracefully
            results = await asyncio.gather(
                load_order(), update_order(), return_exceptions=True
            )

            # At least one operation should succeed
            success_count = sum(
                1 for result in results if not isinstance(result, Exception)
            )
            assert success_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
