#!/usr/bin/env python3
"""
Development utility script for Open Paper Trading MCP
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Development script loaded environment from {env_path}")
else:
    print(f"⚠️  Warning: .env file not found at {env_path}")


def run_command(cmd: str) -> str | None:
    """Run a command and return its result"""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        return None


def start_server() -> None:
    """Start integrated FastAPI + MCP server"""
    print("Starting integrated FastAPI + MCP server...")
    print("FastAPI will be available at http://localhost:2080")
    print("MCP server will be available at http://localhost:2080/mcp")
    os.system("uv run python app/main.py")


def start_mcp_only() -> None:
    """Start integrated server (MCP is now part of FastAPI)"""
    print("Note: MCP is now integrated into FastAPI server.")
    print("Starting integrated FastAPI + MCP server...")
    print("FastAPI will be available at http://localhost:2080")
    print("MCP server will be available at http://localhost:2080/mcp")
    os.system("uv run python app/main.py")


def run_tests() -> None:
    """Run all tests"""
    print("Running tests...")
    os.system("uv run pytest -v")


def format_code() -> None:
    """Format code with ruff"""
    print("Formatting code...")
    os.system("uv run ruff format .")


def lint_code() -> None:
    """Lint code with ruff"""
    print("Linting code...")
    os.system("uv run ruff check . --fix")


def type_check() -> None:
    """Type check with mypy"""
    print("Type checking...")
    os.system("uv run mypy .")


def run_all_checks() -> None:
    """Run all code quality checks"""
    format_code()
    lint_code()
    type_check()
    run_tests()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/dev.py <command>")
        print("Commands:")
        print("  server    - Start development server (FastAPI + MCP)")
        print("  mcp       - Start integrated server (same as 'server')")
        print("  test      - Run tests (uv run pytest -v)")
        print("  format    - Format code (uv run ruff format .)")
        print("  lint      - Lint code (uv run ruff check . --fix)")
        print("  typecheck - Type check code (uv run mypy .)")
        print("  check     - Run all checks (format + lint + typecheck + tests)")
        return

    command = sys.argv[1]

    if command == "server":
        start_server()
    elif command == "mcp":
        start_mcp_only()
    elif command == "test":
        run_tests()
    elif command == "format":
        format_code()
    elif command == "lint":
        lint_code()
    elif command == "typecheck":
        type_check()
    elif command == "check":
        run_all_checks()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
