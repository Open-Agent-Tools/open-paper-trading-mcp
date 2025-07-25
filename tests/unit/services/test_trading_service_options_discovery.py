"""
Tests for TradingService options discovery and market data functionality.

This module covers the find_tradable_options method (lines 716-794) and
get_market_hours method (lines 1379-1412) which provide:
- Tradable options discovery with filtering
- Expiration date filtering and validation
- Strike price range filtering
- Market hours and status information
- Extended functionality adapter integration
- Error handling for invalid parameters

Coverage target: Lines 716-794 (find_tradable_options) + Lines 1379-1412 (get_market_hours)
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.models.assets import Option, Stock


class TestTradingServiceOptionsDiscovery:
    """Test options discovery and market data functionality."""

    @pytest.mark.asyncio
    async def test_find_tradable_options_basic_success(self, trading_service_test_data):
        """Test basic successful options discovery."""
        # Mock option chain data
        mock_options = [
            Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240315C00160000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=160.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240315P00140000",
                underlying=Stock(symbol="AAPL"),
                option_type="PUT",
                strike=140.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="AAPL", expiration_date=datetime(2024, 3, 15)
            )

            assert isinstance(result, dict)
            assert "underlying" in result
            assert result["underlying"] == "AAPL"
            assert "expiration_date" in result
            assert "options" in result
            assert len(result["options"]) == 3

            # Verify option structure
            for option in result["options"]:
                assert "symbol" in option
                assert "option_type" in option
                assert "strike" in option
                assert "expiration_date" in option

    @pytest.mark.asyncio
    async def test_find_tradable_options_with_strike_filter(
        self, trading_service_test_data
    ):
        """Test options discovery with strike price filtering."""
        mock_options = [
            Option(
                symbol="AAPL240315C00140000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=140.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240315C00160000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=160.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240315C00170000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=170.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="AAPL",
                expiration_date=datetime(2024, 3, 15),
                min_strike=145.0,
                max_strike=165.0,
            )

            assert len(result["options"]) == 2  # Only 150 and 160 strikes

            # Verify filtering worked correctly
            strikes = [opt["strike"] for opt in result["options"]]
            assert 150.0 in strikes
            assert 160.0 in strikes
            assert 140.0 not in strikes
            assert 170.0 not in strikes

            # Verify all strikes are within range
            for strike in strikes:
                assert 145.0 <= strike <= 165.0

    @pytest.mark.asyncio
    async def test_find_tradable_options_calls_only_filter(
        self, trading_service_test_data
    ):
        """Test options discovery with calls-only filtering."""
        mock_options = [
            Option(
                symbol="SPY240315C00400000",
                underlying=Stock(symbol="SPY"),
                option_type="CALL",
                strike=400.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="SPY240315P00400000",
                underlying=Stock(symbol="SPY"),
                option_type="PUT",
                strike=400.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="SPY240315C00410000",
                underlying=Stock(symbol="SPY"),
                option_type="CALL",
                strike=410.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="SPY",
                expiration_date=datetime(2024, 3, 15),
                option_type="CALL",
            )

            assert len(result["options"]) == 2  # Only calls

            # Verify all returned options are calls
            for option in result["options"]:
                assert option["option_type"] == "CALL"

    @pytest.mark.asyncio
    async def test_find_tradable_options_puts_only_filter(
        self, trading_service_test_data
    ):
        """Test options discovery with puts-only filtering."""
        mock_options = [
            Option(
                symbol="TSLA240315C00200000",
                underlying=Stock(symbol="TSLA"),
                option_type="CALL",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="TSLA240315P00200000",
                underlying=Stock(symbol="TSLA"),
                option_type="PUT",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="TSLA240315P00190000",
                underlying=Stock(symbol="TSLA"),
                option_type="PUT",
                strike=190.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="TSLA",
                expiration_date=datetime(2024, 3, 15),
                option_type="PUT",
            )

            assert len(result["options"]) == 2  # Only puts

            # Verify all returned options are puts
            for option in result["options"]:
                assert option["option_type"] == "PUT"

    @pytest.mark.asyncio
    async def test_find_tradable_options_combined_filters(
        self, trading_service_test_data
    ):
        """Test options discovery with multiple filters combined."""
        mock_options = [
            Option(
                symbol="QQQ240315C00340000",
                underlying=Stock(symbol="QQQ"),
                option_type="CALL",
                strike=340.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="QQQ240315C00350000",
                underlying=Stock(symbol="QQQ"),
                option_type="CALL",
                strike=350.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="QQQ240315C00360000",
                underlying=Stock(symbol="QQQ"),
                option_type="CALL",
                strike=360.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="QQQ240315P00340000",
                underlying=Stock(symbol="QQQ"),
                option_type="PUT",
                strike=340.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="QQQ240315P00350000",
                underlying=Stock(symbol="QQQ"),
                option_type="PUT",
                strike=350.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="QQQ",
                expiration_date=datetime(2024, 3, 15),
                option_type="CALL",
                min_strike=345.0,
                max_strike=355.0,
            )

            assert len(result["options"]) == 1  # Only 350 call meets all criteria
            option = result["options"][0]
            assert option["option_type"] == "CALL"
            assert option["strike"] == 350.0
            assert 345.0 <= option["strike"] <= 355.0

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_expiration_date(
        self, trading_service_test_data
    ):
        """Test options discovery without expiration date filter."""
        mock_options = [
            Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="AAPL240415C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 4, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="AAPL"
            )

            assert len(result["options"]) == 2  # All options returned
            assert result["expiration_date"] is None

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_options_found(
        self, trading_service_test_data
    ):
        """Test options discovery when no options match criteria."""
        mock_options = []

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="AAPL", expiration_date=datetime(2024, 3, 15)
            )

            assert len(result["options"]) == 0
            assert result["underlying"] == "AAPL"

    @pytest.mark.asyncio
    async def test_find_tradable_options_adapter_error(self, trading_service_test_data):
        """Test options discovery when adapter throws error."""
        with patch.object(
            trading_service_test_data.quote_adapter, "get_chain"
        ) as mock_get_chain:
            mock_get_chain.side_effect = Exception("Chain not available")

            result = await trading_service_test_data.find_tradable_options(
                underlying="INVALID", expiration_date=datetime(2024, 3, 15)
            )

            assert "error" in result
            assert "Chain not available" in result["error"]

    @pytest.mark.asyncio
    async def test_find_tradable_options_invalid_strike_range(
        self, trading_service_test_data
    ):
        """Test options discovery with invalid strike range (min > max)."""
        mock_options = [
            Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            )
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="AAPL",
                expiration_date=datetime(2024, 3, 15),
                min_strike=160.0,  # Min > Max
                max_strike=140.0,
            )

            # Should return empty results due to invalid range
            assert len(result["options"]) == 0

    @pytest.mark.asyncio
    async def test_get_market_hours_with_extended_adapter(
        self, trading_service_test_data
    ):
        """Test get_market_hours with adapter that supports extended functionality."""
        mock_hours = {
            "is_open": True,
            "next_open": "2024-03-15T09:30:00Z",
            "next_close": "2024-03-15T16:00:00Z",
            "timezone": "US/Eastern",
        }

        # Mock adapter with get_market_hours method
        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_market_hours",
            return_value=mock_hours,
        ):
            result = await trading_service_test_data.get_market_hours()

            assert isinstance(result, dict)
            assert result["is_open"] is True
            assert "next_open" in result
            assert "next_close" in result
            assert "timezone" in result

    @pytest.mark.asyncio
    async def test_get_market_hours_fallback_basic_info(
        self, trading_service_test_data
    ):
        """Test get_market_hours fallback when adapter lacks extended functionality."""
        # Remove get_market_hours method to test fallback
        if hasattr(trading_service_test_data.quote_adapter, "get_market_hours"):
            delattr(trading_service_test_data.quote_adapter, "get_market_hours")

        result = await trading_service_test_data.get_market_hours()

        assert isinstance(result, dict)
        assert "source" in result
        assert result["source"] == "fallback"
        assert "message" in result
        assert "Market hours not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_market_hours_adapter_error(self, trading_service_test_data):
        """Test get_market_hours when adapter throws error."""
        with patch.object(
            trading_service_test_data.quote_adapter, "get_market_hours"
        ) as mock_hours:
            mock_hours.side_effect = Exception("Market data unavailable")

            result = await trading_service_test_data.get_market_hours()

            assert "error" in result
            assert "Market data unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_get_market_hours_market_closed(self, trading_service_test_data):
        """Test get_market_hours when market is closed."""
        mock_hours = {
            "is_open": False,
            "next_open": "2024-03-16T09:30:00Z",
            "last_close": "2024-03-15T16:00:00Z",
            "timezone": "US/Eastern",
        }

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_market_hours",
            return_value=mock_hours,
        ):
            result = await trading_service_test_data.get_market_hours()

            assert result["is_open"] is False
            assert "next_open" in result
            assert "last_close" in result

    @pytest.mark.asyncio
    async def test_get_market_hours_weekend(self, trading_service_test_data):
        """Test get_market_hours during weekend."""
        mock_hours = {
            "is_open": False,
            "next_open": "2024-03-18T09:30:00Z",  # Monday
            "last_close": "2024-03-15T16:00:00Z",  # Friday
            "timezone": "US/Eastern",
            "day_type": "weekend",
        }

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_market_hours",
            return_value=mock_hours,
        ):
            result = await trading_service_test_data.get_market_hours()

            assert result["is_open"] is False
            assert result["day_type"] == "weekend"

    @pytest.mark.asyncio
    async def test_get_market_hours_holiday(self, trading_service_test_data):
        """Test get_market_hours during market holiday."""
        mock_hours = {
            "is_open": False,
            "next_open": "2024-03-16T09:30:00Z",
            "last_close": "2024-03-14T16:00:00Z",
            "timezone": "US/Eastern",
            "day_type": "holiday",
            "holiday_name": "Market Holiday",
        }

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_market_hours",
            return_value=mock_hours,
        ):
            result = await trading_service_test_data.get_market_hours()

            assert result["is_open"] is False
            assert result["day_type"] == "holiday"
            assert "holiday_name" in result

    @pytest.mark.asyncio
    async def test_find_tradable_options_response_structure_validation(
        self, trading_service_test_data
    ):
        """Test comprehensive validation of find_tradable_options response structure."""
        mock_options = [
            Option(
                symbol="VALIDATION240315C00100000",
                underlying=Stock(symbol="VALIDATION"),
                option_type="CALL",
                strike=100.0,
                expiration_date=date(2024, 3, 15),
            )
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="VALIDATION", expiration_date=datetime(2024, 3, 15)
            )

            # Verify top-level structure
            required_fields = [
                "underlying",
                "expiration_date",
                "options",
                "filters_applied",
            ]
            for field in required_fields:
                assert field in result

            # Verify option structure
            option = result["options"][0]
            required_option_fields = [
                "symbol",
                "option_type",
                "strike",
                "expiration_date",
                "underlying_symbol",
            ]
            for field in required_option_fields:
                assert field in option

            # Verify filters_applied structure
            assert isinstance(result["filters_applied"], dict)

    @pytest.mark.asyncio
    async def test_find_tradable_options_edge_case_zero_strike(
        self, trading_service_test_data
    ):
        """Test options discovery with zero strike price (edge case)."""
        mock_options = [
            Option(
                symbol="EDGE240315C00000000",
                underlying=Stock(symbol="EDGE"),
                option_type="CALL",
                strike=0.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="EDGE240315C00001000",
                underlying=Stock(symbol="EDGE"),
                option_type="CALL",
                strike=1.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="EDGE",
                expiration_date=datetime(2024, 3, 15),
                min_strike=0.0,
                max_strike=0.5,
            )

            assert len(result["options"]) == 1  # Only the zero strike option
            assert result["options"][0]["strike"] == 0.0

    @pytest.mark.asyncio
    async def test_find_tradable_options_very_high_strikes(
        self, trading_service_test_data
    ):
        """Test options discovery with very high strike prices."""
        mock_options = [
            Option(
                symbol="HIGH240315C00999900",
                underlying=Stock(symbol="HIGH"),
                option_type="CALL",
                strike=9999.0,
                expiration_date=date(2024, 3, 15),
            ),
            Option(
                symbol="HIGH240315C01000000",
                underlying=Stock(symbol="HIGH"),
                option_type="CALL",
                strike=10000.0,
                expiration_date=date(2024, 3, 15),
            ),
        ]

        with patch.object(
            trading_service_test_data.quote_adapter,
            "get_chain",
            return_value=mock_options,
        ):
            result = await trading_service_test_data.find_tradable_options(
                underlying="HIGH",
                expiration_date=datetime(2024, 3, 15),
                min_strike=9500.0,
            )

            assert len(result["options"]) == 2
            for option in result["options"]:
                assert option["strike"] >= 9500.0
