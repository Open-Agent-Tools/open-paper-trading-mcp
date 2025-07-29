"""
Test Advanced Option Market Data in TradingService.

Tests for get_option_market_data() method covering lines 805-850.
Target: 8 comprehensive tests for advanced option market data retrieval.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_options_trading


@pytest.mark.asyncio
class TestTradingServiceOptionMarketData:
    """Test advanced option market data functionality."""

    async def test_get_option_market_data_success(self, async_db_session):
        """Test successful option market data retrieval."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option asset
        option_asset = Option(
            symbol="AAPL240315C00150000",
            underlying=Stock(symbol="AAPL"),
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        # Create option quote with comprehensive market data
        quote = OptionQuote(
            asset=option_asset,
            price=6.25,
            bid=6.20,
            ask=6.30,
            volume=1250,
            delta=0.65,
            gamma=0.04,
            theta=-0.12,
            vega=0.28,
            rho=0.15,
            iv=0.35,
            underlying_price=155.50,
            quote_date=datetime.now(),
            open_interest=8450,
        )

        # Mock dependencies
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_option_market_data("AAPL240315C00150000")

        # Verify comprehensive market data structure
        assert result["option_id"] == "AAPL240315C00150000"
        assert result["symbol"] == "AAPL240315C00150000"
        assert result["underlying_symbol"] == "AAPL"
        assert result["strike_price"] == 150.0
        assert result["expiration_date"] == "2024-03-15"
        assert result["option_type"] == "call"
        assert result["bid_price"] == 6.20
        assert result["ask_price"] == 6.30
        assert result["mark_price"] == 6.25
        assert result["volume"] == 1250
        assert result["open_interest"] == 8450
        assert result["underlying_price"] == 155.50
        assert result["greeks"]["delta"] == 0.65
        assert result["greeks"]["gamma"] == 0.04
        assert result["greeks"]["theta"] == -0.12
        assert result["greeks"]["vega"] == 0.28
        assert result["greeks"]["rho"] == 0.15
        assert result["implied_volatility"] == 0.35
        assert "last_updated" in result

    async def test_get_option_market_data_invalid_symbol(self, async_db_session):
        """Test error handling for invalid option symbols."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Test with stock symbol (not option)
        result = await trading_service.get_option_market_data("AAPL")

        # Verify error response
        assert "error" in result
        assert "Invalid option symbol" in result["error"]
        assert "AAPL" in result["error"]

    async def test_get_option_market_data_no_quote_available(self, async_db_session):
        """Test error handling when no quote is available."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Mock get_enhanced_quote to return regular Quote (not OptionQuote)
        from app.models.quotes import Quote

        quote = Quote(
            asset=Stock(symbol="AAPL"), price=155.50, quote_date=datetime.now()
        )
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_option_market_data("AAPL240315C00150000")

        # Verify error response
        assert "error" in result
        assert "No market data available" in result["error"]
        assert "AAPL240315C00150000" in result["error"]

    async def test_get_option_market_data_quote_exception(self, async_db_session):
        """Test error handling when quote retrieval fails."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Mock get_enhanced_quote to raise exception
        trading_service.get_enhanced_quote = AsyncMock(
            side_effect=Exception("Market data unavailable")
        )

        # Test
        result = await trading_service.get_option_market_data("AAPL240315C00150000")

        # Verify error response
        assert "error" in result
        assert "Market data unavailable" in result["error"]

    async def test_get_option_market_data_put_option(self, async_db_session):
        """Test option market data for put options."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create put option asset
        option_asset = Option(
            symbol="TSLA240315P00200000",
            underlying=Stock(symbol="TSLA"),
            option_type="put",
            strike=200.0,
            expiration_date=date(2024, 3, 15),
        )

        # Create put option quote with negative delta and rho
        quote = OptionQuote(
            asset=option_asset,
            price=8.75,
            bid=8.70,
            ask=8.80,
            volume=850,
            delta=-0.45,  # Put options have negative delta
            gamma=0.03,
            theta=-0.18,
            vega=0.32,
            rho=-0.08,  # Put options have negative rho
            iv=0.42,
            underlying_price=185.25,
            quote_date=datetime.now(),
            open_interest=3250,
        )

        # Mock dependencies
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_option_market_data("TSLA240315P00200000")

        # Verify put option specific attributes
        assert result["option_id"] == "TSLA240315P00200000"
        assert result["underlying_symbol"] == "TSLA"
        assert result["option_type"] == "put"
        assert result["strike_price"] == 200.0
        assert result["greeks"]["delta"] == -0.45  # Negative for puts
        assert result["greeks"]["rho"] == -0.08  # Negative for puts
        assert result["greeks"]["gamma"] == 0.03  # Positive for all options
        assert result["greeks"]["vega"] == 0.32  # Positive for all options

    async def test_get_option_market_data_partial_attributes(self, async_db_session):
        """Test option market data with missing optional attributes."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option asset
        option_asset = Option(
            symbol="SPY240315C00450000",
            underlying=Stock(symbol="SPY"),
            option_type="call",
            strike=450.0,
            expiration_date=date(2024, 3, 15),
        )

        # Create option quote with minimal data (some attributes missing)
        quote = OptionQuote(
            asset=option_asset,
            price=3.50,
            bid=3.45,
            ask=3.55,
            delta=0.25,
            gamma=0.02,
            underlying_price=445.75,
            quote_date=datetime.now(),
            # Missing: volume, open_interest, theta, vega, rho, iv
        )

        # Mock dependencies
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_option_market_data("SPY240315C00450000")

        # Verify that missing attributes are handled gracefully
        assert result["option_id"] == "SPY240315C00450000"
        assert result["mark_price"] == 3.50
        assert result["volume"] is None  # Missing attribute
        assert result["open_interest"] is None  # Missing attribute
        assert result["greeks"]["delta"] == 0.25
        assert result["greeks"]["gamma"] == 0.02
        assert result["greeks"]["theta"] is None  # Missing attribute
        assert result["greeks"]["vega"] is None  # Missing attribute
        assert result["greeks"]["rho"] is None  # Missing attribute
        assert result["implied_volatility"] is None  # Missing attribute

    async def test_get_option_market_data_date_formatting(self, async_db_session):
        """Test option market data with proper date formatting."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option asset with specific expiration date
        option_asset = Option(
            symbol="MSFT241220C00400000",
            underlying=Stock(symbol="MSFT"),
            option_type="call",
            strike=400.0,
            expiration_date=date(2024, 12, 20),  # December 20, 2024
        )

        # Create option quote
        quote = OptionQuote(
            asset=option_asset,
            price=8.50,
            bid=8.45,
            ask=8.55,
            delta=0.42,
            underlying_price=405.75,
            quote_date=datetime(2024, 1, 15, 16, 0, 0),  # Specific time
        )

        # Mock dependencies
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_option_market_data("MSFT241220C00400000")

        # Verify proper date formatting
        assert result["option_id"] == "MSFT241220C00400000"
        assert result["expiration_date"] == "2024-12-20"  # ISO format
        assert result["last_updated"] == "2024-01-15T16:00:00"  # ISO format with time
        assert result["underlying_symbol"] == "MSFT"
        assert result["option_type"] == "call"

    async def test_get_option_market_data_comprehensive_integration(
        self, async_db_session
    ):
        """Test comprehensive option market data integration with database."""
        from unittest.mock import patch

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create complex option asset
        option_asset = Option(
            symbol="QQQ240315C00380000",
            underlying=Stock(symbol="QQQ"),
            option_type="call",
            strike=380.0,
            expiration_date=date(2024, 3, 15),
        )

        # Create comprehensive option quote
        quote = OptionQuote(
            asset=option_asset,
            price=12.45,
            bid=12.35,
            ask=12.55,
            volume=2750,
            delta=0.72,
            gamma=0.018,
            theta=-0.24,
            vega=0.45,
            rho=0.28,
            iv=0.38,
            underlying_price=385.50,
            quote_date=datetime(2024, 1, 15, 14, 30, 0),
            open_interest=15420,
        )

        # Use real database session via proper mocking
        with patch("app.storage.database.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield async_db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock service methods
            trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

            # Test
            result = await trading_service.get_option_market_data("QQQ240315C00380000")

            # Verify comprehensive data integrity
            assert result["option_id"] == "QQQ240315C00380000"
            assert result["symbol"] == "QQQ240315C00380000"
            assert result["underlying_symbol"] == "QQQ"
            assert result["strike_price"] == 380.0
            assert result["expiration_date"] == "2024-03-15"
            assert result["option_type"] == "call"
            assert result["bid_price"] == 12.35
            assert result["ask_price"] == 12.55
            assert result["mark_price"] == 12.45
            assert result["volume"] == 2750
            assert result["open_interest"] == 15420
            assert result["underlying_price"] == 385.50

            # Verify all Greeks are present and correct
            greeks = result["greeks"]
            assert greeks["delta"] == 0.72
            assert greeks["gamma"] == 0.018
            assert greeks["theta"] == -0.24
            assert greeks["vega"] == 0.45
            assert greeks["rho"] == 0.28

            assert result["implied_volatility"] == 0.38
            assert result["last_updated"] == "2024-01-15T14:30:00"

            # Verify no error fields are present
            assert "error" not in result
