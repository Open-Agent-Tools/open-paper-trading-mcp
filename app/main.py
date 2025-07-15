from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any, AsyncGenerator

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import CustomException
from app.storage.database import engine
from app.models.database.base import Base

# Import MCP tools only when not in test mode
try:
    from app.mcp.tools import mcp
except ImportError:
    mcp = None


def initialize_database() -> None:
    """Initialize database tables synchronously."""
    print("Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # Continue anyway for development


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    print("Starting up FastAPI server...")
    initialize_database()
    yield
    # Shutdown
    print("Shutting down FastAPI server...")


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
async def custom_exception_handler(request: Request, exc: CustomException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.get("/")
async def root() -> Dict[str, Any]:
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


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "healthy", "servers": ["fastapi", "mcp"]}


app.include_router(api_router, prefix=settings.API_V1_STR)


def run_mcp_server() -> None:
    """Run the MCP server in a separate thread."""
    if mcp is None:
        print("MCP server not available (likely in test mode)")
        return

    print(
        f"Starting MCP server on {settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}"
    )
    try:
        mcp.run(
            host=settings.MCP_SERVER_HOST,
            port=settings.MCP_SERVER_PORT,
            transport="sse",
        )
    except Exception as e:
        print(f"Error running MCP server: {e}")


def main() -> None:
    """Main entry point to run both servers."""
    # Start MCP server in a separate thread if available
    if mcp is not None:
        mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
        mcp_thread.start()
    else:
        print("MCP server not available - running FastAPI only")

    # Run FastAPI server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=2080,
        reload=True if os.getenv("ENVIRONMENT") == "development" else False,
    )


if __name__ == "__main__":
    main()
