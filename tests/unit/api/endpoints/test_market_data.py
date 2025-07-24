"""
Comprehensive tests for market data endpoints.

Tests all market data endpoints with proper mocking:
- GET /price/{symbol} (get stock price)
- GET /info/{symbol} (get stock information)
- GET /history/{symbol} (get price history)
- GET /search (search stocks)

Covers success paths, error handling, query parameters, and edge cases.
"""

from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient


class TestMarketDataEndpoints:
    """Test suite for market data endpoints."""

    # GET /price/{symbol} endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_price_success(self, mock_get_service, client: TestClient):
        """Test successful stock price retrieval."""
        mock_service = AsyncMock()
        mock_price_data = {
            "symbol": "AAPL",
            "price": 155.0,
            "change": 2.5,
            "change_percent": 1.64,
            "volume": 50000000,
            "market_cap": 2500000000000,
            "timestamp": "2023-06-15T15:30:00Z",
        }
        mock_service.get_stock_price.return_value = mock_price_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.0
        assert data["change"] == 2.5
        assert data["change_percent"] == 1.64
        assert data["volume"] == 50000000
        assert data["market_cap"] == 2500000000000

        mock_service.get_stock_price.assert_called_once_with("AAPL")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_price_not_found(self, mock_get_service, client: TestClient):
        """Test stock price retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_stock_price.return_value = {"error": "Symbol not found"}
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/price/INVALID")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Symbol not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_price_service_error(self, mock_get_service, client: TestClient):
        """Test stock price retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_stock_price.side_effect = Exception("Service unavailable")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Error getting stock price" in data["detail"]

    def test_get_stock_price_invalid_symbol_format(self, client: TestClient):
        """Test stock price retrieval with invalid symbol format."""
        invalid_symbols = ["", "A" * 20, "AAPL@", "AAPL#123", "123AAPL"]

        for symbol in invalid_symbols:
            response = client.get(f"/api/v1/market-data/price/{symbol}")
            # Should handle gracefully
            assert response.status_code in [400, 404, 422, 500]

    # GET /info/{symbol} endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_info_success(self, mock_get_service, client: TestClient):
        """Test successful stock information retrieval."""
        mock_service = AsyncMock()
        mock_info_data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 2500000000000,
            "pe_ratio": 28.5,
            "dividend_yield": 0.0055,
            "eps": 5.45,
            "beta": 1.2,
            "description": "Apple Inc. designs, manufactures, and markets smartphones...",
        }
        mock_service.get_stock_info.return_value = mock_info_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/info/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["sector"] == "Technology"
        assert data["industry"] == "Consumer Electronics"
        assert data["pe_ratio"] == 28.5

        mock_service.get_stock_info.assert_called_once_with("AAPL")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_info_not_found(self, mock_get_service, client: TestClient):
        """Test stock info retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_stock_info.return_value = {
            "error": "Company information not found"
        }
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/info/INVALID")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Company information not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_stock_info_service_error(self, mock_get_service, client: TestClient):
        """Test stock info retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_stock_info.side_effect = Exception("Service unavailable")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/info/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Error getting stock info" in data["detail"]

    # GET /history/{symbol} endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_price_history_success(self, mock_get_service, client: TestClient):
        """Test successful price history retrieval."""
        mock_service = AsyncMock()
        mock_history_data = {
            "symbol": "AAPL",
            "period": "week",
            "data": [
                {
                    "date": "2023-06-12",
                    "open": 148.0,
                    "high": 150.0,
                    "low": 147.5,
                    "close": 149.5,
                    "volume": 45000000,
                },
                {
                    "date": "2023-06-13",
                    "open": 149.5,
                    "high": 153.0,
                    "low": 149.0,
                    "close": 152.0,
                    "volume": 52000000,
                },
                {
                    "date": "2023-06-14",
                    "open": 152.0,
                    "high": 156.0,
                    "low": 151.5,
                    "close": 155.0,
                    "volume": 48000000,
                },
            ],
            "count": 3,
        }
        mock_service.get_price_history.return_value = mock_history_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/history/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["period"] == "week"
        assert len(data["data"]) == 3
        assert data["data"][0]["date"] == "2023-06-12"
        assert data["data"][0]["close"] == 149.5

        mock_service.get_price_history.assert_called_once_with("AAPL", "week")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_price_history_with_period_parameter(
        self, mock_get_service, client: TestClient
    ):
        """Test price history retrieval with custom period parameter."""
        mock_service = AsyncMock()
        mock_history_data = {
            "symbol": "AAPL",
            "period": "month",
            "data": [],
            "count": 0,
        }
        mock_service.get_price_history.return_value = mock_history_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/history/AAPL?period=month")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["period"] == "month"
        mock_service.get_price_history.assert_called_once_with("AAPL", "month")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_price_history_all_periods(self, mock_get_service, client: TestClient):
        """Test price history retrieval with all valid periods."""
        mock_service = AsyncMock()
        mock_service.get_price_history.return_value = {
            "symbol": "AAPL",
            "period": "day",
            "data": [],
        }
        mock_get_service.return_value = mock_service

        valid_periods = ["day", "week", "month", "3month", "year", "5year"]

        for period in valid_periods:
            response = client.get(f"/api/v1/market-data/history/AAPL?period={period}")
            assert response.status_code == status.HTTP_200_OK
            mock_service.get_price_history.assert_called_with("AAPL", period)

    @patch("app.core.dependencies.get_trading_service")
    def test_get_price_history_invalid_period(
        self, mock_get_service, client: TestClient
    ):
        """Test price history retrieval with invalid period."""
        mock_service = AsyncMock()
        mock_service.get_price_history.return_value = {"error": "Invalid period"}
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/history/AAPL?period=invalid")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.core.dependencies.get_trading_service")
    def test_get_price_history_not_found(self, mock_get_service, client: TestClient):
        """Test price history retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_price_history.return_value = {
            "error": "Historical data not found"
        }
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/history/INVALID")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # GET /search endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_search_stocks_success(self, mock_get_service, client: TestClient):
        """Test successful stock search."""
        mock_service = AsyncMock()
        mock_search_data = {
            "query": "Apple",
            "results": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "equity",
                    "exchange": "NASDAQ",
                    "match_score": 1.0,
                },
                {
                    "symbol": "APLE",
                    "name": "Apple Hospitality REIT Inc.",
                    "type": "reit",
                    "exchange": "NYSE",
                    "match_score": 0.8,
                },
            ],
            "count": 2,
        }
        mock_service.search_stocks.return_value = mock_search_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/search?query=Apple")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["query"] == "Apple"
        assert len(data["results"]) == 2
        assert data["results"][0]["symbol"] == "AAPL"
        assert data["results"][0]["name"] == "Apple Inc."
        assert data["results"][0]["match_score"] == 1.0
        assert data["count"] == 2

        mock_service.search_stocks.assert_called_once_with("Apple")

    @patch("app.core.dependencies.get_trading_service")
    def test_search_stocks_by_symbol(self, mock_get_service, client: TestClient):
        """Test stock search by symbol."""
        mock_service = AsyncMock()
        mock_search_data = {
            "query": "AAPL",
            "results": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "equity",
                    "exchange": "NASDAQ",
                    "match_score": 1.0,
                }
            ],
            "count": 1,
        }
        mock_service.search_stocks.return_value = mock_search_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/search?query=AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["query"] == "AAPL"
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "AAPL"

    @patch("app.core.dependencies.get_trading_service")
    def test_search_stocks_no_results(self, mock_get_service, client: TestClient):
        """Test stock search with no results."""
        mock_service = AsyncMock()
        mock_search_data = {"query": "NONEXISTENT", "results": [], "count": 0}
        mock_service.search_stocks.return_value = mock_search_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/search?query=NONEXISTENT")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["query"] == "NONEXISTENT"
        assert len(data["results"]) == 0
        assert data["count"] == 0

    def test_search_stocks_missing_query_parameter(self, client: TestClient):
        """Test stock search without query parameter."""
        response = client.get("/api/v1/market-data/search")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_stocks_empty_query(self, client: TestClient):
        """Test stock search with empty query."""
        response = client.get("/api/v1/market-data/search?query=")

        assert response.status_code in [400, 422]

    @patch("app.core.dependencies.get_trading_service")
    def test_search_stocks_special_characters(
        self, mock_get_service, client: TestClient
    ):
        """Test stock search with special characters."""
        mock_service = AsyncMock()
        mock_service.search_stocks.return_value = {
            "query": "BRK.A",
            "results": [],
            "count": 0,
        }
        mock_get_service.return_value = mock_service

        special_queries = ["BRK.A", "BRK-A", "BRK/A", "A&P"]

        for query in special_queries:
            response = client.get(f"/api/v1/market-data/search?query={query}")
            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    @patch("app.core.dependencies.get_trading_service")
    def test_search_stocks_very_long_query(self, mock_get_service, client: TestClient):
        """Test stock search with very long query."""
        mock_service = AsyncMock()
        mock_service.search_stocks.return_value = {
            "query": "a" * 1000,
            "results": [],
            "count": 0,
        }
        mock_get_service.return_value = mock_service

        long_query = "a" * 1000
        response = client.get(f"/api/v1/market-data/search?query={long_query}")

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]


class TestMarketDataEndpointsErrorHandling:
    """Test error handling scenarios for market data endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_service_unavailable_error(self, mock_get_service, client: TestClient):
        """Test handling when trading service is unavailable."""
        mock_get_service.side_effect = Exception("Service unavailable")

        endpoints = [
            "/api/v1/market-data/price/AAPL",
            "/api/v1/market-data/info/AAPL",
            "/api/v1/market-data/history/AAPL",
            "/api/v1/market-data/search?query=AAPL",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.core.dependencies.get_trading_service")
    def test_timeout_error_handling(self, mock_get_service, client: TestClient):
        """Test handling of timeout errors."""
        mock_service = AsyncMock()
        mock_service.get_stock_price.side_effect = TimeoutError("Request timeout")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/price/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_invalid_url_paths(self, client: TestClient):
        """Test handling of invalid URL paths."""
        invalid_paths = [
            "/api/v1/market-data/price/",  # Empty symbol
            "/api/v1/market-data/info/",  # Empty symbol
            "/api/v1/market-data/history/",  # Empty symbol
        ]

        for path in invalid_paths:
            response = client.get(path)
            assert response.status_code in [404, 422]


class TestMarketDataEndpointsAuthentication:
    """Test authentication scenarios for market data endpoints."""

    def test_endpoints_accessibility(self, client: TestClient):
        """Test that market data endpoints are accessible (assuming public access)."""
        # Market data endpoints are typically public, but test authentication if required
        endpoints_to_test = [
            "/api/v1/market-data/price/AAPL",
            "/api/v1/market-data/info/AAPL",
            "/api/v1/market-data/history/AAPL",
            "/api/v1/market-data/search?query=AAPL",
        ]

        for endpoint in endpoints_to_test:
            response = client.get(endpoint)
            # Should not require authentication for market data
            assert response.status_code in [200, 404, 422, 500]


class TestMarketDataEndpointsPerformance:
    """Test performance-related scenarios for market data endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_concurrent_requests_handling(self, mock_get_service, client: TestClient):
        """Test handling of multiple concurrent requests."""
        mock_service = AsyncMock()
        mock_service.get_stock_price.return_value = {"symbol": "AAPL", "price": 155.0}
        mock_get_service.return_value = mock_service

        # Simulate multiple concurrent requests
        responses = []
        for _ in range(5):
            response = client.get("/api/v1/market-data/price/AAPL")
            responses.append(response)

        # All requests should be handled successfully
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    @patch("app.core.dependencies.get_trading_service")
    def test_large_data_response_handling(self, mock_get_service, client: TestClient):
        """Test handling of large data responses."""
        mock_service = AsyncMock()

        # Create a large search response
        large_results = []
        for i in range(100):
            large_results.append(
                {
                    "symbol": f"STOCK{i:03d}",
                    "name": f"Test Company {i}",
                    "type": "equity",
                    "exchange": "NASDAQ",
                    "match_score": 0.8,
                }
            )

        mock_search_data = {"query": "test", "results": large_results, "count": 100}
        mock_service.search_stocks.return_value = mock_search_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/market-data/search?query=test")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 100
