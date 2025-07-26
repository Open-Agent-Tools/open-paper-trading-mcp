#!/usr/bin/env python3
"""
Development script to build React frontend and serve with FastAPI
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Build React app and start FastAPI server"""
    project_root = Path(__file__).parent.parent
    frontend_dir = project_root / "frontend"

    print("🏗️  Building React frontend...")
    result = subprocess.run(
        ["npm", "run", "build"], cwd=frontend_dir, capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ Build failed: {result.stderr}")
        sys.exit(1)

    print("✅ React build completed successfully")

    print("🚀 Starting FastAPI server with React frontend...")
    print("🔗 Open http://localhost:2080 in your browser")
    print("❤️ Health: http://localhost:2080/health")
    print("📊 API: http://localhost:2080/api/trading/quote/AAPL")
    print("📚 Docs: http://localhost:2080/docs")
    print("Press Ctrl+C to stop")

    # Start the FastAPI server
    subprocess.run([sys.executable, "app/main.py"], cwd=project_root)


if __name__ == "__main__":
    main()
