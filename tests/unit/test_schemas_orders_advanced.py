"""
Advanced test coverage for order schemas.

Tests complex order validation, multi-leg orders, enums,
field validators, order composition patterns, and advanced order types.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.assets import Option, Stock
from app.schemas.orders import (
    MultiLegOrder,
    MultiLegOrderCreate,
    Order,
    OrderCondition,
    OrderCreate,
    OrderLeg,
    OrderLegCreate,
    OrderSide,
    OrderStatus,
    OrderType,
)


class TestOrderEnums:
    """Test order enum values and validation."""

    def test_order_type_enum_values(self):
        """Test all OrderType enum values."""
        expected_values = {
            "buy",
            "sell",
            "buy_to_open",
            "sell_to_open",
            "buy_to_close",
            "sell_to_close",
            "stop_loss",
            "stop_limit",
            "trailing_stop",
        }
        actual_values = {ot.value for ot in OrderType}
        assert actual_values == expected_values

    def test_order_status_enum_values(self):
        """Test all OrderStatus enum values."""
        expected_values = {
            "pending",
            "triggered",
            "filled",
            "cancelled",
            "rejected",
            "partially_filled",
            "expired",
        }
        actual_values = {os.value for os in OrderStatus}
        assert actual_values == expected_values

    def test_order_condition_enum_values(self):
        """Test all OrderCondition enum values."""
        expected_values = {"market", "limit", "stop", "stop_limit"}
        actual_values = {oc.value for oc in OrderCondition}
        assert actual_values == expected_values

    def test_order_side_enum_values(self):
        """Test all OrderSide enum values."""
        expected_values = {"buy", "sell"}
        actual_values = {os.value for os in OrderSide}
        assert actual_values == expected_values

    def test_enum_string_inheritance(self):
        """Test enums inherit from string."""
        assert isinstance(OrderType.BUY, str)
        assert isinstance(OrderStatus.PENDING, str)
        assert isinstance(OrderCondition.MARKET, str)
        assert isinstance(OrderSide.BUY, str)


class TestOrderLeg:
    """Test OrderLeg validation and functionality."""

    def test_order_leg_creation_basic(self):
        """Test creating basic order leg."""
        leg = OrderLeg(
            asset="AAPL", quantity=100, order_type=OrderType.BUY, price=150.0
        )

        assert leg.asset.symbol == "AAPL"
        assert leg.quantity == 100
        assert leg.order_type == OrderType.BUY
        assert leg.price == 150.0

    def test_order_leg_asset_normalization(self):
        """Test asset normalization from string."""
        leg = OrderLeg(
            asset="aapl", quantity=100, order_type=OrderType.BUY, price=150.0
        )

        assert leg.asset.symbol == "AAPL"
        assert isinstance(leg.asset, Stock)

    def test_order_leg_with_asset_object(self):
        """Test order leg with Asset object."""
        stock = Stock(symbol="GOOGL")
        leg = OrderLeg(
            asset=stock, quantity=50, order_type=OrderType.SELL, price=2800.0
        )

        assert leg.asset.symbol == "GOOGL"
        assert leg.asset is stock

    def test_order_leg_with_option_asset(self):
        """Test order leg with option asset."""
        option_symbol = "AAPL240119C00195000"
        leg = OrderLeg(
            asset=option_symbol, quantity=10, order_type=OrderType.BTO, price=5.50
        )

        assert leg.asset.symbol == option_symbol
        assert isinstance(leg.asset, Option)

    def test_order_leg_invalid_asset(self):
        """Test order leg with invalid asset."""
        with pytest.raises(ValidationError) as exc_info:
            OrderLeg(asset="", quantity=100, order_type=OrderType.BUY, price=150.0)

        error = exc_info.value.errors()[0]
        assert "Invalid asset" in error["msg"]

    def test_order_leg_quantity_sign_adjustment_buy(self):
        """Test quantity sign adjustment for buy orders."""
        leg = OrderLeg(
            asset="AAPL",
            quantity=-100,  # Negative input
            order_type=OrderType.BUY,
            price=150.0,
        )

        assert leg.quantity == 100  # Should be positive for buy

    def test_order_leg_quantity_sign_adjustment_sell(self):
        """Test quantity sign adjustment for sell orders."""
        leg = OrderLeg(
            asset="AAPL",
            quantity=100,  # Positive input
            order_type=OrderType.SELL,
            price=150.0,
        )

        assert leg.quantity == -100  # Should be negative for sell

    def test_order_leg_quantity_sign_adjustment_options(self):
        """Test quantity sign adjustment for options orders."""
        # Buy to open - should be positive
        bto_leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=-10,
            order_type=OrderType.BTO,
            price=5.50,
        )
        assert bto_leg.quantity == 10

        # Sell to open - should be negative
        sto_leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=10,
            order_type=OrderType.STO,
            price=5.50,
        )
        assert sto_leg.quantity == -10

        # Buy to close - should be positive
        btc_leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=-10,
            order_type=OrderType.BTC,
            price=5.50,
        )
        assert btc_leg.quantity == 10

        # Sell to close - should be negative
        stc_leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=10,
            order_type=OrderType.STC,
            price=5.50,
        )
        assert stc_leg.quantity == -10

    def test_order_leg_price_sign_adjustment(self):
        """Test price sign adjustment based on order type."""
        # Buy orders - price should be positive
        buy_leg = OrderLeg(
            asset="AAPL", quantity=100, order_type=OrderType.BUY, price=-150.0
        )
        assert buy_leg.price == 150.0

        # Sell orders - price should be negative
        sell_leg = OrderLeg(
            asset="AAPL", quantity=100, order_type=OrderType.SELL, price=150.0
        )
        assert sell_leg.price == -150.0

    def test_order_leg_none_price(self):
        """Test order leg with None price (market order)."""
        leg = OrderLeg(asset="AAPL", quantity=100, order_type=OrderType.BUY, price=None)

        assert leg.price is None


class TestOrder:
    """Test Order schema validation and functionality."""

    def test_order_creation_basic(self):
        """Test creating basic order."""
        order = Order(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )

        assert order.symbol == "AAPL"
        assert order.order_type == OrderType.BUY
        assert order.quantity == 100
        assert order.price == 150.0
        assert order.condition == OrderCondition.MARKET
        assert order.status == OrderStatus.PENDING

    def test_order_symbol_validation_and_normalization(self):
        """Test symbol validation and normalization."""
        order = Order(symbol="aapl", order_type=OrderType.BUY, quantity=100)

        assert order.symbol == "AAPL"

    def test_order_symbol_validation_invalid(self):
        """Test invalid symbol validation."""
        with pytest.raises(ValidationError) as exc_info:
            Order(symbol="", order_type=OrderType.BUY, quantity=100)

        error = exc_info.value.errors()[0]
        assert "Symbol cannot be empty" in error["msg"]

    def test_order_quantity_validation_positive(self):
        """Test quantity must be positive."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=100)
        assert order.quantity == 100

    def test_order_quantity_validation_zero(self):
        """Test quantity cannot be zero."""
        with pytest.raises(ValidationError) as exc_info:
            Order(symbol="AAPL", order_type=OrderType.BUY, quantity=0)

        error = exc_info.value.errors()[0]
        assert error["type"] == "greater_than"

    def test_order_quantity_validation_negative(self):
        """Test quantity cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            Order(symbol="AAPL", order_type=OrderType.BUY, quantity=-100)

        error = exc_info.value.errors()[0]
        assert error["type"] == "greater_than"

    def test_order_with_all_fields(self):
        """Test order with all fields populated."""
        created_at = datetime.now(UTC)
        filled_at = datetime.now(UTC)

        order = Order(
            id="order_123",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.FILLED,
            created_at=created_at,
            filled_at=filled_at,
            stop_price=2750.0,
            trail_percent=5.0,
        )

        assert order.id == "order_123"
        assert order.symbol == "GOOGL"
        assert order.order_type == OrderType.SELL
        assert order.quantity == 50
        assert order.price == 2800.0
        assert order.condition == OrderCondition.LIMIT
        assert order.status == OrderStatus.FILLED
        assert order.created_at == created_at
        assert order.filled_at == filled_at
        assert order.stop_price == 2750.0
        assert order.trail_percent == 5.0

    def test_order_to_leg_conversion(self):
        """Test converting Order to OrderLeg."""
        order = Order(
            symbol="MSFT", order_type=OrderType.BUY, quantity=200, price=300.0
        )

        leg = order.to_leg()

        assert leg.asset.symbol == "MSFT"
        assert leg.quantity == 200
        assert leg.order_type == OrderType.BUY
        assert leg.price == 300.0

    def test_order_stop_price_validation_required(self):
        """Test stop price required for stop orders."""
        with pytest.raises(ValidationError) as exc_info:
            Order(
                symbol="AAPL",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=None,
            )

        error = exc_info.value.errors()[0]
        assert "Stop price is required" in error["msg"]

    def test_order_stop_price_validation_provided(self):
        """Test stop price validation when provided."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=140.0,
        )
        assert order.stop_price == 140.0

    def test_order_trailing_stop_validation_both_params(self):
        """Test trailing stop cannot have both percent and amount."""
        with pytest.raises(ValidationError) as exc_info:
            Order(
                symbol="AAPL",
                order_type=OrderType.TRAILING_STOP,
                quantity=100,
                trail_percent=5.0,
                trail_amount=10.0,
            )

        error = exc_info.value.errors()[0]
        assert "cannot have both trail_percent and trail_amount" in error["msg"]

    def test_order_trailing_stop_validation_neither_param(self):
        """Test trailing stop requires either percent or amount."""
        with pytest.raises(ValidationError) as exc_info:
            Order(symbol="AAPL", order_type=OrderType.TRAILING_STOP, quantity=100)

        error = exc_info.value.errors()[0]
        assert "require either trail_percent or trail_amount" in error["msg"]

    def test_order_trailing_stop_validation_percent_only(self):
        """Test trailing stop with percent only."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
        )
        assert order.trail_percent == 5.0
        assert order.trail_amount is None

    def test_order_trailing_stop_validation_amount_only(self):
        """Test trailing stop with amount only."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_amount=10.0,
        )
        assert order.trail_amount == 10.0
        assert order.trail_percent is None


class TestMultiLegOrder:
    """Test MultiLegOrder functionality and validation."""

    def test_multi_leg_order_creation_basic(self):
        """Test creating basic multi-leg order."""
        leg1 = OrderLeg(
            asset="AAPL", quantity=100, order_type=OrderType.BTO, price=5.50
        )
        leg2 = OrderLeg(
            asset="AAPL", quantity=-100, order_type=OrderType.STO, price=6.00
        )

        order = MultiLegOrder(
            legs=[leg1, leg2], condition=OrderCondition.LIMIT, limit_price=0.50
        )

        assert len(order.legs) == 2
        assert order.condition == OrderCondition.LIMIT
        assert order.limit_price == 0.50
        assert order.status == OrderStatus.PENDING

    def test_multi_leg_order_duplicate_assets_validation(self):
        """Test validation prevents duplicate assets."""
        leg1 = OrderLeg(
            asset="AAPL", quantity=100, order_type=OrderType.BTO, price=5.50
        )
        leg2 = OrderLeg(
            asset="AAPL", quantity=-100, order_type=OrderType.STO, price=6.00
        )

        # This should pass because we allow multiple legs of same underlying
        with pytest.raises(ValidationError) as exc_info:
            MultiLegOrder(legs=[leg1, leg2])

        error = exc_info.value.errors()[0]
        assert "Duplicate assets not allowed" in error["msg"]

    def test_multi_leg_order_add_leg_method(self):
        """Test adding leg to multi-leg order."""
        order = MultiLegOrder(legs=[])

        order.add_leg("AAPL", 100, OrderType.BTO, 5.50)

        assert len(order.legs) == 1
        assert order.legs[0].asset.symbol == "AAPL"
        assert order.legs[0].quantity == 100
        assert order.legs[0].order_type == OrderType.BTO
        assert order.legs[0].price == 5.50

    def test_multi_leg_order_add_leg_invalid_asset(self):
        """Test adding invalid asset leg."""
        order = MultiLegOrder(legs=[])

        with pytest.raises(ValueError) as exc_info:
            order.add_leg("", 100, OrderType.BTO, 5.50)

        assert "Invalid asset" in str(exc_info.value)

    def test_multi_leg_order_buy_to_open_method(self):
        """Test buy_to_open convenience method."""
        order = MultiLegOrder(legs=[])

        result = order.buy_to_open("AAPL", 100, 5.50)

        assert result is order  # Should return self for chaining
        assert len(order.legs) == 1
        assert order.legs[0].order_type == OrderType.BTO

    def test_multi_leg_order_sell_to_open_method(self):
        """Test sell_to_open convenience method."""
        order = MultiLegOrder(legs=[])

        result = order.sell_to_open("AAPL", 100, 6.00)

        assert result is order
        assert len(order.legs) == 1
        assert order.legs[0].order_type == OrderType.STO

    def test_multi_leg_order_buy_to_close_method(self):
        """Test buy_to_close convenience method."""
        order = MultiLegOrder(legs=[])

        result = order.buy_to_close("AAPL", 100, 5.75)

        assert result is order
        assert len(order.legs) == 1
        assert order.legs[0].order_type == OrderType.BTC

    def test_multi_leg_order_sell_to_close_method(self):
        """Test sell_to_close convenience method."""
        order = MultiLegOrder(legs=[])

        result = order.sell_to_close("AAPL", 100, 5.25)

        assert result is order
        assert len(order.legs) == 1
        assert order.legs[0].order_type == OrderType.STC

    def test_multi_leg_order_method_chaining(self):
        """Test method chaining for building complex orders."""
        order = (
            MultiLegOrder(legs=[])
            .buy_to_open("AAPL240119C00195000", 10, 5.50)
            .sell_to_open("AAPL240119C00200000", 10, 3.25)
        )

        assert len(order.legs) == 2
        assert order.legs[0].order_type == OrderType.BTO
        assert order.legs[1].order_type == OrderType.STO

    def test_multi_leg_order_net_price_property(self):
        """Test net_price property calculation."""
        leg1 = OrderLeg(asset="AAPL", quantity=10, order_type=OrderType.BTO, price=5.50)
        leg2 = OrderLeg(
            asset="AAPL", quantity=-10, order_type=OrderType.STO, price=3.25
        )

        order = MultiLegOrder(legs=[leg1, leg2])

        # Net price = 5.50 * 10 + 3.25 * 10 = 55.0 + 32.5 = 87.5
        expected_net = 5.50 * 10 + 3.25 * 10
        assert order.net_price == expected_net

    def test_multi_leg_order_net_price_with_none_price(self):
        """Test net_price property with None prices."""
        leg1 = OrderLeg(asset="AAPL", quantity=10, order_type=OrderType.BTO, price=None)
        leg2 = OrderLeg(
            asset="AAPL", quantity=-10, order_type=OrderType.STO, price=3.25
        )

        order = MultiLegOrder(legs=[leg1, leg2])

        assert order.net_price is None

    def test_multi_leg_order_is_opening_order_property(self):
        """Test is_opening_order property."""
        # Opening order
        opening_leg = OrderLeg(
            asset="AAPL", quantity=10, order_type=OrderType.BTO, price=5.50
        )
        opening_order = MultiLegOrder(legs=[opening_leg])
        assert opening_order.is_opening_order is True

        # Closing order
        closing_leg = OrderLeg(
            asset="AAPL", quantity=-10, order_type=OrderType.STC, price=5.50
        )
        closing_order = MultiLegOrder(legs=[closing_leg])
        assert closing_order.is_opening_order is False

    def test_multi_leg_order_is_closing_order_property(self):
        """Test is_closing_order property."""
        # Closing order
        closing_leg = OrderLeg(
            asset="AAPL", quantity=-10, order_type=OrderType.BTC, price=5.50
        )
        closing_order = MultiLegOrder(legs=[closing_leg])
        assert closing_order.is_closing_order is True

        # Opening order
        opening_leg = OrderLeg(
            asset="AAPL", quantity=10, order_type=OrderType.STO, price=5.50
        )
        opening_order = MultiLegOrder(legs=[opening_leg])
        assert opening_order.is_closing_order is False


class TestOrderCreateSchemas:
    """Test order creation schemas."""

    def test_order_create_basic(self):
        """Test basic OrderCreate schema."""
        order_create = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )

        assert order_create.symbol == "AAPL"
        assert order_create.order_type == OrderType.BUY
        assert order_create.quantity == 100
        assert order_create.price == 150.0
        assert order_create.condition == OrderCondition.MARKET

    def test_order_leg_create_basic(self):
        """Test basic OrderLegCreate schema."""
        leg_create = OrderLegCreate(
            asset="AAPL240119C00195000",
            quantity=10,
            order_type=OrderType.BTO,
            price=5.50,
        )

        assert leg_create.asset == "AAPL240119C00195000"
        assert leg_create.quantity == 10
        assert leg_create.order_type == OrderType.BTO
        assert leg_create.price == 5.50

    def test_multi_leg_order_create_basic(self):
        """Test basic MultiLegOrderCreate schema."""
        leg1 = OrderLegCreate(
            asset="AAPL", quantity=10, order_type=OrderType.BTO, price=5.50
        )
        leg2 = OrderLegCreate(
            asset="AAPL", quantity=-10, order_type=OrderType.STO, price=3.25
        )

        order_create = MultiLegOrderCreate(
            legs=[leg1, leg2], condition=OrderCondition.LIMIT, limit_price=2.25
        )

        assert len(order_create.legs) == 2
        assert order_create.condition == OrderCondition.LIMIT
        assert order_create.limit_price == 2.25


class TestOrderValidationMixin:
    """Test OrderValidationMixin validation patterns."""

    def test_order_type_validation_valid(self):
        """Test valid order type validation."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=100)
        assert order.order_type == OrderType.BUY

    def test_order_quantity_validation_nonzero(self):
        """Test quantity validation from mixin."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=100)
        assert order.quantity == 100

    def test_order_price_validation_positive(self):
        """Test price validation when provided."""
        order = Order(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        assert order.price == 150.0


class TestOrderComplexScenarios:
    """Test complex order scenarios and edge cases."""

    def test_option_spread_order(self):
        """Test creating option spread order."""
        call_leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=10,
            order_type=OrderType.BTO,
            price=5.50,
        )

        put_leg = OrderLeg(
            asset="AAPL240119P00190000",
            quantity=-10,
            order_type=OrderType.STO,
            price=4.25,
        )

        spread_order = MultiLegOrder(
            legs=[call_leg, put_leg], condition=OrderCondition.LIMIT, limit_price=1.25
        )

        assert len(spread_order.legs) == 2
        assert spread_order.legs[0].asset.symbol == "AAPL240119C00195000"
        assert spread_order.legs[1].asset.symbol == "AAPL240119P00190000"

    def test_iron_condor_order(self):
        """Test creating iron condor multi-leg order."""
        order = (
            MultiLegOrder(legs=[])
            .sell_to_open("AAPL240119P00180000", 10, 2.00)
            .buy_to_open("AAPL240119P00175000", 10, 1.25)
            .sell_to_open("AAPL240119C00210000", 10, 3.00)
            .buy_to_open("AAPL240119C00215000", 10, 2.25)
        )

        assert len(order.legs) == 4
        assert all(
            leg.order_type in [OrderType.BTO, OrderType.STO] for leg in order.legs
        )

    def test_order_serialization_with_datetimes(self):
        """Test order serialization with datetime fields."""
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

        order = Order(
            id="datetime_test",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            created_at=created_at,
        )

        data = order.model_dump()
        assert data["created_at"] == created_at

    def test_order_legs_default_empty(self):
        """Test order legs default to empty list."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=100)

        assert order.legs == []
        assert isinstance(order.legs, list)
