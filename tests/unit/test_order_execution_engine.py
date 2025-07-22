"""
Unit tests for the OrderExecutionEngine class.

These tests verify that the order execution engine correctly monitors market data
and executes orders when trigger conditions are met.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assets import Stock
from app.models.quotes import Quote
from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.order_execution_engine import (
    OrderExecutionEngine,
    TriggerCondition,
    OrderExecutionError,
)


@pytest.fixture
def mock_trading_service():
    """Create a mock trading service."""
    service = AsyncMock()
    service.execute_order = AsyncMock()
    return service


@pytest.fixture
def mock_quote_adapter():
    """Create a mock quote adapter."""
    adapter = AsyncMock()
    adapter.get_quote = AsyncMock()
    return adapter


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def execution_engine(mock_trading_service):
    """Create an OrderExecutionEngine instance with mocked dependencies."""
    engine = OrderExecutionEngine(mock_trading_service)
    return engine


class TestTriggerCondition:
    """Tests for the TriggerCondition class."""

    def test_init(self):
        """Test TriggerCondition initialization."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=150.0,
            order_type=OrderType.SELL,
        )

        assert condition.order_id == "test_order"
        assert condition.symbol == "AAPL"
        assert condition.trigger_type == "stop_loss"
        assert condition.trigger_price == 150.0
        assert condition.order_type == OrderType.SELL
        assert condition.high_water_mark is None
        assert condition.low_water_mark is None

    def test_should_trigger_stop_loss_sell(self):
        """Test should_trigger for stop loss sell orders."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=150.0,
            order_type=OrderType.SELL,
        )

        # Price above trigger - should not trigger
        assert not condition.should_trigger(155.0)

        # Price at trigger - should trigger
        assert condition.should_trigger(150.0)

        # Price below trigger - should trigger
        assert condition.should_trigger(145.0)

    def test_should_trigger_stop_loss_buy(self):
        """Test should_trigger for stop loss buy orders."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=150.0,
            order_type=OrderType.BUY,
        )

        # Price below trigger - should not trigger
        assert not condition.should_trigger(145.0)

        # Price at trigger - should trigger
        assert condition.should_trigger(150.0)

        # Price above trigger - should trigger
        assert condition.should_trigger(155.0)

    def test_update_trailing_stop_sell(self):
        """Test update_trailing_stop for sell orders."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        # Create a mock order with trail_percent
        order = MagicMock()
        order.quantity = -10  # Sell order
        order.trail_percent = 5.0
        order.trail_amount = None

        # Price goes up - should update trigger price
        updated = condition.update_trailing_stop(160.0, order)
        assert updated
        assert condition.high_water_mark == 160.0
        assert condition.trigger_price == 160.0 * 0.95  # 5% below high water mark

        # Price goes up more - should update again
        updated = condition.update_trailing_stop(170.0, order)
        assert updated
        assert condition.high_water_mark == 170.0
        assert condition.trigger_price == 170.0 * 0.95

        # Price goes down but still above trigger - should not update
        updated = condition.update_trailing_stop(165.0, order)
        assert not updated
        assert condition.high_water_mark == 170.0
        assert condition.trigger_price == 170.0 * 0.95

    def test_update_trailing_stop_buy(self):
        """Test update_trailing_stop for buy orders."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=155.0,
            order_type=OrderType.BUY,
        )

        # Create a mock order with trail_percent
        order = MagicMock()
        order.quantity = 10  # Buy order
        order.trail_percent = 5.0
        order.trail_amount = None

        # Price goes down - should update trigger price
        updated = condition.update_trailing_stop(140.0, order)
        assert updated
        assert condition.low_water_mark == 140.0
        assert condition.trigger_price == 140.0 * 1.05  # 5% above low water mark

        # Price goes down more - should update again
        updated = condition.update_trailing_stop(130.0, order)
        assert updated
        assert condition.low_water_mark == 130.0
        assert condition.trigger_price == 130.0 * 1.05

        # Price goes up but still below trigger - should not update
        updated = condition.update_trailing_stop(135.0, order)
        assert not updated
        assert condition.low_water_mark == 130.0
        assert condition.trigger_price == 130.0 * 1.05

    def test_update_trailing_stop_with_amount(self):
        """Test update_trailing_stop with trail_amount."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        # Create a mock order with trail_amount
        order = MagicMock()
        order.quantity = -10  # Sell order
        order.trail_percent = None
        order.trail_amount = 5.0

        # Price goes up - should update trigger price
        updated = condition.update_trailing_stop(160.0, order)
        assert updated
        assert condition.high_water_mark == 160.0
        assert condition.trigger_price == 160.0 - 5.0  # $5 below high water mark

        # Price goes up more - should update again
        updated = condition.update_trailing_stop(170.0, order)
        assert updated
        assert condition.high_water_mark == 170.0
        assert condition.trigger_price == 170.0 - 5.0

        # Price goes down but still above trigger - should not update
        updated = condition.update_trailing_stop(165.0, order)
        assert not updated
        assert condition.high_water_mark == 170.0
        assert condition.trigger_price == 170.0 - 5.0


class TestOrderExecutionEngine:
    """Tests for the OrderExecutionEngine class."""

    @pytest.mark.asyncio
    async def test_init(self, mock_trading_service):
        """Test OrderExecutionEngine initialization."""
        engine = OrderExecutionEngine(mock_trading_service)

        assert engine.trading_service == mock_trading_service
        assert not engine.is_running
        assert engine.monitoring_task is None
        assert len(engine.trigger_conditions) == 0
        assert len(engine.monitored_symbols) == 0
        assert engine.orders_processed == 0
        assert engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, execution_engine):
        """Test starting and stopping the execution engine."""
        # Mock _load_pending_orders to avoid database calls
        execution_engine._load_pending_orders = AsyncMock()

        # Start the engine
        await execution_engine.start()
        assert execution_engine.is_running
        assert execution_engine.monitoring_task is not None
        execution_engine._load_pending_orders.assert_called_once()

        # Stop the engine
        await execution_engine.stop()
        assert not execution_engine.is_running
        assert execution_engine.monitoring_task is None

    @pytest.mark.asyncio
    async def test_add_order(self, execution_engine):
        """Test adding an order to the execution engine."""
        # Mock order_converter
        with patch("app.services.order_execution_engine.order_converter") as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Create a stop loss order
            order = Order(
                id="test_order",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=-10,
                price=150.0,
                stop_price=145.0,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Add the order
            await execution_engine.add_order(order)

            # Verify the order was added
            assert "AAPL" in execution_engine.monitored_symbols
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            condition = execution_engine.trigger_conditions["AAPL"][0]
            assert condition.order_id == "test_order"
            assert condition.symbol == "AAPL"
            assert condition.trigger_type == "stop_loss"
            assert condition.trigger_price == 145.0
            assert condition.order_type == OrderType.SELL

    @pytest.mark.asyncio
    async def test_add_order_validation_error(self, execution_engine):
        """Test adding an invalid order to the execution engine."""
        # Mock order_converter
        with patch("app.services.order_execution_engine.order_converter") as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.side_effect = ValueError("Invalid order")

            # Create an invalid order
            order = Order(
                id="test_order",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=-10,
                price=150.0,
                # Missing stop_price
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Add the order - should raise an error
            with pytest.raises(OrderExecutionError):
                await execution_engine.add_order(order)

            # Verify the order was not added
            assert "AAPL" not in execution_engine.monitored_symbols
            assert "AAPL" not in execution_engine.trigger_conditions

    @pytest.mark.asyncio
    async def test_remove_order(self, execution_engine):
        """Test removing an order from the execution engine."""
        # Add two orders for the same symbol
        with patch("app.services.order_execution_engine.order_converter") as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Create orders
            order1 = Order(
                id="test_order_1",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=-10,
                price=150.0,
                stop_price=145.0,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            order2 = Order(
                id="test_order_2",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=-5,
                price=150.0,
                stop_price=140.0,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Add the orders
            await execution_engine.add_order(order1)
            await execution_engine.add_order(order2)

            # Verify both orders were added
            assert "AAPL" in execution_engine.monitored_symbols
            assert len(execution_engine.trigger_conditions["AAPL"]) == 2

            # Remove the first order
            await execution_engine.remove_order("test_order_1")

            # Verify only the second order remains
            assert "AAPL" in execution_engine.monitored_symbols
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            assert execution_engine.trigger_conditions["AAPL"][0].order_id == "test_order_2"

            # Remove the second order
            await execution_engine.remove_order("test_order_2")

            # Verify no orders remain
            assert "AAPL" not in execution_engine.monitored_symbols
            assert "AAPL" not in execution_engine.trigger_conditions

    @pytest.mark.asyncio
    async def test_check_trigger_conditions(self, execution_engine):
        """Test checking trigger conditions."""
        # Add a stop loss order
        with patch("app.services.order_execution_engine.order_converter") as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Create order
            order = Order(
                id="test_order",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=-10,
                price=150.0,
                stop_price=145.0,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Add the order
            await execution_engine.add_order(order)

            # Mock _process_triggered_order
            execution_engine._process_triggered_order = AsyncMock()

            # Check trigger conditions with price above stop - should not trigger
            await execution_engine._check_trigger_conditions("AAPL", 150.0)
            execution_engine._process_triggered_order.assert_not_called()

            # Check trigger conditions with price below stop - should trigger
            await execution_engine._check_trigger_conditions("AAPL", 140.0)
            execution_engine._process_triggered_order.assert_called_once()

            # Verify the order was removed from monitoring
            assert "AAPL" not in execution_engine.monitored_symbols
            assert "AAPL" not in execution_engine.trigger_conditions

    @pytest.mark.asyncio
    async def test_process_triggered_order(self, execution_engine):
        """Test processing a triggered order."""
        # Mock dependencies
        execution_engine._load_order_by_id = AsyncMock()
        execution_engine._update_order_triggered_status = AsyncMock()
        execution_engine._execute_converted_order = AsyncMock()

        # Create a mock order
        mock_order = MagicMock()
        execution_engine._load_order_by_id.return_value = mock_order

        # Mock order_converter
        with patch("app.services.order_execution_engine.order_converter") as mock_converter:
            mock_converter.convert_stop_loss_to_market.return_value = MagicMock()

            # Create a trigger condition
            condition = TriggerCondition(
                order_id="test_order",
                symbol="AAPL",
                trigger_type="stop_loss",
                trigger_price=145.0,
                order_type=OrderType.SELL,
            )

            # Process the triggered order
            await execution_engine._process_triggered_order(condition, 140.0)

            # Verify the order was processed
            execution_engine._load_order_by_id.assert_called_once_with("test_order")
            mock_converter.convert_stop_loss_to_market.assert_called_once_with(mock_order, 140.0)
            execution_engine._update_order_triggered_status.assert_called_once_with("test_order", 140.0)
            execution_engine._execute_converted_order.assert_called_once()
            assert execution_engine.orders_triggered == 1

    @pytest.mark.asyncio
    async def test_load_order_by_id(self, execution_engine):
        """Test loading an order by ID from the database."""
        # Mock database session
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_db_order = MagicMock()
        mock_db_order.id = "test_order"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = -10
        mock_db_order.price = 150.0
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.utcnow()
        mock_db_order.stop_price = 145.0
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None

        mock_result.scalar_one_or_none.return_value = mock_db_order
        mock_db.execute.return_value = mock_result

        # Mock get_async_session
        with patch("app.services.order_execution_engine.get_async_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_db
            mock_get_session.return_value.__aexit__.return_value = None

            # Load the order
            order = await execution_engine._load_order_by_id("test_order")

            # Verify the order was loaded
            assert order is not None
            assert order.id == "test_order"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS
            assert order.quantity == -10
            assert order.price == 150.0
            assert order.status == OrderStatus.PENDING
            assert order.stop_price == 145.0

    @pytest.mark.asyncio
    async def test_execute_converted_order(self, execution_engine):
        """Test executing a converted order."""
        # Create a mock order
        mock_order = MagicMock()
        mock_order.id = "test_order"

        # Execute the order
        await execution_engine._execute_converted_order(mock_order)

        # Verify the order was executed
        execution_engine.trading_service.execute_order.assert_called_once_with(mock_order)

    @pytest.mark.asyncio
    async def test_update_order_triggered_status(self, execution_engine):
        """Test updating an order's triggered status in the database."""
        # Mock database session
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_db_order = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_order
        mock_db.execute.return_value = mock_result

        # Mock get_async_session
        with patch("app.services.order_execution_engine.get_async_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_db
            mock_get_session.return_value.__aexit__.return_value = None

            # Update the order status
            await execution_engine._update_order_triggered_status("test_order", 140.0)

            # Verify the order status was updated
            assert mock_db_order.status == OrderStatus.FILLED
            assert mock_db_order.triggered_at is not None
            assert mock_db_order.filled_at is not None
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pending_orders(self, execution_engine):
        """Test loading pending orders from the database."""
        # Mock database session
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_db_order = MagicMock()
        mock_db_order.id = "test_order"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = -10
        mock_db_order.price = 150.0
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.utcnow()
        mock_db_order.stop_price = 145.0
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None

        mock_result.scalars.return_value.all.return_value = [mock_db_order]
        mock_db.execute.return_value = mock_result

        # Mock get_async_session
        with patch("app.services.order_execution_engine.get_async_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_db
            mock_get_session.return_value.__aexit__.return_value = None

            # Mock add_order
            execution_engine.add_order = AsyncMock()

            # Load pending orders
            await execution_engine._load_pending_orders()

            # Verify add_order was called
            execution_engine.add_order.assert_called_once()
            # Check that the order passed to add_order has the correct properties
            order = execution_engine.add_order.call_args[0][0]
            assert order.id == "test_order"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS
            assert order.quantity == -10
            assert order.price == 150.0
            assert order.status == OrderStatus.PENDING
            assert order.stop_price == 145.0

    def test_get_initial_trigger_price(self, execution_engine):
        """Test getting the initial trigger price for an order."""
        # Test stop loss order
        stop_loss_order = MagicMock()
        stop_loss_order.order_type = OrderType.STOP_LOSS
        stop_loss_order.stop_price = 145.0

        price = execution_engine._get_initial_trigger_price(stop_loss_order)
        assert price == 145.0

        # Test stop limit order
        stop_limit_order = MagicMock()
        stop_limit_order.order_type = OrderType.STOP_LIMIT
        stop_limit_order.stop_price = 145.0

        price = execution_engine._get_initial_trigger_price(stop_limit_order)
        assert price == 145.0

        # Test trailing stop order
        trailing_stop_order = MagicMock()
        trailing_stop_order.order_type = OrderType.TRAILING_STOP

        price = execution_engine._get_initial_trigger_price(trailing_stop_order)
        assert price == 0.0

        # Test invalid order type
        invalid_order = MagicMock()
        invalid_order.order_type = OrderType.MARKET

        with pytest.raises(OrderExecutionError):
            execution_engine._get_initial_trigger_price(invalid_order)

    def test_get_status(self, execution_engine):
        """Test getting the status of the execution engine."""
        # Add some trigger conditions
        execution_engine.trigger_conditions = {
            "AAPL": [MagicMock(), MagicMock()],
            "GOOGL": [MagicMock()],
        }
        execution_engine.monitored_symbols = {"AAPL", "GOOGL"}
        execution_engine.orders_processed = 10
        execution_engine.orders_triggered = 5
        execution_engine.is_running = True

        # Get status
        status = execution_engine.get_status()

        # Verify status
        assert status["is_running"] is True
        assert status["monitored_symbols"] == 2
        assert status["total_trigger_conditions"] == 3
        assert status["orders_processed"] == 10
        assert status["orders_triggered"] == 5
        assert set(status["symbols"]) == {"AAPL", "GOOGL"}

    def test_get_monitored_orders(self, execution_engine):
        """Test getting monitored orders."""
        # Create trigger conditions
        condition1 = TriggerCondition(
            order_id="test_order_1",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        condition2 = TriggerCondition(
            order_id="test_order_2",
            symbol="GOOGL",
            trigger_type="trailing_stop",
            trigger_price=2750.0,
            order_type=OrderType.SELL,
        )

        # Add to engine
        execution_engine.trigger_conditions = {
            "AAPL": [condition1],
            "GOOGL": [condition2],
        }

        # Get monitored orders
        orders = execution_engine.get_monitored_orders()

        # Verify orders
        assert "AAPL" in orders
        assert "GOOGL" in orders
        assert len(orders["AAPL"]) == 1
        assert len(orders["GOOGL"]) == 1
        assert orders["AAPL"][0]["order_id"] == "test_order_1"
        assert orders["AAPL"][0]["trigger_type"] == "stop_loss"
        assert orders["AAPL"][0]["trigger_price"] == 145.0
        assert orders["GOOGL"][0]["order_id"] == "test_order_2"
        assert orders["GOOGL"][0]["trigger_type"] == "trailing_stop"
        assert orders["GOOGL"][0]["trigger_price"] == 2750.0