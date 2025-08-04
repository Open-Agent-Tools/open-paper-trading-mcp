#!/usr/bin/env python3
"""
Open Paper Trading MCP Server - Independent Server
Runs on port 2081 separately from FastAPI
"""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Load environment variables FIRST, before importing anything that might initialize adapters
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment variables from {env_path}")

    # Verify Robinhood credentials are loaded
    import os

    username = os.getenv("ROBINHOOD_USERNAME")
    if username:
        print(f"✅ Robinhood credentials found for user: {username}")
    else:
        print("⚠️ Robinhood credentials not found in environment variables")
else:
    print(f"❌ .env file not found at {env_path}")

# Import MCP tools AFTER environment variables are loaded
from app.core.service_factory import register_services  # noqa: E402
from app.mcp_tools import mcp  # noqa: E402


async def async_register_services() -> None:
    """Register services in async context to handle database connections."""
    register_services()


if __name__ == "__main__":
    print("🚀 Starting MCP server on port 2081...")
    print("🔌 MCP Server: http://localhost:2081/")

    # Register services before starting server
    print("📋 Registering services...")
    try:
        import asyncio

        # Run service registration in async context
        asyncio.run(async_register_services())
        print("✅ Services registered successfully")
    except Exception as e:
        print(f"⚠️ Failed to register services (will run without DB): {e}")
        # Don't exit - let MCP server start anyway for tools that don't need DB
        # The tools will handle the missing service gracefully

    print("🛠️  Available tools (43 total):")
    print("   • Set 1: Core System & Account Tools (9 tools)")
    print("   • Set 2: Market Data Tools (8 tools)")
    print("   • Set 3: Order Management Tools (4 tools)")
    print("   • Set 4: Options Trading Info Tools (6 tools)")
    print("   • Set 5: Stock Trading Tools (8 tools)")
    print("   • Set 6: Options Trading Tools (4 tools)")
    print("   • Set 7: Order Cancellation Tools (4 tools) ✅ IMPLEMENTED")
    print("   • For complete list, call list_tools MCP tool")

    # Run the MCP server directly on port 2081
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=2081, log_level="info")
