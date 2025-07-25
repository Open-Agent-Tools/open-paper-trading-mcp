#!/usr/bin/env python3
"""
Separate FastAPI server for REST API endpoints.

This runs independently from the MCP server.
"""

import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    # Run only FastAPI server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=2080,
        reload=os.getenv("ENVIRONMENT") == "development",
    )
