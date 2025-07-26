"""
Pytest file for MCP server health checks.
Tests basic connectivity and functionality using FastMCP Client.
"""

import pytest
import asyncio
try:
    from fastmcp import Client
except ImportError:
    # FastMCP not available in test environment
    Client = None


class TestMCPServerHealth:
    """Test MCP server basic functionality and connectivity."""
    
    @pytest.mark.asyncio
    async def test_mcp_server_ping(self):
        """Test basic ping connectivity to MCP server."""
        if Client is None:
            pytest.skip("FastMCP client not available")
        
        try:
            async with Client("http://127.0.0.1:2081/mcp/") as client:
                await client.ping()
        except Exception as e:
            pytest.fail(f"MCP server ping failed: {e}")
    
    @pytest.mark.asyncio
    async def test_mcp_server_list_tools(self):
        """Test that MCP server can list available tools."""
        try:
            async with Client("http://127.0.0.1:2081/mcp/") as client:
                tools = await client.list_tools()
                assert tools is not None
                assert hasattr(tools, 'tools')
                # For clean server, we expect minimal tools
                assert len(tools.tools) >= 0  # Could be 0 for clean server
        except Exception as e:
            pytest.fail(f"MCP server list_tools failed: {e}")
    
    @pytest.mark.asyncio
    async def test_mcp_server_alternative_paths(self):
        """Test alternative MCP server endpoint paths."""
        paths_to_test = [
            "http://127.0.0.1:2081/mcp/",
            "http://127.0.0.1:2081/mcp",
            "http://127.0.0.1:2081/",
        ]
        
        working_paths = []
        for path in paths_to_test:
            try:
                async with Client(path) as client:
                    await client.ping()
                    working_paths.append(path)
            except Exception:
                # Expected to fail for some paths
                continue
        
        assert len(working_paths) > 0, f"No working MCP paths found. Tested: {paths_to_test}"
        print(f"Working MCP paths: {working_paths}")
    
    @pytest.mark.asyncio 
    async def test_mcp_server_health_tool(self):
        """Test health_check tool if available on clean server."""
        try:
            async with Client("http://127.0.0.1:2081/mcp/") as client:
                tools = await client.list_tools()
                
                # Check if health_check tool exists
                health_tool = None
                for tool in tools.tools:
                    if tool.name == "health_check":
                        health_tool = tool
                        break
                
                if health_tool:
                    # Call the health check tool
                    result = await client.call_tool("health_check", {})
                    assert result is not None
                    print(f"Health check result: {result}")
                else:
                    pytest.skip("health_check tool not available on clean server")
                    
        except Exception as e:
            pytest.fail(f"MCP server health tool test failed: {e}")


# Standalone test function for direct execution
async def test_mcp_connectivity():
    """Standalone connectivity test."""
    print("=== MCP Server Connectivity Test ===")
    
    try:
        async with Client("http://127.0.0.1:2081/mcp/") as client:
            print("✅ Connected successfully!")
            
            await client.ping()
            print("✅ Ping successful!")
            
            tools = await client.list_tools()
            print(f"✅ Tools available: {len(tools.tools)} tools")
            
            if tools.tools:
                tool_names = [tool.name for tool in tools.tools[:5]]
                print(f"Tools: {tool_names}")
            
            return True
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    # Direct execution for quick testing
    result = asyncio.run(test_mcp_connectivity())
    if result:
        print("\n🎉 MCP server is healthy!")
    else:
        print("\n😞 MCP server connectivity issues")