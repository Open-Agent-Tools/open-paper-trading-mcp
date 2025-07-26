"""
Clean MCP JSON-RPC implementation without external dependencies.
Implements the Model Context Protocol directly for maximum control.
"""

from typing import Any, Dict, List, Optional
import json
import asyncio
from datetime import datetime, timezone


class MCPTool:
    """Represents an MCP tool with metadata and handler."""
    
    def __init__(self, name: str, description: str, handler, input_schema: Optional[Dict] = None):
        self.name = name
        self.description = description
        self.handler = handler
        self.input_schema = input_schema or {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to MCP tools/list format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


class MCPServer:
    """Clean MCP server implementation using JSON-RPC 2.0."""
    
    def __init__(self, name: str):
        self.name = name
        self.tools: Dict[str, MCPTool] = {}
    
    def add_tool(self, name: str, description: str, handler, input_schema: Optional[Dict] = None):
        """Add a tool to the server."""
        self.tools[name] = MCPTool(name, description, handler, input_schema)
    
    def tool(self, name: Optional[str] = None, description: Optional[str] = None, input_schema: Optional[Dict] = None):
        """Decorator to register tools."""
        def decorator(func):
            tool_name = name or func.__name__
            tool_description = description or func.__doc__ or f"Tool: {tool_name}"
            self.add_tool(tool_name, tool_description, func, input_schema)
            return func
        return decorator
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC request."""
        try:
            method = request_data.get("method")
            request_id = request_data.get("id")
            params = request_data.get("params", {})
            
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [tool.to_dict() for tool in self.tools.values()]
                    }
                }
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name not in self.tools:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool not found: {tool_name}",
                            "data": {"available_tools": list(self.tools.keys())}
                        }
                    }
                
                tool = self.tools[tool_name]
                try:
                    # Call the tool handler
                    if asyncio.iscoroutinefunction(tool.handler):
                        result = await tool.handler(**arguments)
                    else:
                        result = tool.handler(**arguments)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"Tool execution error: {str(e)}",
                            "data": {"tool": tool_name}
                        }
                    }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                        "data": {"supported_methods": ["tools/list", "tools/call"]}
                    }
                }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }


# Create the clean MCP server instance
mcp_server = MCPServer("Open Paper Trading MCP")


# Register basic tools
@mcp_server.tool(
    description="Check MCP server health and status",
    input_schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def health_check() -> Dict[str, Any]:
    """Check MCP server health status."""
    return {
        "status": "healthy",
        "server": "mcp_clean",
        "port": "2080",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "architecture": "unified_fastapi",
        "tools_count": len(mcp_server.tools)
    }


@mcp_server.tool(
    description="Get current stock quote with price and volume data",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock symbol (e.g., AAPL, TSLA)"
            }
        },
        "required": ["symbol"]
    }
)
async def get_stock_quote(symbol: str) -> Dict[str, Any]:
    """Get current stock quote."""
    return {
        "symbol": symbol.upper(),
        "price": 150.50,
        "volume": 1000000,
        "change": 2.35,
        "change_percent": 1.58,
        "bid": 150.45,
        "ask": 150.55,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "test_data",
        "status": "success"
    }


@mcp_server.tool(
    description="Get account balance and portfolio summary",
    input_schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def get_account_info() -> Dict[str, Any]:
    """Get account balance information."""
    return {
        "account_id": "unified_test_123",
        "total_balance": 50000.00,
        "cash_balance": 5000.00,
        "equity_balance": 45000.00,
        "buying_power": 10000.00,
        "margin_used": 0.00,
        "day_trades_remaining": 3,
        "status": "active",
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


# Export the server instance
__all__ = ["mcp_server"]