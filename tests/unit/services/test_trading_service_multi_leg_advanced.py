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


@pytest.mark.journey_options_trading
class TestTradingServiceMultiLegAdvanced:
    """Test advanced multi-leg order functionality."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_basic_spread(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order from request data for basic spread."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240315C00160000", "quantity": 1, "side": "sell"},
        ]

        # Mock the underlying create_multi_leg_order method
        mock_order = Order(
            id="MULTILEG12",
            symbol="AAPL_SPREAD",
            quantity=1,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("2.50"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=2.50
            )

            assert isinstance(result, Order)
            assert result.id == "MULTILEG12"
            assert result.symbol == "AAPL_SPREAD"

            # Verify the mock order data was passed correctly
            mock_create.assert_called_once()
            mock_order_data = mock_create.call_args[0][
                0
            ]  # First positional argument (MockOrderData)

            # Verify the MockOrderData structure
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 2

            # Check first leg
            leg1 = mock_order_data.legs[0]
            assert leg1.symbol == "AAPL240315C00150000"
            assert leg1.quantity == 1
            assert leg1.side == "buy"
            assert leg1.order_type == OrderType.BUY
            assert leg1.price == 2.50

            # Check second leg
            leg2 = mock_order_data.legs[1]
            assert leg2.symbol == "AAPL240315C00160000"
            assert leg2.quantity == 1
            assert leg2.side == "sell"
            assert leg2.order_type == OrderType.SELL
            assert leg2.price == 2.50

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_market_order(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg market order from request data."""
        legs = [
            {"symbol": "SPY240315P00400000", "quantity": 2, "side": "buy"},
            {"symbol": "SPY240315P00390000", "quantity": 2, "side": "sell"},
        ]

        mock_order = Order(
            id="MULTILEGMA",
            symbol="SPY240315P00400000",  # Use valid symbol format
            quantity=2,
            order_type=OrderType.BUY,
            side="buy",
            price=None,
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="market", net_price=None
            )

            assert isinstance(result, Order)
            assert result.order_type == OrderType.BUY
            assert result.price is None

            # Verify structured legs for market order
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 2

            # Check each leg individually with correct order type based on side
            leg1 = mock_order_data.legs[0]
            assert leg1.side == "buy"
            assert leg1.order_type == OrderType.BUY
            assert leg1.price is None

            leg2 = mock_order_data.legs[1]
            assert leg2.side == "sell"
            assert leg2.order_type == OrderType.SELL
            assert leg2.price is None

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_complex_iron_condor(
        self, trading_service_synthetic_data
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
            id="IRONCONDOR",
            symbol="TSLA240315C00200000",  # Use valid symbol format
            quantity=1,
            order_type=OrderType.BUY,
            side="sell",  # Net credit strategy
            price=Decimal("3.75"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=3.75
            )

            assert isinstance(result, Order)
            assert result.id == "IRONCONDOR"

            # Verify all 4 legs were structured correctly
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 4

            # Verify each leg has correct structure
            for i, leg in enumerate(mock_order_data.legs):
                assert leg.symbol == legs[i]["symbol"]
                assert leg.quantity == legs[i]["quantity"]
                assert leg.side == legs[i]["side"]
                expected_order_type = (
                    OrderType.SELL if legs[i]["side"] == "sell" else OrderType.BUY
                )
                assert leg.order_type == expected_order_type
                assert leg.price == 3.75

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_single_leg(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with single leg (edge case)."""
        legs = [{"symbol": "AAPL240315C00150000", "quantity": 5, "side": "buy"}]

        mock_order = Order(
            id="SINGLELEG1",
            symbol="AAPL240315C00150000",
            quantity=5,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("7.50"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=7.50
            )

            assert isinstance(result, Order)
            assert result.quantity == 5

            # Verify single leg was structured correctly
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 1

            leg1 = mock_order_data.legs[0]
            assert leg1.symbol == "AAPL240315C00150000"
            assert leg1.quantity == 5
            assert leg1.side == "buy"
            assert leg1.order_type == OrderType.BUY

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_empty_legs(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with empty legs list."""
        legs = []

        mock_order = Order(
            id="EMPTYORDER",
            symbol="AAPL240315C00150000",  # Use valid symbol format
            quantity=1,  # Use valid quantity (must be > 0)
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("0.00"),
            status=OrderStatus.REJECTED,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=0.00
            )

            assert isinstance(result, Order)
            assert result.status == OrderStatus.REJECTED

            # Verify empty legs were passed
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 0

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_mixed_quantities(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with different quantities per leg."""
        legs = [
            {"symbol": "QQQ240315C00350000", "quantity": 10, "side": "buy"},
            {"symbol": "QQQ240315C00360000", "quantity": 5, "side": "sell"},
            {"symbol": "QQQ240315P00340000", "quantity": 3, "side": "sell"},
        ]

        mock_order = Order(
            id="MIXEDQUANT",
            symbol="QQQ240315C00350000",  # Use valid symbol format
            quantity=10,  # Usually based on primary leg
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("5.25"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=5.25
            )

            assert isinstance(result, Order)

            # Verify different quantities were preserved
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 3

            assert mock_order_data.legs[0].quantity == 10
            assert mock_order_data.legs[1].quantity == 5
            assert mock_order_data.legs[2].quantity == 3

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_missing_required_fields(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with missing required fields in legs."""
        legs = [
            {
                "symbol": "AAPL240315C00150000",
                # Missing quantity and side
            }
        ]

        # Should raise ValueError when trying to access missing fields
        with pytest.raises(ValueError, match="Failed to create multi-leg order"):
            await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=5.00
            )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_invalid_order_type(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with invalid order type."""
        legs = [{"symbol": "AAPL240315C00150000", "quantity": 1, "side": "buy"}]

        mock_order = Order(
            id="INVALIDTYP",
            symbol="AAPL240315C00150000",
            quantity=1,
            order_type=OrderType.BUY,  # Default fallback
            side="buy",
            price=Decimal("5.00"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs,
                order_type="invalid_order_type",  # Invalid type
                net_price=5.00,
            )

            assert isinstance(result, Order)

            # Verify invalid order type was passed through (validation in create_multi_leg_order)
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 1

            leg1 = mock_order_data.legs[0]
            # Invalid order types should be handled by the system, likely converted to BUY
            assert leg1.order_type == OrderType.BUY

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_zero_net_price(
        self, trading_service_synthetic_data
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
            id="ZEROPRICE1",
            symbol="SPY240315C00400000",  # Use valid symbol format
            quantity=1,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("0.00"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=0.00
            )

            assert isinstance(result, Order)
            assert result.price == Decimal("0.00")

            # Verify zero price was structured correctly
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 2

            for leg in mock_order_data.legs:
                assert leg.price == 0.00

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_negative_net_price(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with negative net price (credit spread)."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 1, "side": "sell"},  # Credit
            {"symbol": "AAPL240315C00160000", "quantity": 1, "side": "buy"},  # Debit
        ]

        mock_order = Order(
            id="CREDITSPRE",
            symbol="AAPL240315C00150000",  # Use valid symbol format
            quantity=1,
            order_type=OrderType.BUY,
            side="sell",  # Net credit
            price=Decimal("-2.25"),  # Negative indicates credit
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs,
                order_type="limit",
                net_price=-2.25,  # Credit spread
            )

            assert isinstance(result, Order)
            assert result.price == Decimal("-2.25")

            # Verify negative price was handled correctly
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 2

            for leg in mock_order_data.legs:
                assert leg.price == -2.25

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_large_quantities(
        self, trading_service_synthetic_data
    ):
        """Test creating multi-leg order with large quantities."""
        legs = [
            {"symbol": "SPY240315C00400000", "quantity": 1000, "side": "buy"},
            {"symbol": "SPY240315C00410000", "quantity": 1000, "side": "sell"},
        ]

        mock_order = Order(
            id="LARGEORDER",
            symbol="SPY240315C00400000",  # Use valid symbol format
            quantity=1000,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("1.50"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=1.50
            )

            assert isinstance(result, Order)
            assert result.quantity == 1000

            # Verify large quantities were preserved
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 2

            assert mock_order_data.legs[0].quantity == 1000
            assert mock_order_data.legs[1].quantity == 1000

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_underlying_create_error(
        self, trading_service_synthetic_data
    ):
        """Test error handling when underlying create_multi_leg_order fails."""
        legs = [{"symbol": "INVALID240315C00150000", "quantity": 1, "side": "buy"}]

        with patch.object(
            trading_service_synthetic_data, "create_multi_leg_order"
        ) as mock_create:
            mock_create.side_effect = Exception("Invalid symbol format")

            with pytest.raises(Exception, match="Invalid symbol format"):
                await (
                    trading_service_synthetic_data.create_multi_leg_order_from_request(
                        legs=legs, order_type="limit", net_price=5.00
                    )
                )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_preserves_leg_order(
        self, trading_service_synthetic_data
    ):
        """Test that leg order is preserved in multi-leg order creation."""
        legs = [
            {"symbol": "FIRST240315C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "SECOND240315C00160000", "quantity": 1, "side": "sell"},
            {"symbol": "THIRD240315C00170000", "quantity": 1, "side": "buy"},
            {"symbol": "FOURTH240315P00140000", "quantity": 1, "side": "sell"},
        ]

        mock_order = Order(
            id="ORDEREDLEG",
            symbol="FIRST240315C00150000",  # Use valid symbol format
            quantity=1,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("2.00"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=2.00
            )

            assert isinstance(result, Order)

            # Verify leg order was preserved
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 4

            assert mock_order_data.legs[0].symbol == "FIRST240315C00150000"
            assert mock_order_data.legs[1].symbol == "SECOND240315C00160000"
            assert mock_order_data.legs[2].symbol == "THIRD240315C00170000"
            assert mock_order_data.legs[3].symbol == "FOURTH240315P00140000"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_different_sides_validation(
        self, trading_service_synthetic_data
    ):
        """Test multi-leg order with various side combinations."""
        legs = [
            {"symbol": "AAPL240315C00150000", "quantity": 2, "side": "buy"},
            {"symbol": "AAPL240315C00160000", "quantity": 2, "side": "sell"},
            {"symbol": "AAPL240315P00140000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240315P00130000", "quantity": 1, "side": "sell"},
        ]

        mock_order = Order(
            id="MIXEDSIDES",
            symbol="AAPL240315C00150000",  # Use valid symbol format
            quantity=2,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("1.75"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=1.75
            )

            assert isinstance(result, Order)

            # Verify all sides were preserved correctly
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 4

            assert mock_order_data.legs[0].side == "buy"
            assert mock_order_data.legs[0].order_type == OrderType.BUY
            assert mock_order_data.legs[1].side == "sell"
            assert mock_order_data.legs[1].order_type == OrderType.SELL
            assert mock_order_data.legs[2].side == "buy"
            assert mock_order_data.legs[2].order_type == OrderType.BUY
            assert mock_order_data.legs[3].side == "sell"
            assert mock_order_data.legs[3].order_type == OrderType.SELL

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_comprehensive_structure_validation(
        self, trading_service_synthetic_data
    ):
        """Test comprehensive validation of structured legs output."""
        legs = [{"symbol": "TEST240315C00100000", "quantity": 5, "side": "buy"}]

        mock_order = Order(
            id="STRUCTURET",
            symbol="TEST240315C00100000",
            quantity=5,
            order_type=OrderType.BUY,
            side="buy",
            price=Decimal("3.33"),
            status=OrderStatus.PENDING,
            account_id="TESTACCOUN",
        )

        with patch.object(
            trading_service_synthetic_data,
            "create_multi_leg_order",
            return_value=mock_order,
        ) as mock_create:
            result = await trading_service_synthetic_data.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=3.33
            )

            assert isinstance(result, Order)

            # Verify complete structured leg format
            mock_order_data = mock_create.call_args[0][0]
            assert hasattr(mock_order_data, "legs")
            assert len(mock_order_data.legs) == 1

            structured_leg = mock_order_data.legs[0]

            # Check all required fields are present
            assert hasattr(structured_leg, "symbol")
            assert hasattr(structured_leg, "quantity")
            assert hasattr(structured_leg, "side")
            assert hasattr(structured_leg, "order_type")
            assert hasattr(structured_leg, "price")

            # Verify values are correct
            assert structured_leg.symbol == "TEST240315C00100000"
            assert structured_leg.quantity == 5
            assert structured_leg.side == "buy"
            assert structured_leg.order_type == OrderType.BUY
            assert structured_leg.price == 3.33
