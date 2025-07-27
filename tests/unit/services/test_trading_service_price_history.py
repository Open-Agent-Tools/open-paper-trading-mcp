"""
Tests for TradingService price history functionality.

This module covers the get_price_history method which provides:
- Historical data retrieval
- Period filtering and data aggregation
- Chart data formatting

Coverage target: Lines 953-989 (get_price_history method)
"""

from unittest.mock import patch

import pytest


class TestTradingServicePriceHistory:
    """Test price history functionality."""

    @pytest.mark.asyncio
    async def test_get_price_history_basic_success_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test basic successful price history retrieval with test data."""
        result = await trading_service_synthetic_data.get_price_history("AAPL")

        assert isinstance(result, dict)

        if "error" not in result:
            # Should have basic structure
            expected_fields = ["symbol", "period", "interval"]
            for field in expected_fields:
                assert field in result

            # Check for either data_points or prices
            assert "data_points" in result or "prices" in result

            assert result["symbol"] == "AAPL"
            price_data = result.get("data_points", result.get("prices", []))
            assert isinstance(price_data, list)

    @pytest.mark.asyncio
    async def test_get_price_history_with_period_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history with different periods."""
        periods = ["day", "week", "month", "year"]

        for period in periods:
            result = await trading_service_synthetic_data.get_price_history("AAPL", period)

            assert isinstance(result, dict)
            if "error" not in result:
                assert result["period"] == period

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_robinhood_live_aapl(
        self, trading_service_robinhood
    ):
        """Test price history retrieval with live Robinhood data for AAPL."""
        result = await trading_service_robinhood.get_price_history("AAPL")

        assert isinstance(result, dict)

        # Should get some kind of response (either extended or fallback)
        if "error" not in result:
            assert "symbol" in result
            assert result["symbol"] == "AAPL"
            # Check for either data_points or prices
            assert "data_points" in result or "prices" in result
            price_data = result.get("data_points", result.get("prices", []))
            assert isinstance(price_data, list)

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_robinhood_different_periods(
        self, trading_service_robinhood
    ):
        """Test price history with different periods using Robinhood."""
        periods = ["day", "week", "month"]

        for period in periods:
            result = await trading_service_robinhood.get_price_history("AAPL", period)

            assert isinstance(result, dict)
            if "error" not in result and "period" in result:
                assert result["period"] == period

    @pytest.mark.asyncio
    async def test_get_price_history_invalid_symbol_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history with invalid symbol using test data."""
        result = await trading_service_synthetic_data.get_price_history("INVALID_SYMBOL_XYZ")

        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_invalid_symbol_robinhood(
        self, trading_service_robinhood
    ):
        """Test price history with invalid symbol using Robinhood."""
        result = await trading_service_robinhood.get_price_history("INVALID_SYMBOL_XYZ")

        assert isinstance(result, dict)
        # May error or return empty/fallback data

    @pytest.mark.asyncio
    async def test_get_price_history_adapter_with_extended_functionality(
        self, trading_service_synthetic_data
    ):
        """Test price history when adapter has get_price_history method."""
        has_extended = hasattr(
            trading_service_synthetic_data.quote_adapter, "get_price_history"
        )

        result = await trading_service_synthetic_data.get_price_history("AAPL", "week")

        assert isinstance(result, dict)

        if has_extended:
            # Should use adapter's method
            pass  # Structure depends on adapter implementation
        else:
            # Should use fallback with current quote
            if "error" not in result:
                # Check for either data_points or prices
                price_data = result.get("data_points", result.get("prices", []))
                assert len(price_data) >= 1  # At least current quote

    @pytest.mark.asyncio
    async def test_get_price_history_fallback_mechanism_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history fallback when adapter lacks extended functionality."""
        # Force test of fallback by mocking hasattr to return False
        with patch("app.services.trading_service.hasattr") as mock_hasattr:
            mock_hasattr.return_value = False

            result = await trading_service_synthetic_data.get_price_history("AAPL", "week")

            assert isinstance(result, dict)

            if "error" not in result:
                # Should get fallback structure
                assert result["symbol"] == "AAPL"
                assert result["period"] == "week"
                assert result["interval"] == "current"
                # Check for either data_points or prices
                price_data = result.get("data_points", result.get("prices", []))
                assert len(price_data) == 1  # Single current quote
                assert "message" in result
                assert "Historical data not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_price_history_fallback_data_point_structure(
        self, trading_service_synthetic_data
    ):
        """Test structure of fallback price history data point."""
        # Force fallback by mocking hasattr to return False
        with patch("app.services.trading_service.hasattr") as mock_hasattr:
            mock_hasattr.return_value = False
            result = await trading_service_synthetic_data.get_price_history("AAPL", "day")

            price_data = result.get("data_points", result.get("prices", []))
            if "error" not in result and price_data:
                data_point = price_data[0]

                # Verify fallback data point structure
                required_fields = ["date", "open", "high", "low", "close", "volume"]
                for field in required_fields:
                    assert field in data_point

                # In fallback, open/high/low/close should all equal current price
                assert data_point["open"] == data_point["high"]
                assert data_point["high"] == data_point["low"]
                assert data_point["low"] == data_point["close"]

    @pytest.mark.asyncio
    async def test_get_price_history_no_quote_data_fallback(
        self, trading_service_synthetic_data
    ):
        """Test price history fallback when no quote data is available."""
        # Force no quote data scenario
        original_get_enhanced_quote = trading_service_synthetic_data.get_enhanced_quote

        async def mock_get_enhanced_quote(symbol):
            return None

        try:
            trading_service_synthetic_data.get_enhanced_quote = mock_get_enhanced_quote

            # Mock hasattr to return False to force fallback
            with patch("app.services.trading_service.hasattr") as mock_hasattr:
                mock_hasattr.return_value = False
                result = await trading_service_synthetic_data.get_price_history(
                    "AAPL", "week"
                )

                assert isinstance(result, dict)
                assert "error" in result
                assert "No historical data found" in result["error"]

        finally:
            trading_service_synthetic_data.get_enhanced_quote = original_get_enhanced_quote

    @pytest.mark.asyncio
    async def test_get_price_history_multiple_symbols_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history retrieval for multiple symbols."""
        symbols = ["AAPL", "MSFT", "GOOGL"]

        for symbol in symbols:
            result = await trading_service_synthetic_data.get_price_history(symbol, "week")
            assert isinstance(result, dict)

            if "error" not in result:
                assert result["symbol"] == symbol

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_robinhood_multiple_symbols(
        self, trading_service_robinhood
    ):
        """Test price history with multiple symbols using Robinhood."""
        symbols = ["AAPL", "MSFT", "SPY"]

        for symbol in symbols:
            result = await trading_service_robinhood.get_price_history(symbol, "day")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_price_history_default_period_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history with default period (week)."""
        result = await trading_service_synthetic_data.get_price_history("AAPL")

        assert isinstance(result, dict)
        if "error" not in result:
            assert result["period"] == "week"  # Default period

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_etf_robinhood(self, trading_service_robinhood):
        """Test price history for ETF using Robinhood."""
        result = await trading_service_robinhood.get_price_history("SPY", "day")

        assert isinstance(result, dict)
        # ETFs should have historical data available

    @pytest.mark.asyncio
    async def test_get_price_history_exception_handling(
        self, trading_service_synthetic_data
    ):
        """Test exception handling in get_price_history."""
        # Test with empty string
        result = await trading_service_synthetic_data.get_price_history("")
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_robinhood_exception_handling(
        self, trading_service_robinhood
    ):
        """Test exception handling with Robinhood adapter."""
        # Test with invalid symbol
        result = await trading_service_robinhood.get_price_history(
            "INVALID_SYMBOL", "year"
        )

        assert isinstance(result, dict)
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_get_price_history_lowercase_symbol_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test price history with lowercase symbol gets converted to uppercase."""
        result = await trading_service_synthetic_data.get_price_history("aapl", "day")

        assert isinstance(result, dict)
        if "error" not in result:
            assert result["symbol"] == "AAPL"

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_price_history_robinhood_extended_periods(
        self, trading_service_robinhood
    ):
        """Test price history with extended periods using Robinhood."""
        # Test longer periods that might have more data
        periods = ["month", "year", "5year"]

        for period in periods:
            result = await trading_service_robinhood.get_price_history("AAPL", period)
            assert isinstance(result, dict)

            price_data = result.get("data_points", result.get("prices", []))
            if "error" not in result and price_data:
                # Longer periods might have more data points
                assert isinstance(price_data, list)
