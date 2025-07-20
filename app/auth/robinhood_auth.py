"""Robin Stocks authentication management."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import robin_stocks.robinhood as r  # type: ignore

from app.core.logging import logger

from .config import settings


@dataclass
class RobinhoodAuth:
    """Robin Stocks authentication manager."""

    _authenticated: bool = field(default=False, init=False)
    _session_info: dict[str, Any] | None = field(default=None, init=False)

    async def authenticate(self) -> bool:
        """
        Authenticate with Robinhood API.
        Returns:
            bool: True if authentication successful, False otherwise
        """
        logger.info("Attempting to authenticate with Robinhood...")
        try:
            loop = asyncio.get_running_loop()
            self._session_info = await loop.run_in_executor(
                None, lambda: r.login(settings.username, settings.get_password())
            )
            self._authenticated = True
            logger.info("Robinhood authentication successful.")
            return True
        except Exception as e:
            logger.error(f"Robinhood authentication failed: {e}")
            self._authenticated = False
            return False

    async def logout(self) -> bool:
        """
        Logout from Robinhood API.
        Returns:
            bool: True if logout successful, False otherwise
        """
        logger.info("Logging out from Robinhood.")
        r.logout()
        self._authenticated = False
        self._session_info = None
        return True

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._authenticated


# Global authentication instance
_robinhood_auth: RobinhoodAuth | None = None


def get_robinhood_client() -> RobinhoodAuth:
    """
    Get the global Robinhood authentication instance.
    Returns:
        RobinhoodAuth: The global authentication instance
    """
    global _robinhood_auth
    if _robinhood_auth is None:
        _robinhood_auth = RobinhoodAuth()
    return _robinhood_auth
