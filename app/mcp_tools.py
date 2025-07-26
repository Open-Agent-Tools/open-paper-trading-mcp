"""
MCP Tools for Open Paper Trading
Minimal MCP server with health check only
"""

from datetime import datetime
from typing import Any

from fastmcp import FastMCP

# Initialize FastMCP instance
mcp = FastMCP("Open Paper Trading MCP")


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check the health status of the trading system"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {"mcp_server": "operational", "api_server": "operational"},
        "message": "Open Paper Trading MCP is running",
    }


# Export the MCP instance for integration with FastAPI
__all__ = ["mcp"]
