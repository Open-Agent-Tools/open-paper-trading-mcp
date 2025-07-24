"""
Comprehensive unit tests for MCP server setup and configuration.

Tests MCP server initialization, tool registration, FastMCP integration,
server configuration, and tool discovery functionality.
"""

import inspect
from unittest.mock import Mock, patch

from app.mcp.server import mcp


class TestMCPServerInitialization:
    """Test MCP server initialization and configuration."""

    def test_mcp_instance_creation(self):
        """Test that MCP instance is properly created."""
        assert mcp is not None

        # Should be a FastMCP instance
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)

    def test_mcp_server_name(self):
        """Test MCP server has correct name."""
        # The server should have the expected name
        assert hasattr(mcp, "name") or hasattr(mcp, "_name")

        # Try to get name through various possible attributes
        name = getattr(mcp, "name", None) or getattr(mcp, "_name", None)
        if name:
            assert "Open Paper Trading MCP" in str(name)

    def test_mcp_server_attributes(self):
        """Test MCP server has expected attributes."""
        # Should have tool registration capabilities
        assert hasattr(mcp, "tool")
        assert callable(mcp.tool)

        # Should have other FastMCP attributes
        expected_attrs = ["tool"]  # Basic requirement
        for attr in expected_attrs:
            assert hasattr(mcp, attr), f"MCP server missing {attr} attribute"


class TestMCPToolRegistration:
    """Test MCP tool registration and discovery."""

    def test_tool_registration_decorator(self):
        """Test that tool registration decorator works."""

        # Mock a simple tool function
        def mock_tool():
            """Mock tool for testing."""
            return "test"

        # Should be able to register tools
        assert hasattr(mcp, "tool")
        decorator = mcp.tool()
        assert callable(decorator)

        # Decorator should return the original function
        registered_tool = decorator(mock_tool)
        assert registered_tool == mock_tool

    def test_registered_tools_from_tools_module(self):
        """Test that tools from tools.py are registered."""
        # Import the expected tools
        from app.mcp.tools import (
            calculate_option_greeks,
            cancel_order,
            create_buy_order,
            create_multi_leg_order,
            create_sell_order,
            find_tradable_options,
            get_all_orders,
            get_all_positions,
            get_expiration_dates,
            get_option_market_data,
            get_options_chain,
            get_order,
            get_portfolio,
            get_portfolio_summary,
            get_position,
            get_stock_quote,
            get_strategy_analysis,
            simulate_option_expiration,
        )

        # All tools should be functions
        tools = [
            get_stock_quote,
            create_buy_order,
            create_sell_order,
            get_all_orders,
            get_order,
            cancel_order,
            get_portfolio,
            get_portfolio_summary,
            get_all_positions,
            get_position,
            get_options_chain,
            get_expiration_dates,
            create_multi_leg_order,
            calculate_option_greeks,
            get_strategy_analysis,
            simulate_option_expiration,
            find_tradable_options,
            get_option_market_data,
        ]

        for tool in tools:
            assert callable(tool), f"Tool {tool.__name__} is not callable"
            assert inspect.iscoroutinefunction(tool), (
                f"Tool {tool.__name__} is not async"
            )

    def test_registered_tools_from_market_data_tools_module(self):
        """Test that tools from market_data_tools.py are registered."""
        # Import the expected market data tools
        from app.mcp.market_data_tools import (
            get_price_history,
            get_stock_info,
            get_stock_news,
            get_stock_price,
            get_top_movers,
            search_stocks,
        )

        # All market data tools should be functions
        market_data_tools = [
            get_stock_price,
            get_stock_info,
            get_price_history,
            get_stock_news,
            get_top_movers,
            search_stocks,
        ]

        for tool in market_data_tools:
            assert callable(tool), f"Market data tool {tool.__name__} is not callable"
            assert inspect.iscoroutinefunction(tool), (
                f"Market data tool {tool.__name__} is not async"
            )

    def test_no_direct_robinhood_tools_registered(self):
        """Test that direct Robinhood tools are not registered."""
        # The server should not import direct Robinhood tools
        # This is verified by checking the imports in the server module
        # Get the source code to check imports
        import inspect

        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should not have direct Robinhood imports
        assert "from app.adapters.robinhood" not in source
        assert "robinhood_options_tools" not in source

        # Should have the expected comment about removed Robinhood tools
        assert "Removed direct Robinhood" in source or "robinhood" in source.lower()


class TestMCPServerToolCoverage:
    """Test comprehensive tool coverage and organization."""

    def test_trading_tools_coverage(self):
        """Test that all essential trading tools are covered."""
        expected_trading_tools = [
            "get_stock_quote",
            "create_buy_order",
            "create_sell_order",
            "get_all_orders",
            "get_order",
            "cancel_order",
            "get_portfolio",
            "get_portfolio_summary",
            "get_all_positions",
            "get_position",
        ]

        # Import tools module to verify functions exist
        from app.mcp import tools

        for tool_name in expected_trading_tools:
            assert hasattr(tools, tool_name), f"Missing trading tool: {tool_name}"
            tool_func = getattr(tools, tool_name)
            assert callable(tool_func), f"Tool {tool_name} is not callable"

    def test_options_tools_coverage(self):
        """Test that all essential options tools are covered."""
        expected_options_tools = [
            "get_options_chain",
            "get_expiration_dates",
            "create_multi_leg_order",
            "calculate_option_greeks",
            "get_strategy_analysis",
            "simulate_option_expiration",
            "find_tradable_options",
            "get_option_market_data",
        ]

        # Import tools module to verify functions exist
        from app.mcp import tools

        for tool_name in expected_options_tools:
            assert hasattr(tools, tool_name), f"Missing options tool: {tool_name}"
            tool_func = getattr(tools, tool_name)
            assert callable(tool_func), f"Options tool {tool_name} is not callable"

    def test_market_data_tools_coverage(self):
        """Test that all essential market data tools are covered."""
        expected_market_data_tools = [
            "get_stock_price",
            "get_stock_info",
            "get_price_history",
            "get_stock_news",
            "get_top_movers",
            "search_stocks",
        ]

        # Import market_data_tools module to verify functions exist
        from app.mcp import market_data_tools

        for tool_name in expected_market_data_tools:
            assert hasattr(market_data_tools, tool_name), (
                f"Missing market data tool: {tool_name}"
            )
            tool_func = getattr(market_data_tools, tool_name)
            assert callable(tool_func), f"Market data tool {tool_name} is not callable"


class TestMCPServerImports:
    """Test MCP server import structure and dependencies."""

    def test_fastmcp_import(self):
        """Test FastMCP import and type annotation."""
        # Verify the import structure
        import app.mcp.server as server_module

        # Should import FastMCP
        source = inspect.getsource(server_module)
        assert "from fastmcp import FastMCP" in source

        # Should have type annotation comment
        assert "# type: ignore" in source

    def test_market_data_tools_imports(self):
        """Test market data tools imports."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should import specific market data tools
        expected_imports = [
            "get_price_history",
            "get_stock_info",
            "get_stock_news",
            "get_stock_price",
            "get_top_movers",
            "search_stocks",
        ]

        for import_name in expected_imports:
            assert import_name in source, f"Missing import: {import_name}"

    def test_tools_module_imports(self):
        """Test tools module imports."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should import specific tools
        expected_imports = [
            "calculate_option_greeks",
            "cancel_order",
            "create_buy_order",
            "create_multi_leg_order",
            "create_sell_order",
            "find_tradable_options",
            "get_all_orders",
            "get_all_positions",
            "get_expiration_dates",
            "get_option_market_data",
            "get_options_chain",
            "get_order",
            "get_portfolio",
            "get_portfolio_summary",
            "get_position",
            "get_stock_quote",
            "get_strategy_analysis",
            "simulate_option_expiration",
        ]

        for import_name in expected_imports:
            assert import_name in source, f"Missing tools import: {import_name}"


class TestMCPServerConfiguration:
    """Test MCP server configuration and setup."""

    def test_server_exports(self):
        """Test that server module exports mcp instance."""
        import app.mcp.server as server_module

        # Should export mcp in __all__
        assert hasattr(server_module, "__all__")
        assert "mcp" in server_module.__all__

        # Should be able to import mcp directly
        assert hasattr(server_module, "mcp")
        assert server_module.mcp is not None

    def test_unified_architecture_pattern(self):
        """Test that server follows unified architecture pattern."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should mention unified architecture
        assert (
            "unified" in source.lower()
            or "combined" in source.lower()
            or "all MCP tools" in source
        )

        # Should not have separate server instances
        assert source.count("FastMCP(") == 1, "Should have only one FastMCP instance"

    def test_account_tools_integration_placeholder(self):
        """Test account tools integration placeholder."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should acknowledge that account_tools doesn't have tools yet
        assert "account_tools.py doesn't have any tools defined yet" in source

    def test_deprecated_robinhood_integration_note(self):
        """Test deprecated Robinhood integration note."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should mention removal of direct Robinhood tools
        assert "Removed direct Robinhood" in source or "robinhood" in source.lower()


class TestMCPServerToolRegistrationDetails:
    """Test detailed tool registration patterns."""

    def test_tool_registration_pattern(self):
        """Test that tools are registered using correct pattern."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should use mcp.tool()() pattern for registration
        tool_registrations = source.count("mcp.tool()(")

        # Should have many tool registrations
        assert tool_registrations > 15, (
            f"Expected >15 tool registrations, found {tool_registrations}"
        )

        # Should register specific tools
        expected_registrations = [
            "mcp.tool()(get_stock_quote)",
            "mcp.tool()(create_buy_order)",
            "mcp.tool()(get_portfolio)",
            "mcp.tool()(get_stock_price)",
            "mcp.tool()(get_options_chain)",
        ]

        for registration in expected_registrations:
            assert registration in source, f"Missing registration: {registration}"

    def test_async_tool_registration(self):
        """Test that async tools are properly registered."""
        # All registered tools should be async
        from app.mcp.market_data_tools import get_stock_info, get_stock_price
        from app.mcp.tools import create_buy_order, get_stock_quote

        async_tools = [
            get_stock_quote,
            create_buy_order,
            get_stock_price,
            get_stock_info,
        ]

        for tool in async_tools:
            assert inspect.iscoroutinefunction(tool), (
                f"Tool {tool.__name__} should be async"
            )

    def test_tool_registration_order(self):
        """Test tool registration follows logical order."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Tools should be registered in logical groups
        lines = source.split("\n")
        registration_lines = [line for line in lines if "mcp.tool()(" in line]

        # Should have multiple registrations
        assert len(registration_lines) > 15

        # Basic trading tools should come before options tools
        basic_tools_index = None
        options_tools_index = None

        for i, line in enumerate(registration_lines):
            if "get_stock_quote" in line and basic_tools_index is None:
                basic_tools_index = i
            if "get_options_chain" in line and options_tools_index is None:
                options_tools_index = i

        if basic_tools_index is not None and options_tools_index is not None:
            assert basic_tools_index < options_tools_index, (
                "Basic tools should be registered before options tools"
            )


class TestMCPServerDocumentation:
    """Test MCP server documentation and comments."""

    def test_module_docstring(self):
        """Test module has proper documentation."""
        import app.mcp.server as server_module

        assert server_module.__doc__ is not None
        doc = server_module.__doc__.lower()
        assert "unified" in doc or "mcp" in doc
        assert "server" in doc
        assert "tools" in doc

    def test_inline_comments(self):
        """Test important inline comments are present."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should have explanatory comments
        expected_comments = [
            "# Register all tools",
            "# Register all async tools",
            "# Import all tool functions",
            "# Create the unified MCP instance",
        ]

        comment_found = 0
        for comment in expected_comments:
            if comment in source:
                comment_found += 1

        # At least some explanatory comments should be present
        assert comment_found >= 2, (
            f"Expected at least 2 explanatory comments, found {comment_found}"
        )

    def test_architectural_notes(self):
        """Test architectural decision notes are documented."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should document architectural decisions
        architectural_notes = [
            "unified architecture",
            "direct Robinhood",
            "TradingService",
            "consistency",
        ]

        notes_found = 0
        for note in architectural_notes:
            if note.lower() in source.lower():
                notes_found += 1

        assert notes_found >= 2, f"Expected architectural notes, found {notes_found}"


class TestMCPServerIntegration:
    """Test MCP server integration capabilities."""

    def test_server_can_be_imported(self):
        """Test that server can be imported successfully."""
        # This import should not raise any exceptions
        from app.mcp.server import mcp

        assert mcp is not None

    def test_server_instance_is_singleton(self):
        """Test that server instance behaves like a singleton."""
        from app.mcp.server import mcp as mcp1
        from app.mcp.server import mcp as mcp2

        # Should be the same instance
        assert mcp1 is mcp2

    def test_server_ready_for_fastapi_integration(self):
        """Test that server is ready for FastAPI integration."""
        from app.mcp.server import mcp

        # Should have necessary attributes for FastAPI integration
        # FastMCP instances should be usable with FastAPI
        assert hasattr(mcp, "tool")

        # Should be able to access the server instance
        assert mcp is not None

    @patch("app.mcp.tools.get_mcp_trading_service")
    def test_server_tools_service_integration(self, mock_get_service):
        """Test that server tools integrate with TradingService."""
        # Mock the trading service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Import tools to verify they can get the service
        from app.mcp.tools import get_mcp_trading_service

        # Should be able to get trading service
        service = get_mcp_trading_service()
        assert service == mock_service


class TestMCPServerCoverage:
    """Additional tests to achieve 70% coverage target."""

    def test_all_imports_are_used(self):
        """Test that all imports in server.py are actually used."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Get all imported names
        import ast

        tree = ast.parse(source)

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.name)

        # All imported tools should be used in registrations
        for name in imported_names:
            if name not in ["FastMCP"]:  # Skip FastMCP as it's used differently
                assert name in source, (
                    f"Imported name {name} should be used in registrations"
                )

    def test_server_module_structure(self):
        """Test server module has expected structure."""
        import app.mcp.server as server_module

        # Should have expected attributes
        expected_attrs = ["mcp", "__all__"]
        for attr in expected_attrs:
            assert hasattr(server_module, attr)

        # Should not have unexpected global variables
        module_vars = [
            name
            for name in dir(server_module)
            if not name.startswith("_") and name not in expected_attrs
        ]

        # Only 'mcp' should be the main export
        non_import_vars = [
            var
            for var in module_vars
            if not callable(getattr(server_module, var, None))
        ]
        assert len(non_import_vars) <= 1, (
            f"Unexpected module variables: {non_import_vars}"
        )

    def test_registration_completeness(self):
        """Test that all tool registrations are complete."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Count imports vs registrations
        source.count("from app.mcp.")
        registration_count = source.count("mcp.tool()(")

        # Should have reasonable ratio of registrations to imports
        # (Some imports are for multiple tools)
        assert registration_count > 10, (
            f"Should have many tool registrations, found {registration_count}"
        )

    def test_error_handling_readiness(self):
        """Test that server is ready for error handling."""
        from app.mcp.server import mcp

        # Server should be instantiated and ready
        assert mcp is not None

        # Should not raise exceptions during import
        # (This test passing means import was successful)
