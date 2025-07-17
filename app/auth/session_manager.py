"""Session management for Robin Stocks authentication."""

import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
import robin_stocks.robinhood as rh  # type: ignore
from app.core.logging import logger


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass


class RateLimitError(Exception):
    """Custom exception for rate limit errors."""
    pass


class NetworkError(Exception):
    """Custom exception for network errors."""
    pass


def auth_retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator for adding exponential backoff retry logic to authentication methods."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except (AuthenticationError, RateLimitError, NetworkError) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Final auth attempt failed for {func.__name__}: {e}")
                        raise
                    
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(f"Auth attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                    
                    # Increment failure count for circuit breaker
                    self._auth_failure_count += 1
                except Exception as e:
                    # For other exceptions, don't retry
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            return None
        return wrapper
    return decorator


class SessionManager:
    """Manages Robin Stocks authentication session lifecycle with robust error handling."""

    def __init__(self, session_timeout_hours: int = 23, max_auth_failures: int = 5):
        """Initialize session manager."""
        self.session_timeout_hours = session_timeout_hours
        self.max_auth_failures = max_auth_failures
        self.login_time: Optional[datetime] = None
        self.last_successful_call: Optional[datetime] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self._lock = asyncio.Lock()
        self._is_authenticated = False
        
        # Circuit breaker for authentication failures
        self._auth_failure_count = 0
        self._circuit_breaker_reset_time: Optional[datetime] = None
        self._circuit_breaker_open = False
        
        # Authentication metrics
        self._auth_attempts = 0
        self._auth_successes = 0
        self._last_auth_attempt: Optional[datetime] = None
        
        # Token management
        self._auth_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def set_credentials(self, username: str, password: str) -> None:
        """Store credentials for re-authentication."""
        self.username = username
        self.password = password

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_breaker_open:
            return False
            
        # Check if we should reset the circuit breaker
        if (self._circuit_breaker_reset_time and 
            datetime.now() > self._circuit_breaker_reset_time):
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
        logger.error(f"Circuit breaker opened after {self._auth_failure_count} failures. "
                    f"Authentication blocked until {self._circuit_breaker_reset_time}")

    def _classify_error(self, error: Exception) -> Exception:
        """Classify errors for proper retry handling."""
        error_str = str(error).lower()
        
        # Check for specific error patterns
        if any(pattern in error_str for pattern in ['unauthorized', '401', 'invalid credentials', 'authentication failed']):
            return AuthenticationError(f"Authentication failed: {error}")
        elif any(pattern in error_str for pattern in ['rate limit', '429', 'too many requests']):
            return RateLimitError(f"Rate limit exceeded: {error}")
        elif any(pattern in error_str for pattern in ['network', 'connection', 'timeout', 'dns']):
            return NetworkError(f"Network error: {error}")
        else:
            # Return original error for non-retryable cases
            return error

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
            # Check circuit breaker first
            if self._check_circuit_breaker():
                raise AuthenticationError("Circuit breaker is open - authentication blocked")
                
            if self.is_session_valid():
                return True
            return await self._authenticate()

    @auth_retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    async def _authenticate(self) -> bool:
        """Perform authentication with stored credentials."""
        self._auth_attempts += 1
        self._last_auth_attempt = datetime.now()
        
        if not self.username or not self.password:
            logger.error("No credentials available for authentication")
            raise AuthenticationError("No credentials available for authentication")

        try:
            logger.info(f"Attempting to authenticate user: {self.username} (attempt {self._auth_attempts})")
            loop = asyncio.get_event_loop()
            
            # Perform login
            await loop.run_in_executor(None, rh.login, self.username, self.password)

            # Verify login by making a test API call
            user_profile = await loop.run_in_executor(None, rh.load_user_profile)

            if user_profile:
                self.login_time = datetime.now()
                self._is_authenticated = True
                self._auth_successes += 1
                self._auth_failure_count = 0  # Reset failure count on success
                
                # Store token if available
                self._auth_token = getattr(rh, 'token', None)
                if self._auth_token:
                    # Token typically expires in 24 hours
                    self._token_expiry = datetime.now() + timedelta(hours=23)
                
                logger.info(f"Successfully authenticated user: {self.username}")
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
                
            raise classified_error

    def get_auth_token(self) -> Optional[str]:
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

    def get_auth_metrics(self) -> Dict[str, Any]:
        """Get authentication metrics."""
        return {
            "auth_attempts": self._auth_attempts,
            "auth_successes": self._auth_successes,
            "auth_failure_count": self._auth_failure_count,
            "circuit_breaker_open": self._circuit_breaker_open,
            "circuit_breaker_reset_time": self._circuit_breaker_reset_time.isoformat() if self._circuit_breaker_reset_time else None,
            "last_auth_attempt": self._last_auth_attempt.isoformat() if self._last_auth_attempt else None,
            "session_valid": self.is_session_valid(),
            "token_valid": self.is_token_valid(),
            "login_time": self.login_time.isoformat() if self.login_time else None,
            "last_successful_call": self.last_successful_call.isoformat() if self.last_successful_call else None
        }

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
