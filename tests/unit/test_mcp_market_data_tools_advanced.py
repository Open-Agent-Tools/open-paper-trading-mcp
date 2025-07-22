"""
Advanced unit tests for MCP market data tools implementation.

Tests market data MCP tools, async patterns, service integration,
error handling, and response formatting for market data operations.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict

import pytest
import pytest_asyncio

from app.mcp.market_data_tools import (
    GetStockPriceArgs, GetStockInfoArgs, GetPriceHistoryArgs,
    GetStockNewsArgs, SearchStocksArgs, get_stock_price,
    get_stock_info, get_price_history, get_stock_news,
    get_top_movers, search_stocks
)


class TestMCPMarketDataToolsModule:
    """Test MCP market data tools module structure."""

    def test_market_data_tools_module_imports(self):
        """Test that market data tools module imports correctly."""
        import app.mcp.market_data_tools
        assert app.mcp.market_data_tools is not None

    def test_market_data_tools_module_docstring(self):
        """Test module has proper docstring."""
        import app.mcp.market_data_tools
        doc = app.mcp.market_data_tools.__doc__
        assert doc is not None
        assert "market data" in doc.lower()
        assert "TradingService" in doc

    def test_all_market_data_functions_imported(self):
        """Test all expected market data functions are available."""
        import app.mcp.market_data_tools as tools
        
        expected_functions = [
            'get_stock_price',
            'get_stock_info', 
            'get_price_history',
            'get_stock_news',
            'get_top_movers',
            'search_stocks'
        ]
        
        for func_name in expected_functions:
            assert hasattr(tools, func_name), f"Should have {func_name} function"
            func = getattr(tools, func_name)
            assert callable(func), f"{func_name} should be callable"


class TestMCPMarketDataParameterValidation:
    """Test parameter validation for market data tools."""

    def test_get_stock_price_args_validation(self):
        """Test GetStockPriceArgs parameter validation."""
        # Valid args
        args = GetStockPriceArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        
        # Test required field
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetStockPriceArgs()  # Missing required symbol

    def test_get_stock_info_args_validation(self):
        """Test GetStockInfoArgs parameter validation."""
        args = GetStockInfoArgs(symbol="GOOGL")
        assert args.symbol == "GOOGL"
        
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetStockInfoArgs()  # Missing required symbol

    def test_get_price_history_args_validation(self):
        """Test GetPriceHistoryArgs parameter validation."""
        # Valid args with default period
        args = GetPriceHistoryArgs(symbol="MSFT")
        assert args.symbol == "MSFT"
        assert args.period == "week"  # Default value
        
        # Valid args with custom period
        args = GetPriceHistoryArgs(symbol="TSLA", period="month")
        assert args.symbol == "TSLA"
        assert args.period == "month"
        
        # Test valid periods
        valid_periods = ["day", "week", "month", "3month", "year", "5year"]
        for period in valid_periods:
            args = GetPriceHistoryArgs(symbol="TEST", period=period)
            assert args.period == period

    def test_get_stock_news_args_validation(self):
        """Test GetStockNewsArgs parameter validation."""
        args = GetStockNewsArgs(symbol="NVDA")
        assert args.symbol == "NVDA"

    def test_search_stocks_args_validation(self):
        """Test SearchStocksArgs parameter validation."""
        args = SearchStocksArgs(query="Apple Inc")
        assert args.query == "Apple Inc"
        
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchStocksArgs()  # Missing required query


class TestMCPMarketDataAsyncBehavior:
    """Test async behavior of market data tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for market data testing."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            # Configure mock methods
            mock_service.get_stock_price = Mock(return_value={
                "symbol": "AAPL",
                "price": 150.75,
                "change": 2.25,
                "change_percent": 1.52,
                "volume": 45000000,
                "last_updated": "2024-01-15T16:00:00Z"
            })
            
            mock_service.get_stock_info = Mock(return_value={
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "market_cap": 3000000000000,
                "pe_ratio": 25.5,
                "dividend_yield": 0.52
            })
            
            mock_service.get_price_history = Mock(return_value={
                "symbol": "AAPL",
                "period": "week",
                "data": [
                    {"date": "2024-01-08", "open": 148.0, "high": 152.0, "low": 147.0, "close": 150.0, "volume": 50000000},
                    {"date": "2024-01-09", "open": 150.0, "high": 153.0, "low": 149.0, "close": 151.0, "volume": 48000000}
                ]
            })
            
            mock_service.get_stock_news = Mock(return_value={
                "symbol": "AAPL",
                "news": [
                    {
                        "headline": "Apple Reports Strong Q4 Earnings",
                        "summary": "Apple exceeded expectations...",
                        "url": "https://example.com/news1",
                        "published_at": "2024-01-15T10:00:00Z"
                    }
                ]
            })
            
            mock_service.get_top_movers = Mock(return_value={
                "gainers": [
                    {"symbol": "NVDA", "price": 875.0, "change_percent": 5.2}
                ],
                "losers": [
                    {"symbol": "META", "price": 485.0, "change_percent": -3.1}
                ]
            })
            
            mock_service.search_stocks = Mock(return_value={
                "results": [
                    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}
                ]
            })
            
            yield mock_service

    @pytest.mark.asyncio
    async def test_get_stock_price_async(self, mock_trading_service):
        """Test get_stock_price async execution."""
        args = GetStockPriceArgs(symbol="AAPL")
        result = await get_stock_price(args)
        
        # Verify service call
        mock_trading_service.get_stock_price.assert_called_once_with("AAPL")
        
        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert result["price"] == 150.75
        assert "change" in result
        assert "volume" in result

    @pytest.mark.asyncio
    async def test_get_stock_info_async(self, mock_trading_service):
        """Test get_stock_info async execution."""
        args = GetStockInfoArgs(symbol="AAPL")
        result = await get_stock_info(args)
        
        # Verify service call
        mock_trading_service.get_stock_info.assert_called_once_with("AAPL")
        
        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert "sector" in result
        assert "market_cap" in result

    @pytest.mark.asyncio
    async def test_get_price_history_async(self, mock_trading_service):
        """Test get_price_history async execution."""
        args = GetPriceHistoryArgs(symbol="AAPL", period="month")
        result = await get_price_history(args)
        
        # Verify service call
        mock_trading_service.get_price_history.assert_called_once_with("AAPL", "month")
        
        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert result["period"] == "week"  # From mock
        assert "data" in result
        assert isinstance(result["data"], list)

    @pytest.mark.asyncio
    async def test_get_stock_news_async(self, mock_trading_service):
        """Test get_stock_news async execution."""
        args = GetStockNewsArgs(symbol="AAPL")
        result = await get_stock_news(args)
        
        # Verify service call
        mock_trading_service.get_stock_news.assert_called_once_with("AAPL")
        
        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert "news" in result
        assert isinstance(result["news"], list)
        
        if result["news"]:
            news_item = result["news"][0]
            assert "headline" in news_item
            assert "published_at" in news_item

    @pytest.mark.asyncio
    async def test_get_top_movers_async(self, mock_trading_service):
        """Test get_top_movers async execution (no parameters)."""
        result = await get_top_movers()
        
        # Verify service call
        mock_trading_service.get_top_movers.assert_called_once()
        
        # Verify response structure
        assert isinstance(result, dict)
        assert "gainers" in result
        assert "losers" in result
        assert isinstance(result["gainers"], list)
        assert isinstance(result["losers"], list)

    @pytest.mark.asyncio
    async def test_search_stocks_async(self, mock_trading_service):
        """Test search_stocks async execution."""
        args = SearchStocksArgs(query="Apple")
        result = await search_stocks(args)
        
        # Verify service call
        mock_trading_service.search_stocks.assert_called_once_with("Apple")
        
        # Verify response structure
        assert isinstance(result, dict)
        assert "results" in result
        assert isinstance(result["results"], list)
        
        if result["results"]:
            stock_result = result["results"][0]
            assert "symbol" in stock_result
            assert "name" in stock_result


class TestMCPMarketDataSymbolHandling:
    """Test symbol handling in market data tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for symbol testing."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_price = Mock(return_value={"symbol": "TEST", "price": 100.0})
            yield mock_service

    @pytest.mark.asyncio
    async def test_symbol_uppercase_conversion(self, mock_trading_service):
        """Test that symbols are converted to uppercase."""
        args = GetStockPriceArgs(symbol="aapl")  # lowercase
        await get_stock_price(args)
        
        # Should call service with uppercase symbol
        mock_trading_service.get_stock_price.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_symbol_whitespace_stripping(self, mock_trading_service):
        """Test that whitespace is stripped from symbols."""
        args = GetStockPriceArgs(symbol="  MSFT  ")  # with spaces
        await get_stock_price(args)
        
        # Should call service with clean symbol
        mock_trading_service.get_stock_price.assert_called_once_with("MSFT")

    @pytest.mark.asyncio
    async def test_combined_symbol_cleaning(self, mock_trading_service):
        """Test combined symbol cleaning (strip + uppercase)."""
        args = GetStockPriceArgs(symbol="  googl  ")  # lowercase with spaces
        await get_stock_price(args)
        
        # Should call service with clean, uppercase symbol
        mock_trading_service.get_stock_price.assert_called_once_with("GOOGL")

    @pytest.mark.asyncio
    async def test_search_query_cleaning(self):
        """Test that search queries are properly cleaned."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.search_stocks = Mock(return_value={"results": []})
            
            args = SearchStocksArgs(query="  Apple Inc  ")  # with spaces
            await search_stocks(args)
            
            # Should call service with stripped query (but preserve case for company names)
            mock_service.search_stocks.assert_called_once_with("Apple Inc")


class TestMCPMarketDataErrorHandling:
    """Test error handling in market data tools."""

    @pytest.mark.asyncio
    async def test_get_stock_price_error_handling(self):
        """Test error handling in get_stock_price."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_price.side_effect = Exception("Market data service unavailable")
            
            args = GetStockPriceArgs(symbol="INVALID")
            result = await get_stock_price(args)
            
            # Should return error dict, not raise
            assert isinstance(result, dict)
            assert "error" in result
            assert "Market data service unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_get_stock_info_error_handling(self):
        """Test error handling in get_stock_info."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_info.side_effect = ValueError("Invalid symbol format")
            
            args = GetStockInfoArgs(symbol="INVALID")
            result = await get_stock_info(args)
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Invalid symbol format" in result["error"]

    @pytest.mark.asyncio
    async def test_get_price_history_error_handling(self):
        """Test error handling in get_price_history."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_price_history.side_effect = RuntimeError("Database connection failed")
            
            args = GetPriceHistoryArgs(symbol="AAPL", period="week")
            result = await get_price_history(args)
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Database connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_top_movers_error_handling(self):
        """Test error handling in get_top_movers."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_top_movers.side_effect = ConnectionError("API service down")
            
            result = await get_top_movers()
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "API service down" in result["error"]

    @pytest.mark.asyncio
    async def test_search_stocks_error_handling(self):
        """Test error handling in search_stocks."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.search_stocks.side_effect = TimeoutError("Search timeout")
            
            args = SearchStocksArgs(query="Apple")
            result = await search_stocks(args)
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Search timeout" in result["error"]


class TestMCPMarketDataServiceIntegration:
    """Test integration patterns with trading service."""

    def test_trading_service_import_pattern(self):
        """Test that trading service is imported correctly."""
        import app.mcp.market_data_tools
        
        # Should import trading_service from app.services.trading_service
        source_lines = []
        import inspect
        source = inspect.getsource(app.mcp.market_data_tools)
        source_lines = source.split('\n')
        
        import_lines = [line for line in source_lines if 'trading_service' in line and 'import' in line]
        assert len(import_lines) > 0, "Should import trading_service"
        
        # Check specific import pattern
        expected_import = "from app.services.trading_service import trading_service"
        assert any(expected_import in line for line in import_lines)

    @pytest.mark.asyncio
    async def test_service_method_consistency(self):
        """Test that tools call appropriate service methods."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_price = Mock(return_value={"price": 100})
            mock_service.get_stock_info = Mock(return_value={"name": "Test"})
            mock_service.get_price_history = Mock(return_value={"data": []})
            mock_service.get_stock_news = Mock(return_value={"news": []})
            mock_service.get_top_movers = Mock(return_value={"gainers": [], "losers": []})
            mock_service.search_stocks = Mock(return_value={"results": []})
            
            # Test each tool calls appropriate service method
            await get_stock_price(GetStockPriceArgs(symbol="TEST"))
            mock_service.get_stock_price.assert_called()
            
            await get_stock_info(GetStockInfoArgs(symbol="TEST"))
            mock_service.get_stock_info.assert_called()
            
            await get_price_history(GetPriceHistoryArgs(symbol="TEST"))
            mock_service.get_price_history.assert_called()
            
            await get_stock_news(GetStockNewsArgs(symbol="TEST"))
            mock_service.get_stock_news.assert_called()
            
            await get_top_movers()
            mock_service.get_top_movers.assert_called()
            
            await search_stocks(SearchStocksArgs(query="test"))
            mock_service.search_stocks.assert_called()

    @pytest.mark.asyncio
    async def test_service_response_passthrough(self):
        """Test that service responses are passed through correctly."""
        expected_response = {
            "symbol": "AAPL",
            "price": 150.75,
            "custom_field": "test_value"
        }
        
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_price.return_value = expected_response
            
            args = GetStockPriceArgs(symbol="AAPL")
            result = await get_stock_price(args)
            
            # Should pass through the exact response
            assert result == expected_response
            assert result["custom_field"] == "test_value"


class TestMCPMarketDataConcurrency:
    """Test concurrent execution of market data tools."""

    @pytest.mark.asyncio
    async def test_concurrent_price_requests(self):
        """Test concurrent price requests for multiple symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
        
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            call_count = 0
            
            def mock_get_price(symbol):
                nonlocal call_count
                call_count += 1
                return {"symbol": symbol, "price": 100.0 + call_count}
            
            mock_service.get_stock_price.side_effect = mock_get_price
            
            # Create concurrent requests
            tasks = []
            for symbol in symbols:
                args = GetStockPriceArgs(symbol=symbol)
                task = asyncio.create_task(get_stock_price(args))
                tasks.append(task)
            
            # Wait for all to complete
            results = await asyncio.gather(*tasks)
            
            # All should complete successfully
            assert len(results) == len(symbols)
            for i, result in enumerate(results):
                assert "symbol" in result
                assert "price" in result

    @pytest.mark.asyncio
    async def test_mixed_concurrent_market_data_requests(self):
        """Test concurrent execution of different market data tools."""
        with patch('app.mcp.market_data_tools.trading_service') as mock_service:
            mock_service.get_stock_price.return_value = {"symbol": "AAPL", "price": 150.0}
            mock_service.get_stock_info.return_value = {"symbol": "GOOGL", "name": "Alphabet"}
            mock_service.get_top_movers.return_value = {"gainers": [], "losers": []}
            mock_service.search_stocks.return_value = {"results": []}
            
            # Create mixed concurrent requests
            tasks = [
                get_stock_price(GetStockPriceArgs(symbol="AAPL")),
                get_stock_info(GetStockInfoArgs(symbol="GOOGL")),
                get_top_movers(),
                search_stocks(SearchStocksArgs(query="Microsoft"))
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All should complete
            assert len(results) == 4
            assert results[0]["symbol"] == "AAPL"  # price request
            assert results[1]["name"] == "Alphabet"  # info request
            assert "gainers" in results[2]  # top movers
            assert "results" in results[3]  # search


class TestMCPMarketDataToolDocumentation:
    """Test documentation and metadata for market data tools."""

    def test_all_tools_have_docstrings(self):
        """Test all market data tools have proper docstrings."""
        import app.mcp.market_data_tools as tools
        import inspect
        
        tool_functions = [
            'get_stock_price', 'get_stock_info', 'get_price_history',
            'get_stock_news', 'get_top_movers', 'search_stocks'
        ]
        
        for func_name in tool_functions:
            func = getattr(tools, func_name)
            doc = inspect.getdoc(func)
            assert doc is not None and doc.strip(), f"{func_name} should have docstring"
            assert "TradingService" in doc, f"{func_name} should mention TradingService routing"

    def test_parameter_classes_have_descriptions(self):
        """Test parameter model classes have field descriptions."""
        from app.mcp.market_data_tools import (
            GetStockPriceArgs, GetStockInfoArgs, GetPriceHistoryArgs,
            GetStockNewsArgs, SearchStocksArgs
        )
        
        parameter_classes = [
            GetStockPriceArgs, GetStockInfoArgs, GetPriceHistoryArgs,
            GetStockNewsArgs, SearchStocksArgs
        ]
        
        for param_class in parameter_classes:
            schema = param_class.model_json_schema()
            properties = schema.get('properties', {})
            
            for field_name, field_info in properties.items():
                assert 'description' in field_info, f"{param_class.__name__}.{field_name} should have description"
                assert field_info['description'].strip(), f"{param_class.__name__}.{field_name} description should not be empty"

    def test_function_signatures_are_async(self):
        """Test that all market data functions are async."""
        import app.mcp.market_data_tools as tools
        import inspect
        
        tool_functions = [
            'get_stock_price', 'get_stock_info', 'get_price_history',
            'get_stock_news', 'get_top_movers', 'search_stocks'
        ]
        
        for func_name in tool_functions:
            func = getattr(tools, func_name)
            assert inspect.iscoroutinefunction(func), f"{func_name} should be async function"