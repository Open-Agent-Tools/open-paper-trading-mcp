from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

# Load environment variables early
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly at startup
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment variables from {env_path}")
    
    # Verify key environment variables are loaded
    robinhood_user = os.getenv("ROBINHOOD_USERNAME")
    robinhood_pass = os.getenv("ROBINHOOD_PASSWORD")
    if robinhood_user and robinhood_pass:
        print(f"✅ Robinhood credentials loaded for user: {robinhood_user}")
    else:
        print("⚠️  Warning: Robinhood credentials not found in environment")
else:
    print(f"⚠️  Warning: .env file not found at {env_path}")

# uvicorn import removed - now handled by fastapi_server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

# NEW: FastMCP integration for unified architecture
from fastapi.staticfiles import StaticFiles

# NEW: Delay MCP import completely to avoid any circular import issues
MCP_AVAILABLE = False
mcp_app = None

def create_mcp_app():
    """Create MCP app after all other imports are complete."""
    global MCP_AVAILABLE, mcp_app
    try:
        # Import in function to avoid circular import during module loading
        from fastmcp import FastMCP
        
        # Create minimal MCP server inline
        mcp = FastMCP("Open Paper Trading MCP")
        
        @mcp.tool()
        async def health_check() -> dict:
            """Check MCP server health status."""
            return {"status": "healthy", "server": "mcp", "port": "2080"}
        
        @mcp.tool()
        async def get_stock_quote(symbol: str) -> dict:
            """Get stock quote."""
            return {"symbol": symbol.upper(), "price": 150.50, "status": "test"}
        
        # Create ASGI app
        mcp_app = mcp.http_app(path="/mcp")
        MCP_AVAILABLE = True
        print("✅ MCP server created and ASGI app initialized")
        return True
    except Exception as e:
        print(f"⚠️  MCP creation failed: {e}")
        MCP_AVAILABLE = False
        mcp_app = None
        return False

from app.adapters.config import get_adapter_factory
from app.api.routes import api_router
from app.auth.robinhood_auth import get_robinhood_client
from app.core.config import settings
from app.core.exceptions import CustomException
from app.core.logging import setup_logging

# Note: MCP server runs separately via mcp_server.py


async def initialize_database() -> None:
    """Initialize database tables asynchronously."""
    print("Initializing database...")
    try:
        from app.storage.database import init_db

        await init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # Continue anyway for development


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    setup_logging()
    print("Starting up FastAPI server...")
    await initialize_database()

    # Initialize services using service factory
    from app.core.container import container
    from app.core.service_factory import register_services
    from app.services.trading_service import TradingService

    # Register all services in the container
    register_services()

    # Store TradingService in application state for FastAPI dependencies
    trading_service = container.get(TradingService)
    app.state.trading_service = trading_service

    # Lock container to prevent further service registration
    container.lock()

    print("Services initialized and registered in container")

    # Authenticate with Robinhood
    robinhood_client = get_robinhood_client()
    await robinhood_client.authenticate()

    # Start cache warming
    adapter_factory = get_adapter_factory()

    # Get the configured adapter (robinhood if available, otherwise fallback to test)
    try:
        adapter = adapter_factory.create_adapter("robinhood")
        if adapter is not None:
            print("Starting cache warming with Robinhood adapter...")
            await adapter_factory.start_cache_warming(adapter)
        else:
            print("Robinhood adapter not available, trying test adapter...")
            test_adapter = adapter_factory.create_adapter("test_data")
            if test_adapter is not None:
                print("Starting cache warming with test adapter...")
                await adapter_factory.start_cache_warming(test_adapter)
    except Exception as e:
        print(f"Cache warming failed to start: {e}")
        # Continue startup even if cache warming fails

    yield
    
    # Shutdown
    print("Shutting down FastAPI server...")

    # Stop cache warming
    try:
        await adapter_factory.stop_cache_warming()
        print("Cache warming stopped successfully.")
    except Exception as e:
        print(f"Error stopping cache warming: {e}")


# Use standard lifespan initially, will mount MCP later
combined_lifespan = lifespan

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A FastAPI web application for paper trading with MCP support",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=combined_lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(CustomException)
async def custom_exception_handler(
    request: Request, exc: CustomException
) -> JSONResponse:
    """Handle custom exceptions with structured error responses."""
    from datetime import UTC, datetime

    error_content = {
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc.detail),
            "status_code": exc.status_code,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=exc.status_code,
        content=error_content,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions as validation errors."""
    from datetime import UTC, datetime

    from app.core.exceptions import ValidationError

    # Convert ValueError to ValidationError for consistent handling
    ValidationError(str(exc))

    error_content = {
        "error": {
            "type": "ValidationError",
            "message": str(exc),
            "status_code": 422,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=422,
        content=error_content,
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    """Handle database operational errors (connection issues, timeouts, etc.)."""
    import logging
    from datetime import UTC, datetime

    logger = logging.getLogger(__name__)
    logger.error(f"Database operational error: {exc}", exc_info=True)

    error_content = {
        "error": {
            "type": "ServiceUnavailable",
            "message": "Service temporarily unavailable due to database issues",
            "status_code": 503,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=503,
        content=error_content,
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """Handle database integrity constraint violations."""
    import logging
    from datetime import UTC, datetime

    logger = logging.getLogger(__name__)
    logger.error(f"Database integrity error: {exc}", exc_info=True)

    error_content = {
        "error": {
            "type": "BadRequest",
            "message": "Data constraint violation",
            "status_code": 400,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=400,
        content=error_content,
    )


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle general database errors."""
    import logging
    from datetime import UTC, datetime

    logger = logging.getLogger(__name__)
    logger.error(f"Database error: {exc}", exc_info=True)

    error_content = {
        "error": {
            "type": "InternalServerError",
            "message": "Database error occurred",
            "status_code": 500,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=500,
        content=error_content,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response."""
    import logging
    from datetime import UTC, datetime

    # Log the unexpected error
    logger = logging.getLogger(__name__)
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    error_content = {
        "error": {
            "type": "InternalServerError",
            "message": "An internal server error occurred",
            "status_code": 500,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        }
    }

    return JSONResponse(
        status_code=500,
        content=error_content,
    )


# Root endpoint now handled by frontend_html() function below

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "server": "unified"}


# NEW: Simple test endpoint first
@app.get("/test-endpoint")
async def test_endpoint():
    return {"message": "Test endpoint working", "status": "success"}

# NEW: Register MCP endpoint
@app.post("/mcp")
async def mcp_json_rpc_handler(request: Request):
    """Handle MCP JSON-RPC requests directly without FastMCP dependency."""
    import json
    from datetime import datetime, timezone
    
    try:
        body = await request.body()
        data = json.loads(body)
        
        # Handle tools/list method
        if data.get("method") == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "health_check",
                            "description": "Check MCP server health status",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "get_stock_quote",
                            "description": "Get current stock quote",
                            "inputSchema": {
                                "type": "object", 
                                "properties": {
                                    "symbol": {"type": "string", "description": "Stock symbol"}
                                },
                                "required": ["symbol"]
                            }
                        },
                        {
                            "name": "get_account_balance",
                            "description": "Get account balance information",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                }
            }
        
        # Handle tools/call method  
        elif data.get("method") == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if tool_name == "health_check":
                result = {
                    "status": "healthy",
                    "server": "mcp_direct", 
                    "port": "2080",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "architecture": "unified_fastapi"
                }
            elif tool_name == "get_stock_quote":
                symbol = arguments.get("symbol", "UNKNOWN")
                result = {
                    "symbol": symbol.upper(),
                    "price": 150.50,
                    "volume": 1000000,
                    "change": 2.35,
                    "change_percent": 1.58,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "source": "test_data",
                    "status": "success"
                }
            elif tool_name == "get_account_balance":
                result = {
                    "account_id": "unified_test_123",
                    "total_balance": 50000.00,
                    "cash_balance": 5000.00,
                    "equity_balance": 45000.00,
                    "buying_power": 10000.00,
                    "status": "active",
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {tool_name}",
                        "data": {"available_tools": ["health_check", "get_stock_quote", "get_account_balance"]}
                    }
                }
            
            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": result
            }
        
        else:
            return {
                "jsonrpc": "2.0", 
                "id": data.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {data.get('method')}",
                    "data": {"supported_methods": ["tools/list", "tools/call"]}
                }
            }
            
    except json.JSONDecodeError:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error: Invalid JSON"
            }
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": data.get("id") if "data" in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

print("✅ MCP JSON-RPC endpoint implemented directly at /mcp")

# Include API routes after MCP endpoint
app.include_router(api_router, prefix=settings.API_V1_STR)

# Add frontend JSON endpoint
@app.get("/frontend")
async def frontend_json():
    return {
        "message": "Frontend endpoint",
        "links": {
            "docs": "/docs", 
            "api": "/api/v1/",
            "health": "/health"
        }
    }

# Serve the React frontend and static assets
from fastapi.responses import HTMLResponse, FileResponse
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static assets first (before any catch-all routes)
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
    print(f"✅ React assets mounted from {frontend_dist / 'assets'}")

@app.get("/", response_class=HTMLResponse)
async def serve_react_app():
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        # Serve the React app index.html (confirmed working from test server)
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HTMLResponse(content=content, status_code=200)
    else:
        # Fallback if React build not found
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Open Paper Trading MCP</title></head>
        <body>
            <h1>🚀 Open Paper Trading MCP</h1>
            <p>React frontend build not found. Please run: <code>cd frontend && npm run build</code></p>
            <div style="margin: 20px 0;">
                <a href="/docs" style="margin-right: 10px;">📚 API Documentation</a>
                <a href="/health" style="margin-right: 10px;">❤️ Health Check</a>
                <a href="/frontend">📱 Frontend JSON</a>
            </div>
        </body>
        </html>
        """, status_code=200)


if __name__ == "__main__":
    # NEW: Simplified single-server startup
    import uvicorn
    print("🚀 Starting unified FastAPI + MCP server on port 2080...")
    print("🔗 REST API: http://0.0.0.0:2080/api/v1/")
    print("🔗 MCP Server: http://0.0.0.0:2080/mcp/mcp/")
    print("📚 API Docs: http://0.0.0.0:2080/docs")
    uvicorn.run(app, host="0.0.0.0", port=2080, log_level="info")
