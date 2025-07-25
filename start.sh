#!/bin/bash

# Start script for running both FastAPI and FastMCP servers properly

# Start FastAPI server in background
echo "Starting FastAPI server on port 2080..."
uv run python fastapi_server.py &
FASTAPI_PID=$!

# Start FastMCP server  
echo "Starting FastMCP server on port 2081..."
uv run python mcp_server.py &
MCP_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down servers..."
    kill $FASTAPI_PID $MCP_PID
    exit 0
}

# Trap signals
trap shutdown SIGINT SIGTERM

# Wait for both processes
wait $FASTAPI_PID $MCP_PID