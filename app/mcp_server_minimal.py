"""
Minimal MCP server following FastMCP documentation patterns.
This module avoids circular imports by not importing any app modules.
"""

from fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("Open Paper Trading MCP")

@mcp.tool()
async def health_check() -> dict:
    """Check MCP server health status."""
    return {
        "status": "healthy", 
        "server": "mcp_minimal",
        "port": "2080",
        "architecture": "unified"
    }

@mcp.tool()
async def get_stock_quote(symbol: str) -> dict:
    """Get current stock quote (test implementation)."""
    return {
        "symbol": symbol.upper(),
        "price": 150.50,
        "volume": 1000000,
        "change": 2.35,
        "change_percent": 1.58,
        "status": "test_data",
        "message": "This is test data from MCP server"
    }

@mcp.tool()
async def get_account_balance() -> dict:
    """Get account balance information (test implementation)."""
    return {
        "account_id": "test_account_123",
        "total_balance": 50000.00,
        "cash_balance": 5000.00,
        "equity_balance": 45000.00,
        "buying_power": 10000.00,
        "status": "active"
    }

@mcp.tool()
async def list_available_tools() -> dict:
    """List all available MCP tools."""
    return {
        "tools": [
            "health_check",
            "get_stock_quote", 
            "get_account_balance",
            "list_available_tools"
        ],
        "count": 4,
        "server": "mcp_minimal",
        "documentation": "Basic MCP tools for testing unified architecture"
    }

# Export the mcp instance
__all__ = ["mcp"]