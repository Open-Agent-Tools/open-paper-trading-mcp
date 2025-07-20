#!/usr/bin/env python3
"""
Development utility script for Open Paper Trading MCP
"""

import os
import subprocess
import sys


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
    """Start both FastAPI and MCP servers"""
    print("Starting both FastAPI and MCP servers...")
    os.system("uv run python app/main.py")


def run_tests() -> None:
    """Run all tests"""
    print("Running tests...")
    os.system("uv run pytest -v")


def format_code() -> None:
    """Format code with black and isort"""
    print("Formatting code...")
    os.system("uv run black app tests")
    os.system("uv run isort app tests")


def lint_code() -> None:
    """Lint code with flake8"""
    print("Linting code...")
    os.system("uv run flake8 app tests")


def type_check() -> None:
    """Type check with mypy"""
    print("Type checking...")
    os.system("uv run mypy app")


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
        print("  server    - Start development server")
        print("  test      - Run tests")
        print("  format    - Format code")
        print("  lint      - Lint code")
        print("  typecheck - Type check code")
        print("  check     - Run all checks")
        return

    command = sys.argv[1]

    if command == "server":
        start_server()
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
