#!/bin/bash

# Start script for running FastAPI server only
# Skip MCP server due to dependency issues

echo "Starting FastAPI server on port 2080..."
echo "Note: MCP server disabled due to dependency issues"

# Run FastAPI server only - this should work
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 2080