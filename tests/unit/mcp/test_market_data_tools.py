"""
Comprehensive unit tests for MCP market data tools.

Tests async tool functions, parameter validation, TradingService integration,
error handling, and response formatting for market data operations with
direct function parameters (no Pydantic models).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.market_data_tools import (
    get_mcp_trading_service,
    get_price_history,
    get_stock_info,
    get_stock_price,
    market_hours,
    price_history,
    search_stocks,
    search_stocks_tool,
    set_mcp_trading_service,
    stock_events,
    stock_info,
    stock_level2_data,
    stock_price,
    stock_ratings,
)


class TestMarketDataToolsServiceManagement:
    """Test trading service dependency management."""

    def test_set_and_get_mcp_trading_service(self):
        """Test setting and getting trading service."""
        from unittest.mock import Mock

        mock_service = Mock()
        set_mcp_trading_service(mock_service)

        service = get_mcp_trading_service()
        assert service is mock_service

        # Clean up
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    def test_get_mcp_trading_service_not_initialized(self):
        """Test getting service when not initialized raises error."""
        # Clear any existing service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

        with pytest.raises(RuntimeError, match="TradingService not initialized"):
            get_mcp_trading_service()


class TestMarketDataToolFunctions:
    """Test individual market data tool functions with direct parameters."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_stock_price_success(self):
        """Test successful stock price retrieval."""
        mock_result = {
            "symbol": "AAPL",
            "price": 150.25,
            "change": 2.50,
            "change_percent": 1.69,
            "volume": 1000000,
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_price("AAPL")

            # Should return standardized response format
            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stock_price_with_whitespace_symbol(self):
        """Test stock price retrieval with whitespace in symbol."""
        mock_result = {"symbol": "TSLA", "price": 200.00}

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_price("  tsla  ")

            # Should strip and uppercase
            mock_service.assert_called_once_with("TSLA")
            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result

    @pytest.mark.asyncio
    async def test_stock_price_error_handling(self):
        """Test error handling in stock_price."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("API error")

            result = await stock_price("INVALID")

            assert result["result"]["status"] == "error"
            assert "API error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_stock_info_success(self):
        """Test successful stock info retrieval."""
        mock_result = {
            "symbol": "GOOGL",
            "company_name": "Alphabet Inc.",
            "market_cap": 1000000000,
            "pe_ratio": 25.5,
            "description": "Technology company",
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_info("googl")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("GOOGL")

    @pytest.mark.asyncio
    async def test_stock_info_error_handling(self):
        """Test error handling in stock_info."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = ValueError("Invalid symbol")

            result = await stock_info("INVALID")

            assert result["result"]["status"] == "error"
            assert "Invalid symbol" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_search_stocks_tool_success(self):
        """Test successful stock search via search_stocks_tool."""
        mock_result = {
            "query": "Apple",
            "results": [
                {"symbol": "AAPL", "company_name": "Apple Inc."},
                {"symbol": "APLE", "company_name": "Apple Hospitality REIT"},
            ],
        }

        with patch.object(
            get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await search_stocks_tool("  Apple  ")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("Apple")

    @pytest.mark.asyncio
    async def test_search_stocks_tool_error_handling(self):
        """Test error handling in search_stocks_tool."""
        with patch.object(
            get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Search service error")

            result = await search_stocks_tool("test")

            assert result["result"]["status"] == "error"
            assert "Search service error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_market_hours_success(self):
        """Test successful market hours retrieval."""
        mock_result = {
            "market_status": "open",
            "next_open": "2024-07-24T09:30:00-04:00",
            "next_close": "2024-07-24T16:00:00-04:00",
            "is_holiday": False,
            "timezone": "America/New_York",
        }

        with patch.object(
            get_mcp_trading_service(), "get_market_hours", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await market_hours()

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_market_hours_error_handling(self):
        """Test error handling in market_hours."""
        with patch.object(
            get_mcp_trading_service(), "get_market_hours", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Market data unavailable")

            result = await market_hours()

            assert result["result"]["status"] == "error"
            assert "Market data unavailable" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_price_history_success(self):
        """Test successful price history retrieval."""
        mock_result = {
            "symbol": "MSFT",
            "period": "month",
            "data": [
                {
                    "date": "2024-01-01",
                    "open": 100,
                    "high": 105,
                    "low": 98,
                    "close": 102,
                },
                {
                    "date": "2024-01-02",
                    "open": 102,
                    "high": 108,
                    "low": 101,
                    "close": 106,
                },
            ],
        }

        with patch.object(
            get_mcp_trading_service(), "get_price_history", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await price_history("msft", "month")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("MSFT", "month")

    @pytest.mark.asyncio
    async def test_price_history_default_period(self):
        """Test price history with default period."""
        mock_result = {"symbol": "AAPL", "period": "week", "data": []}

        with patch.object(
            get_mcp_trading_service(), "get_price_history", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await price_history("AAPL")

            assert result["result"]["status"] == "success"
            mock_service.assert_called_once_with("AAPL", "week")

    @pytest.mark.asyncio
    async def test_stock_ratings_success(self):
        """Test successful stock ratings retrieval."""
        mock_result = {
            "symbol": "AAPL",
            "overall_rating": "Buy",
            "rating_score": 4.2,
            "total_analysts": 15,
            "ratings_breakdown": {
                "strong_buy": 5,
                "buy": 7,
                "hold": 2,
                "sell": 1,
                "strong_sell": 0,
            },
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_ratings", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_ratings("aapl")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stock_ratings_error_handling(self):
        """Test error handling in stock_ratings."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_ratings", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = ValueError("Invalid symbol")

            result = await stock_ratings("INVALID")

            assert result["result"]["status"] == "error"
            assert "Invalid symbol" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_stock_events_success(self):
        """Test successful stock events retrieval."""
        mock_result = {
            "symbol": "TSLA",
            "upcoming_events": [
                {
                    "event_type": "earnings",
                    "date": "2024-07-30T00:00:00Z",
                    "description": "Q2 2024 Earnings Report",
                }
            ],
            "recent_events": [],
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_events", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_events("tsla")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("TSLA")

    @pytest.mark.asyncio
    async def test_stock_events_error_handling(self):
        """Test error handling in stock_events."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_events", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Events service error")

            result = await stock_events("INVALID")

            assert result["result"]["status"] == "error"
            assert "Events service error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_stock_level2_data_success(self):
        """Test successful Level 2 data retrieval."""
        mock_result = {
            "symbol": "MSFT",
            "timestamp": "2024-07-23T00:00:00Z",
            "bids": [
                {"price": 184.50, "size": 100, "market_maker": "ARCA"},
                {"price": 184.45, "size": 200, "market_maker": "NASDAQ"},
            ],
            "asks": [
                {"price": 184.55, "size": 100, "market_maker": "ARCA"},
                {"price": 184.60, "size": 200, "market_maker": "NASDAQ"},
            ],
            "spread": 0.05,
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_level2_data", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await stock_level2_data("msft")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("MSFT")

    @pytest.mark.asyncio
    async def test_stock_level2_data_error_handling(self):
        """Test error handling in stock_level2_data."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_level2_data", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Level 2 data unavailable")

            result = await stock_level2_data("INVALID")

            assert result["result"]["status"] == "error"
            assert "Level 2 data unavailable" in result["result"]["error"]


class TestMarketDataToolsIntegration:
    """Test integration with TradingService."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    def test_trading_service_instance(self):
        """Test that trading_service is properly instantiated."""
        service = get_mcp_trading_service()
        assert service is not None
        # Should be the mock service we set up
        assert service is self.mock_service

    @pytest.mark.asyncio
    async def test_all_new_tools_use_trading_service(self):
        """Test that all new tools properly integrate with TradingService."""
        with (
            patch.object(
                get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
            ) as mock_price,
            patch.object(
                get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
            ) as mock_info,
            patch.object(
                get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
            ) as mock_search,
            patch.object(
                get_mcp_trading_service(), "get_market_hours", new_callable=AsyncMock
            ) as mock_hours,
            patch.object(
                get_mcp_trading_service(), "get_price_history", new_callable=AsyncMock
            ) as mock_history,
            patch.object(
                get_mcp_trading_service(), "get_stock_ratings", new_callable=AsyncMock
            ) as mock_ratings,
            patch.object(
                get_mcp_trading_service(), "get_stock_events", new_callable=AsyncMock
            ) as mock_events,
            patch.object(
                get_mcp_trading_service(),
                "get_stock_level2_data",
                new_callable=AsyncMock,
            ) as mock_level2,
        ):
            # Set up return values
            mock_price.return_value = {"symbol": "AAPL"}
            mock_info.return_value = {"symbol": "AAPL"}
            mock_search.return_value = {"results": []}
            mock_hours.return_value = {"market_status": "open"}
            mock_history.return_value = {"symbol": "AAPL"}
            mock_ratings.return_value = {"symbol": "AAPL"}
            mock_events.return_value = {"symbol": "AAPL"}
            mock_level2.return_value = {"symbol": "AAPL"}

            # Call all tools
            await stock_price("AAPL")
            await stock_info("AAPL")
            await search_stocks_tool("Apple")
            await market_hours()
            await price_history("AAPL")
            await stock_ratings("AAPL")
            await stock_events("AAPL")
            await stock_level2_data("AAPL")

            # Verify all service methods were called
            mock_price.assert_called_once()
            mock_info.assert_called_once()
            mock_search.assert_called_once()
            mock_hours.assert_called_once()
            mock_history.assert_called_once()
            mock_ratings.assert_called_once()
            mock_events.assert_called_once()
            mock_level2.assert_called_once()


class TestMarketDataToolsErrorHandling:
    """Test comprehensive error handling scenarios."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network-related errors."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = TimeoutError("Request timeout")

            result = await stock_price("AAPL")

            assert result["result"]["status"] == "error"
            assert "Request timeout" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_service_exception_handling(self):
        """Test handling of service-specific exceptions."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = ValueError("Invalid symbol format")

            result = await stock_info("INVALID")

            assert result["result"]["status"] == "error"
            assert "Invalid symbol format" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self):
        """Test handling of unexpected exceptions."""
        with patch.object(
            get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = RuntimeError("Unexpected error")

            result = await search_stocks_tool("test")

            assert result["result"]["status"] == "error"
            assert "Unexpected error" in result["result"]["error"]


class TestMarketDataToolsInputProcessing:
    """Test input processing and normalization."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_symbol_normalization(self):
        """Test that symbols are properly normalized."""
        test_cases = [
            ("aapl", "AAPL"),
            ("  GOOGL  ", "GOOGL"),
            ("\tTSLA\n", "TSLA"),
            ("msft", "MSFT"),
        ]

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = {"symbol": "TEST"}

            for input_symbol, expected_symbol in test_cases:
                await stock_price(input_symbol)

                # Get the last call and verify the symbol was normalized
                last_call_args = mock_service.call_args[0]
                assert last_call_args[0] == expected_symbol

    @pytest.mark.asyncio
    async def test_query_normalization(self):
        """Test that search queries are properly normalized."""
        test_cases = [
            ("  Apple Inc  ", "Apple Inc"),
            ("\tGOOGL\n", "GOOGL"),
            ("Microsoft Corporation", "Microsoft Corporation"),
        ]

        with patch.object(
            get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = {"results": []}

            for input_query, expected_query in test_cases:
                await search_stocks_tool(input_query)

                # Get the last call and verify the query was normalized
                last_call_args = mock_service.call_args[0]
                assert last_call_args[0] == expected_query


class TestMarketDataToolsResponseFormatting:
    """Test response formatting and structure."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_successful_response_format(self):
        """Test that successful responses use standardized format."""
        mock_response = {
            "symbol": "AAPL",
            "price": 150.25,
            "metadata": {"source": "test"},
        }

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_response

            result = await stock_price("AAPL")

            # Should use standardized response format
            assert "result" in result
            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_response

    @pytest.mark.asyncio
    async def test_error_response_format(self):
        """Test that error responses use standardized format."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Test error")

            result = await stock_price("AAPL")

            # Should use standardized error format
            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "Test error" in result["result"]["error"]
            assert "stock_price" in result["result"]["error"]


class TestMarketDataToolsAsyncBehavior:
    """Test async behavior and concurrency."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that tools can be called concurrently."""
        import asyncio

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = {"symbol": "TEST", "price": 100}

            # Create multiple concurrent calls
            tasks = [
                stock_price("AAPL"),
                stock_price("GOOGL"),
                stock_price("MSFT"),
            ]

            results = await asyncio.gather(*tasks)

            # All calls should succeed
            assert len(results) == 3
            for result in results:
                assert result["result"]["status"] == "success"
                assert "symbol" in result["result"]["data"]
                assert "price" in result["result"]["data"]

            # Service should be called 3 times
            assert mock_service.call_count == 3

    @pytest.mark.asyncio
    async def test_async_context_preservation(self):
        """Test that async context is preserved across tool calls."""
        import contextvars

        # Create a context variable
        test_var = contextvars.ContextVar("test_var")
        test_var.set("test_value")

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:

            async def check_context(*args, **kwargs):
                # Verify context is preserved
                assert test_var.get() == "test_value"
                return {"symbol": "AAPL", "price": 100}

            mock_service.side_effect = check_context

            result = await stock_price("AAPL")

            assert result["result"]["data"]["symbol"] == "AAPL"


class TestLegacyCompatibilityFunctions:
    """Test that legacy functions still work for backward compatibility."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    @pytest.mark.asyncio
    async def test_get_stock_price_compatibility(self):
        """Test legacy get_stock_price function."""
        mock_result = {"symbol": "AAPL", "price": 150.25}

        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await get_stock_price("AAPL")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_info_compatibility(self):
        """Test legacy get_stock_info function."""
        mock_result = {"symbol": "GOOGL", "company_name": "Alphabet Inc."}

        with patch.object(
            get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await get_stock_info("GOOGL")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("GOOGL")

    @pytest.mark.asyncio
    async def test_get_price_history_compatibility(self):
        """Test legacy get_price_history function."""
        mock_result = {"symbol": "MSFT", "period": "month", "data": []}

        with patch.object(
            get_mcp_trading_service(), "get_price_history", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await get_price_history("MSFT", "month")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("MSFT", "month")

    @pytest.mark.asyncio
    async def test_search_stocks_compatibility(self):
        """Test legacy search_stocks function."""
        mock_result = {"query": "Apple", "results": []}

        with patch.object(
            get_mcp_trading_service(), "search_stocks", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = mock_result

            result = await search_stocks("Apple")

            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == mock_result
            mock_service.assert_called_once_with("Apple")


class TestMarketDataToolsCoverage:
    """Additional tests to achieve 70% coverage target."""

    def setup_method(self):
        """Set up a mock trading service for each test."""
        from unittest.mock import Mock

        self.mock_service = Mock()
        set_mcp_trading_service(self.mock_service)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear the trading service
        from app.mcp import market_data_tools

        market_data_tools._trading_service = None

    def test_module_imports(self):
        """Test module imports and structure."""
        # Test that all expected functions are importable
        from app.mcp.market_data_tools import (
            market_hours,
            price_history,
            search_stocks_tool,
            stock_events,
            stock_info,
            stock_level2_data,
            stock_price,
            stock_ratings,
        )

        # All functions should be callable
        assert callable(stock_price)
        assert callable(stock_info)
        assert callable(search_stocks_tool)
        assert callable(market_hours)
        assert callable(price_history)
        assert callable(stock_ratings)
        assert callable(stock_events)
        assert callable(stock_level2_data)

    @pytest.mark.asyncio
    async def test_edge_case_inputs(self):
        """Test edge case inputs."""
        with patch.object(
            get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = {"symbol": "A", "price": 1}

            # Test single character symbol
            await stock_price("A")
            mock_service.assert_called_with("A")

            # Test symbol with numbers and dots
            await stock_price("BRK.A")
            mock_service.assert_called_with("BRK.A")

    def test_module_documentation(self):
        """Test module and function documentation."""
        import app.mcp.market_data_tools as module

        # Module should have docstring
        assert module.__doc__ is not None
        assert "market data" in module.__doc__.lower()

        # Functions should have docstrings
        assert stock_price.__doc__ is not None
        assert stock_info.__doc__ is not None
        assert search_stocks_tool.__doc__ is not None
        assert market_hours.__doc__ is not None
        assert price_history.__doc__ is not None
        assert stock_ratings.__doc__ is not None
        assert stock_events.__doc__ is not None
        assert stock_level2_data.__doc__ is not None

    @pytest.mark.asyncio
    async def test_empty_and_none_responses(self):
        """Test handling of empty or None responses."""
        with patch.object(
            get_mcp_trading_service(), "get_market_hours", new_callable=AsyncMock
        ) as mock_service:
            # Test None response
            mock_service.return_value = None
            result = await market_hours()
            assert result["result"]["status"] == "success"
            assert result["result"]["data"] is None

            # Test empty dict response
            mock_service.return_value = {}
            result = await market_hours()
            assert result["result"]["status"] == "success"
            assert result["result"]["data"] == {}

    def test_function_signatures(self):
        """Test that functions have correct signatures."""
        import inspect

        # market_hours should take no arguments
        sig = inspect.signature(market_hours)
        assert len(sig.parameters) == 0

        # Symbol-based tools should take one argument
        for tool_func in [
            stock_price,
            stock_info,
            stock_ratings,
            stock_events,
            stock_level2_data,
        ]:
            sig = inspect.signature(tool_func)
            assert len(sig.parameters) == 1
            param_name = next(iter(sig.parameters.keys()))
            assert param_name == "symbol"

        # search_stocks_tool should take query argument
        sig = inspect.signature(search_stocks_tool)
        assert len(sig.parameters) == 1
        param_name = next(iter(sig.parameters.keys()))
        assert param_name == "query"

        # price_history should take symbol and optional period
        sig = inspect.signature(price_history)
        assert len(sig.parameters) == 2
        param_names = list(sig.parameters.keys())
        assert param_names == ["symbol", "period"]
        assert sig.parameters["period"].default == "week"

    @pytest.mark.asyncio
    async def test_all_tools_symbol_normalization(self):
        """Test that all symbol-based tools normalize symbols correctly."""

        with (
            patch.object(
                get_mcp_trading_service(), "get_stock_price", new_callable=AsyncMock
            ) as mock_price,
            patch.object(
                get_mcp_trading_service(), "get_stock_info", new_callable=AsyncMock
            ) as mock_info,
            patch.object(
                get_mcp_trading_service(), "get_stock_ratings", new_callable=AsyncMock
            ) as mock_ratings,
            patch.object(
                get_mcp_trading_service(), "get_stock_events", new_callable=AsyncMock
            ) as mock_events,
            patch.object(
                get_mcp_trading_service(),
                "get_stock_level2_data",
                new_callable=AsyncMock,
            ) as mock_level2,
        ):
            # Set up return values
            for mock in [mock_price, mock_info, mock_ratings, mock_events, mock_level2]:
                mock.return_value = {"symbol": "TEST"}

            # Test each tool with lowercase input
            await stock_price("aapl")
            await stock_info("aapl")
            await stock_ratings("aapl")
            await stock_events("aapl")
            await stock_level2_data("aapl")

            # Verify all calls were made with uppercase symbol
            mock_price.assert_called_with("AAPL")
            mock_info.assert_called_with("AAPL")
            mock_ratings.assert_called_with("AAPL")
            mock_events.assert_called_with("AAPL")
            mock_level2.assert_called_with("AAPL")

    def test_tool_docstrings_coverage(self):
        """Test that all tools have comprehensive docstrings."""
        tools_to_check = [
            stock_price,
            stock_info,
            search_stocks_tool,
            market_hours,
            price_history,
            stock_ratings,
            stock_events,
            stock_level2_data,
        ]

        for tool in tools_to_check:
            assert tool.__doc__ is not None
            assert (
                len(tool.__doc__.strip()) > 50
            )  # Should have substantial documentation
            # Should mention Args and Returns
            assert (
                "Args:" in tool.__doc__ or tool == market_hours
            )  # market_hours has no args
            assert "Returns:" in tool.__doc__
