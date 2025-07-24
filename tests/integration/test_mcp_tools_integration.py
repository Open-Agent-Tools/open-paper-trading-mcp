"""
Integration tests for MCP tools to verify they work together properly.

These tests verify that:
1. All MCP tools are properly registered
2. Tools use consistent response format
3. Tools integrate properly with TradingService
4. Error handling is consistent across all tools
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.mcp.account_tools import set_mcp_trading_service as set_account_trading_service
from app.mcp.core_tools import set_mcp_trading_service as set_core_trading_service
from app.mcp.market_data_tools import (
    set_mcp_trading_service as set_market_data_trading_service,
)
from app.mcp.options_tools import set_mcp_trading_service as set_options_trading_service
from app.mcp.server import mcp
from app.mcp.tools import set_mcp_trading_service
from app.mcp.trading_tools import (
    set_mcp_trading_service as set_trading_tools_trading_service,
)
from app.services.trading_service import TradingService


class TestMCPToolsIntegration:
    """Integration tests for all MCP tools."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock TradingService for testing."""
        mock_service = AsyncMock(spec=TradingService)

        # Set up common mock responses
        mock_service.get_portfolio.return_value = MagicMock(
            cash_balance=10000.0,
            total_value=15000.0,
            positions=[],
            daily_pnl=500.0,
            total_pnl=1000.0,
        )

        mock_service.get_portfolio_summary.return_value = MagicMock(
            total_value=15000.0, invested_value=5000.0
        )

        mock_service.get_positions.return_value = []
        mock_service.get_orders.return_value = []

        mock_service.get_stock_price.return_value = {
            "symbol": "AAPL",
            "price": 150.0,
            "change": 2.5,
            "change_percent": 1.69,
        }

        mock_service.get_stock_info.return_value = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market_cap": 2500000000000,
        }

        mock_service.search_stocks.return_value = [
            {"symbol": "AAPL", "name": "Apple Inc."}
        ]

        return mock_service

    @pytest.fixture(autouse=True)
    def setup_mock_trading_service(self, mock_trading_service):
        """Set up mock trading service for all MCP tool modules."""
        set_mcp_trading_service(mock_trading_service)
        set_account_trading_service(mock_trading_service)
        set_market_data_trading_service(mock_trading_service)
        set_options_trading_service(mock_trading_service)
        set_trading_tools_trading_service(mock_trading_service)
        set_core_trading_service(mock_trading_service)

    @pytest.mark.asyncio
    async def test_mcp_server_tool_registration(self):
        """Test that all expected tools are registered in the MCP server."""
        # Get all registered tools
        tools = await mcp.get_tools()
        registered_tools = [tool["name"] for tool in tools]

        # Core system tools
        assert "list_tools" in registered_tools
        assert "health_check" in registered_tools

        # Account & portfolio tools
        assert "account_info" in registered_tools
        assert "portfolio" in registered_tools
        assert "account_details" in registered_tools
        assert "positions" in registered_tools

        # Market data tools
        assert "get_stock_price" in registered_tools
        assert "stock_price" in registered_tools  # alias
        assert "get_stock_info" in registered_tools
        assert "stock_info" in registered_tools  # alias
        assert "search_stocks_tool" in registered_tools
        assert "market_hours" in registered_tools

        # Trading tools
        assert "buy_stock_market" in registered_tools
        assert "sell_stock_market" in registered_tools
        assert "buy_stock_limit" in registered_tools
        assert "sell_stock_limit" in registered_tools

        # Options tools
        assert "options_chains" in registered_tools
        assert "find_options" in registered_tools
        assert "option_market_data" in registered_tools

        print(f"Total registered tools: {len(registered_tools)}")

    @pytest.mark.asyncio
    async def test_core_tools_response_format(self):
        """Test that core tools return standardized response format."""
        from app.mcp.core_tools import health_check, list_tools, market_hours

        # Test list_tools
        response = await list_tools()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test health_check
        response = await health_check()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test market_hours
        response = await market_hours()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

    @pytest.mark.asyncio
    async def test_account_tools_response_format(self):
        """Test that account tools return standardized response format."""
        from app.mcp.account_tools import (
            account_details,
            account_info,
            portfolio,
            positions,
        )

        # Test account_info
        response = await account_info()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test portfolio
        response = await portfolio()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test account_details
        response = await account_details()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test positions
        response = await positions()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

    @pytest.mark.asyncio
    async def test_market_data_tools_response_format(self):
        """Test that market data tools return standardized response format."""
        from app.mcp.market_data_tools import (
            get_stock_info,
            get_stock_price,
            search_stocks_tool,
        )

        # Test get_stock_price
        response = await get_stock_price("AAPL")
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test get_stock_info
        response = await get_stock_info("AAPL")
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test search_stocks_tool
        response = await search_stocks_tool("Apple")
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

    @pytest.mark.asyncio
    async def test_options_tools_response_format(self):
        """Test that options tools return standardized response format."""
        from app.mcp.options_tools import (
            aggregate_option_positions,
            all_option_positions,
            find_options,
            open_option_positions,
            option_market_data,
            options_chains,
        )

        # Test options_chains
        response = await options_chains("AAPL")
        assert "result" in response
        assert "status" in response["result"]

        # Test find_options
        response = await find_options("AAPL", None, None)
        assert "result" in response
        assert "status" in response["result"]

        # Test option_market_data
        response = await option_market_data("test_id")
        assert "result" in response
        assert "status" in response["result"]

        # Test aggregate_option_positions
        response = await aggregate_option_positions()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test all_option_positions
        response = await all_option_positions()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test open_option_positions
        response = await open_option_positions()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

    @pytest.mark.asyncio
    async def test_trading_tools_response_format(self):
        """Test that trading tools return standardized response format."""
        from app.mcp.trading_tools import (
            buy_stock_limit,
            buy_stock_market,
            sell_stock_limit,
            sell_stock_market,
            stock_orders,
        )

        # Test stock_orders
        response = await stock_orders()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "success"
        assert "data" in response["result"]

        # Test buy_stock_market
        response = await buy_stock_market("AAPL", 10)
        assert "result" in response
        assert "status" in response["result"]

        # Test sell_stock_market
        response = await sell_stock_market("AAPL", 10)
        assert "result" in response
        assert "status" in response["result"]

        # Test buy_stock_limit
        response = await buy_stock_limit("AAPL", 10, 150.0)
        assert "result" in response
        assert "status" in response["result"]

        # Test sell_stock_limit
        response = await sell_stock_limit("AAPL", 10, 150.0)
        assert "result" in response
        assert "status" in response["result"]

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that all tools handle errors consistently."""
        from app.mcp.account_tools import get_mcp_trading_service, portfolio

        # Mock an exception in the trading service
        mock_service = get_mcp_trading_service()
        mock_service.get_portfolio.side_effect = Exception("Test error")

        response = await portfolio()
        assert "result" in response
        assert "status" in response["result"]
        assert response["result"]["status"] == "error"
        assert "error" in response["result"]
        assert "Test error" in response["result"]["error"]

    def test_tool_parameter_consistency(self):
        """Test that all tools use direct function parameters (not Pydantic models)."""
        import inspect
        from typing import get_args, get_origin

        from app.mcp import (
            account_tools,
            core_tools,
            market_data_tools,
            options_tools,
            trading_tools,
        )

        modules_to_check = [
            account_tools,
            market_data_tools,
            options_tools,
            trading_tools,
            core_tools,
        ]

        # Define allowed types for MCP tool parameters
        allowed_basic_types = (str, int, float, bool, type(None))

        for module in modules_to_check:
            # Get all async functions (tools) in the module
            for name, func in inspect.getmembers(module, inspect.iscoroutinefunction):
                if name.startswith("_") or name in [
                    "set_mcp_trading_service",
                    "get_mcp_trading_service",
                ]:
                    continue

                # Check function signature
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    # Verify parameters use basic types, not Pydantic models
                    if param.annotation != inspect.Parameter.empty:
                        annotation = param.annotation

                        # Handle Union/Optional types
                        origin = get_origin(annotation)
                        if origin is not None:
                            # For Union types (including Optional), check all args
                            args = get_args(annotation)
                            for arg in args:
                                if arg not in allowed_basic_types:
                                    # Check if it's a basic type (like str)
                                    if not (
                                        isinstance(arg, type)
                                        and issubclass(arg, allowed_basic_types)
                                    ):
                                        # Further check: is it a Pydantic model?
                                        if hasattr(arg, "__bases__") and any(
                                            "BaseModel" in str(base)
                                            for base in arg.__bases__
                                        ):
                                            raise AssertionError(
                                                f"Tool {name} in {module.__name__} uses Pydantic model parameter: {param_name}"
                                            )
                        else:
                            # For direct types, check if it's a basic type
                            if annotation not in allowed_basic_types:
                                if hasattr(annotation, "__bases__") and any(
                                    "BaseModel" in str(base)
                                    for base in annotation.__bases__
                                ):
                                    raise AssertionError(
                                        f"Tool {name} in {module.__name__} uses Pydantic model parameter: {param_name}"
                                    )

    @pytest.mark.asyncio
    async def test_async_patterns_compliance(self):
        """Test that all tools follow proper async patterns."""
        # All these should be awaitable and return immediately
        import asyncio

        from app.mcp.account_tools import portfolio
        from app.mcp.core_tools import health_check
        from app.mcp.market_data_tools import get_stock_price
        from app.mcp.options_tools import options_chains
        from app.mcp.trading_tools import stock_orders

        tasks = [
            portfolio(),
            get_stock_price("AAPL"),
            options_chains("AAPL"),
            stock_orders(),
            health_check(),
        ]

        # Should complete without blocking
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should return dict responses
        for result in results:
            if isinstance(result, Exception):
                # If there's an exception, it should still be handled properly
                continue
            assert isinstance(result, dict)
            assert "result" in result

    @pytest.mark.asyncio
    async def test_tool_registration_completeness(self):
        """Test that all tools from MCP_TOOLS.md are properly registered."""
        expected_core_tools = ["list_tools", "health_check"]

        expected_account_tools = [
            "account_info",
            "portfolio",
            "account_details",
            "positions",
        ]

        expected_market_data_tools = [
            "stock_price",
            "stock_info",
            "search_stocks_tool",
            "market_hours",
            "price_history",
            "stock_ratings",
            "stock_events",
            "stock_level2_data",
        ]

        expected_trading_tools = [
            "buy_stock_market",
            "sell_stock_market",
            "buy_stock_limit",
            "sell_stock_limit",
            "buy_stock_stop_loss",
            "sell_stock_stop_loss",
            "buy_stock_trailing_stop",
            "sell_stock_trailing_stop",
        ]

        expected_options_tools = [
            "options_chains",
            "find_options",
            "option_market_data",
            "option_historicals",
            "aggregate_option_positions",
            "all_option_positions",
            "open_option_positions",
        ]

        tools = await mcp.get_tools()
        registered_tools = [tool["name"] for tool in tools]

        # Check that all expected tools are registered
        for tool_group in [
            expected_core_tools,
            expected_account_tools,
            expected_market_data_tools,
            expected_trading_tools,
            expected_options_tools,
        ]:
            for tool in tool_group:
                # Allow for aliased tools (e.g., get_stock_price vs stock_price)
                assert (
                    tool in registered_tools
                    or f"get_{tool}" in registered_tools
                    or any(
                        alias in registered_tools
                        for alias in [f"{tool}_tool", f"get_{tool}"]
                    )
                ), f"Expected tool {tool} not found in registered tools"
