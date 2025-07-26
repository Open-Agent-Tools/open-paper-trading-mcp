"""
MCP Tools for Open Paper Trading
Simple MCP server with basic trading tools for testing
"""

from fastmcp import FastMCP

# Initialize FastMCP instance
mcp = FastMCP("Open Paper Trading MCP")


@mcp.tool
def health_check() -> str:
    """Check the health status of the trading system"""
    return "MCP Server is healthy and operational"


@mcp.tool
def get_account_balance() -> str:
    """Get the current account balance"""
    return "Account balance: $10,000.00 (simulated)"


# Export the MCP instance for integration with FastAPI
__all__ = ["mcp"]
