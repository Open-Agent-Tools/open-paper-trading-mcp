#!/usr/bin/env python3
"""
Quick test script to verify MCP tools work correctly.
"""

import asyncio
from app.mcp.account_tools import account_info, portfolio, account_details, positions
from app.mcp.core_tools import health_check, market_hours
from app.mcp.market_data_tools import get_stock_price, get_stock_info, search_stocks_tool


async def test_mcp_tools():
    """Test core MCP tools."""
    print("Testing MCP tools...")
    
    try:
        # Test health check
        print("\n1. Testing health_check...")
        result = await health_check()
        print(f"✓ health_check: {result.get('result', {}).get('status', 'unknown')}")
        
        # Test market hours
        print("\n2. Testing market_hours...")
        result = await market_hours()
        print(f"✓ market_hours: {result.get('result', {}).get('data', {}).get('status', 'unknown')}")
        
        # Test account info
        print("\n3. Testing account_info...")
        result = await account_info()
        print(f"✓ account_info: {result.get('result', {}).get('status', 'unknown')}")
        
        # Test stock price
        print("\n4. Testing get_stock_price...")
        result = await get_stock_price("AAPL")
        print(f"✓ get_stock_price: {result.get('result', {}).get('status', 'unknown')}")
        
        print("\n✅ All basic MCP tools working!")
        
    except Exception as e:
        print(f"❌ Error testing MCP tools: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())