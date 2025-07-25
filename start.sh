#!/bin/bash

# Start script for running both FastAPI and MCP servers

echo "Starting Open Paper Trading MCP application..."
echo "FastAPI server will run on port 2080"
echo "MCP server will run on port 2081"

# Start MCP server in background directly from app.mcp.server
echo "Starting MCP server..."
uv run python -c "
import uvicorn
from app.mcp.server import mcp
app = mcp.sse_app()
uvicorn.run(app, host='0.0.0.0', port=2081, log_level='info')
" &

# Start FastAPI server in foreground  
echo "Starting FastAPI server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 2080