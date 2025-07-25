"""
Tests for advanced market data MCP tools.
"""

from unittest.mock import patch

import pytest

from app.mcp.advanced_market_data_tools import (
    get_afterhours_data,
    get_dividend_calendar,
    get_earnings_calendar,
    get_economic_calendar,
    get_market_movers,
    get_news_feed,
    get_premarket_data,
    get_sector_performance,
)


class TestAdvancedMarketDataTools:
    """Test advanced market data MCP tools."""

    @pytest.mark.asyncio
    async def test_get_earnings_calendar_default(self):
        """Test earnings calendar with default parameters."""
        result = await get_earnings_calendar()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert "earnings_calendar" in data
        assert "date_range" in data
        assert "total_companies" in data
        assert isinstance(data["earnings_calendar"], list)

    @pytest.mark.asyncio
    async def test_get_earnings_calendar_custom_days(self):
        """Test earnings calendar with custom days ahead."""
        result = await get_earnings_calendar(days_ahead=14)

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["total_companies"] >= 0

    @pytest.mark.asyncio
    async def test_get_dividend_calendar_default(self):
        """Test dividend calendar with default parameters."""
        result = await get_dividend_calendar()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert "dividend_calendar" in data
        assert "date_range" in data
        assert "total_dividends" in data
        assert isinstance(data["dividend_calendar"], list)

    @pytest.mark.asyncio
    async def test_get_market_movers_default(self):
        """Test market movers with default parameters."""
        result = await get_market_movers()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert "gainers" in data
        assert "losers" in data
        assert "most_active" in data
        assert data["market_type"] == "stocks"

        # Check data structure
        assert len(data["gainers"]) > 0
        assert len(data["losers"]) > 0
        assert len(data["most_active"]) > 0

    @pytest.mark.asyncio
    async def test_get_market_movers_custom_type(self):
        """Test market movers with custom market type."""
        result = await get_market_movers(market_type="options")

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["market_type"] == "options"

    @pytest.mark.asyncio
    async def test_get_sector_performance(self):
        """Test sector performance data."""
        result = await get_sector_performance()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert "sectors" in data
        assert "best_performing" in data
        assert "worst_performing" in data
        assert isinstance(data["sectors"], list)
        assert len(data["sectors"]) > 0

        # Check sector data structure
        sector = data["sectors"][0]
        assert "sector" in sector
        assert "change_percent" in sector
        assert "market_cap" in sector

    @pytest.mark.asyncio
    async def test_get_premarket_data(self):
        """Test premarket data for a symbol."""
        result = await get_premarket_data("AAPL")

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["symbol"] == "AAPL"
        assert "premarket_price" in data
        assert "premarket_change" in data
        assert "premarket_volume" in data
        assert "session_start" in data
        assert "session_end" in data

    @pytest.mark.asyncio
    async def test_get_afterhours_data(self):
        """Test afterhours data for a symbol."""
        result = await get_afterhours_data("GOOGL")

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["symbol"] == "GOOGL"
        assert "afterhours_price" in data
        assert "afterhours_change" in data
        assert "afterhours_volume" in data
        assert "session_start" in data
        assert "session_end" in data

    @pytest.mark.asyncio
    async def test_get_economic_calendar_default(self):
        """Test economic calendar with default parameters."""
        result = await get_economic_calendar()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert "economic_calendar" in data
        assert "date_range" in data
        assert "total_events" in data
        assert isinstance(data["economic_calendar"], list)

    @pytest.mark.asyncio
    async def test_get_economic_calendar_custom_days(self):
        """Test economic calendar with custom days ahead."""
        result = await get_economic_calendar(days_ahead=14)

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["total_events"] >= 0

    @pytest.mark.asyncio
    async def test_get_news_feed_general(self):
        """Test general news feed."""
        result = await get_news_feed()

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["symbol"] == "MARKET"
        assert "news_items" in data
        assert "total_items" in data
        assert isinstance(data["news_items"], list)
        assert len(data["news_items"]) > 0

        # Check news item structure
        news_item = data["news_items"][0]
        assert "headline" in news_item
        assert "summary" in news_item
        assert "source" in news_item
        assert "timestamp" in news_item

    @pytest.mark.asyncio
    async def test_get_news_feed_symbol_specific(self):
        """Test symbol-specific news feed."""
        result = await get_news_feed(symbol="AAPL", limit=10)

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["symbol"] == "AAPL"
        assert len(data["news_items"]) <= 10

    @pytest.mark.asyncio
    async def test_symbol_case_handling(self):
        """Test that symbol case is handled correctly."""
        result = await get_premarket_data("aapl")

        assert "result" in result
        assert result["result"]["status"] == "success"

        data = result["result"]["data"]
        assert data["symbol"] == "AAPL"  # Should be converted to uppercase


class TestAdvancedMarketDataToolsErrorHandling:
    """Test error handling in advanced market data tools."""

    @pytest.mark.asyncio
    async def test_earnings_calendar_exception_handling(self):
        """Test earnings calendar handles exceptions gracefully."""
        with patch("app.mcp.advanced_market_data_tools.datetime") as mock_datetime:
            mock_datetime.now.side_effect = Exception("Test error")

            result = await get_earnings_calendar()

            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_premarket_data_exception_handling(self):
        """Test premarket data handles exceptions gracefully."""
        with patch("app.mcp.advanced_market_data_tools.datetime") as mock_datetime:
            mock_datetime.now.side_effect = Exception("Test error")

            result = await get_premarket_data("AAPL")

            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_news_feed_exception_handling(self):
        """Test news feed handles exceptions gracefully."""
        with patch("app.mcp.advanced_market_data_tools.datetime") as mock_datetime:
            mock_datetime.now.side_effect = Exception("Test error")

            result = await get_news_feed()

            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]
