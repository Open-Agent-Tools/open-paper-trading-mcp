"""
Comprehensive unit tests for MCP market data tools.

Tests async tool functions, parameter validation, TradingService integration,
error handling, and response formatting for market data operations.
"""

from unittest.mock import AsyncMock, Mock, patch
from typing import Any

import pytest
import pytest_asyncio
from pydantic import ValidationError

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
    trading_service,
)


class TestMarketDataToolsParameterValidation:
    """Test parameter validation for market data tool arguments."""
    
    def test_get_stock_price_args_validation(self):
        """Test GetStockPriceArgs parameter validation."""
        # Valid args
        args = GetStockPriceArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        
        # Test required field
        with pytest.raises(ValidationError):
            GetStockPriceArgs()
        
        # Test empty symbol
        args = GetStockPriceArgs(symbol="")
        assert args.symbol == ""  # Should be allowed, handling is in tool
    
    def test_get_stock_info_args_validation(self):
        """Test GetStockInfoArgs parameter validation."""
        # Valid args
        args = GetStockInfoArgs(symbol="GOOGL")
        assert args.symbol == "GOOGL"
        
        # Test with whitespace
        args = GetStockInfoArgs(symbol="  TSLA  ")
        assert args.symbol == "  TSLA  "
    
    def test_get_price_history_args_validation(self):
        """Test GetPriceHistoryArgs parameter validation."""
        # Valid args with default period
        args = GetPriceHistoryArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        assert args.period == "week"
        
        # Valid args with custom period
        args = GetPriceHistoryArgs(symbol="MSFT", period="month")
        assert args.symbol == "MSFT"
        assert args.period == "month"
        
        # Test all valid periods
        valid_periods = ["day", "week", "month", "3month", "year", "5year"]
        for period in valid_periods:
            args = GetPriceHistoryArgs(symbol="AAPL", period=period)
            assert args.period == period
    
    def test_get_stock_news_args_validation(self):
        """Test GetStockNewsArgs parameter validation."""
        args = GetStockNewsArgs(symbol="NVDA")
        assert args.symbol == "NVDA"
        
        with pytest.raises(ValidationError):
            GetStockNewsArgs()
    
    def test_search_stocks_args_validation(self):
        """Test SearchStocksArgs parameter validation."""
        args = SearchStocksArgs(query="Apple Inc")
        assert args.query == "Apple Inc"
        
        # Test with symbol
        args = SearchStocksArgs(query="AAPL")
        assert args.query == "AAPL"
        
        with pytest.raises(ValidationError):
            SearchStocksArgs()


class TestMarketDataToolFunctions:
    """Test individual market data tool functions."""
    
    @pytest_asyncio.async
    async def test_get_stock_price_success(self):
        """Test successful stock price retrieval."""
        mock_result = {
            "symbol": "AAPL",
            "price": 150.25,
            "change": 2.50,
            "change_percent": 1.69,
            "volume": 1000000
        }
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("AAPL")
    
    @pytest_asyncio.async
    async def test_get_stock_price_with_whitespace_symbol(self):
        """Test stock price retrieval with whitespace in symbol."""
        mock_result = {"symbol": "TSLA", "price": 200.00}
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetStockPriceArgs(symbol="  tsla  ")
            result = await get_stock_price(args)
            
            # Should strip and uppercase
            mock_service.assert_called_once_with("TSLA")
            assert result == mock_result
    
    @pytest_asyncio.async
    async def test_get_stock_price_error_handling(self):
        """Test error handling in get_stock_price."""
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("API error")
            
            args = GetStockPriceArgs(symbol="INVALID")
            result = await get_stock_price(args)
            
            assert "error" in result
            assert "API error" in result["error"]
    
    @pytest_asyncio.async
    async def test_get_stock_info_success(self):
        """Test successful stock info retrieval."""
        mock_result = {
            "symbol": "GOOGL",
            "company_name": "Alphabet Inc.",
            "market_cap": 1000000000,
            "pe_ratio": 25.5,
            "description": "Technology company"
        }
        
        with patch.object(trading_service, 'get_stock_info', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetStockInfoArgs(symbol="googl")
            result = await get_stock_info(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("GOOGL")
    
    @pytest_asyncio.async
    async def test_get_stock_info_error_handling(self):
        """Test error handling in get_stock_info."""
        with patch.object(trading_service, 'get_stock_info', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = ValueError("Invalid symbol")
            
            args = GetStockInfoArgs(symbol="INVALID")
            result = await get_stock_info(args)
            
            assert "error" in result
            assert "Invalid symbol" in result["error"]
    
    @pytest_asyncio.async
    async def test_get_price_history_success(self):
        """Test successful price history retrieval."""
        mock_result = {
            "symbol": "MSFT",
            "period": "month",
            "data": [
                {"date": "2024-01-01", "open": 100, "high": 105, "low": 98, "close": 102},
                {"date": "2024-01-02", "open": 102, "high": 108, "low": 101, "close": 106}
            ]
        }
        
        with patch.object(trading_service, 'get_price_history', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetPriceHistoryArgs(symbol="msft", period="month")
            result = await get_price_history(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("MSFT", "month")
    
    @pytest_asyncio.async
    async def test_get_price_history_default_period(self):
        """Test price history with default period."""
        mock_result = {"symbol": "AAPL", "period": "week", "data": []}
        
        with patch.object(trading_service, 'get_price_history', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetPriceHistoryArgs(symbol="AAPL")  # No period specified
            result = await get_price_history(args)
            
            mock_service.assert_called_once_with("AAPL", "week")
    
    @pytest_asyncio.async
    async def test_get_stock_news_success(self):
        """Test successful stock news retrieval."""
        mock_result = {
            "symbol": "NVDA",
            "news": [
                {
                    "title": "NVIDIA Reports Strong Earnings",
                    "summary": "Company beats expectations",
                    "published_at": "2024-01-01T10:00:00Z"
                }
            ]
        }
        
        with patch.object(trading_service, 'get_stock_news', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetStockNewsArgs(symbol="nvda")
            result = await get_stock_news(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("NVDA")
    
    @pytest_asyncio.async
    async def test_get_top_movers_success(self):
        """Test successful top movers retrieval."""
        mock_result = {
            "gainers": [
                {"symbol": "AAPL", "change_percent": 5.2},
                {"symbol": "GOOGL", "change_percent": 3.8}
            ],
            "losers": [
                {"symbol": "TSLA", "change_percent": -4.1}
            ]
        }
        
        with patch.object(trading_service, 'get_top_movers', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            result = await get_top_movers()
            
            assert result == mock_result
            mock_service.assert_called_once()
    
    @pytest_asyncio.async
    async def test_get_top_movers_error_handling(self):
        """Test error handling in get_top_movers."""
        with patch.object(trading_service, 'get_top_movers', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Market data unavailable")
            
            result = await get_top_movers()
            
            assert "error" in result
            assert "Market data unavailable" in result["error"]
    
    @pytest_asyncio.async
    async def test_search_stocks_success(self):
        """Test successful stock search."""
        mock_result = {
            "query": "Apple",
            "results": [
                {"symbol": "AAPL", "company_name": "Apple Inc."},
                {"symbol": "APLE", "company_name": "Apple Hospitality REIT"}
            ]
        }
        
        with patch.object(trading_service, 'search_stocks', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = SearchStocksArgs(query="  Apple  ")
            result = await search_stocks(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("Apple")
    
    @pytest_asyncio.async
    async def test_search_stocks_error_handling(self):
        """Test error handling in search_stocks."""
        with patch.object(trading_service, 'search_stocks', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Search service error")
            
            args = SearchStocksArgs(query="test")
            result = await search_stocks(args)
            
            assert "error" in result
            assert "Search service error" in result["error"]


class TestMarketDataToolsIntegration:
    """Test integration with TradingService."""
    
    def test_trading_service_instance(self):
        """Test that trading_service is properly instantiated."""
        assert trading_service is not None
        # Should be a TradingService instance
        from app.services.trading_service import TradingService
        assert isinstance(trading_service, TradingService)
    
    @pytest_asyncio.async
    async def test_all_tools_use_trading_service(self):
        """Test that all tools properly integrate with TradingService."""
        # Mock all TradingService methods used by tools
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_price, \
             patch.object(trading_service, 'get_stock_info', new_callable=AsyncMock) as mock_info, \
             patch.object(trading_service, 'get_price_history', new_callable=AsyncMock) as mock_history, \
             patch.object(trading_service, 'get_stock_news', new_callable=AsyncMock) as mock_news, \
             patch.object(trading_service, 'get_top_movers', new_callable=AsyncMock) as mock_movers, \
             patch.object(trading_service, 'search_stocks', new_callable=AsyncMock) as mock_search:
            
            # Set up return values
            mock_price.return_value = {"symbol": "AAPL"}
            mock_info.return_value = {"symbol": "AAPL"}
            mock_history.return_value = {"symbol": "AAPL"}
            mock_news.return_value = {"symbol": "AAPL"}
            mock_movers.return_value = {"gainers": []}
            mock_search.return_value = {"results": []}
            
            # Call all tools
            await get_stock_price(GetStockPriceArgs(symbol="AAPL"))
            await get_stock_info(GetStockInfoArgs(symbol="AAPL"))
            await get_price_history(GetPriceHistoryArgs(symbol="AAPL"))
            await get_stock_news(GetStockNewsArgs(symbol="AAPL"))
            await get_top_movers()
            await search_stocks(SearchStocksArgs(query="Apple"))
            
            # Verify all service methods were called
            mock_price.assert_called_once()
            mock_info.assert_called_once()
            mock_history.assert_called_once()
            mock_news.assert_called_once()
            mock_movers.assert_called_once()
            mock_search.assert_called_once()


class TestMarketDataToolsErrorHandling:
    """Test comprehensive error handling scenarios."""
    
    @pytest_asyncio.async
    async def test_network_error_handling(self):
        """Test handling of network-related errors."""
        import asyncio
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = asyncio.TimeoutError("Request timeout")
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            assert "error" in result
            assert "Request timeout" in result["error"]
    
    @pytest_asyncio.async
    async def test_service_exception_handling(self):
        """Test handling of service-specific exceptions."""
        with patch.object(trading_service, 'get_stock_info', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = ValueError("Invalid symbol format")
            
            args = GetStockInfoArgs(symbol="INVALID")
            result = await get_stock_info(args)
            
            assert "error" in result
            assert "Invalid symbol format" in result["error"]
    
    @pytest_asyncio.async
    async def test_unexpected_exception_handling(self):
        """Test handling of unexpected exceptions."""
        with patch.object(trading_service, 'search_stocks', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = RuntimeError("Unexpected error")
            
            args = SearchStocksArgs(query="test")
            result = await search_stocks(args)
            
            assert "error" in result
            assert "Unexpected error" in result["error"]


class TestMarketDataToolsInputProcessing:
    """Test input processing and normalization."""
    
    @pytest_asyncio.async
    async def test_symbol_normalization(self):
        """Test that symbols are properly normalized."""
        test_cases = [
            ("aapl", "AAPL"),
            ("  GOOGL  ", "GOOGL"),
            ("\tTSLA\n", "TSLA"),
            ("msft", "MSFT")
        ]
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "TEST"}
            
            for input_symbol, expected_symbol in test_cases:
                args = GetStockPriceArgs(symbol=input_symbol)
                await get_stock_price(args)
                
                # Get the last call and verify the symbol was normalized
                last_call_args = mock_service.call_args[0]
                assert last_call_args[0] == expected_symbol
    
    @pytest_asyncio.async
    async def test_query_normalization(self):
        """Test that search queries are properly normalized."""
        test_cases = [
            ("  Apple Inc  ", "Apple Inc"),
            ("\tGOOGL\n", "GOOGL"),
            ("Microsoft Corporation", "Microsoft Corporation")
        ]
        
        with patch.object(trading_service, 'search_stocks', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"results": []}
            
            for input_query, expected_query in test_cases:
                args = SearchStocksArgs(query=input_query)
                await search_stocks(args)
                
                # Get the last call and verify the query was normalized
                last_call_args = mock_service.call_args[0]
                assert last_call_args[0] == expected_query


class TestMarketDataToolsResponseFormatting:
    """Test response formatting and structure."""
    
    @pytest_asyncio.async
    async def test_successful_response_passthrough(self):
        """Test that successful responses are passed through correctly."""
        mock_response = {
            "symbol": "AAPL",
            "price": 150.25,
            "metadata": {"source": "test"}
        }
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_response
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            # Should return the exact response from service
            assert result == mock_response
    
    @pytest_asyncio.async
    async def test_error_response_formatting(self):
        """Test that error responses are properly formatted."""
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Test error")
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Test error" in result["error"]
    
    @pytest_asyncio.async
    async def test_empty_response_handling(self):
        """Test handling of empty or None responses."""
        with patch.object(trading_service, 'get_top_movers', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = None
            
            result = await get_top_movers()
            
            # Should return None directly (service handles this case)
            assert result is None


class TestMarketDataToolsAsyncBehavior:
    """Test async behavior and concurrency."""
    
    @pytest_asyncio.async
    async def test_concurrent_tool_calls(self):
        """Test that tools can be called concurrently."""
        import asyncio
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "TEST", "price": 100}
            
            # Create multiple concurrent calls
            tasks = [
                get_stock_price(GetStockPriceArgs(symbol="AAPL")),
                get_stock_price(GetStockPriceArgs(symbol="GOOGL")),
                get_stock_price(GetStockPriceArgs(symbol="MSFT"))
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All calls should succeed
            assert len(results) == 3
            for result in results:
                assert "symbol" in result
                assert "price" in result
            
            # Service should be called 3 times
            assert mock_service.call_count == 3
    
    @pytest_asyncio.async
    async def test_async_context_preservation(self):
        """Test that async context is preserved across tool calls."""
        import contextvars
        
        # Create a context variable
        test_var = contextvars.ContextVar('test_var')
        test_var.set('test_value')
        
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            async def check_context(*args, **kwargs):
                # Verify context is preserved
                assert test_var.get() == 'test_value'
                return {"symbol": "AAPL", "price": 100}
            
            mock_service.side_effect = check_context
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            assert result["symbol"] == "AAPL"


class TestMarketDataToolsCoverage:
    """Additional tests to achieve 70% coverage target."""
    
    def test_module_imports(self):
        """Test module imports and structure."""
        # Test that all expected classes and functions are importable
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
            trading_service,
        )
        
        # Verify classes are Pydantic models
        from pydantic import BaseModel
        assert issubclass(GetStockPriceArgs, BaseModel)
        assert issubclass(GetStockInfoArgs, BaseModel)
        assert issubclass(GetPriceHistoryArgs, BaseModel)
        assert issubclass(GetStockNewsArgs, BaseModel)
        assert issubclass(SearchStocksArgs, BaseModel)
    
    def test_argument_model_fields(self):
        """Test argument model field definitions."""
        # Test field descriptions
        assert GetStockPriceArgs.model_fields['symbol'].description is not None
        assert GetStockInfoArgs.model_fields['symbol'].description is not None
        assert GetPriceHistoryArgs.model_fields['symbol'].description is not None
        assert GetPriceHistoryArgs.model_fields['period'].description is not None
        assert GetStockNewsArgs.model_fields['symbol'].description is not None
        assert SearchStocksArgs.model_fields['query'].description is not None
    
    @pytest_asyncio.async
    async def test_edge_case_inputs(self):
        """Test edge case inputs."""
        with patch.object(trading_service, 'get_stock_price', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "A", "price": 1}
            
            # Test single character symbol
            args = GetStockPriceArgs(symbol="A")
            result = await get_stock_price(args)
            mock_service.assert_called_with("A")
            
            # Test symbol with numbers
            args = GetStockPriceArgs(symbol="BRK.A")
            await get_stock_price(args)
            mock_service.assert_called_with("BRK.A")
    
    def test_module_documentation(self):
        """Test module and function documentation."""
        import app.mcp.market_data_tools as module
        
        # Module should have docstring
        assert module.__doc__ is not None
        assert "market data" in module.__doc__.lower()
        
        # Functions should have docstrings
        assert get_stock_price.__doc__ is not None
        assert get_stock_info.__doc__ is not None
        assert get_price_history.__doc__ is not None
        assert get_stock_news.__doc__ is not None
        assert get_top_movers.__doc__ is not None
        assert search_stocks.__doc__ is not None