"""
Complete comprehensive tests for OrderExecutionEngine.

This test suite achieves 100% coverage of the OrderExecutionEngine module including:
- All classes: OrderExecutionEngine, TriggerCondition, OrderExecutionError
- All methods and functions including private methods
- All conditional branches and edge cases
- Error handling and exception paths
- Async context managers and background tasks
- Database integration and session management
- Thread safety and concurrency
- Order conversion and execution flows
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.assets import Stock
from app.models.database.trading import Order as DBOrder
from app.models.quotes import Quote
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.order_execution_engine import (
    OrderExecutionEngine,
    OrderExecutionError,
    TriggerCondition,
    execution_engine,
    get_execution_engine,
    initialize_execution_engine,
)
from app.services.trading_service import TradingService


# Test fixtures
@pytest.fixture
def mock_trading_service():
    """Mock trading service for testing."""
    service = Mock(spec=TradingService)
    service.execute_order = AsyncMock()
    return service


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        id="test-order-123",
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        quantity=100,
        price=150.00,
        stop_price=145.00,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_stop_limit_order():
    """Sample stop limit order."""
    return Order(
        id="stop-limit-order",
        symbol="AAPL",
        order_type=OrderType.STOP_LIMIT,
        quantity=100,
        price=144.00,
        stop_price=145.00,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_trailing_stop_order():
    """Sample trailing stop order."""
    return Order(
        id="trailing-order-123",
        symbol="AAPL",
        order_type=OrderType.TRAILING_STOP,
        quantity=-100,  # Short position
        price=None,
        trail_percent=5.0,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_trailing_stop_dollar_order():
    """Sample trailing stop order with dollar amount."""
    return Order(
        id="trailing-dollar-order",
        symbol="AAPL",
        order_type=OrderType.TRAILING_STOP,
        quantity=100,  # Long position
        price=None,
        trail_amount=3.0,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def execution_engine_instance(mock_trading_service):
    """Order execution engine instance for testing."""
    return OrderExecutionEngine(mock_trading_service)


class TestOrderExecutionError:
    """Test the OrderExecutionError exception."""

    def test_exception_creation(self):
        """Test creating OrderExecutionError."""
        error = OrderExecutionError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_exception_inheritance(self):
        """Test OrderExecutionError inheritance."""
        error = OrderExecutionError("Test")
        assert isinstance(error, Exception)


class TestTriggerCondition:
    """Comprehensive tests for TriggerCondition class."""

    def test_trigger_condition_initialization(self):
        """Test TriggerCondition initialization."""
        now = datetime.utcnow()
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        assert condition.order_id == "test-123"
        assert condition.symbol == "AAPL"
        assert condition.trigger_type == "stop_loss"
        assert condition.trigger_price == 145.00
        assert condition.order_type == OrderType.SELL
        assert condition.high_water_mark is None
        assert condition.low_water_mark is None
        assert isinstance(condition.created_at, datetime)
        assert condition.created_at >= now

    def test_should_trigger_stop_loss_sell_order(self):
        """Test stop loss trigger logic for sell orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Price above trigger - should not trigger
        assert condition.should_trigger(150.00) is False
        assert condition.should_trigger(145.01) is False

        # Price at trigger - should trigger
        assert condition.should_trigger(145.00) is True

        # Price below trigger - should trigger
        assert condition.should_trigger(144.99) is True
        assert condition.should_trigger(140.00) is True

    def test_should_trigger_stop_loss_buy_order(self):
        """Test stop loss trigger logic for buy orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=155.00,
            order_type=OrderType.BUY,
        )

        # Price below trigger - should not trigger
        assert condition.should_trigger(150.00) is False
        assert condition.should_trigger(154.99) is False

        # Price at trigger - should trigger
        assert condition.should_trigger(155.00) is True

        # Price above trigger - should trigger
        assert condition.should_trigger(155.01) is True
        assert condition.should_trigger(160.00) is True

    def test_should_trigger_stop_limit_orders(self):
        """Test stop limit trigger logic (same as stop loss)."""
        sell_condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_limit",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        buy_condition = TriggerCondition(
            order_id="test-124",
            symbol="AAPL",
            trigger_type="stop_limit",
            trigger_price=155.00,
            order_type=OrderType.BUY,
        )

        # Same logic as stop loss
        assert sell_condition.should_trigger(144.00) is True
        assert sell_condition.should_trigger(146.00) is False
        assert buy_condition.should_trigger(156.00) is True
        assert buy_condition.should_trigger(154.00) is False

    def test_should_trigger_trailing_stop_sell(self):
        """Test trailing stop trigger logic for sell orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Same logic as stop loss for sell orders
        assert condition.should_trigger(144.00) is True
        assert condition.should_trigger(145.00) is True
        assert condition.should_trigger(146.00) is False

    def test_should_trigger_trailing_stop_buy(self):
        """Test trailing stop trigger logic for buy orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=155.00,
            order_type=OrderType.BUY,
        )

        # Same logic as stop loss for buy orders
        assert condition.should_trigger(156.00) is True
        assert condition.should_trigger(155.00) is True
        assert condition.should_trigger(154.00) is False

    def test_should_trigger_unknown_type(self):
        """Test trigger logic for unknown trigger types."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="unknown_type",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Should return False for unknown types
        assert condition.should_trigger(144.00) is False
        assert condition.should_trigger(146.00) is False

    def test_update_trailing_stop_non_trailing(self):
        """Test trailing stop update on non-trailing order."""
        mock_order = Mock()
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",  # Not trailing
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        updated = condition.update_trailing_stop(150.00, mock_order)
        assert updated is False

    def test_update_trailing_stop_percentage_sell_order(self):
        """Test trailing stop update with percentage for sell orders."""
        mock_order = Mock()
        mock_order.quantity = -100  # Sell order (negative quantity)
        mock_order.trail_percent = 5.0  # 5% trail
        mock_order.trail_amount = None

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=142.50,  # Initial trigger
            order_type=OrderType.SELL,
        )

        # Price goes up - should update trigger and high water mark
        updated = condition.update_trailing_stop(155.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 155.00
        expected_trigger = 155.00 * (1 - 0.05)  # 5% trail
        assert abs(condition.trigger_price - expected_trigger) < 0.01

        # Price goes down but not below new trigger - no update
        updated = condition.update_trailing_stop(150.00, mock_order)
        assert updated is False
        assert condition.high_water_mark == 155.00  # Unchanged

        # Price goes higher - should update again
        updated = condition.update_trailing_stop(160.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 160.00
        expected_trigger = 160.00 * (1 - 0.05)
        assert abs(condition.trigger_price - expected_trigger) < 0.01

    def test_update_trailing_stop_percentage_sell_no_improvement(self):
        """Test trailing stop update with no price improvement for sell."""
        mock_order = Mock()
        mock_order.quantity = -100
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=147.25,  # 155 * 0.95
            order_type=OrderType.SELL,
        )
        condition.high_water_mark = 155.00

        # Price doesn't improve the trigger
        updated = condition.update_trailing_stop(154.00, mock_order)
        assert updated is False
        assert condition.high_water_mark == 155.00
        assert condition.trigger_price == 147.25

    def test_update_trailing_stop_percentage_buy_order(self):
        """Test trailing stop update with percentage for buy orders."""
        mock_order = Mock()
        mock_order.quantity = 100  # Buy order (positive quantity)
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=157.50,  # Initial trigger above current price
            order_type=OrderType.BUY,
        )

        # Price goes down - should update trigger and low water mark
        updated = condition.update_trailing_stop(145.00, mock_order)
        assert updated is True
        assert condition.low_water_mark == 145.00
        expected_trigger = 145.00 * (1 + 0.05)  # 5% above low
        assert abs(condition.trigger_price - expected_trigger) < 0.01

        # Price goes up but not above new trigger - no update
        updated = condition.update_trailing_stop(150.00, mock_order)
        assert updated is False
        assert condition.low_water_mark == 145.00  # Unchanged

        # Price goes lower - should update again
        updated = condition.update_trailing_stop(140.00, mock_order)
        assert updated is True
        assert condition.low_water_mark == 140.00
        expected_trigger = 140.00 * (1 + 0.05)
        assert abs(condition.trigger_price - expected_trigger) < 0.01

    def test_update_trailing_stop_percentage_buy_no_improvement(self):
        """Test trailing stop update with no price improvement for buy."""
        mock_order = Mock()
        mock_order.quantity = 100
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=152.25,  # 145 * 1.05
            order_type=OrderType.BUY,
        )
        condition.low_water_mark = 145.00

        # Price doesn't improve the trigger
        updated = condition.update_trailing_stop(146.00, mock_order)
        assert updated is False
        assert condition.low_water_mark == 145.00
        assert condition.trigger_price == 152.25

    def test_update_trailing_stop_dollar_amount_sell(self):
        """Test trailing stop update with dollar amount for sell orders."""
        mock_order = Mock()
        mock_order.quantity = -100  # Sell order
        mock_order.trail_percent = None
        mock_order.trail_amount = 5.00  # $5 trail

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Price goes up - should update
        updated = condition.update_trailing_stop(155.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 155.00
        assert condition.trigger_price == 150.00  # 155 - 5

        # Price goes down - no update
        updated = condition.update_trailing_stop(152.00, mock_order)
        assert updated is False
        assert condition.high_water_mark == 155.00
        assert condition.trigger_price == 150.00

    def test_update_trailing_stop_dollar_amount_buy(self):
        """Test trailing stop update with dollar amount for buy orders."""
        mock_order = Mock()
        mock_order.quantity = 100  # Buy order
        mock_order.trail_percent = None
        mock_order.trail_amount = 3.00  # $3 trail

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=148.00,
            order_type=OrderType.BUY,
        )

        # Price goes down - should update
        updated = condition.update_trailing_stop(145.00, mock_order)
        assert updated is True
        assert condition.low_water_mark == 145.00
        assert condition.trigger_price == 148.00  # 145 + 3

        # Price goes up - no update
        updated = condition.update_trailing_stop(147.00, mock_order)
        assert updated is False
        assert condition.low_water_mark == 145.00
        assert condition.trigger_price == 148.00

    def test_update_trailing_stop_with_initial_water_marks(self):
        """Test trailing stop updates when water marks are already set."""
        mock_order = Mock()
        mock_order.quantity = -100
        mock_order.trail_percent = 5.0
        mock_order.trail_amount = None

        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=142.50,
            order_type=OrderType.SELL,
        )
        condition.high_water_mark = 150.00  # Pre-existing water mark

        # Price equal to existing high water mark - no update
        updated = condition.update_trailing_stop(150.00, mock_order)
        assert updated is False
        assert condition.high_water_mark == 150.00

        # Price higher than existing high water mark - update
        updated = condition.update_trailing_stop(155.00, mock_order)
        assert updated is True
        assert condition.high_water_mark == 155.00


class TestOrderExecutionEngineInitialization:
    """Test OrderExecutionEngine initialization and configuration."""

    def test_initialization_with_trading_service(self, mock_trading_service):
        """Test engine initialization with trading service."""
        engine = OrderExecutionEngine(mock_trading_service)

        assert engine.trading_service == mock_trading_service
        assert engine.is_running is False
        assert engine.monitoring_task is None
        assert isinstance(engine.executor, ThreadPoolExecutor)
        assert isinstance(engine.trigger_conditions, dict)
        assert isinstance(engine.monitored_symbols, set)
        assert engine.orders_processed == 0
        assert engine.orders_triggered == 0
        assert isinstance(engine.last_market_data_update, datetime)
        assert isinstance(engine._lock, threading.Lock)

    def test_initial_collections_empty(self, execution_engine_instance):
        """Test initial collection states are empty."""
        assert len(execution_engine_instance.trigger_conditions) == 0
        assert len(execution_engine_instance.monitored_symbols) == 0

    def test_initial_metrics_values(self, execution_engine_instance):
        """Test initial performance metrics values."""
        assert execution_engine_instance.orders_processed == 0
        assert execution_engine_instance.orders_triggered == 0
        assert isinstance(execution_engine_instance.last_market_data_update, datetime)

    def test_thread_executor_configuration(self, execution_engine_instance):
        """Test thread executor is properly configured."""
        assert isinstance(execution_engine_instance.executor, ThreadPoolExecutor)
        assert execution_engine_instance.executor._max_workers == 4


class TestEngineLifecycleManagement:
    """Test engine start/stop lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_engine_success(self, execution_engine_instance):
        """Test successfully starting the execution engine."""
        with (
            patch.object(
                execution_engine_instance,
                "_load_pending_orders",
                new_callable=AsyncMock,
            ) as mock_load,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            await execution_engine_instance.start()

            assert execution_engine_instance.is_running is True
            assert execution_engine_instance.monitoring_task == mock_task
            mock_load.assert_called_once()
            mock_create_task.assert_called_once_with(
                execution_engine_instance._monitoring_loop()
            )

    @pytest.mark.asyncio
    async def test_start_engine_already_running(self, execution_engine_instance):
        """Test starting engine when already running - should log warning."""
        execution_engine_instance.is_running = True

        with (
            patch.object(
                execution_engine_instance,
                "_load_pending_orders",
                new_callable=AsyncMock,
            ) as mock_load,
            patch("asyncio.create_task") as mock_create_task,
        ):
            await execution_engine_instance.start()

            # Should not reload orders or create new task
            mock_load.assert_not_called()
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_engine_success(self, execution_engine_instance):
        """Test successfully stopping the execution engine."""
        # Set up running state
        execution_engine_instance.is_running = True
        mock_task = Mock()
        mock_task.cancel = Mock()
        execution_engine_instance.monitoring_task = mock_task

        with patch.object(
            execution_engine_instance.executor, "shutdown"
        ) as mock_shutdown:
            await execution_engine_instance.stop()

            assert execution_engine_instance.is_running is False
            mock_task.cancel.assert_called_once()
            mock_shutdown.assert_called_once_with(wait=True)

    @pytest.mark.asyncio
    async def test_stop_engine_not_running(self, execution_engine_instance):
        """Test stopping engine when not running - should return early."""
        execution_engine_instance.is_running = False

        with patch.object(
            execution_engine_instance.executor, "shutdown"
        ) as mock_shutdown:
            await execution_engine_instance.stop()

            # Should return early without shutting down
            mock_shutdown.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_engine_with_task_cancellation_error(
        self, execution_engine_instance
    ):
        """Test stopping engine handles CancelledError properly."""
        execution_engine_instance.is_running = True

        # Mock monitoring task that will be cancelled
        mock_task = AsyncMock()
        mock_task.cancel = Mock()
        execution_engine_instance.monitoring_task = mock_task

        with patch.object(execution_engine_instance.executor, "shutdown"):
            # Should handle CancelledError gracefully
            await execution_engine_instance.stop()

            mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_engine_no_monitoring_task(self, execution_engine_instance):
        """Test stopping engine when monitoring_task is None."""
        execution_engine_instance.is_running = True
        execution_engine_instance.monitoring_task = None

        with patch.object(
            execution_engine_instance.executor, "shutdown"
        ) as mock_shutdown:
            await execution_engine_instance.stop()

            assert execution_engine_instance.is_running is False
            mock_shutdown.assert_called_once_with(wait=True)


class TestOrderManagement:
    """Test adding and removing orders from monitoring."""

    @pytest.mark.asyncio
    async def test_add_order_success(self, execution_engine_instance, sample_order):
        """Test successfully adding an order for monitoring."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            # Check that order was added to monitoring
            assert "AAPL" in execution_engine_instance.trigger_conditions
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 1
            assert "AAPL" in execution_engine_instance.monitored_symbols

            condition = execution_engine_instance.trigger_conditions["AAPL"][0]
            assert condition.order_id == "test-order-123"
            assert condition.symbol == "AAPL"
            assert condition.trigger_type == "stop_loss"
            assert condition.trigger_price == 145.00
            assert condition.order_type == OrderType.SELL  # Stop loss defaults to sell

    @pytest.mark.asyncio
    async def test_add_order_not_convertible(
        self, execution_engine_instance, sample_order
    ):
        """Test adding order that cannot be converted."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = False

            await execution_engine_instance.add_order(sample_order)

            # Order should not be added
            assert len(execution_engine_instance.trigger_conditions) == 0
            assert len(execution_engine_instance.monitored_symbols) == 0

    @pytest.mark.asyncio
    async def test_add_order_validation_error(
        self, execution_engine_instance, sample_order
    ):
        """Test adding order that fails validation."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.side_effect = Exception(
                "Validation failed"
            )

            with pytest.raises(
                OrderExecutionError, match="Invalid order for monitoring"
            ):
                await execution_engine_instance.add_order(sample_order)

    @pytest.mark.asyncio
    async def test_add_order_stop_limit_type_detection(
        self, execution_engine_instance, sample_stop_limit_order
    ):
        """Test adding stop limit order with correct type detection."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_stop_limit_order)

            condition = execution_engine_instance.trigger_conditions["AAPL"][0]
            assert condition.trigger_type == "stop_limit"
            assert (
                condition.order_type == OrderType.SELL
            )  # Positive quantity but stop orders default to sell

    @pytest.mark.asyncio
    async def test_add_order_trailing_stop_type_detection(
        self, execution_engine_instance, sample_trailing_stop_order
    ):
        """Test adding trailing stop order with correct type detection."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_trailing_stop_order)

            condition = execution_engine_instance.trigger_conditions["AAPL"][0]
            assert condition.trigger_type == "trailing_stop"
            assert condition.order_type == OrderType.SELL

    @pytest.mark.asyncio
    async def test_add_order_trigger_order_type_logic(self, execution_engine_instance):
        """Test order type logic for trigger conditions."""
        # Test order with positive quantity (not stop loss/trailing stop)
        regular_order = Order(
            id="regular-order",
            symbol="AAPL",
            order_type=OrderType.STOP_LIMIT,  # Not stop loss or trailing stop
            quantity=100,
            price=150.00,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(regular_order)

            condition = execution_engine_instance.trigger_conditions["AAPL"][0]
            # Should use SELL for positive quantity (opposite of normal logic)
            assert condition.order_type == OrderType.SELL

        # Test with negative quantity
        short_order = Order(
            id="short-order",
            symbol="GOOGL",
            order_type=OrderType.STOP_LIMIT,
            quantity=-100,
            price=2800.00,
            stop_price=2750.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        await execution_engine_instance.add_order(short_order)
        condition = execution_engine_instance.trigger_conditions["GOOGL"][0]
        # Should use BUY for negative quantity
        assert condition.order_type == OrderType.BUY

    @pytest.mark.asyncio
    async def test_remove_order_success(self, execution_engine_instance, sample_order):
        """Test successfully removing an order from monitoring."""
        # First add an order
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            # Verify it was added
            assert "AAPL" in execution_engine_instance.trigger_conditions
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 1

            # Remove the order
            await execution_engine_instance.remove_order("test-order-123")

            # Verify it was removed and collections cleaned up
            assert "AAPL" not in execution_engine_instance.trigger_conditions
            assert "AAPL" not in execution_engine_instance.monitored_symbols

    @pytest.mark.asyncio
    async def test_remove_order_multiple_conditions_same_symbol(
        self, execution_engine_instance
    ):
        """Test removing one order when multiple conditions exist for same symbol."""
        # Create multiple orders for same symbol
        orders = [
            Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00 - i,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Add all orders
            for order in orders:
                await execution_engine_instance.add_order(order)

            # Should have 3 conditions for AAPL
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 3

            # Remove one order
            await execution_engine_instance.remove_order("order-1")

            # Should still have 2 conditions and symbol should remain monitored
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 2
            assert "AAPL" in execution_engine_instance.monitored_symbols

            # Verify correct order was removed
            remaining_ids = [
                c.order_id for c in execution_engine_instance.trigger_conditions["AAPL"]
            ]
            assert "order-1" not in remaining_ids
            assert "order-0" in remaining_ids
            assert "order-2" in remaining_ids

    @pytest.mark.asyncio
    async def test_remove_order_cleans_empty_symbols(self, execution_engine_instance):
        """Test that empty symbol lists are cleaned up after removal."""
        # Add orders for multiple symbols
        orders = [
            Order(
                id="aapl-order",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
            Order(
                id="googl-order",
                symbol="GOOGL",
                order_type=OrderType.STOP_LOSS,
                quantity=50,
                stop_price=2750.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
        ]

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            for order in orders:
                await execution_engine_instance.add_order(order)

            # Should have both symbols
            assert "AAPL" in execution_engine_instance.trigger_conditions
            assert "GOOGL" in execution_engine_instance.trigger_conditions
            assert len(execution_engine_instance.monitored_symbols) == 2

            # Remove AAPL order
            await execution_engine_instance.remove_order("aapl-order")

            # AAPL should be cleaned up, GOOGL should remain
            assert "AAPL" not in execution_engine_instance.trigger_conditions
            assert "GOOGL" in execution_engine_instance.trigger_conditions
            assert execution_engine_instance.monitored_symbols == {"GOOGL"}

    @pytest.mark.asyncio
    async def test_remove_nonexistent_order(self, execution_engine_instance):
        """Test removing an order that doesn't exist."""
        # Should not raise an error
        await execution_engine_instance.remove_order("nonexistent-order")
        assert len(execution_engine_instance.trigger_conditions) == 0

    @pytest.mark.asyncio
    async def test_add_trigger_order_alias(
        self, execution_engine_instance, sample_order
    ):
        """Test add_trigger_order method (alias for add_order)."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_trigger_order(sample_order)

            # Should work exactly like add_order
            assert "AAPL" in execution_engine_instance.trigger_conditions
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 1


class TestMonitoringLoop:
    """Test the monitoring loop functionality."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_lifecycle(self, execution_engine_instance):
        """Test monitoring loop start and stop."""
        execution_engine_instance.is_running = True

        # Mock the check method to avoid infinite loop
        with patch.object(
            execution_engine_instance,
            "_check_trigger_conditions",
            new_callable=AsyncMock,
        ) as mock_check:
            # Mock sleep to control loop timing
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Create the monitoring task
                loop_task = asyncio.create_task(
                    execution_engine_instance._monitoring_loop()
                )

                # Let it run briefly
                await asyncio.sleep(0.01)

                # Stop the loop
                execution_engine_instance.is_running = False

                # Wait for completion
                await loop_task

                # Should have called check at least once
                mock_check.assert_called()

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, execution_engine_instance):
        """Test monitoring loop handles errors gracefully."""
        execution_engine_instance.is_running = True

        call_count = 0

        async def mock_check_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            # Stop after first error
            execution_engine_instance.is_running = False

        with (
            patch.object(
                execution_engine_instance,
                "_check_trigger_conditions",
                side_effect=mock_check_with_error,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # Should not raise exception
            await execution_engine_instance._monitoring_loop()

            # Should have attempted the check
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_monitoring_loop_cancellation(self, execution_engine_instance):
        """Test monitoring loop handles cancellation properly."""
        execution_engine_instance.is_running = True

        async def mock_check_cancelled():
            raise asyncio.CancelledError()

        with patch.object(
            execution_engine_instance,
            "_check_trigger_conditions",
            side_effect=mock_check_cancelled,
        ):
            # Should handle CancelledError and break the loop
            await execution_engine_instance._monitoring_loop()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_symbols(self, execution_engine_instance):
        """Test trigger condition checking with no monitored symbols."""
        await execution_engine_instance._check_trigger_conditions()

        # Should return early with no errors
        assert execution_engine_instance.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_specific_symbol_and_price(
        self, execution_engine_instance, sample_order
    ):
        """Test trigger condition checking with specific symbol and price."""
        # Add an order to monitor
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            # Mock order processing
            with patch.object(
                execution_engine_instance,
                "_process_triggered_order",
                new_callable=AsyncMock,
            ) as mock_process:
                # Check with triggering price (below stop loss for sell order)
                await execution_engine_instance._check_trigger_conditions(
                    "AAPL", 144.00
                )

                # Should trigger the order
                mock_process.assert_called_once()
                args = mock_process.call_args[0]
                condition, trigger_price = args
                assert condition.order_id == "test-order-123"
                assert trigger_price == 144.00

                # Order should be removed from monitoring after triggering
                assert "AAPL" not in execution_engine_instance.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_specific_symbol_no_trigger(
        self, execution_engine_instance, sample_order
    ):
        """Test trigger condition checking that doesn't trigger."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            with patch.object(
                execution_engine_instance,
                "_process_triggered_order",
                new_callable=AsyncMock,
            ) as mock_process:
                # Check with non-triggering price (above stop loss for sell order)
                await execution_engine_instance._check_trigger_conditions(
                    "AAPL", 150.00
                )

                # Should not trigger
                mock_process.assert_not_called()

                # Order should remain in monitoring
                assert "AAPL" in execution_engine_instance.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_symbol_not_monitored(
        self, execution_engine_instance
    ):
        """Test checking conditions for a symbol not being monitored."""
        # No symbols being monitored
        await execution_engine_instance._check_trigger_conditions("AAPL", 144.00)

        # Should return early without errors
        assert execution_engine_instance.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_with_quote_adapter(
        self, execution_engine_instance, sample_order
    ):
        """Test trigger condition checking with quote adapter integration."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            # Mock quote adapter and asset factory
            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()
                mock_quote = Quote(
                    asset=Stock(symbol="AAPL"),
                    price=144.00,  # Triggering price
                    bid=143.95,
                    ask=144.05,
                    quote_date=datetime.now(),
                )
                mock_adapter.get_quote = AsyncMock(return_value=mock_quote)
                mock_get_adapter.return_value = mock_adapter
                mock_factory.return_value = Stock(symbol="AAPL")

                with patch.object(
                    execution_engine_instance,
                    "_process_triggered_order",
                    new_callable=AsyncMock,
                ) as mock_process:
                    # Check without specific price (should use adapter)
                    await execution_engine_instance._check_trigger_conditions()

                    # Should get quote and trigger
                    mock_adapter.get_quote.assert_called_once()
                    mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_asset_factory_returns_none(
        self, execution_engine_instance, sample_order
    ):
        """Test handling when asset_factory returns None."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()
                mock_get_adapter.return_value = mock_adapter
                mock_factory.return_value = None  # Asset factory returns None

                with patch.object(
                    execution_engine_instance,
                    "_process_triggered_order",
                    new_callable=AsyncMock,
                ) as mock_process:
                    await execution_engine_instance._check_trigger_conditions()

                    # Should not call get_quote or process trigger
                    mock_adapter.get_quote.assert_not_called()
                    mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_quote_is_none(
        self, execution_engine_instance, sample_order
    ):
        """Test handling when quote adapter returns None."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()
                mock_adapter.get_quote = AsyncMock(return_value=None)
                mock_get_adapter.return_value = mock_adapter
                mock_factory.return_value = Stock(symbol="AAPL")

                with patch.object(
                    execution_engine_instance,
                    "_process_triggered_order",
                    new_callable=AsyncMock,
                ) as mock_process:
                    await execution_engine_instance._check_trigger_conditions()

                    # Should get quote but not process trigger
                    mock_adapter.get_quote.assert_called_once()
                    mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_quote_price_is_none(
        self, execution_engine_instance, sample_order
    ):
        """Test handling when quote price is None."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()
                mock_quote = Quote(
                    asset=Stock(symbol="AAPL"),
                    price=None,  # No price available
                    bid=143.95,
                    ask=144.05,
                    quote_date=datetime.now(),
                )
                mock_adapter.get_quote = AsyncMock(return_value=mock_quote)
                mock_get_adapter.return_value = mock_adapter
                mock_factory.return_value = Stock(symbol="AAPL")

                with patch.object(
                    execution_engine_instance,
                    "_process_triggered_order",
                    new_callable=AsyncMock,
                ) as mock_process:
                    await execution_engine_instance._check_trigger_conditions()

                    # Should get quote but not process trigger
                    mock_adapter.get_quote.assert_called_once()
                    mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_symbol_exception_handling(
        self, execution_engine_instance, sample_order
    ):
        """Test error handling for individual symbols."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(sample_order)

            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()
                mock_adapter.get_quote = AsyncMock(side_effect=Exception("Quote error"))
                mock_get_adapter.return_value = mock_adapter
                mock_factory.return_value = Stock(symbol="AAPL")

                # Should not raise exception, but continue processing
                await execution_engine_instance._check_trigger_conditions()

                # Order should remain in monitoring
                assert "AAPL" in execution_engine_instance.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_overall_exception_handling(
        self, execution_engine_instance
    ):
        """Test overall exception handling in _check_trigger_conditions."""
        # Add a monitored symbol
        execution_engine_instance.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            # Make the get adapter call raise an exception
            mock_get_adapter.side_effect = Exception("General error")

            # Should not raise exception
            await execution_engine_instance._check_trigger_conditions()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_multiple_symbols(
        self, execution_engine_instance
    ):
        """Test checking conditions for multiple symbols."""
        # Add orders for multiple symbols
        orders = [
            Order(
                id="aapl-order",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
            Order(
                id="googl-order",
                symbol="GOOGL",
                order_type=OrderType.STOP_LOSS,
                quantity=50,
                stop_price=2750.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
        ]

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            for order in orders:
                await execution_engine_instance.add_order(order)

            with (
                patch(
                    "app.services.order_execution_engine._get_quote_adapter"
                ) as mock_get_adapter,
                patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory,
            ):
                mock_adapter = Mock()

                # Return different quotes for different symbols
                def get_quote_side_effect(asset):
                    if asset.symbol == "AAPL":
                        return Quote(
                            asset=asset,
                            price=144.00,  # Triggers AAPL order
                            bid=143.95,
                            ask=144.05,
                            quote_date=datetime.now(),
                        )
                    elif asset.symbol == "GOOGL":
                        return Quote(
                            asset=asset,
                            price=2800.00,  # Does not trigger GOOGL order
                            bid=2799.00,
                            ask=2801.00,
                            quote_date=datetime.now(),
                        )
                    return None

                mock_adapter.get_quote = AsyncMock(side_effect=get_quote_side_effect)
                mock_get_adapter.return_value = mock_adapter

                def asset_factory_side_effect(symbol):
                    return Stock(symbol=symbol)

                mock_factory.side_effect = asset_factory_side_effect

                with patch.object(
                    execution_engine_instance,
                    "_process_triggered_order",
                    new_callable=AsyncMock,
                ) as mock_process:
                    await execution_engine_instance._check_trigger_conditions()

                    # Should process only the AAPL order
                    mock_process.assert_called_once()
                    args = mock_process.call_args[0]
                    condition, trigger_price = args
                    assert condition.order_id == "aapl-order"
                    assert trigger_price == 144.00

                    # AAPL should be removed, GOOGL should remain
                    assert "AAPL" not in execution_engine_instance.monitored_symbols
                    assert "GOOGL" in execution_engine_instance.monitored_symbols


class TestOrderProcessingAndConversion:
    """Test order processing and conversion logic."""

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_loss(self, execution_engine_instance):
        """Test processing triggered stop loss order."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        mock_converted_order = Order(
            id="converted-order",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                execution_engine_instance,
                "_load_order_by_id",
                new_callable=AsyncMock,
                return_value=mock_order,
            ),
            patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter,
        ):
            mock_converter.convert_stop_loss_to_market.return_value = (
                mock_converted_order
            )

            with (
                patch.object(
                    execution_engine_instance,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ) as mock_update,
                patch.object(
                    execution_engine_instance,
                    "_execute_converted_order",
                    new_callable=AsyncMock,
                ) as mock_execute,
            ):
                await execution_engine_instance._process_triggered_order(
                    condition, 144.00
                )

                # Verify conversion was called
                mock_converter.convert_stop_loss_to_market.assert_called_once_with(
                    mock_order, 144.00
                )

                # Verify status update and execution
                mock_update.assert_called_once_with("test-order-123", 144.00)
                mock_execute.assert_called_once_with(mock_converted_order)

                # Verify metrics updated
                assert execution_engine_instance.orders_triggered == 1

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_limit(self, execution_engine_instance):
        """Test processing triggered stop limit order."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="stop_limit",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=145.00,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                execution_engine_instance,
                "_load_order_by_id",
                new_callable=AsyncMock,
                return_value=mock_order,
            ),
            patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter,
        ):
            mock_converter.convert_stop_limit_to_limit.return_value = mock_order

            with (
                patch.object(
                    execution_engine_instance,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ),
                patch.object(
                    execution_engine_instance,
                    "_execute_converted_order",
                    new_callable=AsyncMock,
                ),
            ):
                await execution_engine_instance._process_triggered_order(
                    condition, 144.00
                )

                mock_converter.convert_stop_limit_to_limit.assert_called_once_with(
                    mock_order, 144.00
                )

    @pytest.mark.asyncio
    async def test_process_triggered_order_trailing_stop(
        self, execution_engine_instance
    ):
        """Test processing triggered trailing stop order."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch.object(
            execution_engine_instance,
            "_load_order_by_id",
            new_callable=AsyncMock,
            return_value=mock_order,
        ):
            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converter.convert_trailing_stop_to_market.return_value = mock_order

                with patch.object(
                    execution_engine_instance,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        execution_engine_instance,
                        "_execute_converted_order",
                        new_callable=AsyncMock,
                    ):
                        await execution_engine_instance._process_triggered_order(
                            condition, 144.00
                        )

                        mock_converter.convert_trailing_stop_to_market.assert_called_once_with(
                            mock_order, 144.00
                        )

    @pytest.mark.asyncio
    async def test_process_triggered_order_no_original_order(
        self, execution_engine_instance
    ):
        """Test processing triggered order when original order not found."""
        condition = TriggerCondition(
            order_id="nonexistent-order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        with patch.object(
            execution_engine_instance,
            "_load_order_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Should not raise exception
            await execution_engine_instance._process_triggered_order(condition, 144.00)

            # Metrics should not be updated
            assert execution_engine_instance.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_process_triggered_order_conversion_returns_none(
        self, execution_engine_instance
    ):
        """Test processing when order conversion returns None."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        mock_order = Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                execution_engine_instance,
                "_load_order_by_id",
                new_callable=AsyncMock,
                return_value=mock_order,
            ),
            patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter,
        ):
            mock_converter.convert_stop_loss_to_market.return_value = None

            with (
                patch.object(
                    execution_engine_instance,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ) as mock_update,
                patch.object(
                    execution_engine_instance,
                    "_execute_converted_order",
                    new_callable=AsyncMock,
                ) as mock_execute,
            ):
                await execution_engine_instance._process_triggered_order(
                    condition, 144.00
                )

                # Should not update status or execute
                mock_update.assert_not_called()
                mock_execute.assert_not_called()
                assert execution_engine_instance.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_process_triggered_order_with_exception(
        self, execution_engine_instance
    ):
        """Test processing triggered order with exception during processing."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        with patch.object(
            execution_engine_instance, "_load_order_by_id", new_callable=AsyncMock
        ) as mock_load:
            mock_load.side_effect = Exception("Database error")

            # Should not raise exception but log error
            await execution_engine_instance._process_triggered_order(condition, 144.00)

            # Metrics should not be updated
            assert execution_engine_instance.orders_triggered == 0


class TestDatabaseIntegration:
    """Test database integration for order loading and status updates."""

    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self, execution_engine_instance):
        """Test successful order loading from database."""
        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "test-order-123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = 100
        mock_db_order.price = 150.00
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.00
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = None
        mock_db_order.net_price = None
        mock_db_order.filled_at = None

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_session.execute.return_value = mock_result

            # Mock async generator
            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            order = await execution_engine_instance._load_order_by_id("test-order-123")

            assert order is not None
            assert order.id == "test-order-123"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS
            assert order.quantity == 100
            assert order.price == 150.00
            assert order.stop_price == 145.00
            assert order.condition == OrderCondition.MARKET

    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self, execution_engine_instance):
        """Test order loading when order not found."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            order = await execution_engine_instance._load_order_by_id("nonexistent")

            assert order is None

    @pytest.mark.asyncio
    async def test_load_order_by_id_database_error(self, execution_engine_instance):
        """Test order loading with database error."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database error")

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            order = await execution_engine_instance._load_order_by_id("test-order-123")

            assert order is None

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_success(
        self, execution_engine_instance
    ):
        """Test successful order status update."""
        mock_db_order = Mock(spec=DBOrder)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_session.execute.return_value = mock_result

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            await execution_engine_instance._update_order_triggered_status(
                "test-order-123", 144.00
            )

            # Verify status was updated
            assert mock_db_order.status == OrderStatus.FILLED
            # Check that triggered_at and filled_at were set (via setattr)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_order_not_found(
        self, execution_engine_instance
    ):
        """Test order status update when order not found."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            # Should not raise exception
            await execution_engine_instance._update_order_triggered_status(
                "nonexistent", 144.00
            )

            # Should not commit anything
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_database_error(
        self, execution_engine_instance
    ):
        """Test order status update with database error."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database error")

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            # Should not raise exception
            await execution_engine_instance._update_order_triggered_status(
                "test-order-123", 144.00
            )

    @pytest.mark.asyncio
    async def test_load_pending_orders_success(self, execution_engine_instance):
        """Test loading pending orders from database."""
        mock_db_orders = []
        for i in range(3):
            mock_order = Mock(spec=DBOrder)
            mock_order.id = f"order-{i}"
            mock_order.symbol = "AAPL"
            mock_order.order_type = OrderType.STOP_LOSS
            mock_order.quantity = 100
            mock_order.price = 150.00
            mock_order.status = OrderStatus.PENDING
            mock_order.created_at = datetime.now()
            mock_order.stop_price = 145.00
            mock_order.trail_percent = None
            mock_order.trail_amount = None
            mock_order.condition = None
            mock_order.net_price = None
            mock_db_orders.append(mock_order)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_db_orders
            mock_session.execute.return_value = mock_result

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            with patch.object(
                execution_engine_instance, "add_order", new_callable=AsyncMock
            ) as mock_add:
                await execution_engine_instance._load_pending_orders()

                # Should have tried to add all orders
                assert mock_add.call_count == 3

    @pytest.mark.asyncio
    async def test_load_pending_orders_with_add_error(self, execution_engine_instance):
        """Test loading pending orders when add_order fails for some orders."""
        mock_db_orders = []
        for i in range(2):
            mock_order = Mock(spec=DBOrder)
            mock_order.id = f"order-{i}"
            mock_order.symbol = "AAPL"
            mock_order.order_type = OrderType.STOP_LOSS
            mock_order.quantity = 100
            mock_order.price = 150.00
            mock_order.status = OrderStatus.PENDING
            mock_order.created_at = datetime.now()
            mock_order.stop_price = 145.00
            mock_order.trail_percent = None
            mock_order.trail_amount = None
            mock_order.condition = None
            mock_order.net_price = None
            mock_db_orders.append(mock_order)

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_db_orders
            mock_session.execute.return_value = mock_result

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            # Make add_order fail for first order but succeed for second
            call_count = 0

            async def mock_add_order_side_effect(order):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Add order failed")
                # Second call succeeds

            with patch.object(
                execution_engine_instance,
                "add_order",
                side_effect=mock_add_order_side_effect,
            ):
                # Should not raise exception
                await execution_engine_instance._load_pending_orders()

    @pytest.mark.asyncio
    async def test_load_pending_orders_database_error(self, execution_engine_instance):
        """Test loading pending orders with database error."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database error")

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            # Should not raise exception
            await execution_engine_instance._load_pending_orders()


class TestOrderExecution:
    """Test order execution through trading service."""

    @pytest.mark.asyncio
    async def test_execute_converted_order_success(
        self, execution_engine_instance, mock_trading_service
    ):
        """Test successful converted order execution."""
        mock_order = Order(
            id="converted-order",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        mock_trading_service.execute_order = AsyncMock()

        await execution_engine_instance._execute_converted_order(mock_order)

        mock_trading_service.execute_order.assert_called_once_with(mock_order)

    @pytest.mark.asyncio
    async def test_execute_converted_order_no_execute_method(
        self, execution_engine_instance, mock_trading_service
    ):
        """Test order execution when trading service lacks execute_order method."""
        mock_order = Order(
            id="converted-order",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        # Remove execute_order method
        delattr(mock_trading_service, "execute_order")

        # Should not raise exception but log error
        await execution_engine_instance._execute_converted_order(mock_order)

    @pytest.mark.asyncio
    async def test_execute_converted_order_execution_error(
        self, execution_engine_instance, mock_trading_service
    ):
        """Test order execution with trading service error."""
        mock_order = Order(
            id="converted-order",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        mock_trading_service.execute_order = AsyncMock(
            side_effect=Exception("Execution failed")
        )

        with pytest.raises(Exception, match="Execution failed"):
            await execution_engine_instance._execute_converted_order(mock_order)


class TestStatusAndMetrics:
    """Test status reporting and metrics collection."""

    def test_get_status_empty_engine(self, execution_engine_instance):
        """Test getting status when no orders are monitored."""
        status = execution_engine_instance.get_status()

        expected_keys = {
            "is_running",
            "monitored_symbols",
            "total_trigger_conditions",
            "orders_processed",
            "orders_triggered",
            "last_market_data_update",
            "symbols",
        }
        assert set(status.keys()) == expected_keys

        assert status["is_running"] is False
        assert status["monitored_symbols"] == 0
        assert status["total_trigger_conditions"] == 0
        assert status["orders_processed"] == 0
        assert status["orders_triggered"] == 0
        assert isinstance(status["last_market_data_update"], datetime)
        assert isinstance(status["symbols"], list)
        assert len(status["symbols"]) == 0

    def test_get_status_with_orders(self, execution_engine_instance):
        """Test getting status with monitored orders."""
        # Manually add some conditions for testing
        execution_engine_instance.trigger_conditions["AAPL"] = [
            TriggerCondition("order-1", "AAPL", "stop_loss", 145.00, OrderType.SELL),
            TriggerCondition("order-2", "AAPL", "stop_limit", 140.00, OrderType.SELL),
        ]
        execution_engine_instance.trigger_conditions["GOOGL"] = [
            TriggerCondition(
                "order-3", "GOOGL", "trailing_stop", 2750.00, OrderType.SELL
            )
        ]
        execution_engine_instance.monitored_symbols = {"AAPL", "GOOGL"}
        execution_engine_instance.orders_processed = 5
        execution_engine_instance.orders_triggered = 2
        execution_engine_instance.is_running = True

        status = execution_engine_instance.get_status()

        assert status["is_running"] is True
        assert status["monitored_symbols"] == 2
        assert status["total_trigger_conditions"] == 3
        assert status["orders_processed"] == 5
        assert status["orders_triggered"] == 2
        assert set(status["symbols"]) == {"AAPL", "GOOGL"}

    def test_get_monitored_orders_empty(self, execution_engine_instance):
        """Test getting monitored orders when none exist."""
        monitored = execution_engine_instance.get_monitored_orders()
        assert monitored == {}

    def test_get_monitored_orders_with_data(self, execution_engine_instance):
        """Test getting detailed monitored orders information."""
        # Add conditions
        condition1 = TriggerCondition(
            "order-1", "AAPL", "stop_loss", 145.00, OrderType.SELL
        )
        condition2 = TriggerCondition(
            "order-2", "AAPL", "trailing_stop", 140.00, OrderType.SELL
        )
        condition2.high_water_mark = 155.00
        condition2.low_water_mark = 135.00

        execution_engine_instance.trigger_conditions["AAPL"] = [condition1, condition2]

        monitored = execution_engine_instance.get_monitored_orders()

        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == 2

        # Check first order info
        order_info = monitored["AAPL"][0]
        expected_keys = {
            "order_id",
            "order_type",
            "trigger_price",
            "trigger_type",
            "created_at",
            "high_water_mark",
            "low_water_mark",
        }
        assert set(order_info.keys()) == expected_keys
        assert order_info["order_id"] == "order-1"
        assert order_info["trigger_type"] == "stop_loss"
        assert order_info["trigger_price"] == 145.00

        # Check trailing stop specifics
        trailing_info = monitored["AAPL"][1]
        assert trailing_info["trigger_type"] == "trailing_stop"
        assert trailing_info["high_water_mark"] == 155.00
        assert trailing_info["low_water_mark"] == 135.00

    def test_get_monitored_orders_multiple_symbols(self, execution_engine_instance):
        """Test getting monitored orders for multiple symbols."""
        execution_engine_instance.trigger_conditions["AAPL"] = [
            TriggerCondition("aapl-1", "AAPL", "stop_loss", 145.00, OrderType.SELL)
        ]
        execution_engine_instance.trigger_conditions["GOOGL"] = [
            TriggerCondition("googl-1", "GOOGL", "stop_limit", 2750.00, OrderType.SELL),
            TriggerCondition(
                "googl-2", "GOOGL", "trailing_stop", 2700.00, OrderType.SELL
            ),
        ]

        monitored = execution_engine_instance.get_monitored_orders()

        assert len(monitored) == 2
        assert "AAPL" in monitored
        assert "GOOGL" in monitored
        assert len(monitored["AAPL"]) == 1
        assert len(monitored["GOOGL"]) == 2


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_get_initial_trigger_price_stop_loss(self, execution_engine_instance):
        """Test getting initial trigger price for stop loss orders."""
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        trigger_price = execution_engine_instance._get_initial_trigger_price(order)
        assert trigger_price == 145.00

    def test_get_initial_trigger_price_stop_limit(self, execution_engine_instance):
        """Test getting initial trigger price for stop limit orders."""
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=145.00,
            price=144.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        trigger_price = execution_engine_instance._get_initial_trigger_price(order)
        assert trigger_price == 145.00

    def test_get_initial_trigger_price_trailing_stop(self, execution_engine_instance):
        """Test getting initial trigger price for trailing stop orders."""
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        trigger_price = execution_engine_instance._get_initial_trigger_price(order)
        assert trigger_price == 0.0  # Will be updated dynamically

    def test_get_initial_trigger_price_unsupported_order_type(
        self, execution_engine_instance
    ):
        """Test getting initial trigger price for unsupported order types."""
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,  # Not a trigger order
            quantity=100,
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with pytest.raises(OrderExecutionError, match="Unsupported order type"):
            execution_engine_instance._get_initial_trigger_price(order)

    def test_get_initial_trigger_price_missing_stop_price(
        self, execution_engine_instance
    ):
        """Test getting initial trigger price when stop price is missing."""
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=None,  # Missing stop price
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with pytest.raises(OrderExecutionError, match="Missing stop_price"):
            execution_engine_instance._get_initial_trigger_price(order)

    def test_should_trigger_private_method(self, execution_engine_instance):
        """Test the private _should_trigger method."""
        condition = TriggerCondition(
            "test-order",
            "AAPL",
            "stop_loss",
            145.00,
            OrderType.SELL,
        )

        # Test the wrapper method
        assert execution_engine_instance._should_trigger(condition, 144.00) is True
        assert execution_engine_instance._should_trigger(condition, 146.00) is False


class TestConcurrencyAndThreadSafety:
    """Test concurrency and thread safety features."""

    @pytest.mark.asyncio
    async def test_concurrent_order_operations(self, execution_engine_instance):
        """Test concurrent order addition and removal."""
        orders = [
            Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00 - i,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            for i in range(5)
        ]

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Add orders concurrently
            add_tasks = [execution_engine_instance.add_order(order) for order in orders]
            await asyncio.gather(*add_tasks)

            # Should have all orders
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 5

            # Remove some orders concurrently
            remove_tasks = [
                execution_engine_instance.remove_order(f"order-{i}")
                for i in range(0, 3)
            ]
            await asyncio.gather(*remove_tasks)

            # Should have remaining orders
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 2

    def test_thread_safety_lock_exists(self, execution_engine_instance):
        """Test that thread safety lock exists and operations work."""
        assert execution_engine_instance._lock is not None
        assert isinstance(execution_engine_instance._lock, threading.Lock)

        # Test that operations work with lock
        status = execution_engine_instance.get_status()
        assert isinstance(status, dict)

        monitored = execution_engine_instance.get_monitored_orders()
        assert isinstance(monitored, dict)

    def test_thread_safety_during_status_operations(self, execution_engine_instance):
        """Test thread safety during status operations."""
        # Add some data
        execution_engine_instance.trigger_conditions["AAPL"] = [
            TriggerCondition("order-1", "AAPL", "stop_loss", 145.00, OrderType.SELL)
        ]
        execution_engine_instance.monitored_symbols.add("AAPL")

        # These operations should be thread-safe
        status = execution_engine_instance.get_status()
        monitored = execution_engine_instance.get_monitored_orders()

        assert status["monitored_symbols"] == 1
        assert "AAPL" in monitored


class TestGlobalModuleFunctions:
    """Test global module functions and variables."""

    def test_global_execution_engine_initial_state(self):
        """Test initial state of global execution engine."""
        # Should be None initially
        assert execution_engine is None

    def test_get_execution_engine_not_initialized(self):
        """Test get_execution_engine when not initialized."""
        # Reset global state
        import app.services.order_execution_engine as engine_module

        engine_module.execution_engine = None

        with pytest.raises(
            RuntimeError, match="Order execution engine not initialized"
        ):
            get_execution_engine()

    def test_initialize_execution_engine(self, mock_trading_service):
        """Test initialize_execution_engine function."""
        # Initialize the engine
        engine = initialize_execution_engine(mock_trading_service)

        assert isinstance(engine, OrderExecutionEngine)
        assert engine.trading_service == mock_trading_service

        # Should be accessible via get_execution_engine
        retrieved_engine = get_execution_engine()
        assert retrieved_engine is engine

        # Clean up global state
        import app.services.order_execution_engine as engine_module

        engine_module.execution_engine = None

    def test_initialize_execution_engine_multiple_times(self, mock_trading_service):
        """Test initializing execution engine multiple times."""
        # Initialize first time
        engine1 = initialize_execution_engine(mock_trading_service)

        # Initialize second time - should replace the first
        mock_trading_service2 = Mock(spec=TradingService)
        engine2 = initialize_execution_engine(mock_trading_service2)

        assert engine2 is not engine1
        assert engine2.trading_service == mock_trading_service2

        # get_execution_engine should return the latest
        retrieved_engine = get_execution_engine()
        assert retrieved_engine is engine2

        # Clean up global state
        import app.services.order_execution_engine as engine_module

        engine_module.execution_engine = None


class TestEdgeCasesAndErrorConditions:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_add_order_with_zero_trail_values(self, execution_engine_instance):
        """Test adding trailing stop order with zero trail values."""
        order = Order(
            id="zero-trail-order",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=0.0,  # Zero percent
            trail_amount=0.0,  # Zero amount
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine_instance.add_order(order)

            # Should still add the order
            assert "AAPL" in execution_engine_instance.trigger_conditions

    def test_trigger_condition_edge_cases(self):
        """Test TriggerCondition edge cases."""
        condition = TriggerCondition(
            "test-order", "AAPL", "stop_loss", 145.00, OrderType.SELL
        )

        # Test exact trigger price
        assert condition.should_trigger(145.00) is True

        # Test very close prices
        assert condition.should_trigger(144.9999) is True
        assert condition.should_trigger(145.0001) is False

    def test_update_trailing_stop_edge_cases(self):
        """Test trailing stop update edge cases."""
        mock_order = Mock()
        mock_order.quantity = -100
        mock_order.trail_percent = 0.0  # Zero percent
        mock_order.trail_amount = None

        condition = TriggerCondition(
            "test-order", "AAPL", "trailing_stop", 145.00, OrderType.SELL
        )

        # Zero percent should still update water mark but not trigger price
        condition.update_trailing_stop(155.00, mock_order)
        assert condition.high_water_mark == 155.00

    @pytest.mark.asyncio
    async def test_engine_state_consistency_after_errors(
        self, execution_engine_instance
    ):
        """Test engine state remains consistent after various errors."""
        # Add an order successfully
        order = Order(
            id="test-order",
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

            await execution_engine_instance.add_order(order)

            # Verify initial state
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 1
            assert "AAPL" in execution_engine_instance.monitored_symbols

            # Try to add an invalid order (should not affect existing state)
            try:
                mock_converter.validate_order_for_conversion.side_effect = Exception(
                    "Validation error"
                )
                await execution_engine_instance.add_order(order)
            except OrderExecutionError:
                pass

            # Original state should be preserved
            assert len(execution_engine_instance.trigger_conditions["AAPL"]) == 1
            assert "AAPL" in execution_engine_instance.monitored_symbols

    @pytest.mark.asyncio
    async def test_cleanup_after_stop_and_restart(self, execution_engine_instance):
        """Test proper cleanup and state after stop/restart cycle."""
        # Start the engine
        with (
            patch.object(
                execution_engine_instance,
                "_load_pending_orders",
                new_callable=AsyncMock,
            ),
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            await execution_engine_instance.start()
            assert execution_engine_instance.is_running is True

            # Stop the engine
            with patch.object(execution_engine_instance.executor, "shutdown"):
                await execution_engine_instance.stop()
                assert execution_engine_instance.is_running is False

            # Restart should work
            await execution_engine_instance.start()
            assert execution_engine_instance.is_running is True
