#!/usr/bin/env python3
"""
Server Health Check Script

This script checks the health and status of both the FastAPI and MCP servers.
"""

import asyncio
import sys
from typing import Any

import httpx


async def check_fastapi_health() -> dict[str, Any]:
    """Check FastAPI server health."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:2080/", timeout=5.0)
            return {
                "service": "FastAPI",
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response": response.json()
                if response.status_code == 200
                else response.text,
            }
    except Exception as e:
        return {
            "service": "FastAPI",
            "status": "error",
            "error": str(e),
        }


async def check_mcp_http_health() -> dict[str, Any]:
    """Check MCP HTTP server health using FastMCP health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:2080/mcp/health", timeout=5.0)
            return {
                "service": "MCP HTTP",
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response": response.json()
                if response.status_code == 200
                else response.text,
            }
    except Exception as e:
        return {
            "service": "MCP HTTP",
            "status": "error",
            "error": str(e),
        }


async def check_mcp_tools() -> dict[str, Any]:
    """Check MCP tools listing."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:2080/mcp/tools", timeout=10.0)
            if response.status_code == 200:
                tools_data = response.json()
                return {
                    "service": "MCP Tools",
                    "status": "healthy",
                    "tool_count": len(tools_data.get("tools", [])),
                    "tools": [
                        tool.get("name") for tool in tools_data.get("tools", [])[:10]
                    ],  # First 10 tools
                }
            else:
                return {
                    "service": "MCP Tools",
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "response": response.text,
                }
    except Exception as e:
        return {
            "service": "MCP Tools",
            "status": "error",
            "error": str(e),
        }


async def check_mcp_status() -> dict[str, Any]:
    """Check MCP server detailed status endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:2080/mcp/status", timeout=5.0)
            if response.status_code == 200:
                status_data = response.json()
                return {
                    "service": "MCP Status",
                    "status": "healthy",
                    "server_name": status_data.get("server_name"),
                    "tools_count": status_data.get("tools_count", 0),
                    "fastmcp_version": status_data.get("fastmcp_version"),
                    "endpoints": status_data.get("endpoints", {}),
                }
            else:
                return {
                    "service": "MCP Status",
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "response": response.text,
                }
    except Exception as e:
        return {
            "service": "MCP Status",
            "status": "error",
            "error": str(e),
        }


async def check_mcp_readiness() -> dict[str, Any]:
    """Check MCP server readiness probe."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:2080/mcp/ready", timeout=5.0)
            if response.status_code == 200:
                ready_data = response.json()
                return {
                    "service": "MCP Readiness",
                    "status": "ready" if ready_data.get("ready") else "not_ready",
                    "tools_loaded": ready_data.get("tools_loaded", False),
                    "tools_count": ready_data.get("tools_count", 0),
                }
            else:
                return {
                    "service": "MCP Readiness",
                    "status": "not_ready",
                    "status_code": response.status_code,
                    "response": response.text,
                }
    except Exception as e:
        return {
            "service": "MCP Readiness",
            "status": "error",
            "error": str(e),
        }


async def test_mcp_jsonrpc() -> dict[str, Any]:
    """Test MCP JSON-RPC endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            # Test initialize method
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            response = await client.post(
                "http://localhost:2080/mcp",
                json=init_request,
                timeout=10.0,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "service": "MCP JSON-RPC",
                    "status": "healthy",
                    "initialize_response": result,
                }
            else:
                return {
                    "service": "MCP JSON-RPC",
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "response": response.text,
                }
    except Exception as e:
        return {
            "service": "MCP JSON-RPC",
            "status": "error",
            "error": str(e),
        }


async def main() -> None:
    """Run all health checks."""
    print("🏥 Server Health Check")
    print("=" * 50)

    # Run all health checks
    checks = [
        check_fastapi_health(),
        check_mcp_http_health(),
        check_mcp_status(),
        check_mcp_readiness(),
        check_mcp_tools(),
        test_mcp_jsonrpc(),
    ]

    results = await asyncio.gather(*checks, return_exceptions=True)

    # Print results
    all_healthy = True
    for result in results:
        if isinstance(result, Exception):
            print(f"❌ Error: {result}")
            all_healthy = False
            continue

        # Ensure result is dict at this point
        if not isinstance(result, dict):
            print(f"❌ Unexpected result type: {type(result)}")
            all_healthy = False
            continue

        service = result.get("service", "Unknown")
        status = result.get("status", "unknown")

        if status in ["healthy", "ready"]:
            print(f"✅ {service}: {status}")
            if "tool_count" in result or "tools_count" in result:
                count = result.get("tool_count", result.get("tools_count", 0))
                print(f"   📊 Tools: {count}")
                if result.get("tools"):
                    print(f"   🔧 Sample tools: {', '.join(result['tools'][:5])}")
            if "server_name" in result:
                print(f"   🏷️  Server: {result['server_name']}")
            if "fastmcp_version" in result:
                print(f"   📦 FastMCP: {result['fastmcp_version']}")
            if "tools_loaded" in result:
                print(f"   🔧 Tools loaded: {result['tools_loaded']}")
        elif status in ["unhealthy", "not_ready"]:
            print(f"⚠️  {service}: {status}")
            if "status_code" in result:
                print(f"   📄 Status code: {result['status_code']}")
            all_healthy = False
        else:
            print(f"❌ {service}: {status}")
            if "error" in result:
                print(f"   🐛 Error: {result['error']}")
            all_healthy = False

    print("=" * 50)
    if all_healthy:
        print("🎉 All services are healthy!")
        sys.exit(0)
    else:
        print("🚨 Some services have issues!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
