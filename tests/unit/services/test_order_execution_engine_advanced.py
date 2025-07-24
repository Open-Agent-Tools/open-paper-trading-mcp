"""
Comprehensive test suite for OrderExecutionEngine.

Tests all order execution engine functionality including:
- Trigger condition management and evaluation
- Async monitoring loop and worker management
- Order processing and conversion
- Market data integration
- Error handling and recovery
- Performance and concurrency
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.assets import Stock
from app.models.database.trading import Order as DBOrder
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.order_execution_engine import (
    OrderExecutionEngine,
    OrderExecutionError,
    TriggerCondition,
    get_execution_engine,
    initialize_execution_engine,
)
from app.services.trading_service import TradingService


class TestTriggerCondition:
    """Test TriggerCondition class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.trigger = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

    def test_trigger_condition_initialization(self):
        """Test TriggerCondition initialization."""
        assert self.trigger.order_id == "test_order_123"
        assert self.trigger.symbol == "AAPL"
        assert self.trigger.trigger_type == "stop_loss"
        assert self.trigger.trigger_price == 145.0
        assert self.trigger.order_type == OrderType.SELL
        assert self.trigger.high_water_mark is None
        assert self.trigger.low_water_mark is None
        assert isinstance(self.trigger.created_at, datetime)

    def test_should_trigger_stop_loss_sell(self):
        """Test stop loss trigger for sell orders."""
        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        # Price drops below trigger - should trigger
        assert trigger.should_trigger(144.0) is True
        assert trigger.should_trigger(145.0) is True

        # Price above trigger - should not trigger
        assert trigger.should_trigger(146.0) is False

    def test_should_trigger_stop_loss_buy(self):
        """Test stop loss trigger for buy orders."""
        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=155.0,
            order_type=OrderType.BUY,
        )

        # Price rises above trigger - should trigger
        assert trigger.should_trigger(156.0) is True
        assert trigger.should_trigger(155.0) is True

        # Price below trigger - should not trigger
        assert trigger.should_trigger(154.0) is False

    def test_should_trigger_trailing_stop_sell(self):
        """Test trailing stop trigger for sell orders."""
        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        # Price drops below trigger - should trigger
        assert trigger.should_trigger(144.0) is True
        assert trigger.should_trigger(145.0) is True

        # Price above trigger - should not trigger
        assert trigger.should_trigger(146.0) is False

    def test_should_trigger_trailing_stop_buy(self):
        """Test trailing stop trigger for buy orders."""
        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=155.0,
            order_type=OrderType.BUY,
        )

        # Price rises above trigger - should trigger
        assert trigger.should_trigger(156.0) is True
        assert trigger.should_trigger(155.0) is True

        # Price below trigger - should not trigger
        assert trigger.should_trigger(154.0) is False

    def test_should_trigger_invalid_type(self):
        """Test trigger with invalid type."""
        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="invalid_type",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        assert trigger.should_trigger(144.0) is False
        assert trigger.should_trigger(146.0) is False

    def test_update_trailing_stop_percent_sell(self):
        """Test trailing stop update with percentage for sell orders."""
        mock_order = Mock()
        mock_order.quantity = 100  # Positive quantity = sell order
        mock_order.trail_percent = 5.0  # 5%
        mock_order.trail_amount = None

        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=140.0,  # Initial trigger
            order_type=OrderType.SELL,
        )

        # Price moves up - should update trigger
        updated = trigger.update_trailing_stop(150.0, mock_order)
        assert updated is True
        assert trigger.high_water_mark == 150.0
        expected_trigger = 150.0 * (1 - 0.05)  # 142.5
        assert abs(trigger.trigger_price - expected_trigger) < 0.01

        # Price moves down - should not update trigger
        old_trigger = trigger.trigger_price
        updated = trigger.update_trailing_stop(148.0, mock_order)
        assert updated is False
        assert trigger.trigger_price == old_trigger

    def test_update_trailing_stop_percent_buy(self):
        """Test trailing stop update with percentage for buy orders."""
        mock_order = Mock()
        mock_order.quantity = -100  # Negative quantity = buy order
        mock_order.trail_percent = 5.0  # 5%
        mock_order.trail_amount = None

        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=160.0,  # Initial trigger
            order_type=OrderType.BUY,
        )

        # Price moves down - should update trigger
        updated = trigger.update_trailing_stop(145.0, mock_order)
        assert updated is True
        assert trigger.low_water_mark == 145.0
        expected_trigger = 145.0 * (1 + 0.05)  # 152.25
        assert abs(trigger.trigger_price - expected_trigger) < 0.01

        # Price moves up - should not update trigger
        old_trigger = trigger.trigger_price
        updated = trigger.update_trailing_stop(147.0, mock_order)
        assert updated is False
        assert trigger.trigger_price == old_trigger

    def test_update_trailing_stop_amount_sell(self):
        """Test trailing stop update with dollar amount for sell orders."""
        mock_order = Mock()
        mock_order.quantity = 100  # Positive quantity = sell order
        mock_order.trail_percent = None
        mock_order.trail_amount = 5.0  # $5

        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=140.0,  # Initial trigger
            order_type=OrderType.SELL,
        )

        # Price moves up - should update trigger
        updated = trigger.update_trailing_stop(150.0, mock_order)
        assert updated is True
        assert trigger.high_water_mark == 150.0
        expected_trigger = 150.0 - 5.0  # 145.0
        assert trigger.trigger_price == expected_trigger

    def test_update_trailing_stop_amount_buy(self):
        """Test trailing stop update with dollar amount for buy orders."""
        mock_order = Mock()
        mock_order.quantity = -100  # Negative quantity = buy order
        mock_order.trail_percent = None
        mock_order.trail_amount = 5.0  # $5

        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=160.0,  # Initial trigger
            order_type=OrderType.BUY,
        )

        # Price moves down - should update trigger
        updated = trigger.update_trailing_stop(145.0, mock_order)
        assert updated is True
        assert trigger.low_water_mark == 145.0
        expected_trigger = 145.0 + 5.0  # 150.0
        assert trigger.trigger_price == expected_trigger

    def test_update_trailing_stop_non_trailing(self):
        """Test that non-trailing stops don't update."""
        mock_order = Mock()
        mock_order.trail_percent = 5.0

        trigger = TriggerCondition(
            order_id="order_1",
            symbol="AAPL",
            trigger_type="stop_loss",  # Not trailing
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        updated = trigger.update_trailing_stop(150.0, mock_order)
        assert updated is False
        assert trigger.trigger_price == 145.0


class TestOrderExecutionEngine:
    """Test OrderExecutionEngine class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = Mock(spec=TradingService)
        self.engine = OrderExecutionEngine(self.mock_trading_service)

    def test_engine_initialization(self):
        """Test OrderExecutionEngine initialization."""
        assert self.engine.trading_service == self.mock_trading_service
        assert self.engine.is_running is False
        assert self.engine.monitoring_task is None
        assert len(self.engine.trigger_conditions) == 0
        assert len(self.engine.monitored_symbols) == 0
        assert self.engine.orders_processed == 0
        assert self.engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_start_engine(self):
        """Test starting the execution engine."""
        with patch.object(self.engine, "_load_pending_orders") as mock_load:
            mock_load.return_value = None

            with patch("asyncio.create_task") as mock_create_task:
                mock_task = Mock()
                mock_create_task.return_value = mock_task

                await self.engine.start()

                assert self.engine.is_running is True
                assert self.engine.monitoring_task == mock_task
                mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_engine_already_running(self):
        """Test starting engine when already running."""
        self.engine.is_running = True

        with patch.object(self.engine, "_load_pending_orders") as mock_load:
            await self.engine.start()

            # Should not load orders or create new task
            mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_engine(self):
        """Test stopping the execution engine."""
        # Set up a running engine
        self.engine.is_running = True
        mock_task = AsyncMock()
        self.engine.monitoring_task = mock_task

        await self.engine.stop()

        assert self.engine.is_running is False
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_engine_not_running(self):
        """Test stopping engine when not running."""
        assert self.engine.is_running is False

        await self.engine.stop()

        # Should complete without error
        assert self.engine.is_running is False

    @pytest.mark.asyncio
    async def test_add_order_success(self):
        """Test adding a valid order for monitoring."""
        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.STOP_LOSS
        mock_order.stop_price = 145.0
        mock_order.quantity = 100

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await self.engine.add_order(mock_order)

            assert "AAPL" in self.engine.monitored_symbols
            assert len(self.engine.trigger_conditions["AAPL"]) == 1

            condition = self.engine.trigger_conditions["AAPL"][0]
            assert condition.order_id == "test_order_123"
            assert condition.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_add_order_cannot_convert(self):
        """Test adding order that cannot be converted."""
        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = False

            await self.engine.add_order(mock_order)

            # Should not be added to monitoring
            assert len(self.engine.monitored_symbols) == 0

    @pytest.mark.asyncio
    async def test_add_order_validation_failure(self):
        """Test adding order that fails validation."""
        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

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
                await self.engine.add_order(mock_order)

    @pytest.mark.asyncio
    async def test_remove_order(self):
        """Test removing an order from monitoring."""
        # Add an order first
        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.STOP_LOSS
        mock_order.stop_price = 145.0
        mock_order.quantity = 100

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            await self.engine.add_order(mock_order)
            assert len(self.engine.trigger_conditions["AAPL"]) == 1

            # Remove the order
            await self.engine.remove_order("test_order_123")

            # Should be removed from monitoring
            assert "AAPL" not in self.engine.trigger_conditions
            assert "AAPL" not in self.engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_remove_nonexistent_order(self):
        """Test removing an order that doesn't exist."""
        await self.engine.remove_order("nonexistent_order")

        # Should complete without error
        assert len(self.engine.monitored_symbols) == 0

    def test_get_initial_trigger_price_stop_loss(self):
        """Test getting initial trigger price for stop loss orders."""
        mock_order = Mock(spec=Order)
        mock_order.order_type = OrderType.STOP_LOSS
        mock_order.stop_price = 145.0

        price = self.engine._get_initial_trigger_price(mock_order)
        assert price == 145.0

    def test_get_initial_trigger_price_stop_limit(self):
        """Test getting initial trigger price for stop limit orders."""
        mock_order = Mock(spec=Order)
        mock_order.order_type = OrderType.STOP_LIMIT
        mock_order.stop_price = 145.0

        price = self.engine._get_initial_trigger_price(mock_order)
        assert price == 145.0

    def test_get_initial_trigger_price_trailing_stop(self):
        """Test getting initial trigger price for trailing stop orders."""
        mock_order = Mock(spec=Order)
        mock_order.order_type = OrderType.TRAILING_STOP

        price = self.engine._get_initial_trigger_price(mock_order)
        assert price == 0.0  # Should be updated dynamically

    def test_get_initial_trigger_price_missing_stop_price(self):
        """Test getting trigger price when stop_price is missing."""
        mock_order = Mock(spec=Order)
        mock_order.order_type = OrderType.STOP_LOSS
        mock_order.stop_price = None

        with pytest.raises(OrderExecutionError, match="Missing stop_price"):
            self.engine._get_initial_trigger_price(mock_order)

    def test_get_initial_trigger_price_unsupported_type(self):
        """Test getting trigger price for unsupported order type."""
        mock_order = Mock(spec=Order)
        mock_order.order_type = OrderType.MARKET

        with pytest.raises(OrderExecutionError, match="Unsupported order type"):
            self.engine._get_initial_trigger_price(mock_order)

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_symbols(self):
        """Test checking trigger conditions with no monitored symbols."""
        await self.engine._check_trigger_conditions()

        # Should complete without error
        assert self.engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_with_trigger(self):
        """Test checking trigger conditions with triggering condition."""
        # Set up a trigger condition
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_get_adapter.return_value = mock_adapter

            with patch(
                "app.services.order_execution_engine.asset_factory"
            ) as mock_factory:
                mock_asset = Stock("AAPL")
                mock_factory.return_value = mock_asset

                # Mock quote that triggers condition
                mock_quote = Mock()
                mock_quote.price = 144.0  # Below trigger price
                mock_adapter.get_quote.return_value = mock_quote

                with patch.object(
                    self.engine, "_process_triggered_order"
                ) as mock_process:
                    await self.engine._check_trigger_conditions()

                    mock_process.assert_called_once()
                    # Symbol should be removed from monitoring
                    assert "AAPL" not in self.engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_trigger(self):
        """Test checking trigger conditions without triggering."""
        # Set up a trigger condition
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_get_adapter.return_value = mock_adapter

            with patch(
                "app.services.order_execution_engine.asset_factory"
            ) as mock_factory:
                mock_asset = Stock("AAPL")
                mock_factory.return_value = mock_asset

                # Mock quote that doesn't trigger condition
                mock_quote = Mock()
                mock_quote.price = 146.0  # Above trigger price
                mock_adapter.get_quote.return_value = mock_quote

                with patch.object(
                    self.engine, "_process_triggered_order"
                ) as mock_process:
                    await self.engine._check_trigger_conditions()

                    mock_process.assert_not_called()
                    # Symbol should remain in monitoring
                    assert "AAPL" in self.engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_quote_error(self):
        """Test handling quote retrieval errors."""
        # Set up a trigger condition
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_get_adapter.return_value = mock_adapter

            with patch(
                "app.services.order_execution_engine.asset_factory"
            ) as mock_factory:
                mock_asset = Stock("AAPL")
                mock_factory.return_value = mock_asset

                # Mock quote adapter error
                mock_adapter.get_quote.side_effect = Exception("Quote error")

                await self.engine._check_trigger_conditions()

                # Should handle error gracefully
                assert "AAPL" in self.engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_loss(self):
        """Test processing a triggered stop loss order."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

        with patch.object(self.engine, "_load_order_by_id") as mock_load:
            mock_load.return_value = mock_order

            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converted = Mock()
                mock_converter.convert_stop_loss_to_market.return_value = mock_converted

                with (
                    patch.object(
                        self.engine, "_update_order_triggered_status"
                    ) as mock_update,
                    patch.object(
                        self.engine, "_execute_converted_order"
                    ) as mock_execute,
                ):
                    await self.engine._process_triggered_order(condition, 144.0)

                    mock_converter.convert_stop_loss_to_market.assert_called_once_with(
                        mock_order, 144.0
                    )
                    mock_update.assert_called_once()
                    mock_execute.assert_called_once_with(mock_converted)
                    assert self.engine.orders_triggered == 1

    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_limit(self):
        """Test processing a triggered stop limit order."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_limit",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

        with patch.object(self.engine, "_load_order_by_id") as mock_load:
            mock_load.return_value = mock_order

            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converted = Mock()
                mock_converter.convert_stop_limit_to_limit.return_value = mock_converted

                with (
                    patch.object(
                        self.engine, "_update_order_triggered_status"
                    ) as mock_update,
                    patch.object(
                        self.engine, "_execute_converted_order"
                    ) as mock_execute,
                ):
                    await self.engine._process_triggered_order(condition, 144.0)

                    mock_converter.convert_stop_limit_to_limit.assert_called_once_with(
                        mock_order, 144.0
                    )
                    mock_update.assert_called_once()
                    mock_execute.assert_called_once_with(mock_converted)

    @pytest.mark.asyncio
    async def test_process_triggered_order_trailing_stop(self):
        """Test processing a triggered trailing stop order."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

        with patch.object(self.engine, "_load_order_by_id") as mock_load:
            mock_load.return_value = mock_order

            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converted = Mock()
                mock_converter.convert_trailing_stop_to_market.return_value = (
                    mock_converted
                )

                with patch.object(
                    self.engine, "_update_order_triggered_status"
                ) as mock_update:
                    with patch.object(
                        self.engine, "_execute_converted_order"
                    ) as mock_execute:
                        await self.engine._process_triggered_order(condition, 144.0)

                        mock_converter.convert_trailing_stop_to_market.assert_called_once_with(
                            mock_order, 144.0
                        )
                        mock_update.assert_called_once()
                        mock_execute.assert_called_once_with(mock_converted)

    @pytest.mark.asyncio
    async def test_process_triggered_order_missing_original(self):
        """Test processing triggered order when original order not found."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        with patch.object(self.engine, "_load_order_by_id") as mock_load:
            mock_load.return_value = None  # Order not found

            await self.engine._process_triggered_order(condition, 144.0)

            # Should complete without error
            assert self.engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_process_triggered_order_conversion_error(self):
        """Test handling conversion errors in triggered order processing."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"

        with patch.object(self.engine, "_load_order_by_id") as mock_load:
            mock_load.return_value = mock_order

            with patch(
                "app.services.order_execution_engine.order_converter"
            ) as mock_converter:
                mock_converter.convert_stop_loss_to_market.side_effect = Exception(
                    "Conversion error"
                )

                await self.engine._process_triggered_order(condition, 144.0)

                # Should handle error gracefully
                assert self.engine.orders_triggered == 0

    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self):
        """Test loading order by ID successfully."""
        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "test_order_123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.BUY
        mock_db_order.quantity = 100
        mock_db_order.price = 150.0
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = None
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None
        mock_db_order.filled_at = None

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            result = await self.engine._load_order_by_id("test_order_123")

            assert result is not None
            assert result.id == "test_order_123"
            assert result.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self):
        """Test loading order when not found."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            result = await self.engine._load_order_by_id("test_order_123")

            assert result is None

    @pytest.mark.asyncio
    async def test_load_order_by_id_database_error(self):
        """Test handling database errors when loading order."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Database error")

            result = await self.engine._load_order_by_id("test_order_123")

            assert result is None

    @pytest.mark.asyncio
    async def test_execute_converted_order_success(self):
        """Test executing converted order successfully."""
        mock_order = Mock(spec=Order)
        mock_order.id = "converted_order_123"

        # Mock trading service with execute_order method
        self.mock_trading_service.execute_order = AsyncMock()

        await self.engine._execute_converted_order(mock_order)

        self.mock_trading_service.execute_order.assert_called_once_with(mock_order)

    @pytest.mark.asyncio
    async def test_execute_converted_order_no_method(self):
        """Test executing converted order when trading service has no execute_order method."""
        mock_order = Mock(spec=Order)
        mock_order.id = "converted_order_123"

        # Trading service doesn't have execute_order method
        await self.engine._execute_converted_order(mock_order)

        # Should complete without error

    @pytest.mark.asyncio
    async def test_execute_converted_order_execution_error(self):
        """Test handling execution errors when executing converted order."""
        mock_order = Mock(spec=Order)
        mock_order.id = "converted_order_123"

        self.mock_trading_service.execute_order = AsyncMock()
        self.mock_trading_service.execute_order.side_effect = Exception(
            "Execution error"
        )

        with pytest.raises(Exception, match="Execution error"):
            await self.engine._execute_converted_order(mock_order)

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_success(self):
        """Test updating order triggered status successfully."""
        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "test_order_123"

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            await self.engine._update_order_triggered_status("test_order_123", 144.0)

            assert mock_db_order.status == OrderStatus.FILLED
            assert mock_db_order.triggered_at is not None
            assert mock_db_order.filled_at is not None
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_order_triggered_status_not_found(self):
        """Test updating status when order not found."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            await self.engine._update_order_triggered_status("test_order_123", 144.0)

            # Should complete without error
            mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_pending_orders_success(self):
        """Test loading pending orders from database."""
        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "test_order_123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = 100
        mock_db_order.price = 150.0
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.0
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None

        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = [mock_db_order]
            mock_db.execute.return_value = mock_result

            with patch.object(self.engine, "add_order") as mock_add:
                await self.engine._load_pending_orders()

                mock_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pending_orders_database_error(self):
        """Test handling database errors when loading pending orders."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Database error")

            await self.engine._load_pending_orders()

            # Should complete without error

    def test_get_status(self):
        """Test getting engine status."""
        # Add some test conditions
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")
        self.engine.orders_processed = 5
        self.engine.orders_triggered = 2

        status = self.engine.get_status()

        assert status["is_running"] is False
        assert status["monitored_symbols"] == 1
        assert status["total_trigger_conditions"] == 1
        assert status["orders_processed"] == 5
        assert status["orders_triggered"] == 2
        assert "AAPL" in status["symbols"]

    def test_get_monitored_orders(self):
        """Test getting monitored orders."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]

        result = self.engine.get_monitored_orders()

        assert "AAPL" in result
        assert len(result["AAPL"]) == 1
        assert result["AAPL"][0]["order_id"] == "test_order_123"
        assert result["AAPL"][0]["trigger_price"] == 145.0

    @pytest.mark.asyncio
    async def test_monitoring_loop_integration(self):
        """Test the main monitoring loop integration."""
        # This is a simplified integration test
        self.engine.is_running = True

        # Add a condition that will trigger
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        with patch.object(self.engine, "_check_trigger_conditions") as mock_check:
            mock_check.side_effect = [
                None,
                asyncio.CancelledError(),
            ]  # Run once then cancel

            with pytest.raises(asyncio.CancelledError):
                await self.engine._monitoring_loop()

            mock_check.assert_called()

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self):
        """Test error handling in monitoring loop."""
        self.engine.is_running = True

        call_count = 0

        def mock_check_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            else:
                raise asyncio.CancelledError()

        with patch.object(self.engine, "_check_trigger_conditions") as mock_check:
            mock_check.side_effect = mock_check_side_effect

            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(asyncio.CancelledError):
                    await self.engine._monitoring_loop()

                # Should sleep after error
                mock_sleep.assert_called_with(5.0)

    def test_should_trigger_method(self):
        """Test the _should_trigger helper method."""
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )

        assert self.engine._should_trigger(condition, 144.0) is True
        assert self.engine._should_trigger(condition, 146.0) is False

    @pytest.mark.asyncio
    async def test_add_trigger_order_alias(self):
        """Test the add_trigger_order alias method."""
        mock_order = Mock(spec=Order)
        mock_order.id = "test_order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.STOP_LOSS
        mock_order.stop_price = 145.0
        mock_order.quantity = 100

        with patch.object(self.engine, "add_order") as mock_add:
            await self.engine.add_trigger_order(mock_order)

            mock_add.assert_called_once_with(mock_order)


class TestGlobalExecutionEngine:
    """Test global execution engine functions."""

    def test_get_execution_engine_not_initialized(self):
        """Test getting execution engine when not initialized."""
        with patch("app.services.order_execution_engine.execution_engine", None):
            with pytest.raises(
                RuntimeError, match="Order execution engine not initialized"
            ):
                get_execution_engine()

    def test_initialize_execution_engine(self):
        """Test initializing the global execution engine."""
        mock_trading_service = Mock(spec=TradingService)

        with patch("app.services.order_execution_engine.execution_engine", None):
            result = initialize_execution_engine(mock_trading_service)

            assert isinstance(result, OrderExecutionEngine)
            assert result.trading_service == mock_trading_service

    def test_get_execution_engine_initialized(self):
        """Test getting execution engine when initialized."""
        mock_engine = Mock(spec=OrderExecutionEngine)

        with patch("app.services.order_execution_engine.execution_engine", mock_engine):
            result = get_execution_engine()

            assert result == mock_engine


class TestOrderExecutionEnginePerformance:
    """Test performance aspects of OrderExecutionEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = Mock(spec=TradingService)
        self.engine = OrderExecutionEngine(self.mock_trading_service)

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self):
        """Test concurrent processing of multiple orders."""
        # Create multiple orders
        orders = []
        for i in range(10):
            mock_order = Mock(spec=Order)
            mock_order.id = f"test_order_{i}"
            mock_order.symbol = f"SYM{i}"
            mock_order.order_type = OrderType.STOP_LOSS
            mock_order.stop_price = 145.0 + i
            mock_order.quantity = 100
            orders.append(mock_order)

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = None

            # Add all orders concurrently
            tasks = [self.engine.add_order(order) for order in orders]
            await asyncio.gather(*tasks)

            # Verify all were added
            assert len(self.engine.monitored_symbols) == 10

            total_conditions = sum(
                len(conditions)
                for conditions in self.engine.trigger_conditions.values()
            )
            assert total_conditions == 10

    @pytest.mark.asyncio
    async def test_high_frequency_condition_checking(self):
        """Test high-frequency condition checking performance."""
        # Add many conditions
        for i in range(100):
            condition = TriggerCondition(
                order_id=f"order_{i}",
                symbol="AAPL",
                trigger_type="stop_loss",
                trigger_price=145.0 + i * 0.1,
                order_type=OrderType.SELL,
            )
            self.engine.trigger_conditions["AAPL"].append(condition)

        self.engine.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_get_adapter.return_value = mock_adapter

            with patch(
                "app.services.order_execution_engine.asset_factory"
            ) as mock_factory:
                mock_asset = Stock("AAPL")
                mock_factory.return_value = mock_asset

                mock_quote = Mock()
                mock_quote.price = 150.0  # Price that won't trigger any conditions
                mock_adapter.get_quote.return_value = mock_quote

                # Measure time for condition checking
                import time

                start_time = time.time()

                await self.engine._check_trigger_conditions()

                end_time = time.time()
                duration = end_time - start_time

                # Should complete in reasonable time (adjust threshold as needed)
                assert duration < 1.0, f"Condition checking took too long: {duration}s"

    def test_memory_usage_with_many_conditions(self):
        """Test memory usage with many trigger conditions."""
        import sys

        # Measure initial memory
        initial_size = sys.getsizeof(self.engine.trigger_conditions)

        # Add many conditions
        for i in range(1000):
            condition = TriggerCondition(
                order_id=f"order_{i}",
                symbol=f"SYM{i % 10}",  # 10 different symbols
                trigger_type="stop_loss",
                trigger_price=145.0 + i * 0.001,
                order_type=OrderType.SELL,
            )
            symbol = condition.symbol
            if symbol not in self.engine.trigger_conditions:
                self.engine.trigger_conditions[symbol] = []
            self.engine.trigger_conditions[symbol].append(condition)

        # Measure final memory
        final_size = sys.getsizeof(self.engine.trigger_conditions)

        # Memory usage should be reasonable
        memory_increase = final_size - initial_size
        assert memory_increase < 1024 * 1024  # Less than 1MB for 1000 conditions


class TestOrderExecutionEngineErrorScenarios:
    """Test various error scenarios in OrderExecutionEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = Mock(spec=TradingService)
        self.engine = OrderExecutionEngine(self.mock_trading_service)

    @pytest.mark.asyncio
    async def test_corrupted_order_data(self):
        """Test handling of corrupted order data."""
        # Create order with missing required fields
        mock_order = Mock(spec=Order)
        mock_order.id = None  # Missing ID
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.STOP_LOSS

        with patch(
            "app.services.order_execution_engine.order_converter"
        ) as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.side_effect = ValueError(
                "Missing ID"
            )

            with pytest.raises(OrderExecutionError):
                await self.engine.add_order(mock_order)

    @pytest.mark.asyncio
    async def test_database_connection_loss(self):
        """Test handling of database connection loss."""
        with patch(
            "app.services.order_execution_engine.get_async_session"
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Connection lost")

            result = await self.engine._load_order_by_id("test_order_123")

            # Should handle gracefully
            assert result is None

    @pytest.mark.asyncio
    async def test_quote_adapter_unavailable(self):
        """Test handling when quote adapter is unavailable."""
        # Set up monitoring
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_get_adapter.side_effect = Exception("Adapter unavailable")

            await self.engine._check_trigger_conditions()

            # Should handle gracefully and keep monitoring
            assert "AAPL" in self.engine.monitored_symbols

    @pytest.mark.asyncio
    async def test_concurrent_modification_during_processing(self):
        """Test handling concurrent modifications during order processing."""
        # Set up a condition
        condition = TriggerCondition(
            order_id="test_order_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL,
        )
        self.engine.trigger_conditions["AAPL"] = [condition]
        self.engine.monitored_symbols.add("AAPL")

        async def modify_during_processing():
            # Simulate modification during processing
            await asyncio.sleep(0.1)
            self.engine.trigger_conditions["AAPL"] = []

        with patch(
            "app.services.order_execution_engine._get_quote_adapter"
        ) as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_get_adapter.return_value = mock_adapter

            with patch(
                "app.services.order_execution_engine.asset_factory"
            ) as mock_factory:
                mock_asset = Stock("AAPL")
                mock_factory.return_value = mock_asset

                mock_quote = Mock()
                mock_quote.price = 144.0  # Triggers condition
                mock_adapter.get_quote.return_value = mock_quote

                # Start concurrent modification
                modify_task = asyncio.create_task(modify_during_processing())

                # Check conditions
                await self.engine._check_trigger_conditions()

                # Wait for modification to complete
                await modify_task

                # Should handle gracefully without errors
