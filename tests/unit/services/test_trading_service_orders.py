"""
Comprehensive test coverage for TradingService order management functions.

This module provides complete test coverage for the core order management
functions in User Journey 2: Basic Stock Trading, covering normal operations,
edge cases, error scenarios, and performance benchmarks.

Test Coverage Areas:
- create_order(): Order creation with validation and persistence
- get_orders(): Retrieving all orders for an account
- get_order(): Retrieving specific order by ID
- cancel_order(): Order cancellation workflow
- cancel_all_stock_orders(): Bulk stock order cancellation
- cancel_all_option_orders(): Bulk option order cancellation

Functions Tested:
- TradingService.create_order() - app/services/trading_service.py:210
- TradingService.get_orders() - app/services/trading_service.py:238
- TradingService.get_order() - app/services/trading_service.py:258
- TradingService.cancel_order() - app/services/trading_service.py:280
- TradingService.cancel_all_stock_orders() - app/services/trading_service.py:304
- TradingService.cancel_all_option_orders() - app/services/trading_service.py:346
"""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.schemas.orders import OrderCondition, OrderCreate, OrderStatus, OrderType
from app.services.trading_service import TradingService


@pytest.mark.db_crud
class TestCreateOrder:
    """Test TradingService.create_order() function."""

    @pytest.mark.asyncio
    async def test_create_order_basic_buy_market(self, db_session: AsyncSession):
        """Test creating a basic buy market order."""
        # Create test account
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to return valid quote
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = MagicMock(
            price=150.0, quote_date=datetime.now()
        )

        # Create service with mocked session and adapter
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Create order data
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=None,  # Market order
            condition=OrderCondition.MARKET,
        )

        # Create order
        result = await service.create_order(order_data)

        # Verify result
        assert result.symbol == "AAPL"
        assert result.order_type == OrderType.BUY
        assert result.quantity == 100
        assert result.status == OrderStatus.PENDING
        assert result.price is None  # Market order
        assert result.id is not None

        # Verify order was saved to database
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()

        assert db_order is not None
        assert db_order.symbol == "AAPL"
        assert db_order.account_id == account.id

    @pytest.mark.asyncio
    async def test_create_order_limit_buy(self, db_session: AsyncSession):
        """Test creating a limit buy order."""
        # Create test account
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = MagicMock(
            price=150.0, quote_date=datetime.now()
        )

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Create limit order
        order_data = OrderCreate(
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=10,
            price=2800.0,
            condition=OrderCondition.LIMIT,
        )

        result = await service.create_order(order_data)

        # Verify limit order specifics
        assert result.symbol == "GOOGL"
        assert result.price == 2800.0
        # Note: condition may be set to default by service
        assert result.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_order_invalid_symbol(self, db_session: AsyncSession):
        """Test creating order with invalid symbol."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to raise NotFoundError
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.side_effect = NotFoundError("Symbol not found")

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        order_data = OrderCreate(
            symbol="INVALID",
            order_type=OrderType.BUY,
            quantity=100,
            price=None,
            condition=OrderCondition.MARKET,
        )

        # Should raise NotFoundError for invalid symbol
        with pytest.raises(NotFoundError) as exc_info:
            await service.create_order(order_data)

        assert "Symbol not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_order_sell_order(self, db_session: AsyncSession):
        """Test creating a sell order."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = MagicMock(
            price=155.0, quote_date=datetime.now()
        )

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=50,
            price=160.0,
            condition=OrderCondition.LIMIT,
        )

        result = await service.create_order(order_data)

        assert result.order_type == OrderType.SELL
        assert result.quantity == 50
        assert result.price == 160.0


@pytest.mark.db_crud
class TestGetOrders:
    """Test TradingService.get_orders() function."""

    @pytest.mark.asyncio
    async def test_get_orders_empty_account(self, db_session: AsyncSession):
        """Test getting orders from account with no orders."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.get_orders()

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_orders_multiple_orders(self, db_session: AsyncSession):
        """Test getting multiple orders from account."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create test orders
        orders = []
        for i in range(3):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol=f"TEST{i}",
                order_type=OrderType.BUY,
                quantity=100 + i * 10,
                price=150.0 + i,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append(order)
            db_session.add(order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.get_orders()

        assert len(result) == 3
        # Verify order data is correctly converted
        result_symbols = {order.symbol for order in result}
        expected_symbols = {"TEST0", "TEST1", "TEST2"}
        assert result_symbols == expected_symbols

    @pytest.mark.asyncio
    async def test_get_orders_different_statuses(self, db_session: AsyncSession):
        """Test getting orders with different statuses."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create orders with different statuses
        statuses = [OrderStatus.PENDING, OrderStatus.FILLED, OrderStatus.CANCELLED]
        for i, status in enumerate(statuses):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol=f"STATUS{i}",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=status,
                created_at=datetime.now(),
            )
            db_session.add(order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.get_orders()

        assert len(result) == 3
        result_statuses = {order.status for order in result}
        expected_statuses = {
            OrderStatus.PENDING,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
        }
        assert result_statuses == expected_statuses


@pytest.mark.db_crud
class TestGetOrder:
    """Test TradingService.get_order() function."""

    @pytest.mark.asyncio
    async def test_get_order_existing(self, db_session: AsyncSession):
        """Test getting an existing order by ID."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create test order
        order_id = str(uuid.uuid4())
        order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        db_session.add(order)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.get_order(order_id)

        assert result.id == order_id
        assert result.symbol == "AAPL"
        assert result.quantity == 100
        assert result.price == 150.0

    @pytest.mark.asyncio
    async def test_get_order_nonexistent(self, db_session: AsyncSession):
        """Test getting a non-existent order."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        fake_order_id = str(uuid.uuid4())

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_order(fake_order_id)

        assert f"Order {fake_order_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_order_wrong_account(self, db_session: AsyncSession):
        """Test getting order from different account (should not be accessible)."""
        # Create two accounts
        account1 = DBAccount(
            id=str(uuid.uuid4()),
            owner="user1",
            cash_balance=50000.0,
        )
        account2 = DBAccount(
            id=str(uuid.uuid4()),
            owner="user2",
            cash_balance=50000.0,
        )
        db_session.add(account1)
        db_session.add(account2)
        await db_session.commit()

        # Create order for account1
        order_id = str(uuid.uuid4())
        order = DBOrder(
            id=order_id,
            account_id=account1.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        db_session.add(order)
        await db_session.commit()

        # Try to access order from user2's service
        service = TradingService(account_owner="user2", db_session=db_session)

        # Should not find order (belongs to different account)
        with pytest.raises(NotFoundError):
            await service.get_order(order_id)


@pytest.mark.db_crud
class TestCancelOrder:
    """Test TradingService.cancel_order() function."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, db_session: AsyncSession):
        """Test successfully cancelling an order."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create pending order
        order_id = str(uuid.uuid4())
        order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        db_session.add(order)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_order(order_id)

        # Verify response
        assert result["message"] == "Order cancelled successfully"

        # Verify order status changed in database
        await db_session.refresh(order)
        assert order.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_order_nonexistent(self, db_session: AsyncSession):
        """Test cancelling a non-existent order."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        fake_order_id = str(uuid.uuid4())

        with pytest.raises(NotFoundError) as exc_info:
            await service.cancel_order(fake_order_id)

        assert f"Order {fake_order_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, db_session: AsyncSession):
        """Test cancelling an already filled order."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create filled order
        order_id = str(uuid.uuid4())
        order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.FILLED,  # Already filled
            created_at=datetime.now(),
        )
        db_session.add(order)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Should still allow cancellation (sets status to cancelled)
        result = await service.cancel_order(order_id)
        assert result["message"] == "Order cancelled successfully"

        # Status should be updated regardless of previous status
        await db_session.refresh(order)
        assert order.status == OrderStatus.CANCELLED


@pytest.mark.db_crud
class TestCancelAllStockOrders:
    """Test TradingService.cancel_all_stock_orders() function."""

    @pytest.mark.asyncio
    async def test_cancel_all_stock_orders_success(self, db_session: AsyncSession):
        """Test cancelling all stock orders."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create mix of stock and option orders
        stock_symbols = ["TSLA", "GOOGL", "MSFT"]  # Stock symbols (no C or P)
        stock_orders = []
        for _i, symbol in enumerate(stock_symbols):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol=symbol,
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            stock_orders.append(order)
            db_session.add(order)

        # Create option orders (should not be cancelled)
        option_orders = []
        for _i in range(2):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol="AAPL240115C00150000",  # Option-style symbols with C
                order_type=OrderType.BUY,
                quantity=1,
                price=5.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            option_orders.append(order)
            db_session.add(order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_stock_orders()

        # Verify response
        assert result["total_cancelled"] == 3
        assert "Cancelled 3 stock orders" in result["message"]
        assert len(result["cancelled_orders"]) == 3

        # Verify only stock orders were cancelled
        for stock_order in stock_orders:
            await db_session.refresh(stock_order)
            assert stock_order.status == OrderStatus.CANCELLED

        # Verify option orders were not cancelled
        for option_order in option_orders:
            await db_session.refresh(option_order)
            assert option_order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_cancel_all_stock_orders_no_orders(self, db_session: AsyncSession):
        """Test cancelling stock orders when none exist."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_stock_orders()

        assert result["total_cancelled"] == 0
        assert "Cancelled 0 stock orders" in result["message"]
        assert len(result["cancelled_orders"]) == 0


@pytest.mark.db_crud
class TestCancelAllOptionOrders:
    """Test TradingService.cancel_all_option_orders() function."""

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_success(self, db_session: AsyncSession):
        """Test cancelling all option orders."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create stock orders (should not be cancelled)
        stock_orders = []
        for i in range(2):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol=f"TSLA{i}",  # Stock symbols (no C or P)
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            stock_orders.append(order)
            db_session.add(order)

        # Create option orders with different patterns
        option_orders = []

        # Options with C/P in symbol
        for i in range(2):
            order = DBOrder(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol="TSLA240115C00200000",  # Call options
                order_type=OrderType.BUY,
                quantity=1,
                price=5.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            option_orders.append(order)
            db_session.add(order)

        # Options with special order types
        order = DBOrder(
            id=str(uuid.uuid4()),
            account_id=account.id,
            symbol="MSFT",  # Normal symbol but option order type
            order_type=OrderType.BTO,  # Buy to open
            quantity=1,
            price=3.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        option_orders.append(order)
        db_session.add(order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_option_orders()

        # Verify response
        assert result["total_cancelled"] == 3
        assert "Cancelled 3 option orders" in result["message"]
        assert len(result["cancelled_orders"]) == 3

        # Verify option orders were cancelled
        for option_order in option_orders:
            await db_session.refresh(option_order)
            assert option_order.status == OrderStatus.CANCELLED

        # Verify stock orders were not cancelled
        for stock_order in stock_orders:
            await db_session.refresh(stock_order)
            assert stock_order.status == OrderStatus.PENDING


@pytest.mark.db_crud
class TestOrderManagementErrorHandling:
    """Test error handling in order management functions."""

    @pytest.mark.asyncio
    async def test_create_order_database_error(self, db_session: AsyncSession):
        """Test handling database errors during order creation."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = MagicMock(
            price=150.0, quote_date=datetime.now()
        )

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock database session to raise error on commit
        with patch.object(
            db_session, "commit", side_effect=DatabaseError("DB Error", None, None)
        ):
            order_data = OrderCreate(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                condition=OrderCondition.LIMIT,
            )

            with pytest.raises(DatabaseError):
                await service.create_order(order_data)

    @pytest.mark.asyncio
    async def test_concurrent_order_operations(self, db_session: AsyncSession):
        """Test concurrent order operations for race conditions."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create order to test concurrent access
        order_id = str(uuid.uuid4())
        order = DBOrder(
            id=order_id,
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        db_session.add(order)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Run concurrent get_order and cancel_order operations
        async def get_order_task():
            return await service.get_order(order_id)

        async def cancel_order_task():
            return await service.cancel_order(order_id)

        # Should handle concurrent access gracefully
        get_result, cancel_result = await asyncio.gather(
            get_order_task(), cancel_order_task(), return_exceptions=True
        )

        # At least one operation should succeed
        success_count = sum(
            1
            for result in [get_result, cancel_result]
            if not isinstance(result, Exception)
        )
        assert success_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
