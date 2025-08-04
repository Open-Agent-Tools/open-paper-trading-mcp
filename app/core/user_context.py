"""
User context mapping system for MCP tools.

Provides functionality to map user IDs from MCP session context
to account IDs in the trading system using environment variables.
"""

import os
from typing import Any

from fastmcp import Context


class UserContextManager:
    """Manages user context and account mapping for MCP tools."""

    def __init__(self):
        """Initialize the user context manager with environment-based mappings."""
        self._user_account_mapping = self._load_user_mappings()

    def _load_user_mappings(self) -> dict[str, str]:
        """Load user-to-account mappings from environment variables.

        Expected format:
        MCP_USER_ACCOUNT_MAPPING=user1:ACCOUNT001,user2:ACCOUNT002,test_user:UITESTER01

        Returns:
            Dictionary mapping user_id to account_id
        """
        mapping = {}
        env_mapping = os.getenv("MCP_USER_ACCOUNT_MAPPING", "")

        if env_mapping:
            try:
                pairs = env_mapping.split(",")
                for pair in pairs:
                    if ":" in pair:
                        user_id, account_id = pair.strip().split(":", 1)
                        mapping[user_id.strip()] = account_id.strip()
            except Exception as e:
                print(f"⚠️ Error parsing MCP_USER_ACCOUNT_MAPPING: {e}")

        # Add default fallback if no mappings found
        if not mapping:
            # Use environment variables for default user
            default_user = os.getenv("MCP_DEFAULT_USER_ID", "test_user")
            default_account = os.getenv("MCP_DEFAULT_ACCOUNT_ID", "UITESTER01")
            mapping[default_user] = default_account

        return mapping

    def get_account_id_from_context(self, ctx: Context | None = None) -> str | None:
        """Extract account ID from MCP context.

        Args:
            ctx: FastMCP context object

        Returns:
            Account ID for the user, or None if not found
        """
        if not ctx:
            return None

        # Try to get user_id from context session first
        user_id = None
        if hasattr(ctx, 'session') and ctx.session:
            user_id = getattr(ctx.session, 'user_id', None)

        # If not in session, try to get from client_id
        if not user_id:
            # Check if there's client information we can use
            user_id = getattr(ctx, "client_id", None)

        # If still no user_id, try to extract from any available session data
        if not user_id and hasattr(ctx, 'session') and ctx.session:
            # Some MCP implementations may store user info differently
            session_data = getattr(ctx.session, 'data', {}) or {}
            user_id = session_data.get("user_id")

        # Look up account ID for this user
        if user_id and user_id in self._user_account_mapping:
            return self._user_account_mapping[user_id]

        return None

    def get_default_account_id(self) -> str:
        """Get the default account ID from environment or fallback.

        Returns:
            Default account ID
        """
        return os.getenv("MCP_DEFAULT_ACCOUNT_ID", "UITESTER01")

    def get_account_id_for_tool(
        self, ctx: Context | None = None, account_id: str | None = None
    ) -> str:
        """Get the appropriate account ID for an MCP tool call.

        Priority order:
        1. Explicit account_id parameter
        2. Account ID from context mapping
        3. Default account ID from environment

        Args:
            ctx: FastMCP context object
            account_id: Explicit account ID parameter from tool call

        Returns:
            Account ID to use for the operation (never None)
        """
        # 1. Use explicit account_id if provided
        if account_id:
            return account_id

        # 2. Try to get from context (safely handle any exceptions)
        try:
            context_account_id = self.get_account_id_from_context(ctx)
            if context_account_id:
                return context_account_id
        except Exception as e:
            print(f"⚠️ Error getting account from context: {e}")

        # 3. Always fall back to default (never return None)
        return self.get_default_account_id()

    def log_context_info(self, ctx: Context | None = None) -> dict[str, Any]:
        """Log context information for debugging.

        Args:
            ctx: FastMCP context object

        Returns:
            Dictionary with context information
        """
        if not ctx:
            return {"error": "No context provided"}

        info = {
            "request_id": getattr(ctx, "request_id", None),
            "client_id": getattr(ctx, "client_id", None),
            "session_id": getattr(ctx, "session_id", None),
            "state_keys": list(ctx.get_state("*", {}).keys())
            if hasattr(ctx, "get_state")
            else [],
            "available_mappings": list(self._user_account_mapping.keys()),
            "default_account": self.get_default_account_id(),
        }

        return info


# Global instance for use across MCP tools
user_context_manager = UserContextManager()
