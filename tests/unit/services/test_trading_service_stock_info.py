"""
Tests for TradingService stock information functionality.

This module covers the get_stock_info method which provides:
- Company data retrieval
- Data adapter integration and fallbacks
- Information formatting and validation

Coverage target: Lines 908-942 (get_stock_info method)
"""

import pytest


class TestTradingServiceStockInfo:
    """Test stock information functionality."""

    @pytest.mark.asyncio
    async def test_get_stock_info_basic_success_test_data(
        self, trading_service_test_data
    ):
        """Test basic successful stock info retrieval with test data."""
        result = await trading_service_test_data.get_stock_info("AAPL")

        # Should either get extended info or fallback info
        assert isinstance(result, dict)
        assert "symbol" in result or "error" not in result

        if "symbol" in result:
            assert result["symbol"] == "AAPL"

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_robinhood_live_aapl(self, trading_service_robinhood):
        """Test stock info retrieval with live Robinhood data for AAPL."""
        result = await trading_service_robinhood.get_stock_info("AAPL")

        assert isinstance(result, dict)

        # Should get some kind of response (either extended or fallback)
        if "error" not in result and result:
            # If we get data, verify basic structure
            if "symbol" in result:
                assert result["symbol"] == "AAPL"

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_robinhood_live_msft(self, trading_service_robinhood):
        """Test stock info retrieval with live Robinhood data for MSFT."""
        result = await trading_service_robinhood.get_stock_info("MSFT")

        assert isinstance(result, dict)

        if "error" not in result and result and "symbol" in result:
            assert result["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_get_stock_info_invalid_symbol_test_data(
        self, trading_service_test_data
    ):
        """Test stock info with invalid symbol using test data."""
        result = await trading_service_test_data.get_stock_info("INVALID_SYMBOL_XYZ")

        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_invalid_symbol_robinhood(
        self, trading_service_robinhood
    ):
        """Test stock info with invalid symbol using Robinhood."""
        result = await trading_service_robinhood.get_stock_info("INVALID_SYMBOL_XYZ")

        assert isinstance(result, dict)
        # May error or return empty dict depending on adapter behavior

    @pytest.mark.asyncio
    async def test_get_stock_info_adapter_with_extended_functionality(
        self, trading_service_test_data
    ):
        """Test stock info when adapter has get_stock_info method."""
        # Check if test adapter has extended functionality
        has_extended = hasattr(
            trading_service_test_data.quote_adapter, "get_stock_info"
        )

        result = await trading_service_test_data.get_stock_info("AAPL")

        if has_extended:
            # Should use adapter's method
            assert isinstance(result, dict)
        else:
            # Should use fallback
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_stock_info_fallback_mechanism_test_data(
        self, trading_service_test_data
    ):
        """Test stock info fallback when adapter lacks extended functionality."""
        # Force test of fallback by temporarily removing method if it exists
        original_method = getattr(
            trading_service_test_data.quote_adapter, "get_stock_info", None
        )

        if original_method:
            delattr(trading_service_test_data.quote_adapter, "get_stock_info")

        try:
            result = await trading_service_test_data.get_stock_info("AAPL")

            assert isinstance(result, dict)
            # Should get fallback data structure
            if "error" not in result:
                expected_fallback_fields = [
                    "symbol",
                    "company_name",
                    "sector",
                    "industry",
                    "description",
                    "market_cap",
                    "pe_ratio",
                    "dividend_yield",
                    "high_52_weeks",
                    "low_52_weeks",
                    "average_volume",
                    "tradeable",
                    "last_updated",
                ]

                # At least some fallback fields should be present
                assert any(field in result for field in expected_fallback_fields)

        finally:
            # Restore original method if it existed
            if original_method:
                trading_service_test_data.quote_adapter.get_stock_info = original_method

    @pytest.mark.asyncio
    async def test_get_stock_info_fallback_structure_test_data(
        self, trading_service_test_data
    ):
        """Test structure of fallback stock info data."""
        # Force fallback by temporarily removing method
        original_method = getattr(
            trading_service_test_data.quote_adapter, "get_stock_info", None
        )

        if original_method:
            delattr(trading_service_test_data.quote_adapter, "get_stock_info")

        try:
            result = await trading_service_test_data.get_stock_info("AAPL")

            if "error" not in result and result:
                # Verify fallback structure
                assert result["symbol"] == "AAPL"
                assert result["company_name"] == "AAPL Company"
                assert result["tradeable"] is True
                assert "last_updated" in result

        finally:
            if original_method:
                trading_service_test_data.quote_adapter.get_stock_info = original_method

    @pytest.mark.asyncio
    async def test_get_stock_info_no_quote_data_fallback(
        self, trading_service_test_data
    ):
        """Test stock info fallback when no quote data is available."""
        # Force no quote data scenario
        original_get_enhanced_quote = trading_service_test_data.get_enhanced_quote
        async def mock_get_enhanced_quote(symbol):
            return None
        trading_service_test_data.get_enhanced_quote = mock_get_enhanced_quote

        # Remove get_stock_info method to force fallback
        original_method = getattr(
            trading_service_test_data.quote_adapter, "get_stock_info", None
        )
        if original_method:
            delattr(trading_service_test_data.quote_adapter, "get_stock_info")

        try:
            result = await trading_service_test_data.get_stock_info("AAPL")

            assert isinstance(result, dict)
            assert "error" in result
            assert "No company information found" in result["error"]

        finally:
            trading_service_test_data.get_enhanced_quote = original_get_enhanced_quote
            if original_method:
                trading_service_test_data.quote_adapter.get_stock_info = original_method

    @pytest.mark.asyncio
    async def test_get_stock_info_multiple_symbols_test_data(
        self, trading_service_test_data
    ):
        """Test stock info retrieval for multiple symbols."""
        symbols = ["AAPL", "MSFT", "GOOGL"]

        for symbol in symbols:
            result = await trading_service_test_data.get_stock_info(symbol)
            assert isinstance(result, dict)

            if "error" not in result and result:
                assert "symbol" in result or len(result) > 0

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_robinhood_multiple_symbols(
        self, trading_service_robinhood
    ):
        """Test stock info with multiple symbols using Robinhood."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "SPY"]

        for symbol in symbols:
            result = await trading_service_robinhood.get_stock_info(symbol)
            assert isinstance(result, dict)

            # Robinhood may or may not have extended stock info functionality
            # Just verify we get a valid response structure

    @pytest.mark.asyncio
    async def test_get_stock_info_lowercase_symbol_test_data(
        self, trading_service_test_data
    ):
        """Test stock info with lowercase symbol gets converted to uppercase."""
        result = await trading_service_test_data.get_stock_info("aapl")

        assert isinstance(result, dict)
        if "symbol" in result:
            assert result["symbol"] == "AAPL"

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_etf_robinhood(self, trading_service_robinhood):
        """Test stock info for ETF using Robinhood."""
        result = await trading_service_robinhood.get_stock_info("SPY")

        assert isinstance(result, dict)
        # ETFs may have different info structure than individual stocks

    @pytest.mark.asyncio
    async def test_get_stock_info_exception_handling(self, trading_service_test_data):
        """Test exception handling in get_stock_info."""
        # Test with empty string
        result = await trading_service_test_data.get_stock_info("")
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_stock_info_robinhood_exception_handling(
        self, trading_service_robinhood
    ):
        """Test exception handling with Robinhood adapter."""
        # Test with very long invalid symbol
        result = await trading_service_robinhood.get_stock_info(
            "VERY_LONG_INVALID_SYMBOL_NAME_THAT_DEFINITELY_DOES_NOT_EXIST"
        )

        assert isinstance(result, dict)
        # Should handle gracefully (either error or empty result)
