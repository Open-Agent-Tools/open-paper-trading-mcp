# ADK Testing and Evaluations Guide

This guide covers testing and evaluation procedures for the Paper Trading Agent using Google ADK framework.

## Prerequisites

### 1. Environment Setup
```bash
# Set required environment variables
export GOOGLE_API_KEY="your-google-api-key"
export GOOGLE_MODEL="gemini-2.0-flash"  # Optional, defaults to gemini-2.0-flash
export MCP_HTTP_URL="http://localhost:8001/mcp"  # Optional, defaults to this URL
```

Or create a `.env` file in the project root:
```
GOOGLE_API_KEY=your-google-api-key
GOOGLE_MODEL=gemini-2.0-flash
MCP_HTTP_URL=http://localhost:8001/mcp
```

### 2. Install Dependencies
```bash
# Install Google ADK (if not already installed)
pip install google-adk

# Install agent dependencies
pip install -r examples/google_adk_agent/requirements.txt

# Verify ADK installation
adk --help
```

### 3. Start the MCP Server
Before running evaluations, ensure both servers are running:
```bash
# Start both FastAPI and MCP servers
uv run python app/main.py
```

This will start:
- FastAPI server on http://localhost:8000
- MCP server on http://localhost:8001

## Running ADK Evaluations

> **⚠️ Important**: Always run ADK evaluations from the **project root directory** (`/Users/wes/Development/open-paper-trading-mcp/`). The ADK expects the agent module path relative to the current working directory.

### ✅ Correct Way (From Project Root)
```bash
# Navigate to project root first
cd /Users/wes/Development/open-paper-trading-mcp

# Basic evaluation command
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json

# With detailed results output
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json --print_detailed_results

# With specific run ID for tracking
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json --run_id paper_trading_test_$(date +%s)

# With custom model
GOOGLE_MODEL="gemini-2.0-flash-exp" adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json
```

### Expected Tools List
The evaluation expects the following 10 tools to be listed:
- cancel_order
- create_buy_order
- create_sell_order
- get_all_orders
- get_all_positions
- get_order
- get_portfolio
- get_portfolio_summary
- get_position
- get_stock_quote

## Test Setup Verification

Run the setup test to ensure everything is configured correctly:
```bash
uv run python test_adk_setup.py
```

This will check:
- Directory structure
- Test file content
- MCP server functionality
- Environment variables

## Usage Example

```bash
# 1. Set environment variables
export GOOGLE_API_KEY="your-google-api-key"

# 2. Start MCP server (in another terminal)
uv run python app/main.py

# 3. Run evaluation
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json
```

## Additional Resources

- [Google ADK Documentation](https://developers.google.com/agent-development-kit)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [Open Paper Trading MCP Documentation](../../README.md)