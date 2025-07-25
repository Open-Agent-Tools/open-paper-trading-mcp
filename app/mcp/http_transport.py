"""HTTP transport enhancements for the Open Paper Trading MCP server"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to handle request timeouts"""

    def __init__(self, app: Any, timeout: float = 120.0) -> None:
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except TimeoutError:
            return JSONResponse(
                status_code=408,
                content={"error": "Request timeout", "timeout": self.timeout},
            )


def create_http_server(mcp_server: FastMCP) -> FastAPI:
    """Create FastAPI server with MCP integration and enhancements"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Lifespan context manager for startup/shutdown"""
        print("Starting HTTP MCP server")
        yield
        print("Shutting down HTTP MCP server")

    app = FastAPI(
        title="Open Paper Trading MCP Server",
        description="Model Context Protocol server for paper trading",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "https://localhost:*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(TimeoutMiddleware, timeout=120.0)

    # Health check endpoints
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "0.1.0",
            "transport": "http",
        }

    @app.get("/info")
    async def root() -> dict[str, Any]:
        """Root endpoint with server information"""
        return {
            "name": "Open Paper Trading MCP Server",
            "version": "0.1.0",
            "transport": "http",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
            },
            "documentation": "/docs",
        }

    @app.get("/tools")
    async def list_tools() -> dict[str, Any]:
        """List available MCP tools"""
        try:
            tools_dict = await mcp_server.get_tools()

            # Convert Tool objects to MCP protocol format
            serialized_tools = []
            for tool_name in tools_dict:
                tool = await mcp_server.get_tool(tool_name)
                # Use FastMCP's built-in conversion to MCP format
                mcp_tool = tool.to_mcp_tool()
                tool_dict = mcp_tool.model_dump()
                serialized_tools.append(tool_dict)

            return {"tools": serialized_tools}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to list tools: {e}"
            ) from e

    # Create a simple MCP endpoint that handles JSON-RPC directly
    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> Response:
        """Handle MCP JSON-RPC requests directly"""
        try:
            # Get the request body
            body = await request.body()

            # Parse the JSON-RPC request
            try:
                json_request = json.loads(body.decode())
            except json.JSONDecodeError:
                return Response(
                    content=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "error": {"code": -32700, "message": "Parse error"},
                            "id": None,
                        }
                    ).encode(),
                    status_code=400,
                    headers={"content-type": "application/json"},
                )

            # Handle different MCP methods
            method = json_request.get("method")
            request_id = json_request.get("id")
            params = json_request.get("params", {})

            try:
                result: dict[str, Any]
                if method == "initialize":
                    # Return server capabilities
                    result = {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {},
                            "logging": {},
                        },
                        "serverInfo": {
                            "name": "Open Paper Trading MCP",
                            "version": "0.1.0",
                        },
                    }
                elif method == "tools/list":
                    # Use FastMCP's built-in get_tools method (returns dict of tool names)
                    tools_dict = await mcp_server.get_tools()

                    # Convert Tool objects to MCP protocol format
                    serialized_tools = []
                    for tool_name in tools_dict:
                        tool = await mcp_server.get_tool(tool_name)
                        # Use FastMCP's built-in conversion to MCP format
                        mcp_tool = tool.to_mcp_tool()
                        tool_dict = mcp_tool.model_dump()
                        serialized_tools.append(tool_dict)

                    result = {"tools": serialized_tools}

                elif method == "tools/call":
                    # Use FastMCP's built-in get_tool method to find the tool
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})

                    # Get the tool and call it
                    tool = await mcp_server.get_tool(tool_name)
                    if tool is None:
                        raise ValueError(f"Tool '{tool_name}' not found")

                    # Call the tool function directly
                    tool_result = await tool(**arguments)

                    # Our tools return dict objects, convert to MCP protocol format
                    # All content must be "text" type according to MCP spec
                    if isinstance(tool_result, dict):
                        # For structured data, serialize as formatted JSON text
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        tool_result, default=str, indent=2
                                    ),
                                }
                            ]
                        }
                    else:
                        # For simple text/string results
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": str(tool_result),
                                }
                            ]
                        }

                elif method == "notifications/initialized":
                    # Handle initialization notification (no response needed for notifications)
                    print("Client initialization notification received")
                    return Response(status_code=200)

                else:
                    raise ValueError(f"Unknown method: {method}")

                # Return successful response
                response_data = {"jsonrpc": "2.0", "result": result, "id": request_id}

                return Response(
                    content=json.dumps(response_data).encode(),
                    status_code=200,
                    headers={"content-type": "application/json"},
                )

            except Exception as e:
                print(f"MCP method '{method}' failed: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": request_id,
                }
                return Response(
                    content=json.dumps(error_response).encode(),
                    status_code=500,
                    headers={"content-type": "application/json"},
                )

        except Exception as e:
            print(f"MCP endpoint error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {e!s}"},
                "id": None,
            }
            return Response(
                content=json.dumps(error_response).encode(),
                status_code=500,
                headers={"content-type": "application/json"},
            )

    return app


async def run_http_server(
    mcp_server: FastMCP,
    host: str = "localhost",
    port: int = 8001,
) -> None:
    """Run the HTTP server with the MCP server mounted"""
    import uvicorn

    # Create the FastAPI app with our enhancements
    app = create_http_server(mcp_server)

    print(f"Starting HTTP MCP server on {host}:{port}")
    print("Available endpoints:")
    print(f"  - MCP JSON-RPC: http://{host}:{port}/mcp")
    print(f"  - Health Check: http://{host}:{port}/health")
    print(f"  - Tools List: http://{host}:{port}/tools")
    print(f"  - API Documentation: http://{host}:{port}/docs")

    # Configure uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10,
    )

    server = uvicorn.Server(config)
    await server.serve()
