#!/usr/bin/env python3
"""
Open Paper Trading MCP Server - Independent Server
Runs on port 2081 separately from FastAPI
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment variables from {env_path}")

import uvicorn
from app.mcp_tools import mcp

if __name__ == "__main__":
    print("🚀 Starting MCP server on port 2081...")
    print("🔌 MCP Server: http://localhost:2081/")
    print("🛠️  Available tools: health_check, get_account_balance")
    
    # Run the MCP server directly on port 2081
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=2081, log_level="info")