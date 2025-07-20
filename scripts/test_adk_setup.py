#!/usr/bin/env python3
"""Test script to verify ADK evaluation setup."""

import json
import os
import subprocess
import sys


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists and report result."""
    if os.path.exists(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} (NOT FOUND)")
        return False


def check_directory_structure() -> bool:
    """Check if all required directories and files exist."""
    print("🔍 Checking directory structure...")

    required_files = [
        ("tests/evals/", "Evals directory"),
        ("tests/evals/test_config.json", "Test configuration"),
        ("tests/evals/list_available_tools_test.json", "List tools test"),
        ("tests/evals/ADK-testing-evals.md", "Documentation"),
        ("examples/google_adk_agent/", "Agent directory"),
        ("examples/google_adk_agent/agent.py", "Agent module"),
        ("examples/google_adk_agent/prompts.py", "Agent prompts"),
        ("examples/google_adk_agent/__init__.py", "Agent init file"),
        ("examples/google_adk_agent/requirements.txt", "Agent requirements"),
    ]

    all_exist = True
    for path, description in required_files:
        if not check_file_exists(path, description):
            all_exist = False

    return all_exist


def check_test_content() -> bool:
    """Check if test file has correct content."""
    print("\n🔍 Checking test content...")

    try:
        with open("tests/evals/list_available_tools_test.json") as f:
            test_data = json.load(f)

        # Check structure
        if "eval_set_id" in test_data:
            print("✅ Test has eval_set_id")
        else:
            print("❌ Test missing eval_set_id")
            return False

        if "eval_cases" in test_data:
            print("✅ Test has eval_cases")
        else:
            print("❌ Test missing eval_cases")
            return False

        # Check expected tools
        expected_tools = [
            "cancel_order",
            "create_buy_order",
            "create_sell_order",
            "get_all_orders",
            "get_all_positions",
            "get_order",
            "get_portfolio",
            "get_portfolio_summary",
            "get_position",
            "get_stock_quote",
        ]

        eval_case = test_data["eval_cases"][0]
        final_response = eval_case["conversation"][0]["final_response"]["parts"][0][
            "text"
        ]

        all_tools_present = True
        for tool in expected_tools:
            if f"• {tool}" not in final_response:
                print(f"❌ Missing tool in expected response: {tool}")
                all_tools_present = False

        if all_tools_present:
            print("✅ All expected tools present in test")

        return all_tools_present

    except Exception as e:
        print(f"❌ Error checking test content: {e}")
        return False


def check_mcp_server() -> bool:
    """Check if MCP server can be imported."""
    print("\n🔍 Checking MCP server...")

    try:
        # Test import
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from app.main import app; print('Server imports OK')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ MCP server imports successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ MCP server import failed: {e.stderr}")
        return False


def check_environment() -> bool:
    """Check environment variables."""
    print("\n🔍 Checking environment...")

    required_vars = ["GOOGLE_API_KEY"]
    optional_vars = ["GOOGLE_MODEL", "MCP_HTTP_URL"]

    all_good = True

    for var in required_vars:
        if var in os.environ:
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is not set (required for ADK eval)")
            all_good = False

    for var in optional_vars:
        if var in os.environ:
            print(f"✅ {var} is set")
        else:
            print(f"ℹ️  {var} is not set (optional, will use defaults)")

    return all_good


def main() -> bool:
    """Main test function."""
    print("🧪 Testing ADK Evaluation Setup\n")

    # Check working directory
    cwd = os.getcwd()
    if cwd.endswith("open-paper-trading-mcp"):
        print(f"✅ Working directory: {cwd}")
    else:
        print(f"❌ Working directory: {cwd}")
        print("   Expected to end with 'open-paper-trading-mcp'")
        print("   Run from project root directory")
        return False

    # Run all checks
    checks = [
        check_directory_structure(),
        check_test_content(),
        check_mcp_server(),
        check_environment(),
    ]

    if all(checks):
        print("\n🎉 All checks passed! ADK evaluation setup is ready.")
        print("\nTo run the evaluation:")
        print(
            "adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json"
        )
        return True
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
