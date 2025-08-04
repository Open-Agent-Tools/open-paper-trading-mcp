"""Session management for Robin Stocks authentication."""

import asyncio
import os
import random
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

import robin_stocks.robinhood as rh  # type: ignore

from app.core.logging import logger

F = TypeVar("F", bound=Callable[..., Any])


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""

    pass


class RateLimitError(Exception):
    """Custom exception for rate limit errors."""

    pass


class NetworkError(Exception):
    """Custom exception for network errors."""

    pass


def auth_retry_with_backoff(
    max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
) -> Callable[[F], F]:
    """Decorator for adding exponential backoff retry logic to authentication methods."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except (AuthenticationError, RateLimitError, NetworkError) as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Final auth attempt failed for {func.__name__}: {e}"
                        )
                        raise

                    delay = min(
                        base_delay * (2**attempt) + random.uniform(0, 1), max_delay
                    )
                    logger.warning(
                        f"Auth attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

                    # Increment failure count for circuit breaker
                    self._auth_failure_count += 1
                except Exception as e:
                    # For other exceptions, don't retry
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            return None

        return wrapper  # type: ignore

    return decorator


class SessionManager:
    """Manages Robin Stocks authentication session lifecycle with robust error handling."""

    def __init__(self, session_timeout_hours: int = 23, max_auth_failures: int = 5):
        """Initialize session manager."""
        self.session_timeout_hours = session_timeout_hours
        self.max_auth_failures = max_auth_failures
        self.login_time: datetime | None = None
        self.last_successful_call: datetime | None = None
        self.username: str | None = None
        self.password: str | None = None
        self._lock = asyncio.Lock()
        self._is_authenticated = False

        # Circuit breaker for authentication failures
        self._auth_failure_count = 0
        self._circuit_breaker_reset_time: datetime | None = None
        self._circuit_breaker_open = False

        # Authentication metrics
        self._auth_attempts = 0
        self._auth_successes = 0
        self._last_auth_attempt: datetime | None = None

        # Token management with persistent storage
        self._auth_token: str | None = None
        self._token_expiry: datetime | None = None
        
        # Setup persistent token storage
        self.token_dir = Path(os.getenv("ROBINHOOD_TOKEN_PATH", "/app/.tokens"))
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.pickle_path = str(self.token_dir)
        self.pickle_name = "robinhood_session.pickle"
        
        logger.info(f"Robinhood token storage configured at: {self.token_dir / self.pickle_name}")

    def set_credentials(self, username: str, password: str) -> None:
        """Store credentials for re-authentication."""
        self.username = username
        self.password = password

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_breaker_open:
            return False

        # Check if we should reset the circuit breaker
        if (
            self._circuit_breaker_reset_time
            and datetime.now() > self._circuit_breaker_reset_time
        ):
            self._circuit_breaker_open = False
            self._auth_failure_count = 0
            self._circuit_breaker_reset_time = None
            logger.info("Circuit breaker reset - authentication attempts resumed")
            return False

        return True

    def _open_circuit_breaker(self) -> None:
        """Open circuit breaker after too many failures."""
        self._circuit_breaker_open = True
        # Reset after 5 minutes
        self._circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
        logger.error(
            f"Circuit breaker opened after {self._auth_failure_count} failures. "
            f"Authentication blocked until {self._circuit_breaker_reset_time}"
        )

    def _classify_error(self, error: Exception) -> Exception:
        """Classify errors for proper retry handling."""
        error_str = str(error).lower()

        # Check for specific error patterns
        if any(
            pattern in error_str
            for pattern in [
                "unauthorized",
                "401",
                "invalid credentials",
                "authentication failed",
            ]
        ):
            return AuthenticationError(f"Authentication failed: {error}")
        elif any(
            pattern in error_str
            for pattern in ["rate limit", "429", "too many requests"]
        ):
            return RateLimitError(f"Rate limit exceeded: {error}")
        elif any(
            pattern in error_str
            for pattern in ["network", "connection", "timeout", "dns"]
        ):
            return NetworkError(f"Network error: {error}")
        else:
            # Return original error for non-retryable cases
            return error

    def is_session_valid(self) -> bool:
        """Check if current session is still valid."""
        # First check if there's a valid pickle session
        if self._check_pickle_session():
            return True
            
        if not self._is_authenticated or not self.login_time:
            return False

        elapsed = datetime.now() - self.login_time
        if elapsed > timedelta(hours=self.session_timeout_hours):
            logger.info(f"Session expired after {elapsed}")
            return False

        return True
        
    def _check_pickle_session(self) -> bool:
        """Check if there's a valid pickle session file."""
        try:
            pickle_file = self.token_dir / self.pickle_name
            if pickle_file.exists():
                # Check if the pickle file is recent (less than 23 hours old)
                file_age = datetime.now() - datetime.fromtimestamp(pickle_file.stat().st_mtime)
                if file_age < timedelta(hours=self.session_timeout_hours):
                    logger.info(f"Found valid pickle session (age: {file_age})")
                    return True
                else:
                    logger.info(f"Pickle session expired (age: {file_age}), will re-authenticate")
            return False
        except Exception as e:
            logger.warning(f"Error checking pickle session: {e}")
            return False

    def update_last_successful_call(self) -> None:
        """Update timestamp of last successful API call."""
        self.last_successful_call = datetime.now()

    async def ensure_authenticated(self) -> bool:
        """Ensure session is authenticated, re-authenticating if necessary."""
        async with self._lock:
            # Check circuit breaker first
            if self._check_circuit_breaker():
                raise AuthenticationError(
                    "Circuit breaker is open - authentication blocked"
                )

            # Try to load existing session from pickle first
            if await self._try_load_pickle_session():
                return True
                
            if self.is_session_valid():
                return True
            return await self._authenticate()
            
    async def _try_load_pickle_session(self) -> bool:
        """Try to load an existing pickle session."""
        try:
            if self._check_pickle_session():
                loop = asyncio.get_event_loop()
                
                # Load existing session using robin_stocks' built-in session loading
                def load_session():
                    # Robin stocks automatically loads from pickle if no credentials provided
                    # and store_session=True with pickle_path specified
                    return rh.login(
                        username=None,  # No username triggers pickle loading 
                        password=None,  # No password triggers pickle loading
                        expiresIn=86400,
                        scope="internal", 
                        store_session=True,
                        mfa_code=None,
                        pickle_path=self.pickle_path,
                        pickle_name=self.pickle_name
                    )
                
                # Try to load the session
                session_result = await loop.run_in_executor(None, load_session)
                
                # Test if the loaded session is actually valid by making an API call
                user_profile = await loop.run_in_executor(None, rh.load_user_profile)
                
                if user_profile and session_result:
                    self._is_authenticated = True
                    # Update login time to when pickle was created, not now
                    pickle_file = self.token_dir / self.pickle_name
                    if pickle_file.exists():
                        self.login_time = datetime.fromtimestamp(pickle_file.stat().st_mtime)
                    else:
                        self.login_time = datetime.now()
                        
                    logger.info("✅ Successfully loaded existing Robinhood session from pickle")
                    return True
                    
        except Exception as e:
            logger.warning(f"Failed to load pickle session, will authenticate with credentials: {e}")
            
        return False

    @auth_retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    async def _authenticate(self) -> bool:
        """Perform authentication with stored credentials."""
        self._auth_attempts += 1
        self._last_auth_attempt = datetime.now()

        if not self.username or not self.password:
            logger.error("No credentials available for authentication")
            raise AuthenticationError("No credentials available for authentication")

        try:
            logger.info(
                f"Attempting to authenticate user: {self.username} (attempt {self._auth_attempts})"
            )
            loop = asyncio.get_event_loop()

            # Perform login with persistent session storage
            await loop.run_in_executor(
                None, 
                rh.login, 
                self.username, 
                self.password,
                86400,  # expiresIn: 24 hours
                "internal",  # scope
                True,  # store_session
                None,  # mfa_code
                self.pickle_path,  # pickle_path for token storage
                self.pickle_name   # pickle_name
            )

            # Verify login by making a test API call
            user_profile = await loop.run_in_executor(None, rh.load_user_profile)

            if user_profile:
                self.login_time = datetime.now()
                self._is_authenticated = True
                self._auth_successes += 1
                self._auth_failure_count = 0  # Reset failure count on success

                # Store token if available
                self._auth_token = getattr(rh, "token", None)
                if self._auth_token:
                    # Token typically expires in 24 hours
                    self._token_expiry = datetime.now() + timedelta(hours=23)

                logger.info(f"✅ Robinhood credentials loaded for user: {self.username}")
                return True
            else:
                error_msg = "Authentication failed: Could not retrieve user profile"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

        except Exception as e:
            # Classify the error and re-raise as appropriate type
            classified_error = self._classify_error(e)

            # Check if we should open circuit breaker
            if self._auth_failure_count >= self.max_auth_failures:
                self._open_circuit_breaker()

            raise classified_error from e

    def get_auth_token(self) -> str | None:
        """Get current authentication token."""
        return self._auth_token

    def is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        if not self._auth_token or not self._token_expiry:
            return False
        return datetime.now() < self._token_expiry

    async def refresh_token(self) -> bool:
        """Refresh authentication token."""
        try:
            # Force re-authentication to get new token
            self._is_authenticated = False
            self._auth_token = None
            self._token_expiry = None

            return await self.ensure_authenticated()
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    def get_auth_metrics(self) -> dict[str, Any]:
        """Get authentication metrics."""
        return {
            "auth_attempts": self._auth_attempts,
            "auth_successes": self._auth_successes,
            "auth_failure_count": self._auth_failure_count,
            "circuit_breaker_open": self._circuit_breaker_open,
            "circuit_breaker_reset_time": (
                self._circuit_breaker_reset_time.isoformat()
                if self._circuit_breaker_reset_time
                else None
            ),
            "last_auth_attempt": (
                self._last_auth_attempt.isoformat() if self._last_auth_attempt else None
            ),
            "session_valid": self.is_session_valid(),
            "token_valid": self.is_token_valid(),
            "login_time": self.login_time.isoformat() if self.login_time else None,
            "last_successful_call": (
                self.last_successful_call.isoformat()
                if self.last_successful_call
                else None
            ),
        }

    async def with_session(self, api_call_func, *args, **kwargs):
        """Execute an API call with ensured authentication and session persistence."""
        # Ensure we're authenticated before making the call
        if not await self.ensure_authenticated():
            raise AuthenticationError("Could not establish authenticated session")
        
        try:
            # Execute the API call
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, api_call_func, *args, **kwargs)
            
            # Update successful call timestamp
            self.update_last_successful_call()
            return result
            
        except Exception as e:
            # Check if this is an authentication error
            if any(auth_pattern in str(e).lower() for auth_pattern in 
                   ["unauthorized", "401", "invalid token", "session expired"]):
                logger.warning(f"API call failed with auth error, clearing session: {e}")
                # Clear current session and try once more
                self._is_authenticated = False
                self.login_time = None
                
                # Try to re-authenticate and retry the call once
                if await self.ensure_authenticated():
                    try:
                        result = await loop.run_in_executor(None, api_call_func, *args, **kwargs)
                        self.update_last_successful_call()
                        return result
                    except Exception as retry_error:
                        logger.error(f"Retry after re-authentication also failed: {retry_error}")
                        raise retry_error
                else:
                    raise AuthenticationError("Failed to re-authenticate after session expired") from e
            else:
                # Non-authentication error, just re-raise
                raise e

    async def logout(self) -> None:
        """Logout and clear session."""
        async with self._lock:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, rh.logout)
                logger.info("Successfully logged out")
                
                # Also remove the pickle file
                pickle_file = self.token_dir / self.pickle_name
                if pickle_file.exists():
                    pickle_file.unlink()
                    logger.info("Removed stored session pickle file")
                    
            except Exception as e:
                logger.error(f"Error during logout: {e}")
            finally:
                self._is_authenticated = False
                self.login_time = None
                self.last_successful_call = None


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
