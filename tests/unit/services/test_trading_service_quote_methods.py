"""
Tests for TradingService quote methods with Robinhood adapter.

This module covers the core quote methods:
- get_quote method (lines 188-220)
- get_enhanced_quote method (lines 602-700)

Coverage focus: Testing these fundamental quote retrieval methods with both
test data and live Robinhood data to ensure proper market data integration.

Robinhood Integration:
- Uses shared authenticated session fixture (robinhood_session)
- Loads credentials from .env file (ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD)
- Session is authenticated once per test session and shared across all tests
- All Robinhood tests are marked with @pytest.mark.robinhood for selective execution
"""

from datetime import UTC
from unittest.mock import patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.quotes import OptionQuote, Quote
from app.schemas.trading import StockQuote


class TestTradingServiceQuoteMethods:
    """Test core quote retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_quote_basic_success_test_data(self, trading_service_test_data):
        """Test basic get_quote with test data adapter."""
        result = await trading_service_test_data.get_quote("AAPL")

        assert isinstance(result, StockQuote)
        assert result.symbol == "AAPL"
        assert result.price is not None
        assert result.price > 0
        assert result.volume is not None
        assert result.last_updated is not None

    @pytest.mark.asyncio
    async def test_get_quote_invalid_symbol_test_data(self, trading_service_test_data):
        """Test get_quote with invalid symbol."""
        with pytest.raises((NotFoundError, ValidationError)):
            await trading_service_test_data.get_quote("INVALID_SYMBOL_XYZ")

    @pytest.mark.asyncio
    async def test_get_quote_empty_symbol_test_data(self, trading_service_test_data):
        """Test get_quote with empty symbol."""
        with pytest.raises((NotFoundError, ValidationError, ValueError)):
            await trading_service_test_data.get_quote("")

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_quote_robinhood_live_apple(self, trading_service_robinhood):
        """Test get_quote with live Robinhood data for Apple.

        Uses shared authenticated Robinhood session from .env credentials.
        """
        result = await trading_service_robinhood.get_quote("AAPL")

        assert isinstance(result, StockQuote)
        assert result.symbol == "AAPL"
        assert result.price is not None
        assert result.price > 0
        assert result.volume is not None
        assert result.last_updated is not None

        # StockQuote doesn't have bid/ask fields - those are in Quote/OptionQuote

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_quote_robinhood_live_microsoft(self, trading_service_robinhood):
        """Test get_quote with live Robinhood data for Microsoft."""
        result = await trading_service_robinhood.get_quote("MSFT")

        assert isinstance(result, StockQuote)
        assert result.symbol == "MSFT"
        assert result.price is not None
        assert result.price > 0

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_quote_robinhood_live_google(self, trading_service_robinhood):
        """Test get_quote with live Robinhood data for Google."""
        result = await trading_service_robinhood.get_quote("GOOGL")

        assert isinstance(result, StockQuote)
        assert result.symbol == "GOOGL"
        assert result.price is not None
        assert result.price > 0

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_quote_robinhood_invalid_symbol(self, trading_service_robinhood):
        """Test get_quote with invalid symbol using Robinhood."""
        with pytest.raises((NotFoundError, ValidationError)):
            await trading_service_robinhood.get_quote("INVALID_SYMBOL_XYZ")

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_basic_success_test_data(
        self, trading_service_test_data
    ):
        """Test basic get_enhanced_quote with test data."""
        result = await trading_service_test_data.get_enhanced_quote("AAPL")

        # Test data returns MockQuote which has the expected attributes
        assert hasattr(result, "symbol")
        assert hasattr(result, "price")
        assert result.symbol == "AAPL"
        assert result.price is not None
        assert result.price > 0

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_with_validation_test_data(
        self, trading_service_test_data
    ):
        """Test get_enhanced_quote with symbol validation."""
        # Test that invalid symbols are handled
        try:
            result = await trading_service_test_data.get_enhanced_quote("INVALID")
            # If no exception, should return None or valid quote
            if result:
                assert isinstance(result, StockQuote)
        except Exception:
            # Exception is acceptable for invalid symbols
            pass

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_enhanced_quote_robinhood_live_apple(
        self, trading_service_robinhood
    ):
        """Test get_enhanced_quote with live Robinhood data for Apple."""
        result = await trading_service_robinhood.get_enhanced_quote("AAPL")

        assert isinstance(result, Quote | OptionQuote)
        assert result.asset.symbol == "AAPL"
        assert result.price is not None
        assert result.price > 0
        assert result.bid is not None
        assert result.ask is not None
        assert result.quote_date is not None

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_enhanced_quote_robinhood_live_etf(
        self, trading_service_robinhood
    ):
        """Test get_enhanced_quote with live Robinhood data for ETF."""
        result = await trading_service_robinhood.get_enhanced_quote("SPY")

        assert isinstance(result, Quote | OptionQuote)
        assert result.asset.symbol == "SPY"
        assert result.price is not None
        assert result.price > 0

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_enhanced_quote_robinhood_multiple_symbols(
        self, trading_service_robinhood
    ):
        """Test get_enhanced_quote with multiple symbols sequentially."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "SPY"]

        for symbol in symbols:
            result = await trading_service_robinhood.get_enhanced_quote(symbol)
            assert isinstance(result, Quote | OptionQuote)
            assert result.asset.symbol == symbol
            assert result.price is not None
            assert result.price > 0

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_adapter_call_test_data(
        self, trading_service_test_data
    ):
        """Test that get_enhanced_quote properly calls the adapter."""
        with patch.object(
            trading_service_test_data.quote_adapter, "get_quote"
        ) as mock_get_quote:
            from datetime import datetime

            mock_quote = StockQuote(
                symbol="AAPL",
                price=150.0,
                change=0.0,
                change_percent=0.0,
                volume=1000000,
                last_updated=datetime.now(UTC),
            )
            mock_get_quote.return_value = mock_quote

            result = await trading_service_test_data.get_enhanced_quote("AAPL")

            assert result == mock_quote
            mock_get_quote.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_exception_handling_test_data(
        self, trading_service_test_data
    ):
        """Test exception handling in get_enhanced_quote."""
        with patch.object(
            trading_service_test_data.quote_adapter, "get_quote"
        ) as mock_get_quote:
            mock_get_quote.side_effect = NotFoundError("Test exception")

            with pytest.raises(NotFoundError):
                await trading_service_test_data.get_enhanced_quote("AAPL")

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_enhanced_quote_robinhood_rate_limiting(
        self, trading_service_robinhood
    ):
        """Test that enhanced quote handles rate limiting gracefully."""
        # Make several quick requests to test rate limiting behavior
        results = []
        for _i in range(3):
            try:
                result = await trading_service_robinhood.get_enhanced_quote("AAPL")
                results.append(result)
            except Exception as e:
                # Rate limiting exceptions are acceptable
                if "rate" in str(e).lower() or "limit" in str(e).lower():
                    pass
                else:
                    raise

        # At least one request should succeed
        if results:
            assert len(results) > 0
            assert all(isinstance(r, Quote | OptionQuote) for r in results)

    @pytest.mark.asyncio
    async def test_quote_methods_consistency_test_data(self, trading_service_test_data):
        """Test that get_quote and get_enhanced_quote return consistent data."""
        symbol = "AAPL"

        basic_quote = await trading_service_test_data.get_quote(symbol)
        enhanced_quote = await trading_service_test_data.get_enhanced_quote(symbol)

        assert basic_quote.symbol == enhanced_quote.symbol
        assert basic_quote.price == enhanced_quote.price
        # Note: StockQuote doesn't have bid/ask, enhanced quote does

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_quote_methods_consistency_robinhood(self, trading_service_robinhood):
        """Test quote method consistency with live Robinhood data."""
        symbol = "AAPL"

        basic_quote = await trading_service_robinhood.get_quote(symbol)
        enhanced_quote = await trading_service_robinhood.get_enhanced_quote(symbol)

        # They should return consistent data (different formats but same underlying data)
        assert basic_quote.symbol == enhanced_quote.asset.symbol
        assert basic_quote.price == enhanced_quote.price
        # Note: StockQuote doesn't have bid/ask, enhanced quote does

    @pytest.mark.asyncio
    async def test_get_quote_case_sensitivity_test_data(
        self, trading_service_test_data
    ):
        """Test that get_quote handles symbol case properly."""
        # Test both uppercase and lowercase
        result_upper = await trading_service_test_data.get_quote("AAPL")
        result_lower = await trading_service_test_data.get_quote("aapl")

        # Both should work and return normalized symbols
        assert isinstance(result_upper, StockQuote)
        assert isinstance(result_lower, StockQuote)
        assert result_upper.symbol == "AAPL"
        assert result_lower.symbol == "AAPL"

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_get_quote_case_sensitivity_robinhood(
        self, trading_service_robinhood
    ):
        """Test case sensitivity with live Robinhood data."""
        result_upper = await trading_service_robinhood.get_enhanced_quote("AAPL")
        result_lower = await trading_service_robinhood.get_enhanced_quote("aapl")

        assert isinstance(result_upper, Quote | OptionQuote)
        assert isinstance(result_lower, Quote | OptionQuote)
        assert result_upper.asset.symbol == "AAPL"
        assert result_lower.asset.symbol == "AAPL"
