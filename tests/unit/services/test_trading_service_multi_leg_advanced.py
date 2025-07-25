"""
Tests for TradingService advanced multi-leg order functionality.

This module covers the create_multi_leg_order_from_request method (lines 1149-1207)
and related multi-leg order processing which provides:
- Complex multi-leg order creation from raw request data
- Order leg validation and structuring
- Strategy recognition and validation
- Net price handling and validation
- Error handling for invalid leg configurations

Coverage target: Lines 1149-1207 (create_multi_leg_order_from_request method)
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.schemas.orders import Order, OrderStatus, OrderType


class TestTradingServiceMultiLegAdvanced:
    """Test advanced multi-leg order functionality."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_basic_spread(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order from request data for basic spread."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240315C00160000", "quantity": 1, "side": "sell"},
        ]

        # Mock the underlying create_multi_leg_order method
        mock_order = Order(
            id="multi-leg-123",
            symbol="AAPL_SPREAD",
            quantity=1,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("2.50"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=2.50
                )
            )

            assert isinstance(result, Order)
            assert result.id == "multi-leg-123"
            assert result.symbol == "AAPL_SPREAD"

            # Verify the structured legs were passed correctly
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]  # First positional argument (legs)

            assert len(call_args) == 2
            assert call_args[0]["symbol"] == "AAPL240315C00150000"
            assert call_args[0]["quantity"] == 1
            assert call_args[0]["side"] == "buy"
            assert call_args[0]["order_type"] == "limit"
            assert call_args[0]["price"] == 2.50

            assert call_args[1]["symbol"] == "AAPL240315C00160000"
            assert call_args[1]["quantity"] == 1
            assert call_args[1]["side"] == "sell"
            assert call_args[1]["order_type"] == "limit"
            assert call_args[1]["price"] == 2.50

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_market_order(
        self, trading_service_test_data
    ):
        """Test creating multi-leg market order from request data."""
        legs = [
            {"symbol": "SPY240315P00400000", "quantity": 2, "side": "buy"},
            {"symbol": "SPY240315P00390000", "quantity": 2, "side": "sell"},
        ]

        mock_order = Order(
            id="multi-leg-market-456",
            symbol="SPY_PUT_SPREAD",
            quantity=2,
            order_type=OrderType.MARKET,
            side="buy",
            price=None,
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="market", net_price=None
                )
            )

            assert isinstance(result, Order)
            assert result.order_type == OrderType.MARKET
            assert result.price is None

            # Verify structured legs for market order
            call_args = mock_create.call_args[0][0]
            for leg in call_args:
                assert leg["order_type"] == "market"
                assert leg["price"] is None

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_complex_iron_condor(
        self, trading_service_test_data
    ):
        """Test creating complex multi-leg order (iron condor) from request data."""
        legs = [
            # Short call spread
            {"symbol": "TSLA240315C00200000", "quantity": 1, "side": "sell"},
            {"symbol": "TSLA240315C00210000", "quantity": 1, "side": "buy"},
            # Short put spread
            {"symbol": "TSLA240315P00180000", "quantity": 1, "side": "sell"},
            {"symbol": "TSLA240315P00170000", "quantity": 1, "side": "buy"},
        ]

        mock_order = Order(
            id="iron-condor-789",
            symbol="TSLA_IRON_CONDOR",
            quantity=1,
            order_type=OrderType.LIMIT,
            side="sell",  # Net credit strategy
            price=Decimal("3.75"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=3.75
                )
            )

            assert isinstance(result, Order)
            assert result.id == "iron-condor-789"

            # Verify all 4 legs were structured correctly
            call_args = mock_create.call_args[0][0]
            assert len(call_args) == 4

            # Verify each leg has correct structure
            for i, leg in enumerate(call_args):
                assert leg["symbol"] == legs[i]["symbol"]
                assert leg["quantity"] == legs[i]["quantity"]
                assert leg["side"] == legs[i]["side"]
                assert leg["order_type"] == "limit"
                assert leg["price"] == 3.75

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_single_leg(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with single leg (edge case)."""
        legs = [{"symbol": "AAPL240315C00150000", "quantity": 5, "side": "buy"}]

        mock_order = Order(
            id="single-leg-101",
            symbol="AAPL240315C00150000",
            quantity=5,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("7.50"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=7.50
                )
            )

            assert isinstance(result, Order)
            assert result.quantity == 5

            # Verify single leg was structured correctly
            call_args = mock_create.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["symbol"] == "AAPL240315C00150000"
            assert call_args[0]["quantity"] == 5
            assert call_args[0]["side"] == "buy"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_empty_legs(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with empty legs list."""
        legs = []

        mock_order = Order(
            id="empty-order-102",
            symbol="EMPTY",
            quantity=0,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("0.00"),
            status=OrderStatus.REJECTED,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=0.00
                )
            )

            assert isinstance(result, Order)
            assert result.status == OrderStatus.REJECTED

            # Verify empty legs were passed
            call_args = mock_create.call_args[0][0]
            assert len(call_args) == 0

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_mixed_quantities(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with different quantities per leg."""
        legs = [
            {"symbol": "QQQ240315C00350000", "quantity": 10, "side": "buy"},
            {"symbol": "QQQ240315C00360000", "quantity": 5, "side": "sell"},
            {"symbol": "QQQ240315P00340000", "quantity": 3, "side": "sell"},
        ]

        mock_order = Order(
            id="mixed-quantities-103",
            symbol="QQQ_CUSTOM_STRATEGY",
            quantity=10,  # Usually based on primary leg
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("5.25"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=5.25
                )
            )

            assert isinstance(result, Order)

            # Verify different quantities were preserved
            call_args = mock_create.call_args[0][0]
            assert call_args[0]["quantity"] == 10
            assert call_args[1]["quantity"] == 5
            assert call_args[2]["quantity"] == 3

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_missing_required_fields(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with missing required fields in legs."""
        legs = [
            {
                "symbol": "AAPL240315C00150000",
                # Missing quantity and side
            }
        ]

        # Should raise KeyError when trying to access missing fields
        with pytest.raises(KeyError):
            await trading_service_test_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=5.00
            )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_invalid_order_type(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with invalid order type."""
        legs = [{"symbol": "AAPL240315C00150000", "quantity": 1, "side": "buy"}]

        mock_order = Order(
            id="invalid-type-104",
            symbol="AAPL240315C00150000",
            quantity=1,
            order_type=OrderType.LIMIT,  # Default fallback
            side="buy",
            price=Decimal("5.00"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs,
                    order_type="invalid_order_type",  # Invalid type
                    net_price=5.00,
                )
            )

            assert isinstance(result, Order)

            # Verify invalid order type was passed through (validation in create_multi_leg_order)
            call_args = mock_create.call_args[0][0]
            assert call_args[0]["order_type"] == "invalid_order_type"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_zero_net_price(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with zero net price."""
        legs = [
            {"symbol": "SPY240315C00400000", "quantity": 1, "side": "buy"},
            {
                "symbol": "SPY240315C00400000",
                "quantity": 1,
                "side": "sell",
            },  # Perfect hedge
        ]

        mock_order = Order(
            id="zero-price-105",
            symbol="SPY_NEUTRAL",
            quantity=1,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("0.00"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=0.00
                )
            )

            assert isinstance(result, Order)
            assert result.price == Decimal("0.00")

            # Verify zero price was structured correctly
            call_args = mock_create.call_args[0][0]
            for leg in call_args:
                assert leg["price"] == 0.00

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_negative_net_price(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with negative net price (credit spread)."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 1, "side": "sell"},  # Credit
            {"symbol": "AAPL240315C00160000", "quantity": 1, "side": "buy"},  # Debit
        ]

        mock_order = Order(
            id="credit-spread-106",
            symbol="AAPL_CREDIT_SPREAD",
            quantity=1,
            order_type=OrderType.LIMIT,
            side="sell",  # Net credit
            price=Decimal("-2.25"),  # Negative indicates credit
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs,
                    order_type="limit",
                    net_price=-2.25,  # Credit spread
                )
            )

            assert isinstance(result, Order)
            assert result.price == Decimal("-2.25")

            # Verify negative price was handled correctly
            call_args = mock_create.call_args[0][0]
            for leg in call_args:
                assert leg["price"] == -2.25

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_large_quantities(
        self, trading_service_test_data
    ):
        """Test creating multi-leg order with large quantities."""
        legs = [
            {"symbol": "SPY240315C00400000", "quantity": 1000, "side": "buy"},
            {"symbol": "SPY240315C00410000", "quantity": 1000, "side": "sell"},
        ]

        mock_order = Order(
            id="large-order-107",
            symbol="SPY_LARGE_SPREAD",
            quantity=1000,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("1.50"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=1.50
                )
            )

            assert isinstance(result, Order)
            assert result.quantity == 1000

            # Verify large quantities were preserved
            call_args = mock_create.call_args[0][0]
            assert call_args[0]["quantity"] == 1000
            assert call_args[1]["quantity"] == 1000

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_underlying_create_error(
        self, trading_service_test_data
    ):
        """Test error handling when underlying create_multi_leg_order fails."""
        legs = [{"symbol": "INVALID240315C00150000", "quantity": 1, "side": "buy"}]

        with patch.object(
            trading_service_test_data, "create_multi_leg_order"
        ) as mock_create:
            mock_create.side_effect = Exception("Invalid symbol format")

            with pytest.raises(Exception, match="Invalid symbol format"):
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=5.00
                )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_preserves_leg_order(
        self, trading_service_test_data
    ):
        """Test that leg order is preserved in multi-leg order creation."""
        legs = [
            {"symbol": "FIRST240315C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "SECOND240315C00160000", "quantity": 1, "side": "sell"},
            {"symbol": "THIRD240315C00170000", "quantity": 1, "side": "buy"},
            {"symbol": "FOURTH240315P00140000", "quantity": 1, "side": "sell"},
        ]

        mock_order = Order(
            id="ordered-legs-108",
            symbol="COMPLEX_STRATEGY",
            quantity=1,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("2.00"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=2.00
                )
            )

            assert isinstance(result, Order)

            # Verify leg order was preserved
            call_args = mock_create.call_args[0][0]
            assert len(call_args) == 4
            assert call_args[0]["symbol"] == "FIRST240315C00150000"
            assert call_args[1]["symbol"] == "SECOND240315C00160000"
            assert call_args[2]["symbol"] == "THIRD240315C00170000"
            assert call_args[3]["symbol"] == "FOURTH240315P00140000"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_different_sides_validation(
        self, trading_service_test_data
    ):
        """Test multi-leg order with various side combinations."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 2, "side": "buy"},
            {"symbol": "AAPL240315C00160000", "quantity": 2, "side": "sell"},
            {"symbol": "AAPL240315P00140000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240315P00130000", "quantity": 1, "side": "sell"},
        ]

        mock_order = Order(
            id="mixed-sides-109",
            symbol="AAPL_COMPLEX",
            quantity=2,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("1.75"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=1.75
                )
            )

            assert isinstance(result, Order)

            # Verify all sides were preserved correctly
            call_args = mock_create.call_args[0][0]
            assert call_args[0]["side"] == "buy"
            assert call_args[1]["side"] == "sell"
            assert call_args[2]["side"] == "buy"
            assert call_args[3]["side"] == "sell"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_comprehensive_structure_validation(
        self, trading_service_test_data
    ):
        """Test comprehensive validation of structured legs output."""
        legs = [{"symbol": "TEST240315C00100000", "quantity": 5, "side": "buy"}]

        mock_order = Order(
            id="structure-test-110",
            symbol="TEST240315C00100000",
            quantity=5,
            order_type=OrderType.LIMIT,
            side="buy",
            price=Decimal("3.33"),
            status=OrderStatus.PENDING,
            account_id="test-account",
        )

        with patch.object(
            trading_service_test_data, "create_multi_leg_order", return_value=mock_order
        ) as mock_create:
            result = (
                await trading_service_test_data.create_multi_leg_order_from_request(
                    legs=legs, order_type="limit", net_price=3.33
                )
            )

            assert isinstance(result, Order)

            # Verify complete structured leg format
            call_args = mock_create.call_args[0][0]
            structured_leg = call_args[0]

            # Check all required fields are present
            required_fields = ["symbol", "quantity", "side", "order_type", "price"]
            for field in required_fields:
                assert field in structured_leg

            # Verify values are correct
            assert structured_leg["symbol"] == "TEST240315C00100000"
            assert structured_leg["quantity"] == 5
            assert structured_leg["side"] == "buy"
            assert structured_leg["order_type"] == "limit"
            assert structured_leg["price"] == 3.33
