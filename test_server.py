#!/usr/bin/env python3
"""
Test server to verify basic functionality and build up to full integration.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

app = FastAPI(
    title="Open Paper Trading MCP - Test Server",
    description="Test server for step-by-step integration",
    version="0.1.0"
)

# Basic health endpoint
@app.get("/health")
def health():
    return {"status": "healthy", "server": "test"}

# Frontend endpoint serving React
frontend_dist = Path(__file__).parent / "frontend" / "dist"

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Open Paper Trading MCP</title></head>
        <body>
            <h1>🚀 Test Server Running</h1>
            <p>React build not found. Run: <code>cd frontend && npm run build</code></p>
            <p><a href="/health">Health Check</a> | <a href="/docs">API Docs</a></p>
        </body>
        </html>
        """

# Mount static assets if they exist
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

if __name__ == "__main__":
    print("Starting test server...")
    uvicorn.run(app, host="0.0.0.0", port=2080)