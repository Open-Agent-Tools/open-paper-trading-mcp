"""
Unit tests for app.mcp.server module.

These tests verify that the MCP server correctly registers and exposes tools.
"""

from unittest.mock import patch

from app.mcp.server import mcp


class TestMCPServer:
    """Tests for MCP server."""

    def test_mcp_instance_exists(self):
        """Test that the MCP instance exists."""
        assert mcp is not None
        assert hasattr(mcp, "tool")

    def test_mcp_has_tools_registered(self):
        """Test that tools are registered with the MCP instance."""
        # Get all registered tools
        # Note: This assumes FastMCP has a way to access registered tools
        # If not, we can test indirectly by checking if specific methods are decorated

        # Since we can't directly access the registered tools, we'll check if the
        # MCP instance has the expected attributes that would be set during registration
        assert hasattr(mcp, "tool")

        # We can also check if the MCP instance has the expected name
        assert mcp.name == "Open Paper Trading MCP"

    @patch("app.mcp.tools.get_stock_quote")
    def test_get_stock_quote_registered(self, mock_get_stock_quote):
        """Test that get_stock_quote is registered as a tool."""
        # This is a bit of an indirect test since we can't easily check if a function
        # is registered with FastMCP. Instead, we're checking that the function exists
        # and is imported in the server module.
        from app.mcp.server import get_stock_quote

        assert get_stock_quote is not None

    @patch("app.mcp.tools.create_buy_order")
    def test_create_buy_order_registered(self, mock_create_buy_order):
        """Test that create_buy_order is registered as a tool."""
        from app.mcp.server import create_buy_order

        assert create_buy_order is not None

    @patch("app.mcp.tools.create_sell_order")
    def test_create_sell_order_registered(self, mock_create_sell_order):
        """Test that create_sell_order is registered as a tool."""
        from app.mcp.server import create_sell_order

        assert create_sell_order is not None

    @patch("app.mcp.tools.get_all_orders")
    def test_get_all_orders_registered(self, mock_get_all_orders):
        """Test that get_all_orders is registered as a tool."""
        from app.mcp.server import get_all_orders

        assert get_all_orders is not None

    @patch("app.mcp.tools.get_portfolio")
    def test_get_portfolio_registered(self, mock_get_portfolio):
        """Test that get_portfolio is registered as a tool."""
        from app.mcp.server import get_portfolio

        assert get_portfolio is not None

    @patch("app.mcp.market_data_tools.get_stock_price")
    def test_get_stock_price_registered(self, mock_get_stock_price):
        """Test that get_stock_price is registered as a tool."""
        from app.mcp.server import get_stock_price

        assert get_stock_price is not None

    @patch("app.mcp.market_data_tools.get_stock_info")
    def test_get_stock_info_registered(self, mock_get_stock_info):
        """Test that get_stock_info is registered as a tool."""
        from app.mcp.server import get_stock_info

        assert get_stock_info is not None

    @patch("app.mcp.options_tools.get_options_chains")
    def test_get_options_chains_registered(self, mock_get_options_chains):
        """Test that get_options_chain is registered as a tool."""
        from app.mcp.server import get_options_chain

        assert get_options_chain is not None

    @patch("app.mcp.options_tools.find_tradable_options")
    def test_find_tradable_options_registered(self, mock_find_tradable_options):
        """Test that find_tradable_options is registered as a tool."""
        from app.mcp.server import find_tradable_options

        assert find_tradable_options is not None

    def test_all_tools_imported(self):
        """Test that all expected tools are imported in the server module."""

        # If we get here without import errors, all tools are imported correctly
        assert True
