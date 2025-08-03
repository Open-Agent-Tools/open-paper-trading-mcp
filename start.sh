#!/bin/bash
set -e

echo "🚀 Starting Open Paper Trading services..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $POSTGRES_USER -d $POSTGRES_DB; do
  echo "Database not ready, waiting..."
  sleep 2
done
echo "✅ Database is ready!"

# Run database migrations if needed
echo "🔄 Running database migrations..."
cd /app
# Use the DATABASE_URL environment variable for alembic
export SQLALCHEMY_DATABASE_URL=$DATABASE_URL
uv run alembic upgrade head || echo "⚠️ Migration failed or not needed"

# Create log directories
mkdir -p /app/logs /tmp

# Start both servers in parallel
echo "🚀 Starting FastAPI server on port 2080..."
nohup uv run python app/main.py > /tmp/fastapi.log 2>&1 &
FASTAPI_PID=$!

# Also create a copy in the persistent logs volume
nohup tail -f /tmp/fastapi.log > /app/logs/fastapi.log &

echo "🚀 Starting MCP server on port 2081..."
nohup uv run python app/mcp_server.py > /tmp/mcp.log 2>&1 &
MCP_PID=$!

# Also create a copy in the persistent logs volume  
nohup tail -f /tmp/mcp.log > /app/logs/mcp.log &

# Give servers time to start
sleep 5

# Check if servers are still running
if ! kill -0 $FASTAPI_PID 2>/dev/null; then
    echo "❌ FastAPI server failed to start. Logs:"
    cat /tmp/fastapi.log
fi

if ! kill -0 $MCP_PID 2>/dev/null; then
    echo "❌ MCP server failed to start. Logs:"  
    cat /tmp/mcp.log
fi

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $FASTAPI_PID $MCP_PID 2>/dev/null || true
    wait $FASTAPI_PID $MCP_PID 2>/dev/null || true
    echo "✅ Servers stopped"
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Wait for both processes
echo "✅ Both servers started successfully!"
echo "📊 FastAPI server: http://localhost:2080"
echo "🔌 MCP server: http://localhost:2081"
echo "💤 Waiting for servers to complete..."

wait