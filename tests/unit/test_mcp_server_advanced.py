"""
Advanced unit tests for MCP server implementation.

Tests MCP server lifecycle, tool registration, protocol compliance,
and FastMCP integration patterns in the paper trading platform.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Any, Dict

import pytest
import pytest_asyncio

from app.mcp.server import mcp
from app.services.trading_service import TradingService


class TestMCPServerLifecycle:
    """Test MCP server lifecycle management."""

    def test_mcp_server_initialization(self):
        """Test MCP server is properly initialized."""
        assert mcp is not None
        assert hasattr(mcp, 'name')
        assert mcp.name == "Open Paper Trading MCP"
        assert hasattr(mcp, 'tool')

    def test_mcp_server_instance_type(self):
        """Test MCP server is proper FastMCP instance."""
        from fastmcp import FastMCP
        assert isinstance(mcp, FastMCP)

    def test_mcp_server_has_tool_decorator(self):
        """Test MCP server has tool decorator functionality."""
        assert callable(mcp.tool)
        # Test decorator can be called
        decorated = mcp.tool()
        assert callable(decorated)

    @patch('app.mcp.server.FastMCP')
    def test_mcp_server_creation_with_name(self, mock_fastmcp):
        """Test MCP server is created with correct name."""
        mock_instance = Mock()
        mock_fastmcp.return_value = mock_instance
        
        # Re-import to trigger creation with mocked FastMCP
        import importlib
        import app.mcp.server
        importlib.reload(app.mcp.server)
        
        mock_fastmcp.assert_called_with("Open Paper Trading MCP")


class TestMCPToolRegistration:
    """Test MCP tool registration and validation."""

    def test_all_tools_imported(self):
        """Test all expected tools are imported in server module."""
        from app.mcp import server
        
        # Core trading tools
        assert hasattr(server, 'get_stock_quote')
        assert hasattr(server, 'create_buy_order')
        assert hasattr(server, 'create_sell_order')
        assert hasattr(server, 'cancel_order')
        assert hasattr(server, 'get_all_orders')
        assert hasattr(server, 'get_order')
        
        # Portfolio tools
        assert hasattr(server, 'get_portfolio')
        assert hasattr(server, 'get_portfolio_summary')
        assert hasattr(server, 'get_all_positions')
        assert hasattr(server, 'get_position')
        
        # Options tools
        assert hasattr(server, 'get_options_chain')
        assert hasattr(server, 'get_expiration_dates')
        assert hasattr(server, 'create_multi_leg_order')
        assert hasattr(server, 'calculate_option_greeks')
        assert hasattr(server, 'get_strategy_analysis')
        assert hasattr(server, 'simulate_option_expiration')
        assert hasattr(server, 'find_tradable_options')
        assert hasattr(server, 'get_option_market_data')
        
        # Market data tools
        assert hasattr(server, 'get_stock_price')
        assert hasattr(server, 'get_stock_info')
        assert hasattr(server, 'get_price_history')
        assert hasattr(server, 'get_stock_news')
        assert hasattr(server, 'get_top_movers')
        assert hasattr(server, 'search_stocks')

    def test_tools_are_callable(self):
        """Test all imported tools are callable functions."""
        from app.mcp import server
        
        tool_functions = [
            'get_stock_quote', 'create_buy_order', 'create_sell_order',
            'cancel_order', 'get_all_orders', 'get_order',
            'get_portfolio', 'get_portfolio_summary', 'get_all_positions',
            'get_position', 'get_options_chain', 'get_expiration_dates',
            'create_multi_leg_order', 'calculate_option_greeks',
            'get_strategy_analysis', 'simulate_option_expiration',
            'find_tradable_options', 'get_option_market_data',
            'get_stock_price', 'get_stock_info', 'get_price_history',
            'get_stock_news', 'get_top_movers', 'search_stocks'
        ]
        
        for tool_name in tool_functions:
            tool_func = getattr(server, tool_name)
            assert callable(tool_func), f"{tool_name} should be callable"

    @patch('app.mcp.server.mcp')
    def test_tool_registration_calls(self, mock_mcp):
        """Test that tools are registered with MCP server."""
        mock_mcp.tool.return_value = lambda x: x  # Mock decorator
        
        # Re-import to trigger registration
        import importlib
        import app.mcp.server
        importlib.reload(app.mcp.server)
        
        # Should have been called multiple times for tool registration
        assert mock_mcp.tool.call_count > 20  # We have 20+ tools

    def test_no_duplicate_tool_names(self):
        """Test there are no duplicate tool registrations."""
        from app.mcp import server
        
        # Get all function names that would be registered as tools
        tool_names = []
        for attr_name in dir(server):
            attr = getattr(server, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                if hasattr(attr, '__module__') and 'mcp' in attr.__module__:
                    tool_names.append(attr_name)
        
        # Check for duplicates
        unique_names = set(tool_names)
        assert len(tool_names) == len(unique_names), "No duplicate tool names allowed"


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance and message handling."""

    @pytest_asyncio.fixture
    async def mock_mcp_context(self):
        """Create a mock MCP execution context."""
        context = Mock()
        context.session = Mock()
        context.request_id = "test-request-123"
        context.client_info = {"name": "test-client", "version": "1.0.0"}
        return context

    @pytest.mark.asyncio
    async def test_mcp_tool_execution_pattern(self, mock_mcp_context):
        """Test MCP tools follow proper execution patterns."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        # Mock the trading service
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_quote.return_value = Mock(
                symbol="AAPL",
                price=150.00,
                change=1.50,
                change_percent=1.0,
                volume=1000000,
                last_updated=Mock(isoformat=Mock(return_value="2024-01-01T12:00:00Z"))
            )
            mock_get_service.return_value = mock_service
            
            # Test tool execution
            args = GetQuoteArgs(symbol="AAPL")
            result = await get_stock_quote(args)
            
            # Should return JSON string
            assert isinstance(result, str)
            assert "AAPL" in result
            assert "150.0" in result

    @pytest.mark.asyncio
    async def test_mcp_tool_error_handling(self, mock_mcp_context):
        """Test MCP tools handle errors gracefully."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_quote.side_effect = Exception("Market data unavailable")
            mock_get_service.return_value = mock_service
            
            args = GetQuoteArgs(symbol="INVALID")
            result = await get_stock_quote(args)
            
            # Should return error message, not raise exception
            assert isinstance(result, str)
            assert "Error getting quote" in result
            assert "Market data unavailable" in result

    def test_mcp_tool_parameter_validation(self):
        """Test MCP tool parameter models validate correctly."""
        from app.mcp.tools import GetQuoteArgs, CreateOrderArgs
        from app.schemas.orders import OrderType
        
        # Valid parameters
        quote_args = GetQuoteArgs(symbol="AAPL")
        assert quote_args.symbol == "AAPL"
        
        order_args = CreateOrderArgs(
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=100,
            price=2000.50
        )
        assert order_args.symbol == "GOOGL"
        assert order_args.quantity == 100
        
        # Invalid parameters should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            CreateOrderArgs(
                symbol="GOOGL",
                order_type=OrderType.BUY,
                quantity=-100,  # Invalid negative quantity
                price=2000.50
            )


class TestMCPServiceIntegration:
    """Test MCP server integration with TradingService."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create a mock trading service for testing."""
        service = AsyncMock(spec=TradingService)
        service.get_quote = AsyncMock()
        service.create_order = AsyncMock()
        service.get_orders = AsyncMock()
        service.get_portfolio = AsyncMock()
        service.get_positions = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_mcp_trading_service_dependency_injection(self, mock_trading_service):
        """Test MCP tools receive TradingService dependency."""
        from app.mcp.tools import set_mcp_trading_service, get_mcp_trading_service
        
        # Set the trading service
        set_mcp_trading_service(mock_trading_service)
        
        # Get should return the same instance
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service == mock_trading_service

    def test_mcp_trading_service_not_initialized_error(self):
        """Test error when trading service is not initialized."""
        from app.mcp.tools import _trading_service, get_mcp_trading_service
        
        # Clear the global service
        import app.mcp.tools
        app.mcp.tools._trading_service = None
        
        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()
        
        assert "TradingService not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_async_pattern_consistency(self):
        """Test MCP tools follow consistent async patterns."""
        from app.mcp import tools
        import inspect
        
        # Get all MCP tool functions
        tool_functions = []
        for name in dir(tools):
            obj = getattr(tools, name)
            if (callable(obj) and 
                not name.startswith('_') and 
                name not in ['set_mcp_trading_service', 'get_mcp_trading_service']):
                tool_functions.append((name, obj))
        
        # All tool functions should be async
        for name, func in tool_functions:
            if name.endswith('Args') or name in ['get_mcp_trading_service', 'set_mcp_trading_service']:
                continue  # Skip parameter classes and utility functions
                
            assert inspect.iscoroutinefunction(func), f"{name} should be async"


class TestMCPErrorHandlingPatterns:
    """Test error handling patterns in MCP implementation."""

    @pytest.mark.asyncio
    async def test_mcp_tool_exception_to_string_pattern(self):
        """Test MCP tools convert exceptions to error strings."""
        from app.mcp.tools import create_buy_order, CreateOrderArgs
        from app.schemas.orders import OrderType
        
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.create_order.side_effect = ValueError("Invalid order data")
            mock_get_service.return_value = mock_service
            
            args = CreateOrderArgs(
                symbol="TEST",
                order_type=OrderType.BUY,
                quantity=100,
                price=50.0
            )
            
            result = await create_buy_order(args)
            
            # Should return error string, not raise
            assert isinstance(result, str)
            assert "Error creating buy order" in result
            assert "Invalid order data" in result

    @pytest.mark.asyncio
    async def test_mcp_json_serialization_error_handling(self):
        """Test MCP tools handle JSON serialization errors."""
        from app.mcp.tools import get_portfolio
        
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            mock_service = AsyncMock()
            # Create a mock portfolio with non-serializable object
            mock_portfolio = Mock()
            mock_portfolio.positions = []
            mock_portfolio.cash_balance = 10000.0
            mock_portfolio.total_value = 10000.0
            mock_portfolio.daily_pnl = 0.0
            mock_portfolio.total_pnl = 0.0
            
            # Add datetime that might cause serialization issues
            import datetime
            mock_portfolio.non_serializable = datetime.datetime.now()
            
            mock_service.get_portfolio.return_value = mock_portfolio
            mock_get_service.return_value = mock_service
            
            # Should handle the error gracefully
            result = await get_portfolio()
            assert isinstance(result, str)


class TestMCPToolDocumentation:
    """Test MCP tool documentation and metadata."""

    def test_all_tools_have_docstrings(self):
        """Test all MCP tools have proper docstrings."""
        from app.mcp import tools
        import inspect
        
        tool_functions = [
            'get_stock_quote', 'create_buy_order', 'create_sell_order',
            'cancel_order', 'get_all_orders', 'get_order',
            'get_portfolio', 'get_portfolio_summary', 'get_all_positions',
            'get_position', 'get_options_chain', 'get_expiration_dates',
            'create_multi_leg_order', 'calculate_option_greeks',
            'get_strategy_analysis', 'simulate_option_expiration',
            'find_tradable_options', 'get_option_market_data'
        ]
        
        for func_name in tool_functions:
            func = getattr(tools, func_name)
            doc = inspect.getdoc(func)
            assert doc is not None and doc.strip(), f"{func_name} should have docstring"

    def test_deprecated_tools_marked(self):
        """Test deprecated tools are properly marked."""
        from app.mcp.tools import get_stock_quote
        import inspect
        
        doc = inspect.getdoc(get_stock_quote)
        assert "[DEPRECATED]" in doc, "Deprecated tools should be marked in docstring"

    def test_parameter_classes_have_field_descriptions(self):
        """Test parameter model classes have field descriptions."""
        from app.mcp.tools import GetQuoteArgs, CreateOrderArgs
        
        # Check GetQuoteArgs
        schema = GetQuoteArgs.model_json_schema()
        properties = schema.get('properties', {})
        for field_name, field_info in properties.items():
            assert 'description' in field_info, f"{field_name} should have description"
            assert field_info['description'].strip(), f"{field_name} description should not be empty"
        
        # Check CreateOrderArgs
        schema = CreateOrderArgs.model_json_schema()
        properties = schema.get('properties', {})
        for field_name, field_info in properties.items():
            assert 'description' in field_info, f"{field_name} should have description"


class TestMCPConcurrencyHandling:
    """Test MCP server handles concurrent requests properly."""

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self):
        """Test MCP tools can handle concurrent execution."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_quote.return_value = Mock(
                symbol="AAPL",
                price=150.00,
                change=1.50,
                change_percent=1.0,
                volume=1000000,
                last_updated=Mock(isoformat=Mock(return_value="2024-01-01T12:00:00Z"))
            )
            mock_get_service.return_value = mock_service
            
            # Create multiple concurrent requests
            tasks = []
            symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
            
            for symbol in symbols:
                args = GetQuoteArgs(symbol=symbol)
                task = asyncio.create_task(get_stock_quote(args))
                tasks.append(task)
            
            # Wait for all to complete
            results = await asyncio.gather(*tasks)
            
            # All should complete successfully
            assert len(results) == len(symbols)
            for result in results:
                assert isinstance(result, str)
                assert "price" in result

    @pytest.mark.asyncio
    async def test_mcp_tool_session_isolation(self):
        """Test MCP tools maintain proper session isolation."""
        from app.mcp.tools import create_buy_order, CreateOrderArgs
        from app.schemas.orders import OrderType
        
        # This test ensures that concurrent tool calls don't interfere
        # with each other's database sessions or state
        with patch('app.mcp.tools.get_mcp_trading_service') as mock_get_service:
            call_count = 0
            
            async def mock_create_order(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)  # Simulate async operation
                return Mock(
                    id=f"order-{call_count}",
                    symbol="TEST",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=50.0,
                    status="pending",
                    created_at=Mock(isoformat=Mock(return_value="2024-01-01T12:00:00Z"))
                )
            
            mock_service = AsyncMock()
            mock_service.create_order = mock_create_order
            mock_get_service.return_value = mock_service
            
            # Create multiple concurrent orders
            args = CreateOrderArgs(
                symbol="TEST",
                order_type=OrderType.BUY,
                quantity=100,
                price=50.0
            )
            
            tasks = [create_buy_order(args) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            # All should complete successfully
            assert len(results) == 5
            for result in results:
                assert isinstance(result, str)
                assert "order-" in result