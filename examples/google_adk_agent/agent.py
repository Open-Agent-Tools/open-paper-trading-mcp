"""Paper Trading Agent Configuration.

This module configures Paper_Trading_Agent, a specialized agent for handling
paper trading operations through our MCP server.

It uses the specified Google model and connects to our open-paper-trading-mcp server
to provide simulated trading capabilities.
"""

import logging
import os
import warnings

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams,
)

from .prompts import agent_instruction

# Initialize environment and logging
# Load .env from project root (two levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)
logging.basicConfig(level=logging.ERROR)
warnings.filterwarnings("ignore")


def create_agent() -> Agent:
    """
    Creates and returns a configured Paper Trading agent instance.

    Returns:
        Agent: Configured Paper Trading agent with HTTP transport to MCP server.
    """

    # Use HTTP transport - server must be running separately
    http_url = os.environ.get("MCP_HTTP_URL", "http://localhost:8001/mcp")
    agent_tools = [
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=http_url,
            ),
        ),
    ]

    return Agent(
        model=os.environ.get("GOOGLE_MODEL") or "gemini-2.0-flash",
        name="Paper_Trading_Agent",
        instruction=agent_instruction,
        description="Specialized paper trading agent that can perform simulated trading operations through MCP tools.",
        tools=agent_tools,
    )


# Configure specialized Paper Trading operations agent
root_agent = create_agent()