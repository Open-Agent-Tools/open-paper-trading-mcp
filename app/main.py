import os
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.config import get_adapter_factory
from app.api.routes import api_router
from app.auth.robinhood_auth import get_robinhood_client
from app.core.config import settings
from app.core.exceptions import CustomException
from app.core.logging import setup_logging

# Import the unified MCP server instance
mcp_instance: Any | None = None
with suppress(ImportError):
    from app.mcp.server import mcp as mcp_instance


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


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A FastAPI web application for paper trading with MCP support",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
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
    from datetime import datetime, UTC

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
    from datetime import datetime, UTC

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


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response."""
    import logging
    from datetime import datetime, UTC

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


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "message": "Welcome to Open Paper Trading MCP API",
        "endpoints": {
            "api": f"{settings.API_V1_STR}/",
            "docs": "/docs",
            "health": "/health",
            "mcp": {
                "host": settings.MCP_SERVER_HOST,
                "port": settings.MCP_SERVER_PORT,
                "name": settings.MCP_SERVER_NAME,
            },
        },
    }


app.include_router(api_router, prefix=settings.API_V1_STR)


def run_mcp_server() -> None:
    """Run the MCP server in a separate thread."""
    if mcp_instance is None:
        print("MCP server not available (likely in test mode)")
        return

    print(
        f"Starting MCP server on {settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}"
    )
    try:
        mcp_instance.run(
            host=settings.MCP_SERVER_HOST,
            port=settings.MCP_SERVER_PORT,
            transport="sse",
        )
    except Exception as e:
        print(f"Error running MCP server: {e}")


def main() -> None:
    """Main entry point to run both servers."""
    # Start MCP server in a separate thread if available
    if mcp_instance is not None:
        mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
        mcp_thread.start()
    else:
        print("MCP server not available - running FastAPI only")

    # Run FastAPI server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=2080,
        reload=os.getenv("ENVIRONMENT") == "development",
    )


if __name__ == "__main__":
    main()
