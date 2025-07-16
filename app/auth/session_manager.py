"""Session management for Robin Stocks authentication."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional
import robin_stocks.robinhood as rh
from app.core.logging import logger

class SessionManager:
    """Manages Robin Stocks authentication session lifecycle."""

    def __init__(self, session_timeout_hours: int = 23):
        """Initialize session manager."""
        self.session_timeout_hours = session_timeout_hours
        self.login_time: Optional[datetime] = None
        self.last_successful_call: Optional[datetime] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self._lock = asyncio.Lock()
        self._is_authenticated = False

    def set_credentials(self, username: str, password: str) -> None:
        """Store credentials for re-authentication."""
        self.username = username
        self.password = password

    def is_session_valid(self) -> bool:
        """Check if current session is still valid."""
        if not self._is_authenticated or not self.login_time:
            return False

        elapsed = datetime.now() - self.login_time
        if elapsed > timedelta(hours=self.session_timeout_hours):
            logger.info(f"Session expired after {elapsed}")
            return False

        return True

    def update_last_successful_call(self) -> None:
        """Update timestamp of last successful API call."""
        self.last_successful_call = datetime.now()

    async def ensure_authenticated(self) -> bool:
        """Ensure session is authenticated, re-authenticating if necessary."""
        async with self._lock:
            if self.is_session_valid():
                return True
            return await self._authenticate()

    async def _authenticate(self) -> bool:
        """Perform authentication with stored credentials."""
        if not self.username or not self.password:
            logger.error("No credentials available for authentication")
            return False

        try:
            logger.info(f"Attempting to authenticate user: {self.username}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, rh.login, self.username, self.password
            )
            
            # Verify login by making a test API call
            user_profile = await loop.run_in_executor(None, rh.load_user_profile)

            if user_profile:
                self.login_time = datetime.now()
                self._is_authenticated = True
                logger.info(f"Successfully authenticated user: {self.username}")
                return True
            else:
                logger.error("Authentication failed: Could not retrieve user profile")
                return False

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def logout(self) -> None:
        """Logout and clear session."""
        async with self._lock:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, rh.logout)
                logger.info("Successfully logged out")
            except Exception as e:
                logger.error(f"Error during logout: {e}")
            finally:
                self._is_authenticated = False
                self.login_time = None
                self.last_successful_call = None

# Global session manager instance
_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager