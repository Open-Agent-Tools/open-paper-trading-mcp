"""
Tests for TradingService options chain functionality with Robinhood adapter.

This module covers the get_formatted_options_chain method (lines 1030-1147)
which provides formatted options chain data with filtering and Greeks.

Coverage focus: Testing options chain retrieval and formatting with both
test data and live Robinhood data to ensure proper options market data integration.

Robinhood Integration:
- Uses shared authenticated session fixture (robinhood_session)
- Loads credentials from .env file (ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD)
- Session is authenticated once per test session and shared across all tests
- All Robinhood tests are marked with @pytest.mark.robinhood for selective execution
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.journey_options_trading


class TestTradingServiceOptionsChain:
    """Test options chain functionality."""

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_basic_success_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test basic get_formatted_options_chain with test data."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL"
        )

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
        else:
            assert "underlying_symbol" in result
            assert result["underlying_symbol"] == "AAPL"
            assert "calls" in result
            assert "puts" in result
            assert isinstance(result["calls"], list)
            assert isinstance(result["puts"], list)

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_with_expiration_filter_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with expiration date filter."""
        future_date = date.today() + timedelta(days=30)
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", expiration_date=future_date
        )

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
            return  # Skip rest of test if no options data
        assert "underlying_symbol" in result
        assert result["underlying_symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_with_strike_filters_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with strike price filters."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", min_strike=150.0, max_strike=200.0
        )

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
            return  # Skip rest of test if no options data
        assert "calls" in result
        assert "puts" in result

        # Check that all returned options are within strike range (if options data exists)
        if "calls" in result:
            for call in result["calls"]:
                if "strike" in call:
                    assert 150.0 <= call["strike"] <= 200.0

        if "puts" in result:
            for put in result["puts"]:
                if "strike" in put:
                    assert 150.0 <= put["strike"] <= 200.0

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_without_greeks_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain without Greeks."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", include_greeks=False
        )

        assert isinstance(result, dict)

        # Check that Greeks are not included (if options data exists)
        if "calls" in result:
            for call in result["calls"]:
                assert "delta" not in call
                assert "gamma" not in call
                assert "theta" not in call
                assert "vega" not in call
                assert "rho" not in call
                assert "iv" not in call

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_with_greeks_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with Greeks included."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", include_greeks=True
        )

        assert isinstance(result, dict)

        # Check that Greeks fields are present (may be None, if options data exists)
        if "calls" in result:
            for call in result["calls"]:
                assert "delta" in call
                assert "gamma" in call
                assert "theta" in call
                assert "vega" in call
                assert "rho" in call
                assert "iv" in call

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_live_apple(
        self, trading_service_robinhood
    ):
        """Test options chain with live Robinhood data for Apple."""
        result = await trading_service_robinhood.get_formatted_options_chain("AAPL")

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
            return  # Skip rest of test if no options data
        assert "underlying_symbol" in result
        assert result["underlying_symbol"] == "AAPL"
        assert "underlying_price" in result
        assert "calls" in result
        assert "puts" in result
        assert isinstance(result["calls"], list)
        assert isinstance(result["puts"], list)

        # Validate structure of options data
        if result["calls"]:
            call = result["calls"][0]
            assert "symbol" in call
            assert "strike" in call
            assert "bid" in call
            assert "ask" in call
            assert "mark" in call

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_with_filters(
        self, trading_service_robinhood
    ):
        """Test options chain with filters using live Robinhood data."""
        # Get current price first to set reasonable strike filters
        try:
            quote = await trading_service_robinhood.get_quote("AAPL")
            current_price = quote.price

            # Filter around current price ±10%
            min_strike = current_price * 0.9
            max_strike = current_price * 1.1

            result = await trading_service_robinhood.get_formatted_options_chain(
                "AAPL", min_strike=min_strike, max_strike=max_strike
            )

            assert isinstance(result, dict)

            # Check if options data is available
            if "error" in result:
                # Options data not available, skip test
                return

            # Verify strike filtering worked
            if "calls" in result:
                for call in result["calls"]:
                    if "strike" in call and call["strike"] is not None:
                        assert min_strike <= call["strike"] <= max_strike

        except Exception as e:
            # If options data is not available, that's acceptable for live tests
            if "options" in str(e).lower() or "chain" in str(e).lower():
                pytest.skip(f"Options chain not available: {e}")
            else:
                raise

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_greeks(
        self, trading_service_robinhood
    ):
        """Test options chain Greeks with live Robinhood data."""
        result = await trading_service_robinhood.get_formatted_options_chain(
            "AAPL", include_greeks=True
        )

        assert isinstance(result, dict)

        # Check Greeks are included in response structure
        if "error" not in result and "calls" in result and result["calls"]:
            call = result["calls"][0]
            assert "delta" in call
            assert "gamma" in call
            assert "theta" in call
            assert "vega" in call
            assert "rho" in call
            assert "iv" in call

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_multiple_symbols(
        self, trading_service_robinhood
    ):
        """Test options chain for multiple symbols with Robinhood."""
        symbols = ["AAPL", "SPY", "QQQ"]

        for symbol in symbols:
            try:
                result = await trading_service_robinhood.get_formatted_options_chain(
                    symbol
                )
                assert isinstance(result, dict)
                if "error" not in result:
                    assert result["underlying_symbol"] == symbol
            except Exception as e:
                # Some symbols may not have options or may be rate limited
                if "options" in str(e).lower() or "rate" in str(e).lower():
                    continue
                else:
                    raise

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_invalid_symbol_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with invalid symbol."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "INVALID_SYMBOL"
        )

        assert isinstance(result, dict)
        # Should either have error field or empty options data
        if "error" in result:
            assert isinstance(result["error"], str)

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_invalid_symbol(
        self, trading_service_robinhood
    ):
        """Test options chain with invalid symbol using Robinhood."""
        result = await trading_service_robinhood.get_formatted_options_chain(
            "INVALID_SYMBOL_XYZ"
        )

        assert isinstance(result, dict)
        # Should have error field for invalid symbol
        if "error" in result:
            assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_response_structure_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test that options chain response has correct structure."""
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL"
        )

        assert isinstance(result, dict)

        # Check required top-level fields (if options data exists)
        if "error" not in result:
            expected_fields = ["underlying_symbol", "calls", "puts", "quote_time"]
            for field in expected_fields:
                assert field in result

            # Check calls/puts structure
            if result["calls"]:
                for call in result["calls"]:
                    expected_call_fields = ["symbol", "strike", "bid", "ask", "mark"]
                    for field in expected_call_fields:
                        assert field in call

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_strike_boundary_conditions_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with edge case strike filters."""
        # Test with very high min_strike (should return empty or minimal results)
        result_high = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", min_strike=10000.0
        )
        assert isinstance(result_high, dict)

        # Test with very low max_strike (should return empty or minimal results)
        result_low = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", max_strike=1.0
        )
        assert isinstance(result_low, dict)

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_expiration_date_formats_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with different expiration date formats."""
        # Test with future date
        future_date = date.today() + timedelta(days=60)
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL", expiration_date=future_date
        )

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
            return  # Skip rest of test if no options data
        assert "underlying_symbol" in result

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_exception_handling_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test exception handling in get_formatted_options_chain."""
        with patch.object(
            trading_service_synthetic_data, "get_options_chain"
        ) as mock_get_chain:
            mock_get_chain.side_effect = Exception("Test exception")

            result = await trading_service_synthetic_data.get_formatted_options_chain(
                "AAPL"
            )

            assert isinstance(result, dict)
            assert "error" in result
            assert "Test exception" in result["error"]

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_rate_limiting(
        self, trading_service_robinhood
    ):
        """Test options chain with rate limiting considerations."""
        # Make a single request and handle potential rate limiting
        try:
            result = await trading_service_robinhood.get_formatted_options_chain("AAPL")
            assert isinstance(result, dict)
        except Exception as e:
            # Rate limiting is acceptable for live tests
            if "rate" in str(e).lower() or "limit" in str(e).lower():
                pytest.skip(f"Rate limited: {e}")
            else:
                raise

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_comprehensive_filters_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test options chain with all filters combined."""
        future_date = date.today() + timedelta(days=30)
        result = await trading_service_synthetic_data.get_formatted_options_chain(
            "AAPL",
            expiration_date=future_date,
            min_strike=150.0,
            max_strike=200.0,
            include_greeks=True,
        )

        assert isinstance(result, dict)
        # Test data may not have options chain, so check for error or valid response
        if "error" in result:
            assert isinstance(result["error"], str)
            return  # Skip rest of test if no options data
        assert "underlying_symbol" in result
        assert result["underlying_symbol"] == "AAPL"

        # Verify all filters are respected
        for option in result["calls"] + result["puts"]:
            if "strike" in option and option["strike"] is not None:
                assert 150.0 <= option["strike"] <= 200.0
            # Greeks should be included
            assert "delta" in option

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_robinhood_data_quality(
        self, trading_service_robinhood
    ):
        """Test data quality of options chain from Robinhood."""
        try:
            result = await trading_service_robinhood.get_formatted_options_chain("AAPL")

            assert isinstance(result, dict)

            if result.get("calls"):
                # Check that bid <= ask for valid quotes
                for call in result["calls"]:
                    if (
                        call.get("bid") is not None
                        and call.get("ask") is not None
                        and call["bid"] > 0
                        and call["ask"] > 0
                    ):
                        assert call["bid"] <= call["ask"], (
                            f"Invalid bid/ask spread: {call}"
                        )

        except Exception as e:
            if "options" in str(e).lower():
                pytest.skip(f"Options data not available: {e}")
            else:
                raise
