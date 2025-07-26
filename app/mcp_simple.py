"""
Simple MCP server with minimal dependencies to avoid circular imports.
"""

from fastmcp import FastMCP

# Create the MCP instance
mcp = FastMCP("Open Paper Trading MCP")

@mcp.tool()
async def health_check() -> dict:
    """Check MCP server health."""
    return {"status": "healthy", "server": "mcp", "tools": "available"}

@mcp.tool()
async def get_stock_price(symbol: str) -> dict:
    """Get current stock price (test implementation)."""
    return {
        "symbol": symbol.upper(),
        "price": 150.50,
        "status": "test_data",
        "message": "This is test data from MCP server"
    }

@mcp.tool()
async def list_tools_simple() -> dict:
    """List available MCP tools."""
    return {
        "tools": ["health_check", "get_stock_price", "list_tools_simple"],
        "count": 3,
        "status": "available"
    }

# Export the mcp instance
__all__ = ["mcp"]