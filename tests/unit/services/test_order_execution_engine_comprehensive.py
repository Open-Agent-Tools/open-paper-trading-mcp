"""
Comprehensive tests for OrderExecutionEngine - persistent background order execution service.

Tests cover:
- Engine initialization and lifecycle management
- Trigger condition creation and evaluation
- Order monitoring loop functionality
- Order conversion and execution
- Background task management
- Database integration for order loading
- Error handling and recovery
- Performance metrics and status reporting
- Thread safety and concurrency
- Stop loss, stop limit, and trailing stop orders
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from decimal import Decimal

from app.schemas.orders import Order, OrderStatus, OrderType, OrderCondition
from app.models.database.trading import Order as DBOrder
from app.services.order_execution_engine import (
    OrderExecutionEngine,
    TriggerCondition,
    OrderExecutionError,
)
from app.services.trading_service import TradingService
from app.models.quotes import Quote
from app.models.assets import Stock


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
def sample_trailing_stop_order():
    """Sample trailing stop order for testing."""
    return Order(
        id="trailing-order-123",
        symbol="AAPL",
        order_type=OrderType.TRAILING_STOP,
        quantity=100,
        price=None,
        trail_percent=5.0,  # 5% trailing stop
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_quote():
    """Sample quote for testing."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        price=150.00,
        bid=149.95,
        ask=150.05,
        quote_date=datetime.now(),
    )


@pytest.fixture
def execution_engine(mock_trading_service):
    """Order execution engine instance for testing."""
    return OrderExecutionEngine(mock_trading_service)


class TestOrderExecutionEngineInitialization:
    """Test engine initialization and configuration."""

    def test_initialization(self, mock_trading_service):
        """Test engine initialization with trading service."""
        engine = OrderExecutionEngine(mock_trading_service)

        assert engine.trading_service == mock_trading_service
        assert engine.is_running is False
        assert engine.monitoring_task is None
        assert engine.executor is not None
        assert isinstance(engine.trigger_conditions, dict)
        assert isinstance(engine.monitored_symbols, set)
        assert engine.orders_processed == 0
        assert engine.orders_triggered == 0
        assert engine._lock is not None

    def test_initial_metrics(self, execution_engine):
        """Test initial performance metrics."""
        assert execution_engine.orders_processed == 0
        assert execution_engine.orders_triggered == 0
        assert execution_engine.last_market_data_update is not None
        assert isinstance(execution_engine.last_market_data_update, datetime)

    def test_initial_collections(self, execution_engine):
        """Test initial collection states."""
        assert len(execution_engine.trigger_conditions) == 0
        assert len(execution_engine.monitored_symbols) == 0


class TestEngineLifecycleManagement:
    """Test engine start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_engine(self, execution_engine):
        """Test starting the execution engine."""
        with patch.object(
            execution_engine, "_load_pending_orders", new_callable=AsyncMock
        ):
            with patch("asyncio.create_task") as mock_create_task:
                mock_task = Mock()
                mock_create_task.return_value = mock_task

                await execution_engine.start()

                assert execution_engine.is_running is True
                assert execution_engine.monitoring_task == mock_task
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_engine_already_running(self, execution_engine):
        """Test starting engine when already running."""
        execution_engine.is_running = True

        with patch.object(
            execution_engine, "_load_pending_orders", new_callable=AsyncMock
        ) as mock_load:
            await execution_engine.start()

            # Should not reload orders
            mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_engine(self, execution_engine):
        """Test stopping the execution engine."""
        # Set up running state
        execution_engine.is_running = True
        mock_task = Mock()
        mock_task.cancel = Mock()
        execution_engine.monitoring_task = mock_task

        with patch.object(execution_engine.executor, "shutdown") as mock_shutdown:
            await execution_engine.stop()

            assert execution_engine.is_running is False
            mock_task.cancel.assert_called_once()
            mock_shutdown.assert_called_once_with(wait=True)

    @pytest.mark.asyncio
    async def test_stop_engine_not_running(self, execution_engine):
        """Test stopping engine when not running."""
        execution_engine.is_running = False

        with patch.object(execution_engine.executor, "shutdown") as mock_shutdown:
            await execution_engine.stop()

            # Should not shutdown executor
            mock_shutdown.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_engine_with_task_cancellation(self, execution_engine):
        """Test stopping engine with proper task cancellation."""
        execution_engine.is_running = True

        # Mock monitoring task that raises CancelledError
        mock_task = AsyncMock()
        mock_task.cancel = Mock()
        execution_engine.monitoring_task = mock_task

        with patch.object(execution_engine.executor, "shutdown"):
            await execution_engine.stop()

            mock_task.cancel.assert_called_once()


class TestTriggerConditionLogic:
    """Test trigger condition creation and evaluation."""

    def test_trigger_condition_creation(self):
        """Test creating trigger conditions."""
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

    def test_stop_loss_trigger_sell(self):
        """Test stop loss trigger for sell orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Price above trigger - should not trigger
        assert condition.should_trigger(150.00) is False

        # Price at trigger - should trigger
        assert condition.should_trigger(145.00) is True

        # Price below trigger - should trigger
        assert condition.should_trigger(140.00) is True

    def test_stop_loss_trigger_buy(self):
        """Test stop loss trigger for buy orders."""
        condition = TriggerCondition(
            order_id="test-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=155.00,
            order_type=OrderType.BUY,
        )

        # Price below trigger - should not trigger
        assert condition.should_trigger(150.00) is False

        # Price at trigger - should trigger
        assert condition.should_trigger(155.00) is True

        # Price above trigger - should trigger
        assert condition.should_trigger(160.00) is True

    def test_trailing_stop_update_percentage_sell(self):
        """Test trailing stop updates for percentage-based sell orders."""
        # Mock order with trail_percent
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
        new_trigger = 155.00 * (1 - 0.05)  # 5% trail
        assert abs(condition.trigger_price - new_trigger) < 0.01

        # Price goes down but not below new trigger - no update
        updated = condition.update_trailing_stop(150.00, mock_order)
        assert updated is False
        assert condition.high_water_mark == 155.00  # Unchanged

    def test_trailing_stop_update_dollar_amount_sell(self):
        """Test trailing stop updates for dollar amount-based sell orders."""
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

    def test_trailing_stop_update_buy_order(self):
        """Test trailing stop updates for buy orders."""
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
        new_trigger = 145.00 * (1 + 0.05)  # 5% above low
        assert abs(condition.trigger_price - new_trigger) < 0.01

    def test_trailing_stop_non_trailing_type(self):
        """Test trailing stop update on non-trailing condition."""
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


class TestOrderManagement:
    """Test adding and removing orders from monitoring."""

    @pytest.mark.asyncio
    async def test_add_order_success(self, execution_engine, sample_order):
        """Test successfully adding an order for monitoring."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            # Check that order was added to monitoring
            assert "AAPL" in execution_engine.trigger_conditions
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            assert "AAPL" in execution_engine.monitored_symbols

            condition = execution_engine.trigger_conditions["AAPL"][0]
            assert condition.order_id == "test-order-123"
            assert condition.symbol == "AAPL"
            assert condition.trigger_type == "stop_loss"

    @pytest.mark.asyncio
    async def test_add_order_not_convertible(self, execution_engine, sample_order):
        """Test adding order that can't be converted."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = False

            await execution_engine.add_order(sample_order)

            # Order should not be added
            assert len(execution_engine.trigger_conditions) == 0
            assert len(execution_engine.monitored_symbols) == 0

    @pytest.mark.asyncio
    async def test_add_order_validation_error(self, execution_engine, sample_order):
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
                await execution_engine.add_order(sample_order)

    @pytest.mark.asyncio
    async def test_remove_order_success(self, execution_engine, sample_order):
        """Test successfully removing an order from monitoring."""
        # First add an order
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            # Verify it was added
            assert "AAPL" in execution_engine.trigger_conditions
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1

            # Remove the order
            await execution_engine.remove_order("test-order-123")

            # Verify it was removed
            assert "AAPL" not in execution_engine.trigger_conditions
            assert "AAPL" not in execution_engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_remove_order_multiple_conditions(self, execution_engine):
        """Test removing one order when multiple conditions exist for same symbol."""
        # Add multiple orders for same symbol
        order1 = Order(
            id="order-1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        order2 = Order(
            id="order-2",
            symbol="AAPL",
            order_type=OrderType.STOP_LIMIT,
            quantity=50,
            stop_price=140.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(order1)
            await execution_engine.add_order(order2)

            # Should have 2 conditions for AAPL
            assert len(execution_engine.trigger_conditions["AAPL"]) == 2

            # Remove one order
            await execution_engine.remove_order("order-1")

            # Should still have 1 condition and symbol should remain monitored
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            assert "AAPL" in execution_engine.monitored_symbols

            # Verify correct order was removed
            remaining_condition = execution_engine.trigger_conditions["AAPL"][0]
            assert remaining_condition.order_id == "order-2"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_order(self, execution_engine):
        """Test removing an order that doesn't exist."""
        # Should not raise an error
        await execution_engine.remove_order("nonexistent-order")

        assert len(execution_engine.trigger_conditions) == 0


class TestMonitoringLoop:
    """Test the monitoring loop functionality."""

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_symbols(self, execution_engine):
        """Test trigger condition checking with no monitored symbols."""
        # Should return early with no symbols
        await execution_engine._check_trigger_conditions()

        # No errors should occur
        assert execution_engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_with_specific_price(
        self, execution_engine, sample_order
    ):
        """Test trigger condition checking with specific symbol and price."""
        # Add an order to monitor
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            # Mock order processing
            with patch.object(
                execution_engine, "_process_triggered_order", new_callable=AsyncMock
            ) as mock_process:
                # Check with triggering price
                await execution_engine._check_trigger_conditions(
                    "AAPL", 144.00
                )  # Below stop loss

                # Should trigger the order
                mock_process.assert_called_once()

                # Order should be removed from monitoring
                assert "AAPL" not in execution_engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_trigger(
        self, execution_engine, sample_order
    ):
        """Test trigger condition checking that doesn't trigger."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            with patch.object(
                execution_engine, "_process_triggered_order", new_callable=AsyncMock
            ) as mock_process:
                # Check with non-triggering price
                await execution_engine._check_trigger_conditions(
                    "AAPL", 150.00
                )  # Above stop loss

                # Should not trigger
                mock_process.assert_not_called()

                # Order should remain in monitoring
                assert "AAPL" in execution_engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_quote_adapter_integration(
        self, execution_engine, sample_order
    ):
        """Test trigger condition checking with quote adapter integration."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            # Mock quote adapter
            with patch(
                "app.services.order_execution_engine._get_quote_adapter"
            ) as mock_get_adapter:
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

                with patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory:
                    mock_factory.return_value = Stock(symbol="AAPL")

                    with patch.object(
                        execution_engine,
                        "_process_triggered_order",
                        new_callable=AsyncMock,
                    ) as mock_process:
                        # Check without specific price (should use adapter)
                        await execution_engine._check_trigger_conditions()

                        # Should get quote and trigger
                        mock_adapter.get_quote.assert_called_once()
                        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_error_handling(
        self, execution_engine, sample_order
    ):
        """Test error handling in trigger condition checking."""
        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await execution_engine.add_order(sample_order)

            # Mock quote adapter to raise exception
            with patch(
                "app.services.order_execution_engine._get_quote_adapter"
            ) as mock_get_adapter:
                mock_adapter = Mock()
                mock_adapter.get_quote = AsyncMock(side_effect=Exception("Quote error"))
                mock_get_adapter.return_value = mock_adapter

                with patch(
                    "app.services.order_execution_engine.asset_factory"
                ) as mock_factory:
                    mock_factory.return_value = Stock(symbol="AAPL")

                    # Should not raise exception, but continue processing
                    await execution_engine._check_trigger_conditions()

                    # Order should remain in monitoring
                    assert "AAPL" in execution_engine.monitored_symbols


class TestOrderProcessing:
    """Test order processing and conversion."""

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_loss(self, execution_engine):
        """Test processing triggered stop loss order."""
        condition = TriggerCondition(
            order_id="test-order-123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Mock order loading
        mock_order = Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch.object(
            execution_engine, "_load_order_by_id", return_value=mock_order
        ):
            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converted_order = Order(
                    id="converted-order",
                    symbol="AAPL",
                    order_type=OrderType.SELL,
                    quantity=100,
                    price=144.00,
                    status=OrderStatus.PENDING,
                    created_at=datetime.now(),
                )
                mock_converter.convert_stop_loss_to_market.return_value = (
                    mock_converted_order
                )

                with patch.object(
                    execution_engine,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        execution_engine,
                        "_execute_converted_order",
                        new_callable=AsyncMock,
                    ):
                        await execution_engine._process_triggered_order(
                            condition, 144.00
                        )

                        # Verify conversion was called
                        mock_converter.convert_stop_loss_to_market.assert_called_once_with(
                            mock_order, 144.00
                        )

                        # Verify order was executed
                        execution_engine._execute_converted_order.assert_called_once_with(
                            mock_converted_order
                        )

                        # Verify metrics updated
                        assert execution_engine.orders_triggered == 1

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_limit(self, execution_engine):
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

        with patch.object(
            execution_engine, "_load_order_by_id", return_value=mock_order
        ):
            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converter.convert_stop_limit_to_limit.return_value = mock_order

                with patch.object(
                    execution_engine,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        execution_engine,
                        "_execute_converted_order",
                        new_callable=AsyncMock,
                    ):
                        await execution_engine._process_triggered_order(
                            condition, 144.00
                        )

                        mock_converter.convert_stop_limit_to_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_triggered_order_trailing_stop(self, execution_engine):
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
            execution_engine, "_load_order_by_id", return_value=mock_order
        ):
            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converter.convert_trailing_stop_to_market.return_value = mock_order

                with patch.object(
                    execution_engine,
                    "_update_order_triggered_status",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        execution_engine,
                        "_execute_converted_order",
                        new_callable=AsyncMock,
                    ):
                        await execution_engine._process_triggered_order(
                            condition, 144.00
                        )

                        mock_converter.convert_trailing_stop_to_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_triggered_order_no_original(self, execution_engine):
        """Test processing triggered order when original order not found."""
        condition = TriggerCondition(
            order_id="nonexistent-order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        with patch.object(execution_engine, "_load_order_by_id", return_value=None):
            # Should not raise exception
            await execution_engine._process_triggered_order(condition, 144.00)

            # Metrics should not be updated
            assert execution_engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_process_triggered_order_conversion_error(self, execution_engine):
        """Test processing triggered order with conversion error."""
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

        with patch.object(
            execution_engine, "_load_order_by_id", return_value=mock_order
        ):
            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converter.convert_stop_loss_to_market.side_effect = Exception(
                    "Conversion error"
                )

                # Should not raise exception but log error
                await execution_engine._process_triggered_order(condition, 144.00)

                # Metrics should not be updated
                assert execution_engine.orders_triggered == 0


class TestDatabaseIntegration:
    """Test database integration for order loading and status updates."""

    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self, execution_engine):
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

            order = await execution_engine._load_order_by_id("test-order-123")

            assert order is not None
            assert order.id == "test-order-123"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS

    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self, execution_engine):
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

            order = await execution_engine._load_order_by_id("nonexistent")

            assert order is None

    @pytest.mark.asyncio
    async def test_load_order_by_id_database_error(self, execution_engine):
        """Test order loading with database error."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database error")

            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            order = await execution_engine._load_order_by_id("test-order-123")

            assert order is None

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_success(self, execution_engine):
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

            await execution_engine._update_order_triggered_status(
                "test-order-123", 144.00
            )

            # Verify status was updated
            assert mock_db_order.status == OrderStatus.FILLED
            assert mock_db_order.triggered_at is not None
            assert mock_db_order.filled_at is not None
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pending_orders_success(self, execution_engine):
        """Test loading pending orders from database."""
        mock_db_orders = [
            Mock(
                spec=DBOrder,
                id="order-1",
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                price=150.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                stop_price=145.00,
            ),
            Mock(
                spec=DBOrder,
                id="order-2",
                symbol="GOOGL",
                order_type=OrderType.STOP_LIMIT,
                quantity=50,
                price=2800.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                stop_price=2750.00,
            ),
        ]

        # Set additional required attributes
        for order in mock_db_orders:
            order.trail_percent = None
            order.trail_amount = None
            order.condition = None
            order.net_price = None

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
                execution_engine, "add_order", new_callable=AsyncMock
            ) as mock_add:
                await execution_engine._load_pending_orders()

                # Should have tried to add both orders
                assert mock_add.call_count == 2


class TestExecutionAndErrorHandling:
    """Test order execution and error handling."""

    @pytest.mark.asyncio
    async def test_execute_converted_order_success(
        self, execution_engine, mock_trading_service
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

        # Mock trading service has execute_order method
        mock_trading_service.execute_order = AsyncMock()

        await execution_engine._execute_converted_order(mock_order)

        mock_trading_service.execute_order.assert_called_once_with(mock_order)

    @pytest.mark.asyncio
    async def test_execute_converted_order_no_method(
        self, execution_engine, mock_trading_service
    ):
        """Test order execution when trading service lacks method."""
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
        del mock_trading_service.execute_order

        # Should not raise exception but log error
        await execution_engine._execute_converted_order(mock_order)

    @pytest.mark.asyncio
    async def test_execute_converted_order_execution_error(
        self, execution_engine, mock_trading_service
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
            await execution_engine._execute_converted_order(mock_order)


class TestStatusAndMetrics:
    """Test status reporting and metrics."""

    def test_get_status_empty(self, execution_engine):
        """Test getting status when no orders are monitored."""
        status = execution_engine.get_status()

        assert "is_running" in status
        assert "monitored_symbols" in status
        assert "total_trigger_conditions" in status
        assert "orders_processed" in status
        assert "orders_triggered" in status
        assert "last_market_data_update" in status
        assert "symbols" in status

        assert status["is_running"] is False
        assert status["monitored_symbols"] == 0
        assert status["total_trigger_conditions"] == 0
        assert status["orders_processed"] == 0
        assert status["orders_triggered"] == 0
        assert isinstance(status["symbols"], list)
        assert len(status["symbols"]) == 0

    def test_get_status_with_orders(self, execution_engine):
        """Test getting status with monitored orders."""
        # Manually add some conditions for testing
        execution_engine.trigger_conditions["AAPL"] = [
            TriggerCondition("order-1", "AAPL", "stop_loss", 145.00, OrderType.SELL),
            TriggerCondition("order-2", "AAPL", "stop_limit", 140.00, OrderType.SELL),
        ]
        execution_engine.trigger_conditions["GOOGL"] = [
            TriggerCondition(
                "order-3", "GOOGL", "trailing_stop", 2750.00, OrderType.SELL
            )
        ]
        execution_engine.monitored_symbols = {"AAPL", "GOOGL"}
        execution_engine.orders_processed = 5
        execution_engine.orders_triggered = 2

        status = execution_engine.get_status()

        assert status["monitored_symbols"] == 2
        assert status["total_trigger_conditions"] == 3
        assert status["orders_processed"] == 5
        assert status["orders_triggered"] == 2
        assert set(status["symbols"]) == {"AAPL", "GOOGL"}

    def test_get_monitored_orders(self, execution_engine):
        """Test getting detailed monitored orders information."""
        # Add conditions
        condition1 = TriggerCondition(
            "order-1", "AAPL", "stop_loss", 145.00, OrderType.SELL
        )
        condition2 = TriggerCondition(
            "order-2", "AAPL", "trailing_stop", 140.00, OrderType.SELL
        )
        condition2.high_water_mark = 155.00

        execution_engine.trigger_conditions["AAPL"] = [condition1, condition2]

        monitored = execution_engine.get_monitored_orders()

        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == 2

        order_info = monitored["AAPL"][0]
        assert "order_id" in order_info
        assert "order_type" in order_info
        assert "trigger_price" in order_info
        assert "trigger_type" in order_info
        assert "created_at" in order_info

        # Check trailing stop specifics
        trailing_info = monitored["AAPL"][1]
        assert trailing_info["trigger_type"] == "trailing_stop"
        assert trailing_info["high_water_mark"] == 155.00


class TestConcurrencyAndThreadSafety:
    """Test concurrency and thread safety features."""

    @pytest.mark.asyncio
    async def test_concurrent_order_operations(self, execution_engine):
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
            add_tasks = [execution_engine.add_order(order) for order in orders]
            await asyncio.gather(*add_tasks)

            # Should have all orders
            assert len(execution_engine.trigger_conditions["AAPL"]) == 5

            # Remove some orders concurrently
            remove_tasks = [
                execution_engine.remove_order(f"order-{i}") for i in range(0, 3)
            ]
            await asyncio.gather(*remove_tasks)

            # Should have remaining orders
            assert len(execution_engine.trigger_conditions["AAPL"]) == 2

    def test_thread_safety_with_lock(self, execution_engine):
        """Test that operations use thread safety lock."""
        # Lock should be acquired during operations
        assert execution_engine._lock is not None

        # Test that status operations work with lock
        status = execution_engine.get_status()
        assert isinstance(status, dict)

        monitored = execution_engine.get_monitored_orders()
        assert isinstance(monitored, dict)


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_get_initial_trigger_price_stop_loss(self, execution_engine):
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

        trigger_price = execution_engine._get_initial_trigger_price(order)
        assert trigger_price == 145.00

    def test_get_initial_trigger_price_stop_limit(self, execution_engine):
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

        trigger_price = execution_engine._get_initial_trigger_price(order)
        assert trigger_price == 145.00

    def test_get_initial_trigger_price_trailing_stop(self, execution_engine):
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

        trigger_price = execution_engine._get_initial_trigger_price(order)
        assert trigger_price == 0.0  # Will be updated dynamically

    def test_get_initial_trigger_price_unsupported(self, execution_engine):
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
            execution_engine._get_initial_trigger_price(order)

    def test_get_initial_trigger_price_missing_stop_price(self, execution_engine):
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
            execution_engine._get_initial_trigger_price(order)
