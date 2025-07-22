"""
Unit tests for app.mcp.market_data_tools module.

These tests verify that the MCP market data tools functions correctly interact with the trading service
and properly handle responses and errors.
"""

import pytest

from app.mcp.market_data_tools import (
    GetPriceHistoryArgs,
    GetStockInfoArgs,
    GetStockNewsArgs,
    GetStockPriceArgs,
    SearchStocksArgs,
    get_price_history,
    get_stock_info,
    get_stock_news,
    get_stock_price,
    get_top_movers,
    search_stocks,
)


class TestMCPMarketDataTools:
    """Tests for MCP market data tools."""

    @pytest.mark.asyncio
    async def test_get_stock_price_success(self, mock_trading_service):
        """Test successful stock price retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_result = {
            "symbol": symbol,
            "price": 150.0,
            "change": 5.0,
            "change_percent": 3.33,
            "volume": 1000,
            "bid": 149.95,
            "ask": 150.05,
            "last_updated": "2024-01-01T12:00:00",
        }
        mock_trading_service.get_stock_price.return_value = mock_result

        # Act
        result = await get_stock_price(GetStockPriceArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_price.assert_called_once_with(
            symbol.strip().upper()
        )
        assert result == mock_result
        assert result["symbol"] == symbol
        assert result["price"] == 150.0

    @pytest.mark.asyncio
    async def test_get_stock_price_error(self, mock_trading_service):
        """Test error handling in stock price retrieval."""
        # Arrange
        symbol = "INVALID"
        mock_trading_service.get_stock_price.side_effect = Exception("Symbol not found")

        # Act
        result = await get_stock_price(GetStockPriceArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_price.assert_called_once_with(
            symbol.strip().upper()
        )
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_stock_info_success(self, mock_trading_service):
        """Test successful stock info retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_result = {
            "symbol": symbol,
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": "2.5T",
            "pe_ratio": 30.5,
            "dividend_yield": 0.5,
            "52_week_high": 180.0,
            "52_week_low": 120.0,
        }
        mock_trading_service.get_stock_info.return_value = mock_result

        # Act
        result = await get_stock_info(GetStockInfoArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_info.assert_called_once_with(
            symbol.strip().upper()
        )
        assert result == mock_result
        assert result["symbol"] == symbol
        assert result["company_name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_get_stock_info_error(self, mock_trading_service):
        """Test error handling in stock info retrieval."""
        # Arrange
        symbol = "INVALID"
        mock_trading_service.get_stock_info.side_effect = Exception("Symbol not found")

        # Act
        result = await get_stock_info(GetStockInfoArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_info.assert_called_once_with(
            symbol.strip().upper()
        )
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_price_history_success(self, mock_trading_service):
        """Test successful price history retrieval."""
        # Arrange
        symbol = "AAPL"
        period = "week"
        mock_result = {
            "symbol": symbol,
            "period": period,
            "data_points": [
                {
                    "date": "2024-01-01",
                    "open": 150.0,
                    "high": 152.0,
                    "low": 149.0,
                    "close": 151.0,
                    "volume": 1000000,
                },
                {
                    "date": "2024-01-02",
                    "open": 151.0,
                    "high": 153.0,
                    "low": 150.0,
                    "close": 152.0,
                    "volume": 1100000,
                },
                {
                    "date": "2024-01-03",
                    "open": 152.0,
                    "high": 154.0,
                    "low": 151.0,
                    "close": 153.0,
                    "volume": 1200000,
                },
            ],
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
        }
        mock_trading_service.get_price_history.return_value = mock_result

        # Act
        result = await get_price_history(
            GetPriceHistoryArgs(symbol=symbol, period=period)
        )

        # Assert
        mock_trading_service.get_price_history.assert_called_once_with(
            symbol.strip().upper(), period
        )
        assert result == mock_result
        assert result["symbol"] == symbol
        assert result["period"] == period
        assert len(result["data_points"]) == 3

    @pytest.mark.asyncio
    async def test_get_price_history_error(self, mock_trading_service):
        """Test error handling in price history retrieval."""
        # Arrange
        symbol = "INVALID"
        period = "week"
        mock_trading_service.get_price_history.side_effect = Exception(
            "Symbol not found"
        )

        # Act
        result = await get_price_history(
            GetPriceHistoryArgs(symbol=symbol, period=period)
        )

        # Assert
        mock_trading_service.get_price_history.assert_called_once_with(
            symbol.strip().upper(), period
        )
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_stock_news_success(self, mock_trading_service):
        """Test successful stock news retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_result = {
            "symbol": symbol,
            "news": [
                {
                    "title": "Apple Reports Record Earnings",
                    "date": "2024-01-01",
                    "source": "Financial Times",
                    "url": "https://example.com/news1",
                    "summary": "Apple reported record earnings for Q4 2023.",
                },
                {
                    "title": "Apple Announces New iPhone",
                    "date": "2024-01-02",
                    "source": "TechCrunch",
                    "url": "https://example.com/news2",
                    "summary": "Apple announced the new iPhone 16 today.",
                },
            ],
            "count": 2,
        }
        mock_trading_service.get_stock_news.return_value = mock_result

        # Act
        result = await get_stock_news(GetStockNewsArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_news.assert_called_once_with(
            symbol.strip().upper()
        )
        assert result == mock_result
        assert result["symbol"] == symbol
        assert len(result["news"]) == 2

    @pytest.mark.asyncio
    async def test_get_stock_news_error(self, mock_trading_service):
        """Test error handling in stock news retrieval."""
        # Arrange
        symbol = "INVALID"
        mock_trading_service.get_stock_news.side_effect = Exception("Symbol not found")

        # Act
        result = await get_stock_news(GetStockNewsArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_stock_news.assert_called_once_with(
            symbol.strip().upper()
        )
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_top_movers_success(self, mock_trading_service):
        """Test successful top movers retrieval."""
        # Arrange
        mock_result = {
            "movers": [
                {
                    "symbol": "AAPL",
                    "price": 150.0,
                    "change": 5.0,
                    "change_percent": 3.33,
                },
                {
                    "symbol": "GOOGL",
                    "price": 2800.0,
                    "change": 50.0,
                    "change_percent": 1.82,
                },
                {
                    "symbol": "MSFT",
                    "price": 300.0,
                    "change": 10.0,
                    "change_percent": 3.45,
                },
            ],
            "timestamp": "2024-01-01T12:00:00",
            "market_status": "open",
        }
        mock_trading_service.get_top_movers.return_value = mock_result

        # Act
        result = await get_top_movers()

        # Assert
        mock_trading_service.get_top_movers.assert_called_once()
        assert result == mock_result
        assert "movers" in result
        assert len(result["movers"]) == 3

    @pytest.mark.asyncio
    async def test_get_top_movers_error(self, mock_trading_service):
        """Test error handling in top movers retrieval."""
        # Arrange
        mock_trading_service.get_top_movers.side_effect = Exception("Market closed")

        # Act
        result = await get_top_movers()

        # Assert
        mock_trading_service.get_top_movers.assert_called_once()
        assert "error" in result
        assert "Market closed" in result["error"]

    @pytest.mark.asyncio
    async def test_search_stocks_success(self, mock_trading_service):
        """Test successful stock search."""
        # Arrange
        query = "Apple"
        mock_result = {
            "query": query,
            "results": [
                {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock"},
                {
                    "symbol": "AAPL.BA",
                    "name": "Apple Inc. (Buenos Aires)",
                    "type": "stock",
                },
            ],
            "count": 2,
        }
        mock_trading_service.search_stocks.return_value = mock_result

        # Act
        result = await search_stocks(SearchStocksArgs(query=query))

        # Assert
        mock_trading_service.search_stocks.assert_called_once_with(query.strip())
        assert result == mock_result
        assert result["query"] == query
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_search_stocks_error(self, mock_trading_service):
        """Test error handling in stock search."""
        # Arrange
        query = ""  # Empty query
        mock_trading_service.search_stocks.side_effect = Exception("Invalid query")

        # Act
        result = await search_stocks(SearchStocksArgs(query=query))

        # Assert
        mock_trading_service.search_stocks.assert_called_once_with(query.strip())
        assert "error" in result
        assert "Invalid query" in result["error"]
