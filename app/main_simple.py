#!/usr/bin/env python3
"""
Simple server with just core trading service and frontend.
Minimal architecture for clean start.
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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# Create minimal FastAPI app
app = FastAPI(
    title="Open Paper Trading",
    description="Simple paper trading with core service and frontend",
    version="0.1.0"
)

# Basic health endpoint
@app.get("/health")
async def health():
    return {"status": "healthy", "server": "simple"}

# Serve React frontend
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the React frontend."""
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Open Paper Trading</title></head>
        <body>
            <h1>🚀 Open Paper Trading</h1>
            <p>Simple server running!</p>
            <p>React build not found. Run: <code>cd frontend && npm run build</code></p>
            <p><a href="/health">Health Check</a> | <a href="/docs">API Docs</a></p>
        </body>
        </html>
        """

# Mount React assets if they exist
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
    print(f"✅ React assets mounted from {frontend_dist / 'assets'}")

if __name__ == "__main__":
    print("🚀 Starting simple server on port 2080...")
    print("🔗 Frontend: http://localhost:2080/")
    print("❤️ Health: http://localhost:2080/health")
    print("📚 Docs: http://localhost:2080/docs")
    uvicorn.run(app, host="0.0.0.0", port=2080, log_level="info")