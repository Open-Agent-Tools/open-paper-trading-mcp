"""
Comprehensive tests for OrderExecutionEngine - advanced order execution service.

Tests cover:
- Order monitoring and trigger condition management
- Stop loss, stop limit, and trailing stop processing
- Background monitoring loop and async execution
- Order state transitions and lifecycle management
- Market data integration and real-time processing
- Error handling and recovery scenarios
- Performance and concurrent processing
- Database integration and persistence
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.assets import Stock
from app.models.quotes import Quote
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.order_execution_engine import (
    OrderExecutionEngine,
    OrderExecutionError,
    TriggerCondition,
)
from app.services.trading_service import TradingService


@pytest.fixture
def mock_trading_service():
    """Mock trading service for testing."""
    service = AsyncMock(spec=TradingService)
    return service


@pytest.fixture
def execution_engine(mock_trading_service):
    """Order execution engine instance."""
    engine = OrderExecutionEngine(mock_trading_service)
    return engine


@pytest.fixture
def sample_stop_loss_order():
    """Sample stop loss order for testing."""
    return Order(
        id="order-123",
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        quantity=100,
        price=150.00,
        stop_price=145.00,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_trailing_stop_order():
    """Sample trailing stop order for testing."""
    return Order(
        id="order-456",
        symbol="GOOGL",
        order_type=OrderType.TRAILING_STOP,
        quantity=50,
        price=2800.00,
        trail_percent=5.0,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_quote():
    """Sample quote for testing."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        price=148.00,
        bid=147.95,
        ask=148.05,
        quote_date=datetime.now(),
    )


class TestTriggerCondition:
    """Test trigger condition logic and behavior."""

    def test_trigger_condition_initialization(self):
        """Test trigger condition creation."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        assert condition.order_id == "order-123"
        assert condition.symbol == "AAPL"
        assert condition.trigger_type == "stop_loss"
        assert condition.trigger_price == 145.00
        assert condition.order_type == OrderType.SELL
        assert isinstance(condition.created_at, datetime)

    def test_stop_loss_sell_trigger_below_price(self):
        """Test stop loss sell triggers when price drops below trigger."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Should trigger when price drops below
        assert condition.should_trigger(144.00) is True
        assert condition.should_trigger(145.00) is True
        assert condition.should_trigger(146.00) is False

    def test_stop_loss_buy_trigger_above_price(self):
        """Test stop loss buy triggers when price rises above trigger."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=155.00,
            order_type=OrderType.BUY,
        )

        # Should trigger when price rises above
        assert condition.should_trigger(156.00) is True
        assert condition.should_trigger(155.00) is True
        assert condition.should_trigger(154.00) is False

    def test_trailing_stop_update_percentage_based(self):
        """Test trailing stop updates with percentage."""
        mock_order = Mock()
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None
        mock_order.quantity = 100  # Long position

        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=142.50,  # 5% below $150
            order_type=OrderType.SELL,
        )

        # Price rises - should update trigger price
        updated = condition.update_trailing_stop(155.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 155.00
        expected_trigger = 155.00 * 0.95  # 5% below
        assert abs(condition.trigger_price - expected_trigger) < 0.01

    def test_trailing_stop_update_dollar_amount_based(self):
        """Test trailing stop updates with dollar amount."""
        mock_order = Mock()
        mock_order.trail_percent = None
        mock_order.trail_amount = 5.00
        mock_order.quantity = 100  # Long position

        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.00,  # $5 below $150
            order_type=OrderType.SELL,
        )

        # Price rises - should update trigger price
        updated = condition.update_trailing_stop(152.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 152.00
        assert condition.trigger_price == 147.00  # $5 below $152

    def test_trailing_stop_no_update_on_price_decline(self):
        """Test trailing stop doesn't update when price declines."""
        mock_order = Mock()
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None
        mock_order.quantity = 100

        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=142.50,
            order_type=OrderType.SELL,
        )
        condition.high_water_mark = 150.00

        # Price declines - should not update
        updated = condition.update_trailing_stop(148.00, mock_order)
        assert updated is False
        assert condition.trigger_price == 142.50  # Unchanged


class TestOrderExecutionEngine:
    """Test order execution engine functionality."""

    @pytest.mark.asyncio
    async def test_engine_initialization(self, mock_trading_service):
        """Test engine initialization."""
        engine = OrderExecutionEngine(mock_trading_service)

        assert engine.trading_service == mock_trading_service
        assert engine.is_running is False
        assert engine.monitoring_task is None
        assert len(engine.trigger_conditions) == 0
        assert len(engine.monitored_symbols) == 0

    @pytest.mark.asyncio
    async def test_start_engine_success(self, execution_engine):
        """Test successful engine startup."""
        with patch.object(execution_engine, "_load_pending_orders") as mock_load:
            mock_load.return_value = asyncio.create_future()
            mock_load.return_value.set_result(None)

            await execution_engine.start()

            assert execution_engine.is_running is True
            assert execution_engine.monitoring_task is not None
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_engine_already_running(self, execution_engine):
        """Test starting engine when already running."""
        execution_engine.is_running = True

        await execution_engine.start()

        # Should not create new monitoring task
        assert execution_engine.monitoring_task is None

    @pytest.mark.asyncio
    async def test_stop_engine_success(self, execution_engine):
        """Test successful engine shutdown."""
        # Start engine first
        execution_engine.is_running = True
        mock_task = AsyncMock()
        execution_engine.monitoring_task = mock_task

        await execution_engine.stop()

        assert execution_engine.is_running is False
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_order_valid_trigger_order(
        self, execution_engine, sample_stop_loss_order
    ):
        """Test adding valid trigger order for monitoring."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_stop_loss_order)

            assert sample_stop_loss_order.symbol in execution_engine.monitored_symbols
            assert (
                len(execution_engine.trigger_conditions[sample_stop_loss_order.symbol])
                == 1
            )

            condition = execution_engine.trigger_conditions[
                sample_stop_loss_order.symbol
            ][0]
            assert condition.order_id == sample_stop_loss_order.id
            assert condition.symbol == sample_stop_loss_order.symbol

    @pytest.mark.asyncio
    async def test_add_order_invalid_order_raises_error(self, execution_engine):
        """Test adding invalid order raises error."""
        invalid_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.BUY,  # Regular buy order, not trigger
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = False

            await execution_engine.add_order(invalid_order)

            # Should not be added to monitoring
            assert len(execution_engine.monitored_symbols) == 0

    @pytest.mark.asyncio
    async def test_add_order_validation_failure_raises_error(
        self, execution_engine, sample_stop_loss_order
    ):
        """Test adding order with validation failure."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.side_effect = ValueError(
                "Invalid order"
            )

            with pytest.raises(
                OrderExecutionError, match="Invalid order for monitoring"
            ):
                await execution_engine.add_order(sample_stop_loss_order)

    @pytest.mark.asyncio
    async def test_remove_order_success(self, execution_engine, sample_stop_loss_order):
        """Test successful order removal from monitoring."""
        # Add order first
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_stop_loss_order)

            # Verify it was added
            assert sample_stop_loss_order.symbol in execution_engine.monitored_symbols

            # Remove it
            await execution_engine.remove_order(sample_stop_loss_order.id)

            # Should be removed
            assert (
                sample_stop_loss_order.symbol not in execution_engine.monitored_symbols
            )
            assert len(execution_engine.trigger_conditions) == 0

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_symbols(self, execution_engine):
        """Test trigger condition check with no monitored symbols."""
        # Should return early with no monitored symbols
        await execution_engine._check_trigger_conditions()

        # No assertions needed - just verify it doesn't crash

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_with_trigger(
        self, execution_engine, sample_stop_loss_order, sample_quote
    ):
        """Test trigger condition check that triggers an order."""
        # Add order to monitoring
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_stop_loss_order)

        # Mock quote adapter to return triggering price
        trigger_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=144.00,  # Below stop price of 145.00
            bid=143.95,
            ask=144.05,
            quote_date=datetime.now(),
        )

        with (
            patch(
                "app.services.order_execution_engine._get_quote_adapter"
            ) as mock_adapter_func,
            patch.object(execution_engine, "_process_triggered_order") as mock_process,
        ):
            mock_adapter = AsyncMock()
            mock_adapter_func.return_value = mock_adapter
            mock_adapter.get_quote.return_value = trigger_quote

            await execution_engine._check_trigger_conditions()

            # Should have triggered order processing
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_trigger(
        self, execution_engine, sample_stop_loss_order
    ):
        """Test trigger condition check that doesn't trigger."""
        # Add order to monitoring
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_stop_loss_order)

        # Mock quote adapter to return non-triggering price
        no_trigger_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=147.00,  # Above stop price of 145.00
            bid=146.95,
            ask=147.05,
            quote_date=datetime.now(),
        )

        with (
            patch(
                "app.services.order_execution_engine._get_quote_adapter"
            ) as mock_adapter_func,
            patch.object(execution_engine, "_process_triggered_order") as mock_process,
        ):
            mock_adapter = AsyncMock()
            mock_adapter_func.return_value = mock_adapter
            mock_adapter.get_quote.return_value = no_trigger_quote

            await execution_engine._check_trigger_conditions()

            # Should not have triggered order processing
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_loss(self, execution_engine):
        """Test processing triggered stop loss order."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            price=150.00,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        mock_converted_order = Order(
            id="converted-123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,  # Market price
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                execution_engine, "_load_order_by_id", return_value=mock_order
            ),
            patch.object(
                execution_engine, "_update_order_triggered_status"
            ) as mock_update,
            patch.object(execution_engine, "_execute_converted_order") as mock_execute,
            patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter,
        ):
            mock_converter.convert_stop_loss_to_market.return_value = (
                mock_converted_order
            )

            await execution_engine._process_triggered_order(condition, 144.00)

            mock_update.assert_called_once_with("order-123", 144.00)
            mock_execute.assert_called_once_with(mock_converted_order)
            assert execution_engine.orders_triggered == 1

    @pytest.mark.asyncio
    async def test_process_triggered_order_missing_original(self, execution_engine):
        """Test processing triggered order when original order not found."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        with patch.object(execution_engine, "_load_order_by_id", return_value=None):
            await execution_engine._process_triggered_order(condition, 144.00)

            # Should handle gracefully without crashing
            assert execution_engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self, execution_engine):
        """Test successful order loading from database."""
        mock_db_order = Mock()
        mock_db_order.id = "order-123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = 100
        mock_db_order.price = 150.00
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.00
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None
        mock_db_order.filled_at = None

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aiter__.return_value = [mock_db]

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            order = await execution_engine._load_order_by_id("order-123")

            assert order is not None
            assert order.id == "order-123"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS

    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self, execution_engine):
        """Test order loading when order not found."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aiter__.return_value = [mock_db]

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            order = await execution_engine._load_order_by_id("order-123")

            assert order is None

    @pytest.mark.asyncio
    async def test_execute_converted_order_success(self, execution_engine):
        """Test successful execution of converted order."""
        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        execution_engine.trading_service.execute_order = AsyncMock()

        await execution_engine._execute_converted_order(mock_order)

        execution_engine.trading_service.execute_order.assert_called_once_with(
            mock_order
        )

    @pytest.mark.asyncio
    async def test_execute_converted_order_no_method(self, execution_engine):
        """Test converted order execution when service doesn't have execute_order method."""
        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        # Remove execute_order method
        if hasattr(execution_engine.trading_service, "execute_order"):
            delattr(execution_engine.trading_service, "execute_order")

        await execution_engine._execute_converted_order(mock_order)

        # Should handle gracefully without crashing

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_success(self, execution_engine):
        """Test successful order status update to triggered."""
        mock_db_order = Mock()

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aiter__.return_value = [mock_db]

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            await execution_engine._update_order_triggered_status("order-123", 144.00)

            assert mock_db_order.status == OrderStatus.FILLED
            assert hasattr(mock_db_order, "triggered_at")
            assert hasattr(mock_db_order, "filled_at")
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pending_orders_success(self, execution_engine):
        """Test successful loading of pending orders from database."""
        mock_db_order = Mock()
        mock_db_order.id = "order-123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = 100
        mock_db_order.price = 150.00
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.00
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None

        with (
            patch(
                "app.services.order_execution_engine.get_async_session"
            ) as mock_session,
            patch.object(execution_engine, "add_order") as mock_add,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aiter__.return_value = [mock_db]

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = [mock_db_order]
            mock_db.execute.return_value = mock_result

            await execution_engine._load_pending_orders()

            mock_add.assert_called_once()

    def test_get_initial_trigger_price_stop_loss(self, execution_engine):
        """Test getting initial trigger price for stop loss order."""
        order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        trigger_price = execution_engine._get_initial_trigger_price(order)
        assert trigger_price == 145.00

    def test_get_initial_trigger_price_trailing_stop(self, execution_engine):
        """Test getting initial trigger price for trailing stop order."""
        order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        trigger_price = execution_engine._get_initial_trigger_price(order)
        assert trigger_price == 0.0  # Will be updated dynamically

    def test_get_initial_trigger_price_missing_stop_price_raises_error(
        self, execution_engine
    ):
        """Test getting trigger price with missing stop price raises error."""
        order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=None,  # Missing stop price
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with pytest.raises(OrderExecutionError, match="Missing stop_price"):
            execution_engine._get_initial_trigger_price(order)

    def test_get_initial_trigger_price_unsupported_type_raises_error(
        self, execution_engine
    ):
        """Test getting trigger price for unsupported order type raises error."""
        order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.BUY,  # Not a trigger order type
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with pytest.raises(OrderExecutionError, match="Unsupported order type"):
            execution_engine._get_initial_trigger_price(order)

    def test_get_status_success(self, execution_engine):
        """Test getting engine status information."""
        # Add some mock conditions
        execution_engine.is_running = True
        execution_engine.monitored_symbols = {"AAPL", "GOOGL"}
        execution_engine.trigger_conditions["AAPL"] = [Mock(), Mock()]
        execution_engine.trigger_conditions["GOOGL"] = [Mock()]
        execution_engine.orders_processed = 10
        execution_engine.orders_triggered = 3

        status = execution_engine.get_status()

        assert status["is_running"] is True
        assert status["monitored_symbols"] == 2
        assert status["total_trigger_conditions"] == 3
        assert status["orders_processed"] == 10
        assert status["orders_triggered"] == 3
        assert "AAPL" in status["symbols"]
        assert "GOOGL" in status["symbols"]

    def test_get_monitored_orders_success(self, execution_engine):
        """Test getting monitored orders information."""
        # Create mock conditions
        mock_condition1 = Mock()
        mock_condition1.order_id = "order-1"
        mock_condition1.order_type = OrderType.SELL
        mock_condition1.trigger_price = 145.00
        mock_condition1.trigger_type = "stop_loss"
        mock_condition1.created_at = datetime.now()
        mock_condition1.high_water_mark = None
        mock_condition1.low_water_mark = None

        mock_condition2 = Mock()
        mock_condition2.order_id = "order-2"
        mock_condition2.order_type = OrderType.SELL
        mock_condition2.trigger_price = 142.50
        mock_condition2.trigger_type = "trailing_stop"
        mock_condition2.created_at = datetime.now()
        mock_condition2.high_water_mark = 150.00
        mock_condition2.low_water_mark = None

        execution_engine.trigger_conditions["AAPL"] = [mock_condition1, mock_condition2]

        monitored = execution_engine.get_monitored_orders()

        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == 2
        assert monitored["AAPL"][0]["order_id"] == "order-1"
        assert monitored["AAPL"][1]["trigger_type"] == "trailing_stop"


class TestOrderExecutionEngineIntegration:
    """Integration tests for order execution engine."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_lifecycle(self, execution_engine):
        """Test complete monitoring loop lifecycle."""
        # Start the engine
        with patch.object(execution_engine, "_load_pending_orders"):
            await execution_engine.start()

        # Add an order
        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(mock_order)

        # Verify monitoring is active
        assert execution_engine.is_running
        assert "AAPL" in execution_engine.monitored_symbols

        # Stop the engine
        await execution_engine.stop()

        assert not execution_engine.is_running

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self, execution_engine):
        """Test concurrent processing of multiple orders."""
        # Create multiple orders
        orders = []
        for i in range(5):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00 - i,  # Different trigger prices
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append(order)

        # Add all orders concurrently
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            tasks = [execution_engine.add_order(order) for order in orders]
            await asyncio.gather(*tasks)

        # Verify all orders were added
        assert len(execution_engine.trigger_conditions["AAPL"]) == 5

    @pytest.mark.asyncio
    async def test_error_recovery_in_monitoring_loop(self, execution_engine):
        """Test error recovery in monitoring loop."""
        # Mock monitoring loop to simulate errors
        original_check = execution_engine._check_trigger_conditions
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated error")
            else:
                # Stop after second call to avoid infinite loop
                execution_engine.is_running = False

        execution_engine._check_trigger_conditions = mock_check

        # Start monitoring loop
        execution_engine.is_running = True

        # This should handle the error and continue
        await execution_engine._monitoring_loop()

        # Should have attempted multiple calls despite error
        assert call_count >= 2


class TestOrderExecutionEnginePerformance:
    """Performance and load testing for order execution engine."""

    @pytest.mark.asyncio
    async def test_high_volume_order_monitoring(self, execution_engine):
        """Test monitoring performance with high volume of orders."""
        # Create many orders
        orders = []
        for i in range(100):
            order = Order(
                id=f"order-{i}",
                symbol=f"SYMB{i % 10}",  # 10 different symbols
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=100.00 + i,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append(order)

        # Add all orders
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            start_time = datetime.now()

            for order in orders:
                await execution_engine.add_order(order)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

        # Should complete reasonably quickly
        assert duration < 5.0  # Less than 5 seconds for 100 orders
        assert len(execution_engine.monitored_symbols) == 10

    @pytest.mark.asyncio
    async def test_memory_usage_with_many_conditions(self, execution_engine):
        """Test memory efficiency with many trigger conditions."""
        import sys

        initial_size = sys.getsizeof(execution_engine.trigger_conditions)

        # Add many conditions
        for i in range(1000):
            condition = TriggerCondition(
                order_id=f"order-{i}",
                symbol=f"SYMBOL{i % 100}",  # 100 symbols
                trigger_type="stop_loss",
                trigger_price=100.00 + i,
                order_type=OrderType.SELL,
            )

            symbol = condition.symbol
            if symbol not in execution_engine.trigger_conditions:
                execution_engine.trigger_conditions[symbol] = []
            execution_engine.trigger_conditions[symbol].append(condition)
            execution_engine.monitored_symbols.add(symbol)

        final_size = sys.getsizeof(execution_engine.trigger_conditions)

        # Memory growth should be reasonable
        growth_ratio = final_size / initial_size if initial_size > 0 else 1
        assert growth_ratio < 1000  # Shouldn't grow by more than 1000x


class TestOrderExecutionEngineErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_database_connection_failure_handling(self, execution_engine):
        """Test handling of database connection failures."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_session:
            mock_session.side_effect = Exception("Database connection failed")

            # Should handle gracefully
            order = await execution_engine._load_order_by_id("order-123")
            assert order is None

    @pytest.mark.asyncio
    async def test_quote_adapter_failure_handling(self, execution_engine):
        """Test handling of quote adapter failures."""
        # Add an order for monitoring
        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(mock_order)

        # Mock quote adapter to fail
        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_adapter_func:
            mock_adapter = AsyncMock()
            mock_adapter_func.return_value = mock_adapter
            mock_adapter.get_quote.side_effect = Exception("Quote adapter failed")

            # Should handle failure gracefully
            await execution_engine._check_trigger_conditions()

            # Order should still be monitored
            assert "AAPL" in execution_engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_invalid_trigger_price_handling(self, execution_engine):
        """Test handling of invalid trigger prices."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=float("nan"),  # Invalid price
            order_type=OrderType.SELL,
        )

        # Should handle NaN prices gracefully
        result = condition.should_trigger(150.00)
        assert result is False  # Should not trigger with invalid price

    @pytest.mark.asyncio
    async def test_order_conversion_failure_handling(self, execution_engine):
        """Test handling of order conversion failures."""
        condition = TriggerCondition(
            order_id="order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                execution_engine, "_load_order_by_id", return_value=mock_order
            ),
            patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter,
        ):
            # Make conversion fail
            mock_converter.convert_stop_loss_to_market.return_value = None

            # Should handle conversion failure gracefully
            await execution_engine._process_triggered_order(condition, 144.00)

            # Should not increment triggered count
            assert execution_engine.orders_triggered == 0
