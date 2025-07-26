#!/usr/bin/env python3
"""
Standalone MCP server test to verify MCP functionality works independently.
"""

import uvicorn
from fastmcp import FastMCP

# Create simple MCP server
mcp = FastMCP("Test MCP Server")

@mcp.tool()
async def test_health() -> dict:
    """Test health check for MCP server."""
    return {"status": "healthy", "server": "mcp-standalone"}

@mcp.tool()
async def get_account_info() -> dict:
    """Get basic account information."""
    return {"account_id": "test123", "balance": 10000.0, "status": "active"}

if __name__ == "__main__":
    print("🧪 Starting standalone MCP server on port 2081...")
    print("🔗 MCP Server: http://localhost:2081/")
    
    # Use the direct run method for standalone server
    mcp.run(host="0.0.0.0", port=2081, transport="streamable-http")