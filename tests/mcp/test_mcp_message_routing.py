"""
MCP Message Handling and Routing Tests

Tests for Model Context Protocol message handling, routing, and client interactions.
Focuses on message processing, tool invocation, and response formatting.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.mcp.server import mcp
from app.mcp.tools import set_mcp_trading_service
from app.services.trading_service import TradingService


class TestMCPMessageRouting:
    """Test MCP message routing to appropriate tools."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service for tests."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        # Cleanup
        import app.mcp.tools

        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_route_to_stock_quote_tool(self, setup_mcp_service):
        """Test MCP routes messages to stock quote tool."""
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        # Mock service response
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.0
        mock_quote.change = 2.5
        mock_quote.change_percent = 1.69
        mock_quote.volume = 50000000
        mock_quote.last_updated = datetime.now()

        setup_mcp_service.get_quote.return_value = mock_quote

        # Route message to tool
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Verify routing and response
        setup_mcp_service.get_quote.assert_called_once_with("AAPL")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["symbol"] == "AAPL"
        assert parsed["price"] == 150.0

    @pytest.mark.asyncio
    async def test_mcp_route_to_order_creation_tool(self, setup_mcp_service):
        """Test MCP routes messages to order creation tools."""
        from app.mcp.tools import CreateOrderArgs, create_buy_order
        from app.schemas.orders import OrderCondition, OrderType

        # Mock order response
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.0
        mock_order.status = "PENDING"
        mock_order.created_at = datetime.now()

        setup_mcp_service.create_order.return_value = mock_order

        # Route message
        args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        result = await create_buy_order(args)

        # Verify routing
        setup_mcp_service.create_order.assert_called_once()
        call_args = setup_mcp_service.create_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.order_type == OrderType.BUY
        assert call_args.condition == OrderCondition.MARKET

        # Verify response
        parsed = json.loads(result)
        assert parsed["id"] == "order_123"
        assert parsed["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_mcp_route_to_portfolio_tools(self, setup_mcp_service):
        """Test MCP routes messages to portfolio management tools."""
        from app.mcp.tools import get_portfolio, get_portfolio_summary

        # Mock portfolio data
        mock_portfolio = Mock()
        mock_portfolio.positions = []
        mock_portfolio.cash_balance = 10000.0
        mock_portfolio.total_value = 15000.0
        mock_portfolio.daily_pnl = 500.0
        mock_portfolio.total_pnl = 2000.0

        mock_summary = Mock()
        mock_summary.total_value = 15000.0
        mock_summary.cash_balance = 10000.0
        mock_summary.invested_value = 5000.0
        mock_summary.daily_pnl = 500.0
        mock_summary.daily_pnl_percent = 3.33
        mock_summary.total_pnl = 2000.0
        mock_summary.total_pnl_percent = 15.38

        setup_mcp_service.get_portfolio.return_value = mock_portfolio
        setup_mcp_service.get_portfolio_summary.return_value = mock_summary

        # Test portfolio routing
        portfolio_result = await get_portfolio()
        parsed_portfolio = json.loads(portfolio_result)
        assert parsed_portfolio["cash_balance"] == 10000.0
        assert parsed_portfolio["total_value"] == 15000.0

        # Test portfolio summary routing
        summary_result = await get_portfolio_summary()
        parsed_summary = json.loads(summary_result)
        assert parsed_summary["total_value"] == 15000.0
        assert parsed_summary["total_pnl_percent"] == 15.38

    @pytest.mark.asyncio
    async def test_mcp_route_to_market_data_tools(self, setup_mcp_service):
        """Test MCP routes messages to market data tools."""
        from app.mcp.market_data_tools import (
            GetStockInfoArgs,
            GetStockPriceArgs,
            get_stock_info,
            get_stock_price,
        )

        # Mock market data responses
        price_response = {
            "symbol": "AAPL",
            "price": 150.0,
            "change": 2.5,
            "change_percent": 1.69,
            "volume": 50000000,
        }

        info_response = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "market_cap": 2500000000000,
            "pe_ratio": 25.5,
            "dividend_yield": 0.5,
        }

        setup_mcp_service.get_stock_price.return_value = price_response
        setup_mcp_service.get_stock_info.return_value = info_response

        # Test price routing
        price_args = GetStockPriceArgs(symbol="AAPL")
        price_result = await get_stock_price(price_args)
        assert price_result["symbol"] == "AAPL"
        assert price_result["price"] == 150.0

        # Test info routing
        info_args = GetStockInfoArgs(symbol="AAPL")
        info_result = await get_stock_info(info_args)
        assert info_result["company_name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_mcp_route_to_options_tools(self, setup_mcp_service):
        """Test MCP routes messages to options trading tools."""
        from app.mcp.tools import (
            CalculateGreeksArgs,
            GetOptionsChainArgs,
            calculate_option_greeks,
            get_options_chain,
        )

        # Mock options data
        options_chain = {
            "symbol": "AAPL",
            "expiration_dates": ["2024-01-19", "2024-02-16"],
            "calls": [{"strike": 150.0, "bid": 5.0, "ask": 5.5, "volume": 1000}],
            "puts": [],
        }

        greeks_data = {
            "delta": 0.65,
            "gamma": 0.02,
            "theta": -0.05,
            "vega": 0.15,
            "rho": 0.08,
        }

        setup_mcp_service.get_formatted_options_chain.return_value = options_chain
        setup_mcp_service.calculate_greeks.return_value = greeks_data

        # Test options chain routing
        chain_args = GetOptionsChainArgs(symbol="AAPL")
        chain_result = await get_options_chain(chain_args)
        parsed_chain = json.loads(chain_result)
        assert parsed_chain["symbol"] == "AAPL"
        assert len(parsed_chain["expiration_dates"]) == 2

        # Test Greeks calculation routing
        greeks_args = CalculateGreeksArgs(option_symbol="AAPL240119C00150000")
        greeks_result = await calculate_option_greeks(greeks_args)
        parsed_greeks = json.loads(greeks_result)
        assert parsed_greeks["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_mcp_concurrent_message_routing(self, setup_mcp_service):
        """Test MCP handles concurrent message routing correctly."""
        from app.mcp.market_data_tools import GetStockPriceArgs, get_stock_price
        from app.mcp.tools import get_all_orders, get_all_positions

        # Mock concurrent responses
        setup_mcp_service.get_orders.return_value = []
        setup_mcp_service.get_positions.return_value = []
        setup_mcp_service.get_stock_price.return_value = {
            "symbol": "AAPL",
            "price": 150.0,
        }

        # Execute tools concurrently
        tasks = [
            get_all_orders(),
            get_all_positions(),
            get_stock_price(GetStockPriceArgs(symbol="AAPL")),
        ]

        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 3
        assert isinstance(results[0], str)  # Orders JSON
        assert isinstance(results[1], str)  # Positions JSON
        assert isinstance(results[2], dict)  # Price dict


class TestMCPMessageProcessing:
    """Test MCP message processing and validation."""

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

    def test_mcp_message_argument_validation(self):
        """Test MCP validates message arguments correctly."""
        from pydantic import ValidationError

        from app.mcp.tools import CreateOrderArgs, GetQuoteArgs
        from app.schemas.orders import OrderType

        # Valid arguments should pass
        valid_quote = GetQuoteArgs(symbol="AAPL")
        assert valid_quote.symbol == "AAPL"

        valid_order = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        assert valid_order.quantity == 100

        # Invalid arguments should fail
        with pytest.raises(ValidationError):
            GetQuoteArgs()  # Missing symbol

        with pytest.raises(ValidationError):
            CreateOrderArgs(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=-100,  # Invalid negative quantity
                price=150.0,
            )

    @pytest.mark.asyncio
    async def test_mcp_message_response_formatting(self, setup_mcp_service):
        """Test MCP formats responses correctly."""
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        # Mock quote response
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.0
        mock_quote.change = 2.5
        mock_quote.change_percent = 1.69
        mock_quote.volume = 50000000
        mock_quote.last_updated = datetime(2024, 1, 1, 12, 0, 0)

        setup_mcp_service.get_quote.return_value = mock_quote

        # Execute and verify response format
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Should be JSON string
        assert isinstance(result, str)

        # Should parse to valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

        # Should have expected fields
        expected_fields = [
            "symbol",
            "price",
            "change",
            "change_percent",
            "volume",
            "last_updated",
        ]
        for field in expected_fields:
            assert field in parsed

        # Should have correct types
        assert isinstance(parsed["symbol"], str)
        assert isinstance(parsed["price"], int | float)
        assert isinstance(parsed["volume"], int)

    @pytest.mark.asyncio
    async def test_mcp_message_error_response_formatting(self, setup_mcp_service):
        """Test MCP formats error responses correctly."""
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        # Mock service error
        setup_mcp_service.get_quote.side_effect = ValueError("Invalid symbol")

        args = GetQuoteArgs(symbol="INVALID")
        result = await get_stock_quote(args)

        # Should be error string
        assert isinstance(result, str)
        assert "Error getting quote: Invalid symbol" in result

    def test_mcp_message_field_descriptions(self):
        """Test MCP message fields have proper descriptions."""
        from app.mcp.tools import CreateOrderArgs, GetQuoteArgs

        # Check quote args descriptions
        quote_fields = GetQuoteArgs.model_fields
        assert "symbol" in quote_fields
        symbol_field = quote_fields["symbol"]
        assert hasattr(symbol_field, "description")
        assert "symbol" in symbol_field.description.lower()

        # Check order args descriptions
        order_fields = CreateOrderArgs.model_fields
        for field_name in ["symbol", "order_type", "quantity", "price"]:
            assert field_name in order_fields
            field_info = order_fields[field_name]
            assert hasattr(field_info, "description")
            assert field_info.description is not None

    @pytest.mark.asyncio
    async def test_mcp_message_processing_async_flow(self, setup_mcp_service):
        """Test MCP message processing in async context."""
        from app.mcp.tools import CreateOrderArgs, create_sell_order
        from app.schemas.orders import OrderType

        # Mock async order creation
        mock_order = AsyncMock()
        mock_order.id = "sell_order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 50
        mock_order.price = 155.0
        mock_order.status = "PENDING"
        mock_order.created_at = datetime.now()

        setup_mcp_service.create_order.return_value = mock_order

        # Process message asynchronously
        args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.SELL, quantity=50, price=155.0
        )

        result = await create_sell_order(args)

        # Verify async processing
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["id"] == "sell_order_123"
        assert parsed["order_type"] == OrderType.SELL


class TestMCPClientInteractions:
    """Test MCP client interactions and communication patterns."""

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

    def test_mcp_client_tool_discovery(self):
        """Test MCP supports client tool discovery."""
        # Client should be able to discover available tools
        from app.mcp.market_data_tools import (
            get_price_history,
            get_stock_info,
            get_stock_price,
        )
        from app.mcp.tools import (
            cancel_order,
            create_buy_order,
            create_sell_order,
            get_all_orders,
            get_portfolio,
            get_stock_quote,
        )

        # All tools should be discoverable functions
        trading_tools = [
            get_stock_quote,
            create_buy_order,
            create_sell_order,
            get_portfolio,
            get_all_orders,
            cancel_order,
        ]

        market_tools = [get_stock_price, get_stock_info, get_price_history]

        all_tools = trading_tools + market_tools

        for tool in all_tools:
            assert callable(tool)
            assert hasattr(tool, "__name__")
            assert hasattr(tool, "__doc__")
            assert tool.__doc__ is not None

    def test_mcp_client_tool_schema_introspection(self):
        """Test MCP supports client tool schema introspection."""
        from app.mcp.market_data_tools import GetStockPriceArgs
        from app.mcp.tools import CreateOrderArgs, GetQuoteArgs

        # Clients should be able to introspect argument schemas
        arg_models = [GetQuoteArgs, CreateOrderArgs, GetStockPriceArgs]

        for model in arg_models:
            # Should have Pydantic model fields
            assert hasattr(model, "model_fields")

            # Should have JSON schema
            schema = model.model_json_schema()
            assert isinstance(schema, dict)
            assert "properties" in schema

            # Properties should have descriptions
            for _prop_name, prop_info in schema["properties"].items():
                assert "description" in prop_info

    @pytest.mark.asyncio
    async def test_mcp_client_session_management(self, setup_mcp_service):
        """Test MCP supports client session management."""
        from app.mcp.tools import get_all_positions, get_portfolio

        # Mock portfolio data
        mock_portfolio = Mock()
        mock_portfolio.positions = []
        mock_portfolio.cash_balance = 10000.0
        mock_portfolio.total_value = 10000.0
        mock_portfolio.daily_pnl = 0.0
        mock_portfolio.total_pnl = 0.0

        mock_positions = []

        setup_mcp_service.get_portfolio.return_value = mock_portfolio
        setup_mcp_service.get_positions.return_value = mock_positions

        # Client should be able to make multiple requests in sequence
        portfolio_result = await get_portfolio()
        positions_result = await get_all_positions()

        # Both should succeed
        assert isinstance(portfolio_result, str)
        assert isinstance(positions_result, str)

        # Should maintain state consistency
        parsed_portfolio = json.loads(portfolio_result)
        parsed_positions = json.loads(positions_result)

        assert parsed_portfolio["cash_balance"] == 10000.0
        assert isinstance(parsed_positions, list)

    @pytest.mark.asyncio
    async def test_mcp_client_error_handling(self, setup_mcp_service):
        """Test MCP provides appropriate error responses to clients."""
        from app.mcp.tools import GetOrderArgs, get_order

        # Mock service error
        setup_mcp_service.get_order.side_effect = ValueError("Order not found")

        args = GetOrderArgs(order_id="nonexistent")
        result = await get_order(args)

        # Client should receive formatted error message
        assert isinstance(result, str)
        assert "Error getting order" in result
        assert "Order not found" in result

    @pytest.mark.asyncio
    async def test_mcp_client_data_consistency(self, setup_mcp_service):
        """Test MCP maintains data consistency for clients."""
        from app.mcp.tools import CreateOrderArgs, create_buy_order, get_all_orders
        from app.schemas.orders import OrderType

        # Mock order creation and retrieval
        created_order = Mock()
        created_order.id = "consistent_order_123"
        created_order.symbol = "AAPL"
        created_order.order_type = OrderType.BUY
        created_order.quantity = 100
        created_order.price = 150.0
        created_order.status = "PENDING"
        created_order.created_at = datetime.now()

        order_list = [created_order]

        setup_mcp_service.create_order.return_value = created_order
        setup_mcp_service.get_orders.return_value = order_list

        # Create order
        create_args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        create_result = await create_buy_order(create_args)

        # Get orders
        orders_result = await get_all_orders()

        # Data should be consistent
        created_order_data = json.loads(create_result)
        orders_list = json.loads(orders_result)

        assert created_order_data["id"] == "consistent_order_123"
        assert len(orders_list) == 1
        assert orders_list[0]["id"] == "consistent_order_123"

    def test_mcp_client_protocol_compliance(self):
        """Test MCP server is compliant with client protocol expectations."""

        # Server should be FastMCP instance
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)

        # Should have tool registration capability
        assert hasattr(mcp, "tool")
        assert callable(mcp.tool())

        # Should support MCP protocol methods expected by clients
        # (Specific protocol methods depend on FastMCP implementation)
        assert mcp is not None

    @pytest.mark.asyncio
    async def test_mcp_client_streaming_responses(self, setup_mcp_service):
        """Test MCP handles client streaming response patterns."""
        from app.mcp.market_data_tools import GetPriceHistoryArgs, get_price_history

        # Mock historical data (simulating streaming-like response)
        history_data = {
            "symbol": "AAPL",
            "period": "week",
            "data": [
                {"date": "2024-01-01", "price": 145.0},
                {"date": "2024-01-02", "price": 147.0},
                {"date": "2024-01-03", "price": 150.0},
            ],
        }

        setup_mcp_service.get_price_history.return_value = history_data

        args = GetPriceHistoryArgs(symbol="AAPL", period="week")
        result = await get_price_history(args)

        # Should handle large data responses
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert len(result["data"]) == 3

    @pytest.mark.asyncio
    async def test_mcp_client_timeout_handling(self, setup_mcp_service):
        """Test MCP handles client timeout scenarios."""
        from app.mcp.market_data_tools import GetStockNewsArgs, get_stock_news

        # Mock timeout
        setup_mcp_service.get_stock_news.side_effect = TimeoutError("Request timeout")

        args = GetStockNewsArgs(symbol="AAPL")
        result = await get_stock_news(args)

        # Should handle timeout gracefully
        assert isinstance(result, dict)
        assert "error" in result
        assert "Request timeout" in result["error"]
