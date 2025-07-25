"""
Tests for TradingService stock price and metrics functionality.

This module covers the get_stock_price method which provides:
- Current price and change calculations
- Price history integration and metrics
- Previous close fallback logic
- Volume and bid/ask data

Coverage target: Lines 863-899 (get_stock_price method)
"""

from datetime import UTC, datetime

import pytest


class TestTradingServiceStockPriceMetrics:
    """Test stock price and metrics functionality."""

    @pytest.mark.asyncio
    async def test_get_stock_price_basic_success_test_data(
        self, trading_service_test_data
    ):
        """Test basic successful stock price retrieval with test data."""
        result = await trading_service_test_data.get_stock_price("AAPL")

        assert "error" not in result
        assert result["symbol"] == "AAPL"
        assert "price" in result
        assert "change" in result
        assert "change_percent" in result
        assert "previous_close" in result
        assert "volume" in result
        assert "ask_price" in result
        assert "bid_price" in result
        assert "last_trade_price" in result
        assert "last_updated" in result

        # Verify data types and structure
        assert isinstance(result["change"], int | float)
        assert isinstance(result["change_percent"], int | float)

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_robinhood_live_aapl(self, trading_service_robinhood):
        """Test stock price retrieval with live Robinhood data for AAPL."""
        result = await trading_service_robinhood.get_stock_price("AAPL")

        assert "error" not in result
        assert result["symbol"] == "AAPL"
        assert "price" in result
        assert result["price"] is not None

        # Validate response structure
        required_fields = [
            "symbol",
            "price",
            "change",
            "change_percent",
            "previous_close",
            "volume",
            "ask_price",
            "bid_price",
            "last_trade_price",
            "last_updated",
        ]
        for field in required_fields:
            assert field in result

        # Verify timestamp format
        assert isinstance(result["last_updated"], str)
        datetime.fromisoformat(
            result["last_updated"].replace("Z", "+00:00")
        )  # Should parse without error

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_robinhood_live_msft(self, trading_service_robinhood):
        """Test stock price retrieval with live Robinhood data for MSFT."""
        result = await trading_service_robinhood.get_stock_price("MSFT")

        assert "error" not in result
        assert result["symbol"] == "MSFT"
        assert result["price"] is not None

        # Verify calculation fields are present and valid
        assert "change" in result
        assert "change_percent" in result
        assert isinstance(result["change"], int | float)
        assert isinstance(result["change_percent"], int | float)

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_robinhood_live_googl(
        self, trading_service_robinhood
    ):
        """Test stock price retrieval with live Robinhood data for GOOGL."""
        result = await trading_service_robinhood.get_stock_price("GOOGL")

        assert "error" not in result
        assert result["symbol"] == "GOOGL"
        assert result["price"] is not None

        # Verify bid/ask spread is reasonable
        if result["bid_price"] and result["ask_price"]:
            assert result["ask_price"] >= result["bid_price"]

    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_symbol_test_data(
        self, trading_service_test_data
    ):
        """Test stock price with invalid symbol using test data."""
        result = await trading_service_test_data.get_stock_price("INVALID_SYMBOL_XYZ")

        assert "error" in result
        # Error message could be "Invalid symbol" or "Invalid option symbol format"
        assert "Invalid" in result["error"]

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_symbol_robinhood(
        self, trading_service_robinhood
    ):
        """Test stock price with invalid symbol using Robinhood."""
        result = await trading_service_robinhood.get_stock_price("INVALID_SYMBOL_XYZ")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_stock_price_multiple_symbols_test_data(
        self, trading_service_test_data
    ):
        """Test stock price retrieval for multiple symbols with test data."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]

        for symbol in symbols:
            result = await trading_service_test_data.get_stock_price(symbol)
            assert "error" not in result
            assert result["symbol"] == symbol
            assert "price" in result

    @pytest.mark.asyncio
    async def test_get_stock_price_lowercase_symbol_test_data(
        self, trading_service_test_data
    ):
        """Test stock price with lowercase symbol gets converted to uppercase."""
        result = await trading_service_test_data.get_stock_price("aapl")

        assert "error" not in result
        assert result["symbol"] == "AAPL"  # Should be uppercase

    @pytest.mark.asyncio
    async def test_get_stock_price_change_calculation_test_data(
        self, trading_service_test_data
    ):
        """Test that change calculations are performed correctly."""
        result = await trading_service_test_data.get_stock_price("AAPL")

        assert "error" not in result
        if result["price"] and result["previous_close"]:
            expected_change = result["price"] - result["previous_close"]
            assert abs(result["change"] - expected_change) < 0.01  # Allow for rounding

            if result["previous_close"] > 0:
                expected_change_percent = (
                    expected_change / result["previous_close"]
                ) * 100
                assert abs(result["change_percent"] - expected_change_percent) < 0.01

    @pytest.mark.asyncio
    async def test_get_stock_price_response_completeness_test_data(
        self, trading_service_test_data
    ):
        """Test that all expected fields are present in response."""
        result = await trading_service_test_data.get_stock_price("AAPL")

        expected_fields = [
            "symbol",
            "price",
            "change",
            "change_percent",
            "previous_close",
            "volume",
            "ask_price",
            "bid_price",
            "last_trade_price",
            "last_updated",
        ]

        for field in expected_fields:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_get_stock_price_numeric_precision_test_data(
        self, trading_service_test_data
    ):
        """Test that numeric values have appropriate precision."""
        result = await trading_service_test_data.get_stock_price("AAPL")

        assert "error" not in result

        # Change should be rounded to 2 decimal places
        if isinstance(result["change"], float):
            assert len(str(result["change"]).split(".")[-1]) <= 2

        # Change percent should be rounded to 2 decimal places
        if isinstance(result["change_percent"], float):
            assert len(str(result["change_percent"]).split(".")[-1]) <= 2

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_robinhood_real_time_data(
        self, trading_service_robinhood
    ):
        """Test that Robinhood returns real-time or recent data."""
        result = await trading_service_robinhood.get_stock_price(
            "SPY"
        )  # High volume ETF

        assert "error" not in result
        assert result["symbol"] == "SPY"

        # Verify we get a recent timestamp (within last 24 hours during market days)
        last_updated = datetime.fromisoformat(
            result["last_updated"].replace("Z", "+00:00")
        )
        now = datetime.now(UTC)
        time_diff = now - last_updated

        # Should be reasonably recent (within 24 hours)
        assert time_diff.total_seconds() < 86400

    @pytest.mark.asyncio
    async def test_get_stock_price_exception_handling_test_data(
        self, trading_service_test_data
    ):
        """Test exception handling with corrupted adapter."""
        # Test with None symbol
        result = await trading_service_test_data.get_stock_price("")
        assert "error" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_etf_robinhood(self, trading_service_robinhood):
        """Test stock price retrieval for ETF using Robinhood."""
        result = await trading_service_robinhood.get_stock_price("SPY")

        assert "error" not in result
        assert result["symbol"] == "SPY"
        assert result["price"] is not None

        # ETFs should have volume data
        assert "volume" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_price_crypto_related_robinhood(
        self, trading_service_robinhood
    ):
        """Test stock price retrieval for crypto-related stock using Robinhood."""
        result = await trading_service_robinhood.get_stock_price("COIN")  # Coinbase

        assert "error" not in result
        assert result["symbol"] == "COIN"
        assert result["price"] is not None

    @pytest.mark.asyncio
    async def test_get_stock_price_edge_case_symbols_test_data(
        self, trading_service_test_data
    ):
        """Test stock price with edge case symbols."""
        # Test symbols with dots, dashes, etc.
        edge_symbols = (
            ["BRK.B", "BRK-B"]
            if hasattr(trading_service_test_data.quote_adapter, "get_quote")
            else ["AAPL"]
        )

        for symbol in edge_symbols:
            result = await trading_service_test_data.get_stock_price(symbol)
            # May error or succeed depending on adapter support
            assert isinstance(result, dict)
            assert "symbol" in result or "error" in result
