#!/usr/bin/env python3
"""
Proper FastMCP server following gofastmcp.com guidelines.

This server runs independently and provides MCP tools via HTTP transport.
"""

import time
from typing import Any

from fastapi.responses import JSONResponse

# Import the MCP instance with all registered tools
from app.mcp.server import mcp

# Add health check endpoints as recommended by FastMCP documentation
@mcp.custom_route("/health", methods=["GET"])
async def health_check() -> JSONResponse:
    """Health check endpoint for the MCP server."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": time.time(),
        "server": "Open Paper Trading MCP",
        "version": "v0.5.0",
        "transport": "http"
    })

@mcp.custom_route("/status", methods=["GET"])
async def status_check() -> JSONResponse:
    """Detailed status endpoint for the MCP server."""
    return JSONResponse({
        "status": "operational", 
        "server_name": "Open Paper Trading MCP",
        "mcp_version": "1.11.0",
        "fastmcp_version": "2.10.5",
        "tools_count": len(mcp._tools) if hasattr(mcp, '_tools') else 0,
        "uptime": time.time(),
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health", 
            "status": "/status",
            "docs": "/docs"
        }
    })

@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check() -> JSONResponse:
    """Readiness probe for container orchestration."""
    # Check if MCP tools are properly loaded
    tools_loaded = hasattr(mcp, '_tools') and len(mcp._tools) > 0
    
    if tools_loaded:
        return JSONResponse({
            "ready": True,
            "tools_loaded": tools_loaded,
            "tools_count": len(mcp._tools)
        })
    else:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "tools_loaded": tools_loaded,
                "error": "MCP tools not properly loaded"
            }
        )

if __name__ == "__main__":
    # Run FastMCP server with HTTP transport as recommended
    import uvicorn
    from fastmcp.transports.http import FastMCPHTTPHandler

    # Create FastAPI app from FastMCP
    app = FastMCPHTTPHandler(mcp).app

    # Run with uvicorn directly for better control
    uvicorn.run(app, host="0.0.0.0", port=2081)
