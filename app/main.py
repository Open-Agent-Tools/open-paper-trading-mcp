#!/usr/bin/env python3
"""
Open Paper Trading - FastAPI + React Frontend (MCP runs separately)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment variables from {env_path}")

    # Verify key environment variables
    robinhood_user = os.getenv("ROBINHOOD_USERNAME")
    if robinhood_user:
        print(f"✅ Robinhood credentials loaded for user: {robinhood_user}")
    else:
        print("⚠️  Warning: Robinhood credentials not found in environment")
else:
    print(f"⚠️  Warning: .env file not found at {env_path}")

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.trading import router as trading_router
from app.core.service_factory import register_services

# Create FastAPI app (MCP server runs independently on port 2081)
app = FastAPI(
    title="Open Paper Trading",
    description="Paper trading platform with FastAPI and React frontend",
    version="0.1.0",
)

# Register services (dependency injection)
register_services()

# Include API routes
app.include_router(trading_router)

# Basic health endpoint
@app.get("/health")
async def health():
    return {"status": "healthy", "server": "fastapi+mcp+react"}

# Setup paths
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static files for React build assets
if frontend_dist.exists():
    # Mount static directory for assets (JS, CSS, etc.)
    static_dir = frontend_dist / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        print(f"✅ Static assets mounted from {static_dir}")

    # Also mount assets directory if it exists (fallback)
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        print(f"✅ Assets mounted from {assets_dir}")

@app.get("/")
async def serve_react_app():
    """Serve the React app index.html"""
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    else:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Open Paper Trading</title></head>
        <body>
            <h1>🚀 Open Paper Trading</h1>
            <p>Server with FastAPI, MCP, and React frontend running!</p>
            <p>React build not found. Run: <code>cd frontend && npm run build</code></p>
            <div style="margin: 20px 0;">
                <a href="/health">❤️ Health Check</a> |
                <a href="/mcp/">🔌 MCP Server</a> |
                <a href="/docs">📚 API Docs</a>
            </div>
        </body>
        </html>
        """)

# Catch-all handler for React Router (SPA routing)
@app.get("/{path:path}")
async def serve_react_app_catch_all(path: str, request: Request):
    """Catch-all route to serve React app for client-side routing"""
    # Don't intercept API routes, health, docs - let them 404 properly
    if (
        path.startswith("api/")
        or path.startswith("health")
        or path.startswith("docs")
        or path.startswith("openapi.json")
    ):
        raise HTTPException(status_code=404, detail="Not found")

    # For all other routes, serve the React app
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    else:
        return HTMLResponse(
            "<h1>React app not built</h1><p>Run: <code>cd frontend && npm run build</code></p>"
        )

if __name__ == "__main__":
    print("🚀 Starting Open Paper Trading FastAPI server on port 2080...")
    print("🔗 Frontend: http://localhost:2080/")
    print("❤️ Health: http://localhost:2080/health")
    print("📚 Docs: http://localhost:2080/docs")
    print("ℹ️  MCP Server runs independently on port 2081")
    uvicorn.run(app, host="0.0.0.0", port=2080, log_level="info")
