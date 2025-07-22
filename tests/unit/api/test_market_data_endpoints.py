"""
Comprehensive tests for market data endpoints.

Tests for:
- GET /price/{symbol} (get_stock_price_endpoint)
- GET /info/{symbol} (get_stock_info_endpoint)
- GET /history/{symbol} (get_price_history_endpoint)
- GET /news/{symbol} (get_stock_news_endpoint)
- GET /movers (get_top_movers_endpoint)
- GET /search (search_stocks_endpoint)

All tests use proper async patterns with comprehensive mocking of TradingService.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.services.trading_service import TradingService


class TestMarketDataEndpoints:
    """Test market data endpoints with comprehensive coverage."""

    # GET /price/{symbol} endpoint tests
    @pytest.mark.asyncio
    async def test_get_stock_price_success(self, client):
        """Test successful stock price retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_price_data = {
            "symbol": "AAPL",
            "price": 155.50,
            "change": 2.50,
            "change_percent": 1.64,
            "volume": 50000000,
            "market_cap": 2500000000000,
            "timestamp": "2023-06-15T15:30:00Z",
        }
        mock_service.get_stock_price.return_value = mock_price_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.50
        assert data["change"] == 2.50
        assert data["change_percent"] == 1.64
        assert data["volume"] == 50000000
        assert data["market_cap"] == 2500000000000
        assert "timestamp" in data

        mock_service.get_stock_price.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_price_not_found(self, client):
        """Test stock price retrieval for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_stock_price.return_value = {"error": "Symbol not found"}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/price/NONEXISTENT")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_stock_price_service_error(self, client):
        """Test stock price retrieval when service raises exception."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_stock_price.side_effect = Exception("API timeout")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_stock_price_special_characters(self, client):
        """Test stock price retrieval with special characters in symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_price_data = {
            "symbol": "BRK.A",
            "price": 400000.00,
            "change": -500.00,
            "change_percent": -0.12,
            "volume": 1000,
            "market_cap": 800000000000,
        }
        mock_service.get_stock_price.return_value = mock_price_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/price/BRK.A")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["symbol"] == "BRK.A"
        assert data["price"] == 400000.00

    # GET /info/{symbol} endpoint tests
    @pytest.mark.asyncio
    async def test_get_stock_info_success(self, client):
        """Test successful stock info retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_info_data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 2500000000000,
            "pe_ratio": 28.5,
            "dividend_yield": 0.0055,
            "beta": 1.2,
            "52_week_high": 182.94,
            "52_week_low": 124.17,
            "description": "Apple Inc. designs, manufactures, and markets smartphones...",
        }
        mock_service.get_stock_info.return_value = mock_info_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/info/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["sector"] == "Technology"
        assert data["industry"] == "Consumer Electronics"
        assert data["pe_ratio"] == 28.5
        assert data["dividend_yield"] == 0.0055
        assert "description" in data

        mock_service.get_stock_info.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_info_not_found(self, client):
        """Test stock info retrieval for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_stock_info.return_value = {"error": "Symbol not found"}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/info/NONEXISTENT")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_stock_info_minimal_data(self, client):
        """Test stock info with minimal available data."""
        mock_service = MagicMock(spec=TradingService)
        mock_info_data = {
            "symbol": "PENNY",
            "name": "Penny Stock Corp",
            "market_cap": 1000000,  # Small market cap
            "pe_ratio": None,  # No P/E ratio
            "dividend_yield": 0.0,  # No dividend
            "beta": None,  # No beta available
        }
        mock_service.get_stock_info.return_value = mock_info_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/info/PENNY")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["symbol"] == "PENNY"
        assert data["pe_ratio"] is None
        assert data["beta"] is None

    # GET /history/{symbol} endpoint tests
    @pytest.mark.asyncio
    async def test_get_price_history_success_default_period(self, client):
        """Test successful price history retrieval with default period."""
        mock_service = MagicMock(spec=TradingService)
        mock_history_data = {
            "symbol": "AAPL",
            "period": "week",
            "data": [
                {
                    "date": "2023-06-12",
                    "open": 150.0,
                    "high": 152.0,
                    "low": 149.5,
                    "close": 151.0,
                    "volume": 45000000,
                },
                {
                    "date": "2023-06-13",
                    "open": 151.0,
                    "high": 153.5,
                    "low": 150.5,
                    "close": 153.0,
                    "volume": 52000000,
                },
                {
                    "date": "2023-06-14",
                    "open": 153.0,
                    "high": 156.0,
                    "low": 152.0,
                    "close": 155.5,
                    "volume": 60000000,
                },
            ],
            "summary": {
                "start_price": 150.0,
                "end_price": 155.5,
                "change": 5.5,
                "change_percent": 3.67,
                "high": 156.0,
                "low": 149.5,
            },
        }
        mock_service.get_price_history.return_value = mock_history_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/history/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["period"] == "week"
        assert len(data["data"]) == 3
        assert data["data"][0]["date"] == "2023-06-12"
        assert data["summary"]["change"] == 5.5

        mock_service.get_price_history.assert_called_once_with("AAPL", "week")

    @pytest.mark.asyncio
    async def test_get_price_history_custom_period(self, client):
        """Test price history retrieval with custom period."""
        mock_service = MagicMock(spec=TradingService)
        mock_history_data = {
            "symbol": "AAPL",
            "period": "month",
            "data": [],  # Mock empty for brevity
        }
        mock_service.get_price_history.return_value = mock_history_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/history/AAPL?period=month")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["period"] == "month"

        mock_service.get_price_history.assert_called_once_with("AAPL", "month")

    @pytest.mark.asyncio
    async def test_get_price_history_invalid_period(self, client):
        """Test price history retrieval with invalid period."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_price_history.return_value = {
            "error": "Invalid period: invalid_period"
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/market-data/history/AAPL?period=invalid_period"
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_price_history_all_periods(self, client):
        """Test price history retrieval for all supported periods."""
        periods = ["day", "week", "month", "3month", "year", "5year"]
        mock_service = MagicMock(spec=TradingService)

        for period in periods:
            mock_service.get_price_history.return_value = {
                "symbol": "AAPL",
                "period": period,
                "data": [],
            }

            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    response = await ac.get(
                        f"/api/v1/market-data/history/AAPL?period={period}"
                    )

            assert response.status_code == status.HTTP_200_OK

    # GET /news/{symbol} endpoint tests
    @pytest.mark.asyncio
    async def test_get_stock_news_success(self, client):
        """Test successful stock news retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_news_data = {
            "symbol": "AAPL",
            "articles": [
                {
                    "title": "Apple Reports Strong Q2 Earnings",
                    "url": "https://example.com/news/1",
                    "published_at": "2023-06-15T14:30:00Z",
                    "source": "MarketWatch",
                    "summary": "Apple Inc. reported better than expected quarterly earnings...",
                },
                {
                    "title": "Apple Stock Hits New High",
                    "url": "https://example.com/news/2",
                    "published_at": "2023-06-15T10:15:00Z",
                    "source": "Reuters",
                    "summary": "Shares of Apple reached a new 52-week high today...",
                },
            ],
            "count": 2,
            "last_updated": "2023-06-15T15:30:00Z",
        }
        mock_service.get_stock_news.return_value = mock_news_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/news/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["count"] == 2
        assert len(data["articles"]) == 2
        assert data["articles"][0]["title"] == "Apple Reports Strong Q2 Earnings"
        assert data["articles"][0]["source"] == "MarketWatch"
        assert "last_updated" in data

        mock_service.get_stock_news.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_news_no_articles(self, client):
        """Test stock news retrieval when no articles available."""
        mock_service = MagicMock(spec=TradingService)
        mock_news_data = {
            "symbol": "OBSCURE",
            "articles": [],
            "count": 0,
            "last_updated": "2023-06-15T15:30:00Z",
        }
        mock_service.get_stock_news.return_value = mock_news_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/news/OBSCURE")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["articles"] == []

    @pytest.mark.asyncio
    async def test_get_stock_news_not_found(self, client):
        """Test stock news retrieval for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_stock_news.return_value = {"error": "Symbol not found"}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/news/NONEXISTENT")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # GET /movers endpoint tests
    @pytest.mark.asyncio
    async def test_get_top_movers_success(self, client):
        """Test successful top movers retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_movers_data = {
            "gainers": [
                {
                    "symbol": "TSLA",
                    "price": 250.0,
                    "change": 25.0,
                    "change_percent": 11.11,
                },
                {
                    "symbol": "NVDA",
                    "price": 400.0,
                    "change": 35.0,
                    "change_percent": 9.59,
                },
            ],
            "losers": [
                {
                    "symbol": "META",
                    "price": 200.0,
                    "change": -20.0,
                    "change_percent": -9.09,
                },
                {
                    "symbol": "NFLX",
                    "price": 350.0,
                    "change": -30.0,
                    "change_percent": -7.89,
                },
            ],
            "most_active": [
                {"symbol": "AAPL", "price": 155.0, "volume": 100000000},
                {"symbol": "MSFT", "price": 300.0, "volume": 80000000},
            ],
            "last_updated": "2023-06-15T15:30:00Z",
        }
        mock_service.get_top_movers.return_value = mock_movers_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/movers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "gainers" in data
        assert "losers" in data
        assert "most_active" in data
        assert len(data["gainers"]) == 2
        assert len(data["losers"]) == 2
        assert data["gainers"][0]["symbol"] == "TSLA"
        assert data["gainers"][0]["change_percent"] == 11.11
        assert data["losers"][0]["change_percent"] == -9.09

        mock_service.get_top_movers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_top_movers_market_closed(self, client):
        """Test top movers retrieval when market is closed."""
        mock_service = MagicMock(spec=TradingService)
        mock_movers_data = {
            "gainers": [],
            "losers": [],
            "most_active": [],
            "market_status": "closed",
            "last_updated": "2023-06-15T20:00:00Z",
            "message": "Market is currently closed",
        }
        mock_service.get_top_movers.return_value = mock_movers_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/movers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["market_status"] == "closed"
        assert len(data["gainers"]) == 0

    @pytest.mark.asyncio
    async def test_get_top_movers_service_error(self, client):
        """Test top movers retrieval when service returns error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_top_movers.return_value = {"error": "Market data unavailable"}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/movers")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # GET /search endpoint tests
    @pytest.mark.asyncio
    async def test_search_stocks_success_by_symbol(self, client):
        """Test successful stock search by symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_search_data = {
            "query": "AAPL",
            "results": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "equity",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "match_score": 1.0,
                }
            ],
            "count": 1,
            "search_time_ms": 25,
        }
        mock_service.search_stocks.return_value = mock_search_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["query"] == "AAPL"
        assert data["count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "AAPL"
        assert data["results"][0]["name"] == "Apple Inc."
        assert data["results"][0]["match_score"] == 1.0

        mock_service.search_stocks.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_search_stocks_success_by_company_name(self, client):
        """Test successful stock search by company name."""
        mock_service = MagicMock(spec=TradingService)
        mock_search_data = {
            "query": "Apple",
            "results": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "equity",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "match_score": 0.95,
                }
            ],
            "count": 1,
        }
        mock_service.search_stocks.return_value = mock_search_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=Apple")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == "Apple"
        assert data["results"][0]["match_score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_stocks_multiple_results(self, client):
        """Test stock search returning multiple results."""
        mock_service = MagicMock(spec=TradingService)
        mock_search_data = {
            "query": "tech",
            "results": [
                {"symbol": "AAPL", "name": "Apple Inc.", "match_score": 0.8},
                {"symbol": "MSFT", "name": "Microsoft Corporation", "match_score": 0.7},
                {"symbol": "GOOGL", "name": "Alphabet Inc.", "match_score": 0.6},
            ],
            "count": 3,
        }
        mock_service.search_stocks.return_value = mock_search_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=tech")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3
        # Results should be ordered by match score
        assert data["results"][0]["match_score"] >= data["results"][1]["match_score"]

    @pytest.mark.asyncio
    async def test_search_stocks_no_results(self, client):
        """Test stock search with no results."""
        mock_service = MagicMock(spec=TradingService)
        mock_search_data = {"query": "nonexistent", "results": [], "count": 0}
        mock_service.search_stocks.return_value = mock_search_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=nonexistent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    @pytest.mark.asyncio
    async def test_search_stocks_missing_query(self, client):
        """Test stock search without query parameter."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/market-data/search")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_search_stocks_empty_query(self, client):
        """Test stock search with empty query."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/market-data/search?query=")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_search_stocks_service_error(self, client):
        """Test stock search when service returns error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.search_stocks.return_value = {
            "error": "Search service unavailable"
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=AAPL")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Edge cases and additional tests
    @pytest.mark.asyncio
    async def test_market_data_endpoints_with_special_symbols(self, client):
        """Test market data endpoints handle special symbols correctly."""
        special_symbols = ["BRK.A", "BRK.B", "SPY"]

        for symbol in special_symbols:
            mock_service = MagicMock(spec=TradingService)
            mock_service.get_stock_price.return_value = {
                "symbol": symbol,
                "price": 100.0,
            }

            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    response = await ac.get(f"/api/v1/market-data/price/{symbol}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["symbol"] == symbol

    @pytest.mark.asyncio
    async def test_market_data_endpoints_case_sensitivity(self, client):
        """Test market data endpoints handle case sensitivity correctly."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_stock_price.return_value = {
            "symbol": "AAPL",  # Service should normalize to uppercase
            "price": 155.0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/market-data/price/aapl"
                )  # lowercase input

        assert response.status_code == status.HTTP_200_OK
        mock_service.get_stock_price.assert_called_once_with("aapl")

    @pytest.mark.asyncio
    async def test_market_data_endpoints_unicode_handling(self, client):
        """Test market data endpoints handle Unicode characters in search."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.search_stocks.return_value = {
            "query": "苹果",  # "Apple" in Chinese
            "results": [],
            "count": 0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/search?query=苹果")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == "苹果"

    @pytest.mark.asyncio
    async def test_market_data_endpoints_large_datasets(self, client):
        """Test market data endpoints handle large datasets correctly."""
        mock_service = MagicMock(spec=TradingService)

        # Mock large price history dataset
        large_history = {
            "symbol": "AAPL",
            "period": "5year",
            "data": [
                {"date": f"2023-{i:02d}-01", "close": 150.0 + i} for i in range(1, 61)
            ],  # 60 months
        }
        mock_service.get_price_history.return_value = large_history

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/history/AAPL?period=5year")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 60

    @pytest.mark.asyncio
    async def test_market_data_dependency_injection(self):
        """Test that market data service dependency injection works correctly."""
        from app.core.dependencies import get_trading_service

        # Create a mock request with app state
        mock_request = MagicMock()
        mock_service = MagicMock(spec=TradingService)
        mock_request.app.state.trading_service = mock_service

        result = get_trading_service(mock_request)
        assert result is mock_service

    @pytest.mark.asyncio
    async def test_market_data_endpoints_response_structure(self, client):
        """Test that market data endpoints return properly structured responses."""
        mock_service = MagicMock(spec=TradingService)

        # Test price response structure
        mock_service.get_stock_price.return_value = {
            "symbol": "AAPL",
            "price": 155.0,
            "change": 2.5,
            "change_percent": 1.6,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required fields are present
        required_fields = ["symbol", "price"]
        for field in required_fields:
            assert field in data

    @pytest.mark.asyncio
    async def test_market_data_query_parameter_validation(self, client):
        """Test query parameter validation for search endpoint."""
        # Test with very long query
        long_query = "a" * 1000

        mock_service = MagicMock(spec=TradingService)
        mock_service.search_stocks.return_value = {
            "query": long_query,
            "results": [],
            "count": 0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    f"/api/v1/market-data/search?query={long_query}"
                )

        assert response.status_code == status.HTTP_200_OK
