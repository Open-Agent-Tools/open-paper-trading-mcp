"""
Comprehensive tests for order conversion service.

Tests all conversion logic including:
- Stop loss order conversion to market orders
- Stop limit order conversion to limit orders
- Trailing stop order updates and conversions
- Order validation and error handling
- Conversion history tracking
- Edge cases and error conditions
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.order_conversion import (
    OrderConversionError,
    OrderConverter,
    order_converter,
)


class TestOrderConverter:
    """Test cases for OrderConverter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = OrderConverter()
        self.test_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def create_test_order(
        self,
        order_type: OrderType,
        quantity: int = 100,
        symbol: str = "AAPL",
        stop_price: float | None = None,
        limit_price: float | None = None,
        trail_percent: float | None = None,
        trail_amount: float | None = None,
        order_id: str = "test_order_123",
    ) -> Order:
        """Helper to create test orders."""
        return Order(
            id=order_id,
            symbol=symbol,
            order_type=order_type,
            quantity=quantity,
            price=limit_price,
            status=OrderStatus.PENDING,
            created_at=self.test_time,
            condition=OrderCondition.STOP if stop_price else OrderCondition.LIMIT,
            stop_price=stop_price,
            trail_percent=trail_percent,
            trail_amount=trail_amount,
            net_price=None,
        )


class TestStopLossConversion(TestOrderConverter):
    """Test stop loss order conversion to market orders."""

    def test_convert_protective_stop_loss_triggered(self):
        """Test converting protective stop loss when price drops below stop price."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=100,  # Positive = protective stop
            stop_price=150.0,
        )
        current_price = 149.0  # Below stop price

        converted = self.converter.convert_stop_loss_to_market(
            order, current_price, self.test_time
        )

        assert converted.order_type == OrderType.SELL
        assert converted.quantity == 100
        assert converted.price is None  # Market order
        assert converted.condition == OrderCondition.MARKET
        assert converted.status == OrderStatus.PENDING
        assert converted.id == "test_order_123_converted"
        assert converted.stop_price is None

    def test_convert_buy_stop_loss_triggered(self):
        """Test converting buy stop (negative quantity) when price rises above stop."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=-100,  # Negative = buy stop
            stop_price=155.0,
        )
        current_price = 156.0  # Above stop price

        converted = self.converter.convert_stop_loss_to_market(
            order, current_price, self.test_time
        )

        assert converted.order_type == OrderType.BUY
        assert converted.quantity == 100  # Made positive
        assert converted.price is None
        assert converted.condition == OrderCondition.MARKET

    def test_stop_loss_trigger_condition_not_met_protective(self):
        """Test error when protective stop condition not met."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=100,  # Protective stop
            stop_price=150.0,
        )
        current_price = 155.0  # Above stop price - should not trigger

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_loss_to_market(order, current_price)

        assert "trigger condition not met" in str(exc_info.value)
        assert "price=155.0" in str(exc_info.value)
        assert "stop_price=150.0" in str(exc_info.value)
        assert "is_protective_stop=True" in str(exc_info.value)

    def test_stop_loss_trigger_condition_not_met_buy_stop(self):
        """Test error when buy stop condition not met."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=-100,  # Buy stop
            stop_price=155.0,
        )
        current_price = 150.0  # Below stop price - should not trigger

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_loss_to_market(order, current_price)

        assert "trigger condition not met" in str(exc_info.value)
        assert "is_protective_stop=False" in str(exc_info.value)

    def test_stop_loss_wrong_order_type(self):
        """Test error when trying to convert non-stop-loss order."""
        order = self.create_test_order(order_type=OrderType.BUY, quantity=100)

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_loss_to_market(order, 150.0)

        assert "Cannot convert OrderType.BUY to market order" in str(exc_info.value)

    def test_stop_loss_missing_stop_price(self):
        """Test error when stop loss order missing stop price."""
        # Can't create invalid order due to schema validation, so we test the converter logic directly
        # by bypassing schema validation using model_copy
        valid_order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=150.0
        )

        # Create invalid order by copying and modifying
        invalid_order = valid_order.model_copy()
        invalid_order.stop_price = None

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_loss_to_market(invalid_order, 150.0)

        assert "Stop loss order missing stop_price" in str(exc_info.value)

    def test_stop_loss_with_no_order_id(self):
        """Test converting stop loss order with no ID."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=150.0,
            order_id=None,
        )
        current_price = 149.0

        converted = self.converter.convert_stop_loss_to_market(order, current_price)

        assert converted.id is None
        assert converted.order_type == OrderType.SELL

    def test_stop_loss_conversion_default_timestamp(self):
        """Test stop loss conversion with default timestamp."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=150.0
        )
        current_price = 149.0

        with patch("app.services.order_conversion.datetime") as mock_dt:
            mock_dt.utcnow.return_value = self.test_time
            converted = self.converter.convert_stop_loss_to_market(order, current_price)

        assert converted.created_at == self.test_time


class TestStopLimitConversion(TestOrderConverter):
    """Test stop limit order conversion to limit orders."""

    def test_convert_protective_stop_limit_triggered(self):
        """Test converting protective stop limit when triggered."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,  # Protective stop
            stop_price=150.0,
            limit_price=149.0,
        )
        current_price = 149.5  # Below stop price

        converted = self.converter.convert_stop_limit_to_limit(
            order, current_price, self.test_time
        )

        assert converted.order_type == OrderType.SELL
        assert converted.quantity == 100
        assert converted.price == 149.0  # Uses limit price
        assert converted.condition == OrderCondition.LIMIT
        assert converted.status == OrderStatus.PENDING
        assert converted.stop_price is None

    def test_convert_buy_stop_limit_triggered(self):
        """Test converting buy stop limit when triggered."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=-100,  # Buy stop
            stop_price=155.0,
            limit_price=156.0,
        )
        current_price = 156.0  # Above stop price

        converted = self.converter.convert_stop_limit_to_limit(order, current_price)

        assert converted.order_type == OrderType.BUY
        assert converted.quantity == 100  # Made positive
        assert converted.price == 156.0
        assert converted.condition == OrderCondition.LIMIT

    def test_stop_limit_wrong_order_type(self):
        """Test error when trying to convert non-stop-limit order."""
        order = self.create_test_order(order_type=OrderType.STOP_LOSS, quantity=100)

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_limit_to_limit(order, 150.0)

        assert "Cannot convert OrderType.STOP_LOSS to limit order" in str(
            exc_info.value
        )

    def test_stop_limit_missing_stop_price(self):
        """Test error when stop limit order missing stop price."""
        # Create valid order first, then modify to make invalid
        valid_order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=150.0,
            limit_price=149.0,
        )

        invalid_order = valid_order.model_copy()
        invalid_order.stop_price = None

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_limit_to_limit(invalid_order, 150.0)

        assert "Stop limit order missing stop_price" in str(exc_info.value)

    def test_stop_limit_missing_limit_price(self):
        """Test error when stop limit order missing limit price."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=150.0,
            limit_price=None,
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_limit_to_limit(order, 149.0)

        assert "Stop limit order missing limit price" in str(exc_info.value)

    def test_stop_limit_trigger_condition_not_met(self):
        """Test error when stop limit trigger condition not met."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,  # Protective stop
            stop_price=150.0,
            limit_price=149.0,
        )
        current_price = 155.0  # Above stop price - should not trigger

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_stop_limit_to_limit(order, current_price)

        assert "Stop limit trigger condition not met" in str(exc_info.value)


class TestTrailingStopUpdate(TestOrderConverter):
    """Test trailing stop order updates."""

    def test_update_trailing_stop_percentage_protective_first_time(self):
        """Test updating trailing stop with percentage trail (first time)."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,  # Protective stop
            stop_price=None,  # First time setting
            trail_percent=5.0,
        )
        current_price = 160.0

        updated = self.converter.update_trailing_stop(order, current_price)

        expected_stop = 160.0 * (1 - 5.0 / 100)  # 152.0
        assert updated.stop_price == expected_stop
        assert updated.trail_percent == 5.0
        assert updated.order_type == OrderType.TRAILING_STOP

    def test_update_trailing_stop_percentage_protective_raise_stop(self):
        """Test updating trailing stop - price went up, raise stop price."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,  # Protective stop
            stop_price=150.0,  # Current stop
            trail_percent=5.0,
        )
        current_price = 170.0  # Price went up

        updated = self.converter.update_trailing_stop(order, current_price)

        expected_stop = 170.0 * (1 - 5.0 / 100)  # 161.5
        assert updated.stop_price == expected_stop  # Higher than 150.0

    def test_update_trailing_stop_percentage_protective_no_change(self):
        """Test updating trailing stop - price went down, keep existing stop."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,  # Protective stop
            stop_price=152.0,  # Current stop
            trail_percent=5.0,
        )
        current_price = 155.0  # Price went down from previous high

        updated = self.converter.update_trailing_stop(order, current_price)

        155.0 * (1 - 5.0 / 100)  # 147.25
        assert updated.stop_price == 152.0  # Keep higher existing stop

    def test_update_trailing_stop_percentage_buy_stop(self):
        """Test updating trailing stop for buy stop (negative quantity)."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=-100,  # Buy stop
            stop_price=155.0,  # Current stop
            trail_percent=5.0,
        )
        current_price = 150.0  # Price went down

        updated = self.converter.update_trailing_stop(order, current_price)

        150.0 * (1 + 5.0 / 100)  # 157.5
        assert updated.stop_price == 155.0  # Keep lower existing stop (min)

    def test_update_trailing_stop_amount_protective(self):
        """Test updating trailing stop with dollar amount trail."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,  # Protective stop
            stop_price=None,
            trail_amount=5.0,
        )
        current_price = 160.0

        updated = self.converter.update_trailing_stop(order, current_price)

        expected_stop = 160.0 - 5.0  # 155.0
        assert updated.stop_price == expected_stop

    def test_update_trailing_stop_amount_buy_stop(self):
        """Test updating trailing stop with dollar amount for buy stop."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=-100,  # Buy stop
            stop_price=None,
            trail_amount=5.0,
        )
        current_price = 150.0

        updated = self.converter.update_trailing_stop(order, current_price)

        expected_stop = 150.0 + 5.0  # 155.0
        assert updated.stop_price == expected_stop

    def test_update_trailing_stop_wrong_order_type(self):
        """Test error when trying to update non-trailing stop."""
        order = self.create_test_order(order_type=OrderType.STOP_LOSS, quantity=100)

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.update_trailing_stop(order, 150.0)

        assert "Cannot update OrderType.STOP_LOSS as trailing stop" in str(
            exc_info.value
        )

    def test_update_trailing_stop_missing_trail_parameters(self):
        """Test error when trailing stop missing trail parameters."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=None,
            trail_amount=None,
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.update_trailing_stop(order, 150.0)

        assert "Trailing stop order missing trail parameters" in str(exc_info.value)

    def test_update_trailing_stop_invalid_parameters(self):
        """Test error path for invalid trailing stop parameters."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=None,
            trail_amount=None,
        )
        # Manually set both to trigger error condition
        order.trail_percent = None
        order.trail_amount = None

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.update_trailing_stop(order, 150.0)

        assert "missing trail parameters" in str(exc_info.value)


class TestTrailingStopConversion(TestOrderConverter):
    """Test trailing stop conversion to market orders."""

    def test_convert_trailing_stop_to_market_protective(self):
        """Test converting protective trailing stop to market order."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,  # Positive quantity
            stop_price=150.0,
            trail_percent=5.0,
        )
        current_price = 149.0

        converted = self.converter.convert_trailing_stop_to_market(
            order, current_price, self.test_time
        )

        assert (
            converted.order_type == OrderType.BUY
        )  # Quantity >= 0 = BUY in trailing stop logic
        assert converted.quantity == 100
        assert converted.price is None  # Market order
        assert converted.condition == OrderCondition.MARKET
        assert converted.stop_price is None
        assert converted.trail_percent is None
        assert converted.trail_amount is None

    def test_convert_trailing_stop_to_market_buy_stop(self):
        """Test converting buy trailing stop to market order."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=-100,  # Negative = buy stop
            stop_price=155.0,
            trail_percent=5.0,
        )
        current_price = 156.0

        converted = self.converter.convert_trailing_stop_to_market(order, current_price)

        assert (
            converted.order_type == OrderType.SELL
        )  # Quantity < 0 = SELL in conversion logic
        assert converted.quantity == 100  # Made positive
        assert converted.condition == OrderCondition.MARKET

    def test_convert_trailing_stop_wrong_order_type(self):
        """Test error when trying to convert non-trailing stop."""
        order = self.create_test_order(order_type=OrderType.STOP_LOSS, quantity=100)

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.convert_trailing_stop_to_market(order, 150.0)

        assert "Cannot convert OrderType.STOP_LOSS to market order" in str(
            exc_info.value
        )

    def test_convert_trailing_stop_no_order_id(self):
        """Test converting trailing stop with no order ID."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP, quantity=100, order_id=None
        )

        converted = self.converter.convert_trailing_stop_to_market(order, 150.0)

        assert converted.id is None


class TestOrderValidation(TestOrderConverter):
    """Test order validation methods."""

    def test_can_convert_order_convertible_types(self):
        """Test can_convert_order for convertible order types."""
        convertible_types = [
            OrderType.STOP_LOSS,
            OrderType.STOP_LIMIT,
            OrderType.TRAILING_STOP,
        ]

        for order_type in convertible_types:
            order = self.create_test_order(order_type=order_type, quantity=100)
            assert self.converter.can_convert_order(order) is True

    def test_can_convert_order_non_convertible_types(self):
        """Test can_convert_order for non-convertible order types."""
        non_convertible_types = [
            OrderType.BUY,
            OrderType.SELL,
            OrderType.BTO,
            OrderType.STO,
            OrderType.BTC,
            OrderType.STC,
        ]

        for order_type in non_convertible_types:
            order = self.create_test_order(order_type=order_type, quantity=100)
            assert self.converter.can_convert_order(order) is False

    def test_get_conversion_requirements_stop_loss(self):
        """Test conversion requirements for stop loss orders."""
        requirements = self.converter.get_conversion_requirements(OrderType.STOP_LOSS)

        expected = {
            "stop_price": True,
            "price": False,
            "trail_percent": False,
            "trail_amount": False,
        }
        assert requirements == expected

    def test_get_conversion_requirements_stop_limit(self):
        """Test conversion requirements for stop limit orders."""
        requirements = self.converter.get_conversion_requirements(OrderType.STOP_LIMIT)

        expected = {
            "stop_price": True,
            "price": True,
            "trail_percent": False,
            "trail_amount": False,
        }
        assert requirements == expected

    def test_get_conversion_requirements_trailing_stop(self):
        """Test conversion requirements for trailing stop orders."""
        requirements = self.converter.get_conversion_requirements(
            OrderType.TRAILING_STOP
        )

        expected = {
            "stop_price": False,
            "price": False,
            "trail_percent": False,
            "trail_amount": False,
        }
        assert requirements == expected

    def test_get_conversion_requirements_unknown_type(self):
        """Test conversion requirements for unknown order type."""
        requirements = self.converter.get_conversion_requirements(OrderType.BUY)
        assert requirements == {}

    def test_validate_order_for_conversion_valid_stop_loss(self):
        """Test validation for valid stop loss order."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=150.0
        )

        assert self.converter.validate_order_for_conversion(order) is True

    def test_validate_order_for_conversion_valid_stop_limit(self):
        """Test validation for valid stop limit order."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=150.0,
            limit_price=149.0,
        )

        assert self.converter.validate_order_for_conversion(order) is True

    def test_validate_order_for_conversion_valid_trailing_stop_percent(self):
        """Test validation for trailing stop with percentage."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP, quantity=100, trail_percent=5.0
        )

        assert self.converter.validate_order_for_conversion(order) is True

    def test_validate_order_for_conversion_valid_trailing_stop_amount(self):
        """Test validation for trailing stop with dollar amount."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP, quantity=100, trail_amount=5.0
        )

        assert self.converter.validate_order_for_conversion(order) is True

    def test_validate_order_for_conversion_non_convertible(self):
        """Test validation error for non-convertible order type."""
        order = self.create_test_order(order_type=OrderType.BUY, quantity=100)

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.validate_order_for_conversion(order)

        assert "Order type OrderType.BUY is not convertible" in str(exc_info.value)

    def test_validate_order_for_conversion_stop_loss_missing_stop_price(self):
        """Test validation error for stop loss missing stop price."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=None
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.validate_order_for_conversion(order)

        assert "OrderType.STOP_LOSS requires stop_price" in str(exc_info.value)

    def test_validate_order_for_conversion_stop_limit_missing_price(self):
        """Test validation error for stop limit missing limit price."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=150.0,
            limit_price=None,
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.validate_order_for_conversion(order)

        assert "OrderType.STOP_LIMIT requires price" in str(exc_info.value)

    def test_validate_order_for_conversion_trailing_stop_no_trail_params(self):
        """Test validation error for trailing stop with no trail parameters."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=None,
            trail_amount=None,
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.validate_order_for_conversion(order)

        assert "Trailing stop requires either trail_percent or trail_amount" in str(
            exc_info.value
        )

    def test_validate_order_for_conversion_trailing_stop_both_trail_params(self):
        """Test validation error for trailing stop with both trail parameters."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            trail_amount=10.0,
        )

        with pytest.raises(OrderConversionError) as exc_info:
            self.converter.validate_order_for_conversion(order)

        assert "Trailing stop cannot have both trail_percent and trail_amount" in str(
            exc_info.value
        )


class TestConversionHistory(TestOrderConverter):
    """Test conversion history tracking."""

    def test_log_conversion_with_order_id(self):
        """Test logging conversion with order ID."""
        original_order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=150.0,
            order_id="original_123",
        )

        converted_order = Order(
            id="converted_123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=None,
            status=OrderStatus.PENDING,
            created_at=self.test_time,
            condition=OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        trigger_price = 149.0

        with patch("app.services.order_conversion.datetime") as mock_dt:
            mock_dt.utcnow.return_value = self.test_time
            self.converter._log_conversion(
                original_order, converted_order, trigger_price, "stop_loss_to_market"
            )

        history = self.converter.get_conversion_history("original_123")
        assert history is not None
        assert history["original_order_id"] == "original_123"
        assert history["converted_order_id"] == "converted_123"
        assert history["conversion_type"] == "stop_loss_to_market"
        assert history["trigger_price"] == 149.0
        assert history["original_type"] == OrderType.STOP_LOSS
        assert history["converted_type"] == OrderType.SELL
        assert history["timestamp"] == self.test_time

    def test_log_conversion_without_order_id(self):
        """Test logging conversion without order ID."""
        original_order = self.create_test_order(
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=150.0,
            order_id=None,
        )

        converted_order = Order(
            id=None,
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            price=None,
            status=OrderStatus.PENDING,
            created_at=self.test_time,
            condition=OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        # Should not raise error
        self.converter._log_conversion(
            original_order, converted_order, 149.0, "test_conversion"
        )

        # Should not create history entry
        assert len(self.converter.conversion_history) == 0

    def test_get_conversion_history_nonexistent(self):
        """Test getting history for non-existent order."""
        history = self.converter.get_conversion_history("nonexistent")
        assert history is None


class TestOrderConverterLogging(TestOrderConverter):
    """Test logging functionality."""

    @patch("app.services.order_conversion.logger")
    def test_logging_during_conversion(self, mock_logger):
        """Test that conversions are logged properly."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=150.0
        )
        current_price = 149.0

        self.converter.convert_stop_loss_to_market(order, current_price)

        # Check that info log was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "Order conversion: stop_loss_to_market" in log_message
        assert "OrderType.STOP_LOSS AAPL -> OrderType.SELL" in log_message
        assert "at price 149.0" in log_message


class TestGlobalConverterInstance:
    """Test the global converter instance."""

    def test_global_instance_exists(self):
        """Test that global converter instance exists."""
        assert order_converter is not None
        assert isinstance(order_converter, OrderConverter)

    def test_global_instance_functionality(self):
        """Test that global instance works correctly."""
        order = Order(
            id="test",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            price=None,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            condition=OrderCondition.STOP,
            stop_price=150.0,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        assert order_converter.can_convert_order(order) is True


class TestEdgeCases(TestOrderConverter):
    """Test edge cases and error conditions."""

    def test_zero_quantity_order(self):
        """Test handling of zero quantity orders."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=0, stop_price=150.0
        )
        current_price = 149.0

        converted = self.converter.convert_stop_loss_to_market(order, current_price)
        assert converted.quantity == 0

    def test_negative_stop_price(self):
        """Test handling of negative stop prices."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=-150.0
        )
        current_price = -151.0

        # Should work with negative prices (exotic scenarios)
        converted = self.converter.convert_stop_loss_to_market(order, current_price)
        assert converted is not None

    def test_very_large_quantities(self):
        """Test handling of very large quantities."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=1000000, stop_price=150.0
        )
        current_price = 149.0

        converted = self.converter.convert_stop_loss_to_market(order, current_price)
        assert converted.quantity == 1000000

    def test_very_small_trail_percent(self):
        """Test handling of very small trail percentages."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=0.01,  # 0.01%
        )
        current_price = 100.0

        updated = self.converter.update_trailing_stop(order, current_price)
        expected_stop = 100.0 * (1 - 0.01 / 100)  # 99.9999
        assert abs(updated.stop_price - expected_stop) < 1e-6

    def test_very_large_trail_percent(self):
        """Test handling of very large trail percentages."""
        order = self.create_test_order(
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=90.0,  # 90%
        )
        current_price = 100.0

        updated = self.converter.update_trailing_stop(order, current_price)
        expected_stop = 100.0 * (1 - 90.0 / 100)  # 10.0
        assert updated.stop_price == expected_stop

    def test_extreme_market_prices(self):
        """Test conversion with extreme market prices."""
        order = self.create_test_order(
            order_type=OrderType.STOP_LOSS, quantity=100, stop_price=0.01
        )
        current_price = 0.005  # Very low price

        converted = self.converter.convert_stop_loss_to_market(order, current_price)
        assert converted is not None
        assert converted.order_type == OrderType.SELL

    def test_model_copy_preserves_all_fields(self):
        """Test that model_copy preserves all order fields during trailing stop update."""
        original_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        order = Order(
            id="test_123",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            price=None,
            status=OrderStatus.PENDING,
            created_at=original_time,
            condition=OrderCondition.STOP,
            stop_price=150.0,
            trail_percent=5.0,
            trail_amount=None,
            net_price=None,
        )

        updated = self.converter.update_trailing_stop(order, 160.0)

        # Check that all original fields are preserved except stop_price
        assert updated.id == order.id
        assert updated.symbol == order.symbol
        assert updated.order_type == order.order_type
        assert updated.quantity == order.quantity
        assert updated.price == order.price
        assert updated.status == order.status
        assert updated.created_at == order.created_at
        assert updated.condition == order.condition
        assert updated.trail_percent == order.trail_percent
        assert updated.trail_amount == order.trail_amount
        assert updated.net_price == order.net_price
        # Only stop_price should change
        assert updated.stop_price != order.stop_price
