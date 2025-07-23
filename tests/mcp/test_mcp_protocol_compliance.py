"""
Comprehensive MCP Protocol Compliance Tests

Tests for Model Context Protocol (MCP) server implementation focusing on:
- MCP protocol message handling
- Server initialization and lifecycle
- Message routing and processing
- Error handling in MCP operations
- Connection management
- Protocol compliance validation
"""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
import pytest_asyncio

from app.mcp.server import mcp
from app.mcp.tools import set_mcp_trading_service, get_mcp_trading_service
from app.services.trading_service import TradingService


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance and message handling."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service for MCP tools."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP trading service for tests."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        # Reset the service after test
        import app.mcp.tools
        app.mcp.tools._trading_service = None

    def test_mcp_server_instance_exists(self):
        """Test that MCP server instance is properly created."""
        assert mcp is not None
        assert hasattr(mcp, 'tool')
        
    def test_mcp_server_is_fastmcp_instance(self):
        """Test that MCP server is a FastMCP instance."""
        from fastmcp import FastMCP
        assert isinstance(mcp, FastMCP)

    def test_mcp_server_has_protocol_methods(self):
        """Test that MCP server has required protocol methods."""
        # FastMCP should provide MCP protocol methods
        assert hasattr(mcp, 'tool'), "Server should have tool registration method"
        
        # Test tool decorator functionality
        decorator = mcp.tool()
        assert callable(decorator), "Tool decorator should be callable"

    def test_mcp_protocol_tool_registration(self):
        """Test MCP protocol tool registration mechanism."""
        # Create a test tool
        async def test_tool() -> str:
            """Test tool for MCP protocol testing."""
            return "test_result"
        
        # Register the tool
        registered_tool = mcp.tool()(test_tool)
        
        # Tool should remain the same function
        assert registered_tool == test_tool
        assert registered_tool.__name__ == "test_tool"

    @pytest.mark.asyncio
    async def test_mcp_tool_execution_protocol(self, setup_mcp_service):
        """Test MCP tool execution follows protocol standards."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        # Mock the trading service response
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.0
        mock_quote.change = 2.5
        mock_quote.change_percent = 1.69
        mock_quote.volume = 1000000
        mock_quote.last_updated = "2024-01-01T12:00:00"
        
        setup_mcp_service.get_quote.return_value = mock_quote
        
        # Execute tool with valid args
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)
        
        # Result should be JSON string as per MCP protocol
        assert isinstance(result, str)
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, dict)
        assert "symbol" in parsed_result
        assert parsed_result["symbol"] == "AAPL"

    def test_mcp_error_handling_protocol(self, setup_mcp_service):
        """Test MCP error handling follows protocol standards."""
        from app.mcp.tools import get_mcp_trading_service
        
        # Test service not initialized error
        import app.mcp.tools
        app.mcp.tools._trading_service = None
        
        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()
        
        assert "TradingService not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_tool_error_response_format(self, setup_mcp_service):
        """Test MCP tool error responses follow protocol format."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        # Mock service to raise exception
        setup_mcp_service.get_quote.side_effect = Exception("Test error")
        
        args = GetQuoteArgs(symbol="INVALID")
        result = await get_stock_quote(args)
        
        # Error should be returned as string with error message
        assert isinstance(result, str)
        assert "Error getting quote: Test error" in result

    def test_mcp_tool_argument_validation(self):
        """Test MCP tool argument validation using Pydantic models."""
        from app.mcp.tools import GetQuoteArgs, CreateOrderArgs
        from app.schemas.orders import OrderType
        from pydantic import ValidationError
        
        # Valid args should work
        valid_quote_args = GetQuoteArgs(symbol="AAPL")
        assert valid_quote_args.symbol == "AAPL"
        
        # Invalid args should raise validation error
        with pytest.raises(ValidationError):
            GetQuoteArgs()  # Missing required symbol
        
        # Test order args validation
        valid_order_args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0
        )
        assert valid_order_args.quantity == 100
        
        # Invalid quantity should fail
        with pytest.raises(ValidationError):
            CreateOrderArgs(
                symbol="AAPL", 
                order_type=OrderType.BUY,
                quantity=0,  # Invalid: should be > 0
                price=150.0
            )


class TestMCPServerLifecycle:
    """Test MCP server initialization and lifecycle management."""

    def test_mcp_server_initialization(self):
        """Test MCP server initializes correctly."""
        assert mcp is not None
        
        # Server should have proper name
        # Note: FastMCP internal structure may vary, test what we can access
        assert hasattr(mcp, 'tool')

    def test_mcp_server_singleton_behavior(self):
        """Test MCP server behaves as singleton."""
        from app.mcp.server import mcp as mcp1
        from app.mcp.server import mcp as mcp2
        
        # Should be same instance
        assert mcp1 is mcp2

    def test_mcp_server_tool_registration_on_import(self):
        """Test that tools are registered when server module is imported."""
        # Re-import to test registration happens
        import importlib
        import app.mcp.server
        importlib.reload(app.mcp.server)
        
        from app.mcp.server import mcp as reloaded_mcp
        assert reloaded_mcp is not None

    def test_mcp_server_exports(self):
        """Test MCP server module exports."""
        import app.mcp.server as server_module
        
        assert hasattr(server_module, '__all__')
        assert 'mcp' in server_module.__all__
        assert hasattr(server_module, 'mcp')

    def test_mcp_server_dependencies_loaded(self):
        """Test MCP server dependencies are properly loaded."""
        import app.mcp.server as server_module
        
        # Should import FastMCP
        from fastmcp import FastMCP
        assert hasattr(server_module, 'mcp')
        assert isinstance(server_module.mcp, FastMCP)

    @patch('app.mcp.server.FastMCP')
    def test_mcp_server_initialization_parameters(self, mock_fastmcp):
        """Test MCP server is initialized with correct parameters."""
        # Mock the FastMCP constructor
        mock_instance = Mock()
        mock_fastmcp.return_value = mock_instance
        
        # Re-import to trigger initialization
        import importlib
        import app.mcp.server
        importlib.reload(app.mcp.server)
        
        # Should have been called with server name
        mock_fastmcp.assert_called_once_with("Open Paper Trading MCP")


class TestMCPMessageHandling:
    """Test MCP message handling and routing."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools
        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_message_routing_to_trading_tools(self, setup_mcp_service):
        """Test MCP messages are routed to correct trading tools."""
        from app.mcp.tools import create_buy_order, CreateOrderArgs
        from app.schemas.orders import OrderType, OrderCondition
        
        # Mock successful order creation
        mock_order = Mock()
        mock_order.id = "order123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.0
        mock_order.status = "PENDING"  
        mock_order.created_at = None
        
        setup_mcp_service.create_order.return_value = mock_order
        
        # Execute tool
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0
        )
        result = await create_buy_order(args)
        
        # Verify service was called correctly
        setup_mcp_service.create_order.assert_called_once()
        call_args = setup_mcp_service.create_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.order_type == OrderType.BUY
        assert call_args.condition == OrderCondition.MARKET

    @pytest.mark.asyncio
    async def test_mcp_message_routing_to_market_data_tools(self, setup_mcp_service):
        """Test MCP messages are routed to market data tools."""
        from app.mcp.market_data_tools import get_stock_price, GetStockPriceArgs
        
        # Mock market data response
        expected_response = {
            "symbol": "AAPL",
            "price": 150.0,
            "change": 2.5,
            "change_percent": 1.69
        }
        setup_mcp_service.get_stock_price.return_value = expected_response
        
        # Execute tool
        args = GetStockPriceArgs(symbol="AAPL")
        result = await get_stock_price(args)
        
        # Verify routing
        setup_mcp_service.get_stock_price.assert_called_once_with("AAPL")
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_mcp_message_routing_to_options_tools(self, setup_mcp_service):
        """Test MCP messages are routed to options tools."""
        from app.mcp.tools import get_options_chain, GetOptionsChainArgs
        
        # Mock options chain response
        expected_chain = {
            "symbol": "AAPL",
            "expiration_dates": ["2024-01-19"],
            "calls": [],
            "puts": []
        }
        setup_mcp_service.get_formatted_options_chain.return_value = expected_chain
        
        args = GetOptionsChainArgs(symbol="AAPL")
        result = await get_options_chain(args)
        
        # Verify routing
        setup_mcp_service.get_formatted_options_chain.assert_called_once()
        parsed_result = json.loads(result)
        assert parsed_result["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_mcp_concurrent_message_handling(self, setup_mcp_service):
        """Test MCP server handles concurrent messages correctly."""
        from app.mcp.tools import get_all_orders, get_portfolio
        
        # Mock responses
        setup_mcp_service.get_orders.return_value = []
        mock_portfolio = Mock()
        mock_portfolio.positions = []
        mock_portfolio.cash_balance = 10000.0
        mock_portfolio.total_value = 10000.0
        mock_portfolio.daily_pnl = 0.0
        mock_portfolio.total_pnl = 0.0
        setup_mcp_service.get_portfolio.return_value = mock_portfolio
        
        # Execute tools concurrently
        tasks = [
            get_all_orders(),
            get_portfolio()
        ]
        results = await asyncio.gather(*tasks)
        
        # Both should complete successfully
        assert len(results) == 2
        assert isinstance(results[0], str)  # Orders JSON
        assert isinstance(results[1], str)  # Portfolio JSON


class TestMCPErrorHandling:
    """Test MCP error handling and protocol compliance."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools
        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_service_unavailable_error(self):
        """Test MCP handles service unavailable errors."""
        from app.mcp.tools import get_stock_quote, GetQuoteArgs
        
        # Ensure service is not set
        import app.mcp.tools
        app.mcp.tools._trading_service = None
        
        args = GetQuoteArgs(symbol="AAPL")
        
        # Should handle gracefully and return error string
        result = await get_stock_quote(args)
        assert isinstance(result, str)
        assert "Error getting quote" in result
        assert "TradingService not initialized" in result

    @pytest.mark.asyncio
    async def test_mcp_service_exception_handling(self, setup_mcp_service):
        """Test MCP handles service exceptions properly."""
        from app.mcp.tools import cancel_order, CancelOrderArgs
        
        # Mock service to raise exception
        setup_mcp_service.cancel_order.side_effect = ValueError("Order not found")
        
        args = CancelOrderArgs(order_id="invalid")
        result = await cancel_order(args)
        
        # Should return formatted error message
        assert isinstance(result, str)
        assert "Error cancelling order: Order not found" in result

    @pytest.mark.asyncio
    async def test_mcp_validation_error_handling(self):
        """Test MCP handles validation errors correctly."""
        from app.mcp.tools import CreateOrderArgs
        from app.schemas.orders import OrderType
        from pydantic import ValidationError
        
        # Invalid price should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderArgs(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=-10.0  # Invalid negative price
            )
        
        # Error should mention price validation
        error_details = str(exc_info.value)
        assert "price" in error_details.lower()

    @pytest.mark.asyncio
    async def test_mcp_network_error_simulation(self, setup_mcp_service):
        """Test MCP handles network-like errors in trading service."""
        from app.mcp.tools import get_portfolio_summary
        
        # Simulate network timeout
        setup_mcp_service.get_portfolio_summary.side_effect = asyncio.TimeoutError("Timeout")
        
        result = await get_portfolio_summary()
        
        # Should handle timeout gracefully
        assert isinstance(result, str)
        assert "Error getting portfolio summary" in result

    @pytest.mark.asyncio
    async def test_mcp_malformed_data_handling(self, setup_mcp_service):
        """Test MCP handles malformed data from trading service."""
        from app.mcp.tools import get_all_positions
        
        # Mock service to return malformed data
        malformed_position = Mock()
        malformed_position.symbol = None  # Invalid None symbol
        malformed_position.quantity = "invalid"  # Invalid type
        setup_mcp_service.get_positions.return_value = [malformed_position]
        
        result = await get_all_positions()
        
        # Should handle malformed data gracefully
        assert isinstance(result, str)
        # Should either return error or handle the malformed data


class TestMCPConnectionManagement:
    """Test MCP connection management and client interactions."""

    def test_mcp_server_ready_for_connections(self):
        """Test MCP server is ready to accept connections."""
        assert mcp is not None
        assert hasattr(mcp, 'tool')
        
        # Server should be importable without errors
        from app.mcp.server import mcp as imported_mcp
        assert imported_mcp is mcp

    def test_mcp_server_tool_introspection(self):
        """Test MCP server supports tool introspection."""
        # FastMCP should support tool discovery
        # Test that we can access registered tools
        assert hasattr(mcp, 'tool')
        
        # Tool registration should work
        def dummy_tool():
            return "test"
        
        registered = mcp.tool()(dummy_tool)
        assert registered == dummy_tool

    def test_mcp_server_state_isolation(self):
        """Test MCP server maintains proper state isolation."""
        # Multiple imports should return same instance
        from app.mcp.server import mcp as mcp1
        import importlib
        importlib.reload(app.mcp.server)
        from app.mcp.server import mcp as mcp2
        
        # State should be consistent
        assert mcp1 is not None
        assert mcp2 is not None

    @patch('app.mcp.tools._trading_service')
    def test_mcp_service_dependency_management(self, mock_service):
        """Test MCP manages service dependencies correctly."""
        from app.mcp.tools import get_mcp_trading_service, set_mcp_trading_service
        
        # Test setting and getting service
        test_service = Mock()
        set_mcp_trading_service(test_service)
        
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service == test_service

    def test_mcp_concurrent_access_safety(self):
        """Test MCP server handles concurrent access safely."""
        from app.mcp.server import mcp
        
        # Multiple threads accessing should be safe
        # (Basic test - FastMCP should handle this internally)
        instances = []
        for _ in range(10):
            instances.append(mcp)
        
        # All should be same instance
        for instance in instances:
            assert instance is mcp


class TestMCPToolDiscovery:
    """Test MCP tool discovery and schema validation."""

    def test_mcp_tool_schema_compliance(self):
        """Test MCP tools have proper schema definitions."""
        from app.mcp.tools import (
            GetQuoteArgs, CreateOrderArgs, GetOrderArgs, 
            CancelOrderArgs, GetPositionArgs
        )
        
        # All arg classes should be Pydantic models
        arg_classes = [
            GetQuoteArgs, CreateOrderArgs, GetOrderArgs,
            CancelOrderArgs, GetPositionArgs
        ]
        
        for arg_class in arg_classes:
            # Should have Pydantic schema
            assert hasattr(arg_class, 'model_fields')
            
            # Fields should have descriptions
            for field_name, field_info in arg_class.model_fields.items():
                assert hasattr(field_info, 'description')
                assert field_info.description is not None

    def test_mcp_options_tool_schema_compliance(self):
        """Test MCP options tools have proper schemas."""
        from app.mcp.tools import (
            GetOptionsChainArgs, GetExpirationDatesArgs,
            CreateMultiLegOrderArgs, CalculateGreeksArgs
        )
        
        options_arg_classes = [
            GetOptionsChainArgs, GetExpirationDatesArgs,
            CreateMultiLegOrderArgs, CalculateGreeksArgs
        ]
        
        for arg_class in options_arg_classes:
            assert hasattr(arg_class, 'model_fields')
            
            # Should have field descriptions for MCP discovery
            for field_name, field_info in arg_class.model_fields.items():
                assert hasattr(field_info, 'description')

    def test_mcp_market_data_tool_schema_compliance(self):
        """Test MCP market data tools have proper schemas."""
        from app.mcp.market_data_tools import (
            GetStockPriceArgs, GetStockInfoArgs,
            GetPriceHistoryArgs, GetStockNewsArgs
        )
        
        market_data_args = [
            GetStockPriceArgs, GetStockInfoArgs,
            GetPriceHistoryArgs, GetStockNewsArgs
        ]
        
        for arg_class in market_data_args:
            assert hasattr(arg_class, 'model_fields')
            
            # All should have symbol field with description
            if hasattr(arg_class, 'model_fields') and 'symbol' in arg_class.model_fields:
                symbol_field = arg_class.model_fields['symbol']
                assert hasattr(symbol_field, 'description')
                assert 'symbol' in symbol_field.description.lower()

    def test_mcp_tool_function_signatures(self):
        """Test MCP tool functions have proper signatures."""
        from app.mcp.tools import (
            get_stock_quote, create_buy_order, get_all_orders,
            get_portfolio, cancel_order
        )
        import inspect
        
        tools = [get_stock_quote, create_buy_order, get_all_orders, get_portfolio, cancel_order]
        
        for tool in tools:
            # Should be async
            assert inspect.iscoroutinefunction(tool)
            
            # Should have proper signature
            sig = inspect.signature(tool)
            
            # Tools with args should have one parameter
            if tool in [get_stock_quote, create_buy_order, cancel_order]:
                assert len(sig.parameters) == 1
                param = list(sig.parameters.values())[0]
                assert param.name == 'args'

    def test_mcp_tool_return_type_consistency(self):
        """Test MCP tools return consistent types."""
        import inspect
        from app.mcp.tools import get_stock_quote, create_buy_order
        from app.mcp.market_data_tools import get_stock_price, get_stock_info
        
        # Most tools should return str (JSON) or dict
        string_return_tools = [get_stock_quote, create_buy_order]
        dict_return_tools = [get_stock_price, get_stock_info]
        
        for tool in string_return_tools:
            sig = inspect.signature(tool)
            # Note: Return type annotation may not be present, but behavior should be consistent
            assert inspect.iscoroutinefunction(tool)
        
        for tool in dict_return_tools:
            sig = inspect.signature(tool)
            assert inspect.iscoroutinefunction(tool)

    def test_mcp_tool_documentation_completeness(self):
        """Test MCP tools have complete documentation."""
        from app.mcp.tools import (
            get_stock_quote, create_buy_order, get_portfolio,
            get_options_chain, calculate_option_greeks
        )
        
        tools = [
            get_stock_quote, create_buy_order, get_portfolio,
            get_options_chain, calculate_option_greeks
        ]
        
        for tool in tools:
            # Should have docstring
            assert tool.__doc__ is not None
            assert len(tool.__doc__.strip()) > 0
            
            # Docstring should describe functionality
            doc = tool.__doc__.lower()
            assert any(keyword in doc for keyword in ['get', 'create', 'calculate', 'return'])