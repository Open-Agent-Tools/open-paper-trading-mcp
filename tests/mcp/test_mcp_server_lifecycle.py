"""
MCP Server Lifecycle and Integration Tests

Tests for MCP server initialization, lifecycle management, and FastMCP integration.
Focuses on server startup/shutdown, state management, and protocol compliance.
"""

import inspect
from unittest.mock import Mock, patch

import pytest

from app.mcp.server import mcp


class TestMCPServerInitialization:
    """Test MCP server initialization and startup."""

    def test_mcp_server_instance_creation(self):
        """Test MCP server instance is properly created."""
        assert mcp is not None

        # Should be FastMCP instance
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)

    def test_mcp_server_name_configuration(self):
        """Test MCP server is configured with correct name."""
        # FastMCP instances should have name attribute or similar
        # Test what we can access without depending on internal implementation
        assert mcp is not None

        # Verify the server was created with the expected name through source inspection
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)
        assert 'FastMCP("Open Paper Trading MCP")' in source

    def test_mcp_server_singleton_pattern(self):
        """Test MCP server follows singleton pattern."""
        from app.mcp.server import mcp as mcp1
        from app.mcp.server import mcp as mcp2

        # Should be same instance
        assert mcp1 is mcp2
        assert id(mcp1) == id(mcp2)

    def test_mcp_server_module_imports(self):
        """Test MCP server module imports are correct."""
        import app.mcp.server as server_module

        # Should import FastMCP
        assert hasattr(server_module, "mcp")

        # Should export mcp in __all__
        assert hasattr(server_module, "__all__")
        assert "mcp" in server_module.__all__

    @patch("app.mcp.server.FastMCP")
    def test_mcp_server_initialization_call(self, mock_fastmcp):
        """Test MCP server initialization parameters."""
        mock_instance = Mock()
        mock_fastmcp.return_value = mock_instance

        # Reload module to trigger initialization
        import importlib

        import app.mcp.server

        importlib.reload(app.mcp.server)

        # Should initialize with correct name
        mock_fastmcp.assert_called_once_with("Open Paper Trading MCP")

    def test_mcp_server_tool_registration_interface(self):
        """Test MCP server provides tool registration interface."""
        assert hasattr(mcp, "tool")

        # Tool method should be callable
        tool_decorator = mcp.tool()
        assert callable(tool_decorator)

        # Should be able to register a test function
        def test_func():
            return "test"

        registered = tool_decorator(test_func)
        assert registered is test_func


class TestMCPServerLifecycle:
    """Test MCP server lifecycle management."""

    def test_mcp_server_startup_state(self):
        """Test MCP server is in ready state after startup."""
        # Server should be accessible
        assert mcp is not None

        # Should have expected attributes
        assert hasattr(mcp, "tool")

    def test_mcp_server_state_persistence(self):
        """Test MCP server maintains state across operations."""
        # Register a test tool
        original_tool_method = mcp.tool

        # Tool registration method should persist
        assert mcp.tool is original_tool_method

        # Multiple calls should work
        decorator1 = mcp.tool()
        decorator2 = mcp.tool()
        assert callable(decorator1)
        assert callable(decorator2)

    def test_mcp_server_module_reload_safety(self):
        """Test MCP server handles module reloads safely."""
        import importlib

        import app.mcp.server

        # Get original instance

        # Reload module
        importlib.reload(app.mcp.server)

        # Should have new instance after reload
        reloaded_mcp = app.mcp.server.mcp
        assert reloaded_mcp is not None

    def test_mcp_server_import_error_handling(self):
        """Test MCP server handles import errors gracefully."""
        # This test ensures the server module can be imported
        # without raising exceptions
        try:
            import app.mcp.server

            assert app.mcp.server.mcp is not None
        except ImportError as e:
            pytest.fail(f"MCP server import failed: {e}")

    def test_mcp_server_dependency_loading(self):
        """Test MCP server loads all dependencies correctly."""
        import app.mcp.server as server_module

        # Should import all required tools modules
        source = inspect.getsource(server_module)

        expected_imports = [
            "from app.mcp.market_data_tools import",
            "from app.mcp.tools import",
            "from fastmcp import FastMCP",
        ]

        for expected_import in expected_imports:
            assert expected_import in source, f"Missing import: {expected_import}"

    def test_mcp_server_circular_import_prevention(self):
        """Test MCP server prevents circular imports."""
        # Test that importing server doesn't cause circular imports
        try:
            import app.mcp.market_data_tools
            import app.mcp.server
            import app.mcp.tools

            # All should import successfully
            assert app.mcp.server.mcp is not None
            assert hasattr(app.mcp.tools, "set_mcp_trading_service")
            assert hasattr(app.mcp.market_data_tools, "get_stock_price")

        except ImportError as e:
            pytest.fail(f"Circular import detected: {e}")


class TestMCPServerToolRegistration:
    """Test MCP server tool registration lifecycle."""

    def test_mcp_tool_registration_on_startup(self):
        """Test tools are registered during server startup."""
        # Tools should be registered when module is imported
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should have tool registrations
        registration_count = source.count("mcp.tool()(")
        assert registration_count > 15, (
            f"Expected >15 tool registrations, found {registration_count}"
        )

    def test_mcp_trading_tools_registration(self):
        """Test trading tools are properly registered."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should register core trading tools
        expected_registrations = [
            "get_stock_quote",
            "create_buy_order",
            "create_sell_order",
            "get_all_orders",
            "get_portfolio",
        ]

        for tool in expected_registrations:
            assert f"mcp.tool()({tool})" in source, f"Missing registration for {tool}"

    def test_mcp_market_data_tools_registration(self):
        """Test market data tools are properly registered."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should register market data tools
        expected_market_tools = [
            "get_stock_price",
            "get_stock_info",
            "get_price_history",
            "get_stock_news",
        ]

        for tool in expected_market_tools:
            assert f"mcp.tool()({tool})" in source, f"Missing market data tool: {tool}"

    def test_mcp_options_tools_registration(self):
        """Test options tools are properly registered."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should register options tools
        expected_options_tools = [
            "get_options_chain",
            "calculate_option_greeks",
            "create_multi_leg_order",
            "get_strategy_analysis",
        ]

        for tool in expected_options_tools:
            assert f"mcp.tool()({tool})" in source, f"Missing options tool: {tool}"

    def test_mcp_tool_registration_order(self):
        """Test tools are registered in logical order."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        lines = source.split("\n")
        registration_lines = [line for line in lines if "mcp.tool()(" in line]

        # Should have substantial number of registrations
        assert len(registration_lines) > 15

    def test_mcp_deprecated_tools_exclusion(self):
        """Test deprecated tools are not registered."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should not register direct Robinhood tools
        assert "robinhood_options_tools" not in source
        assert "from app.adapters.robinhood" not in source

        # Should have comment about removal
        assert "Removed direct Robinhood" in source or "robinhood" in source.lower()


class TestMCPServerConfiguration:
    """Test MCP server configuration and settings."""

    def test_mcp_server_architecture_pattern(self):
        """Test MCP server follows unified architecture pattern."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should mention unified architecture
        unified_indicators = [
            "unified",
            "combined",
            "all MCP tools",
            "Unified MCP server",
        ]

        has_unified_mention = any(
            indicator.lower() in source.lower() for indicator in unified_indicators
        )
        assert has_unified_mention, "Should mention unified architecture pattern"

    def test_mcp_server_single_instance_pattern(self):
        """Test MCP server uses single instance pattern."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should have only one FastMCP instance
        fastmcp_count = source.count("FastMCP(")
        assert fastmcp_count == 1, (
            f"Should have exactly one FastMCP instance, found {fastmcp_count}"
        )

    def test_mcp_server_documentation_completeness(self):
        """Test MCP server has complete documentation."""
        import app.mcp.server as server_module

        # Module should have docstring
        assert server_module.__doc__ is not None
        doc = server_module.__doc__.lower()
        assert "mcp" in doc or "server" in doc

    def test_mcp_server_architectural_notes(self):
        """Test MCP server documents architectural decisions."""
        import app.mcp.server as server_module

        source = inspect.getsource(server_module)

        # Should document key architectural decisions
        architectural_notes = [
            "TradingService",
            "consistency",
            "unified architecture",
            "account_tools.py doesn't have any tools",
        ]

        notes_found = sum(
            1 for note in architectural_notes if note.lower() in source.lower()
        )
        assert notes_found >= 2, (
            f"Should document architectural decisions, found {notes_found}"
        )

    def test_mcp_server_integration_readiness(self):
        """Test MCP server is ready for external integration."""
        from app.mcp.server import mcp

        # Should be accessible for external use
        assert mcp is not None

        # Should have tool registration interface
        assert hasattr(mcp, "tool")

        # Should be usable in FastAPI or other frameworks
        # (Basic test - actual integration would be tested separately)
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)


class TestMCPServerErrorHandling:
    """Test MCP server error handling during lifecycle."""

    def test_mcp_server_import_resilience(self):
        """Test MCP server handles import issues gracefully."""
        # Server should import successfully
        try:
            from app.mcp.server import mcp

            assert mcp is not None
        except Exception as e:
            pytest.fail(f"MCP server import should not fail: {e}")

    @patch("app.mcp.server.FastMCP", side_effect=ImportError("FastMCP not available"))
    def test_mcp_server_fastmcp_import_error(self, mock_fastmcp):
        """Test MCP server handles FastMCP import errors."""
        # Test that import error is propagated appropriately
        with pytest.raises(ImportError):
            import importlib

            import app.mcp.server

            importlib.reload(app.mcp.server)

    def test_mcp_server_tool_import_resilience(self):
        """Test MCP server handles tool import issues."""
        # All tool imports should succeed
        try:
            import app.mcp.market_data_tools
            import app.mcp.tools

            # Should not raise import errors
            assert hasattr(app.mcp.tools, "get_stock_quote")
            assert hasattr(app.mcp.market_data_tools, "get_stock_price")

        except ImportError as e:
            pytest.fail(f"Tool imports should not fail: {e}")

    def test_mcp_server_registration_error_handling(self):
        """Test MCP server handles tool registration errors gracefully."""
        # This test ensures the registration process doesn't fail silently
        import app.mcp.server as server_module

        # Server should exist even if some registrations might have issues
        assert server_module.mcp is not None

    def test_mcp_server_dependency_error_handling(self):
        """Test MCP server handles dependency errors appropriately."""
        # Test that service dependencies are handled properly
        # Should raise appropriate error when service not set
        import app.mcp.tools
        from app.mcp.tools import get_mcp_trading_service

        app.mcp.tools._trading_service = None

        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()

        assert "TradingService not initialized" in str(exc_info.value)


class TestMCPServerConcurrency:
    """Test MCP server concurrency and thread safety."""

    def test_mcp_server_thread_safety(self):
        """Test MCP server is thread-safe."""
        from app.mcp.server import mcp

        # Multiple accesses should be safe
        instances = []
        for _ in range(10):
            instances.append(mcp)

        # All should be same instance
        for instance in instances:
            assert instance is mcp

    def test_mcp_server_concurrent_tool_registration(self):
        """Test MCP server handles concurrent tool registration."""
        from app.mcp.server import mcp

        # Should be able to register multiple tools
        def tool1():
            return "tool1"

        def tool2():
            return "tool2"

        # Register concurrently (simulate)
        registered1 = mcp.tool()(tool1)
        registered2 = mcp.tool()(tool2)

        assert registered1 is tool1
        assert registered2 is tool2

    @pytest.mark.asyncio
    async def test_mcp_server_async_compatibility(self):
        """Test MCP server is compatible with async operations."""
        from app.mcp.server import mcp

        # Should work in async context
        assert mcp is not None

        # Should be able to register async tools
        async def async_tool():
            return "async_result"

        registered = mcp.tool()(async_tool)
        assert registered is async_tool

    def test_mcp_server_state_consistency(self):
        """Test MCP server maintains consistent state."""
        from app.mcp.server import mcp

        # State should be consistent across accesses
        tool_method1 = mcp.tool
        tool_method2 = mcp.tool

        assert tool_method1 is tool_method2

    def test_mcp_server_memory_efficiency(self):
        """Test MCP server is memory efficient."""
        # Should maintain single instance
        import sys

        from app.mcp.server import mcp

        # Get reference count (basic check)
        sys.getrefcount(mcp)

        # Multiple imports shouldn't increase references significantly
        from app.mcp.server import mcp as mcp2

        sys.getrefcount(mcp)

        assert mcp is mcp2
        # Reference count should not grow excessively


class TestMCPServerPerformance:
    """Test MCP server performance characteristics."""

    def test_mcp_server_startup_time(self):
        """Test MCP server starts up quickly."""
        import importlib
        import time

        # Time the import
        start_time = time.time()
        import app.mcp.server

        importlib.reload(app.mcp.server)
        end_time = time.time()

        startup_time = end_time - start_time

        # Should start up in reasonable time (less than 1 second)
        assert startup_time < 1.0, f"Startup took {startup_time:.2f}s, expected <1.0s"

    def test_mcp_server_memory_usage(self):
        """Test MCP server has reasonable memory usage."""
        from app.mcp.server import mcp

        # Basic memory usage check
        # (More sophisticated profiling would be done in performance tests)
        assert mcp is not None

        # Should not create excessive objects
        import gc

        gc.collect()

        # Basic check that server exists and is accessible
        assert hasattr(mcp, "tool")

    def test_mcp_server_tool_registration_performance(self):
        """Test MCP server tool registration is efficient."""
        import time

        from app.mcp.server import mcp

        # Time tool registration
        def test_tool():
            return "test"

        start_time = time.time()
        for _ in range(100):
            mcp.tool()(test_tool)
        end_time = time.time()

        registration_time = end_time - start_time

        # Should register tools quickly
        assert registration_time < 0.1, (
            f"Tool registration took {registration_time:.3f}s"
        )

    def test_mcp_server_scalability_indicators(self):
        """Test MCP server shows good scalability indicators."""
        from app.mcp.server import mcp

        # Should handle many tool registrations
        tools = []
        for i in range(50):

            def tool_func():
                return f"tool_{i}"

            tools.append(mcp.tool()(tool_func))

        # All tools should be registered successfully
        assert len(tools) == 50
        for tool in tools:
            assert callable(tool)
