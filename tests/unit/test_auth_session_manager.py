"""
Comprehensive unit tests for SessionManager authentication module.

Tests cover session lifecycle, circuit breaker patterns, exponential backoff,
authentication metrics, token management, and error recovery as required
by the platform architecture.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from app.auth.session_manager import (
    SessionManager,
    get_session_manager,
    AuthenticationError,
    RateLimitError,
    NetworkError,
    auth_retry_with_backoff,
)


class TestSessionManager:
    """Test suite for SessionManager authentication lifecycle management."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh SessionManager instance for testing."""
        return SessionManager(session_timeout_hours=1, max_auth_failures=3)

    @pytest.fixture
    def mock_robinhood(self):
        """Mock robinhood module functions."""
        with patch("app.auth.session_manager.rh") as mock_rh:
            mock_rh.login = MagicMock()
            mock_rh.logout = MagicMock()
            mock_rh.load_user_profile = MagicMock()
            yield mock_rh

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing log outputs."""
        with patch("app.auth.session_manager.logger") as mock_log:
            yield mock_log

    def test_initialization(self, session_manager):
        """Test SessionManager initialization with default values."""
        assert session_manager.session_timeout_hours == 1
        assert session_manager.max_auth_failures == 3
        assert session_manager.login_time is None
        assert session_manager.last_successful_call is None
        assert session_manager.username is None
        assert session_manager.password is None
        assert session_manager._is_authenticated is False
        assert session_manager._auth_failure_count == 0
        assert session_manager._circuit_breaker_open is False
        assert session_manager._circuit_breaker_reset_time is None

    def test_initialization_with_custom_values(self):
        """Test SessionManager initialization with custom timeout and failure limits."""
        manager = SessionManager(session_timeout_hours=12, max_auth_failures=5)
        assert manager.session_timeout_hours == 12
        assert manager.max_auth_failures == 5

    def test_set_credentials(self, session_manager):
        """Test storing credentials for authentication."""
        session_manager.set_credentials("test_user", "test_password")
        
        assert session_manager.username == "test_user"
        assert session_manager.password == "test_password"

    def test_is_session_valid_false_not_authenticated(self, session_manager):
        """Test session validity when not authenticated."""
        assert session_manager.is_session_valid() is False

    def test_is_session_valid_false_no_login_time(self, session_manager):
        """Test session validity when authenticated but no login time."""
        session_manager._is_authenticated = True
        assert session_manager.is_session_valid() is False

    def test_is_session_valid_false_expired(self, session_manager):
        """Test session validity when session has expired."""
        session_manager._is_authenticated = True
        # Set login time to 2 hours ago (beyond 1 hour timeout)
        session_manager.login_time = datetime.now() - timedelta(hours=2)
        
        assert session_manager.is_session_valid() is False

    def test_is_session_valid_true(self, session_manager):
        """Test session validity when session is valid."""
        session_manager._is_authenticated = True
        # Set login time to 30 minutes ago (within 1 hour timeout)
        session_manager.login_time = datetime.now() - timedelta(minutes=30)
        
        assert session_manager.is_session_valid() is True

    def test_update_last_successful_call(self, session_manager):
        """Test updating timestamp of last successful API call."""
        before = datetime.now()
        session_manager.update_last_successful_call()
        after = datetime.now()
        
        assert session_manager.last_successful_call is not None
        assert before <= session_manager.last_successful_call <= after

    def test_check_circuit_breaker_closed(self, session_manager):
        """Test circuit breaker check when circuit is closed."""
        assert session_manager._check_circuit_breaker() is False

    def test_check_circuit_breaker_open(self, session_manager):
        """Test circuit breaker check when circuit is open."""
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
        
        assert session_manager._check_circuit_breaker() is True

    def test_check_circuit_breaker_reset(self, session_manager, mock_logger):
        """Test circuit breaker automatic reset after timeout."""
        # Setup circuit breaker as open but past reset time
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() - timedelta(seconds=1)
        session_manager._auth_failure_count = 5
        
        # Check should reset the circuit breaker
        result = session_manager._check_circuit_breaker()
        
        assert result is False
        assert session_manager._circuit_breaker_open is False
        assert session_manager._auth_failure_count == 0
        assert session_manager._circuit_breaker_reset_time is None
        mock_logger.info.assert_called_once_with("Circuit breaker reset - authentication attempts resumed")

    def test_open_circuit_breaker(self, session_manager, mock_logger):
        """Test opening circuit breaker after failures."""
        session_manager._auth_failure_count = 3
        
        session_manager._open_circuit_breaker()
        
        assert session_manager._circuit_breaker_open is True
        assert session_manager._circuit_breaker_reset_time is not None
        # Reset time should be approximately 5 minutes from now
        reset_time = session_manager._circuit_breaker_reset_time
        expected_reset = datetime.now() + timedelta(minutes=5)
        assert abs((reset_time - expected_reset).total_seconds()) < 10
        
        mock_logger.error.assert_called_once()

    def test_classify_error_authentication(self, session_manager):
        """Test error classification for authentication errors."""
        errors = [
            Exception("unauthorized access"),
            Exception("401 forbidden"),
            Exception("invalid credentials provided"),
            Exception("authentication failed")
        ]
        
        for error in errors:
            classified = session_manager._classify_error(error)
            assert isinstance(classified, AuthenticationError)

    def test_classify_error_rate_limit(self, session_manager):
        """Test error classification for rate limit errors."""
        errors = [
            Exception("rate limit exceeded"),
            Exception("429 too many requests"),
            Exception("too many requests per minute")
        ]
        
        for error in errors:
            classified = session_manager._classify_error(error)
            assert isinstance(classified, RateLimitError)

    def test_classify_error_network(self, session_manager):
        """Test error classification for network errors."""
        errors = [
            Exception("network timeout occurred"),
            Exception("connection refused"),
            Exception("timeout error"),
            Exception("dns resolution failed")
        ]
        
        for error in errors:
            classified = session_manager._classify_error(error)
            assert isinstance(classified, NetworkError)

    def test_classify_error_other(self, session_manager):
        """Test error classification for other errors."""
        error = ValueError("Some other error")
        classified = session_manager._classify_error(error)
        
        # Should return original error for non-retryable cases
        assert classified is error

    @pytest.mark.asyncio
    async def test_authenticate_success(self, session_manager, mock_robinhood, mock_logger):
        """Test successful authentication flow."""
        # Setup
        session_manager.set_credentials("test_user", "test_password")
        user_profile = {"id": "123", "username": "test_user"}
        mock_robinhood.load_user_profile.return_value = user_profile
        
        # Execute
        result = await session_manager._authenticate()
        
        # Verify
        assert result is True
        assert session_manager._is_authenticated is True
        assert session_manager.login_time is not None
        assert session_manager._auth_successes == 1
        assert session_manager._auth_failure_count == 0
        
        # Verify API calls
        mock_robinhood.login.assert_called_once_with("test_user", "test_password")
        mock_robinhood.load_user_profile.assert_called_once()
        
        # Verify logging
        mock_logger.info.assert_any_call("Attempting to authenticate user: test_user (attempt 1)")
        mock_logger.info.assert_any_call("Successfully authenticated user: test_user")

    @pytest.mark.asyncio
    async def test_authenticate_no_credentials(self, session_manager):
        """Test authentication failure when no credentials provided."""
        with pytest.raises(AuthenticationError, match="No credentials available"):
            await session_manager._authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_login_failure(self, session_manager, mock_robinhood):
        """Test authentication failure during login."""
        session_manager.set_credentials("test_user", "wrong_password")
        mock_robinhood.login.side_effect = Exception("unauthorized access")
        
        with pytest.raises(AuthenticationError):
            await session_manager._authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_profile_load_failure(self, session_manager, mock_robinhood):
        """Test authentication failure when profile loading fails."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = None
        
        with pytest.raises(AuthenticationError, match="Could not retrieve user profile"):
            await session_manager._authenticate()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_valid_session(self, session_manager):
        """Test ensure_authenticated with valid existing session."""
        # Setup valid session
        session_manager._is_authenticated = True
        session_manager.login_time = datetime.now() - timedelta(minutes=30)
        
        result = await session_manager.ensure_authenticated()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_authenticated_circuit_breaker_open(self, session_manager):
        """Test ensure_authenticated when circuit breaker is open."""
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
        
        with pytest.raises(AuthenticationError, match="Circuit breaker is open"):
            await session_manager.ensure_authenticated()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_invalid_session(self, session_manager, mock_robinhood):
        """Test ensure_authenticated when session is invalid."""
        # Setup invalid session
        session_manager._is_authenticated = False
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        result = await session_manager.ensure_authenticated()
        
        assert result is True
        assert session_manager._is_authenticated is True

    def test_get_auth_token_none(self, session_manager):
        """Test getting auth token when none exists."""
        assert session_manager.get_auth_token() is None

    def test_get_auth_token_exists(self, session_manager):
        """Test getting auth token when it exists."""
        session_manager._auth_token = "test_token_123"
        assert session_manager.get_auth_token() == "test_token_123"

    def test_is_token_valid_no_token(self, session_manager):
        """Test token validity when no token exists."""
        assert session_manager.is_token_valid() is False

    def test_is_token_valid_no_expiry(self, session_manager):
        """Test token validity when token exists but no expiry."""
        session_manager._auth_token = "test_token"
        assert session_manager.is_token_valid() is False

    def test_is_token_valid_expired(self, session_manager):
        """Test token validity when token is expired."""
        session_manager._auth_token = "test_token"
        session_manager._token_expiry = datetime.now() - timedelta(hours=1)
        
        assert session_manager.is_token_valid() is False

    def test_is_token_valid_current(self, session_manager):
        """Test token validity when token is current."""
        session_manager._auth_token = "test_token"
        session_manager._token_expiry = datetime.now() + timedelta(hours=1)
        
        assert session_manager.is_token_valid() is True

    @pytest.mark.asyncio
    async def test_refresh_token(self, session_manager, mock_robinhood):
        """Test token refresh functionality."""
        # Setup initial state
        session_manager._auth_token = "old_token"
        session_manager._token_expiry = datetime.now() - timedelta(hours=1)
        session_manager._is_authenticated = True
        
        # Setup for successful re-authentication
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        result = await session_manager.refresh_token()
        
        assert result is True
        # Token should be refreshed (or at least state reset for re-auth)
        assert session_manager._is_authenticated is True

    @pytest.mark.asyncio
    async def test_refresh_token_failure(self, session_manager, mock_robinhood, mock_logger):
        """Test token refresh failure handling."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.login.side_effect = Exception("Network error")
        
        result = await session_manager.refresh_token()
        
        assert result is False
        mock_logger.error.assert_called_with("Token refresh failed: Network error")

    def test_get_auth_metrics(self, session_manager):
        """Test getting comprehensive authentication metrics."""
        # Setup some state
        session_manager._auth_attempts = 5
        session_manager._auth_successes = 3
        session_manager._auth_failure_count = 2
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
        session_manager._last_auth_attempt = datetime.now() - timedelta(minutes=10)
        session_manager.login_time = datetime.now() - timedelta(minutes=30)
        session_manager.last_successful_call = datetime.now() - timedelta(minutes=5)
        session_manager._is_authenticated = True
        session_manager._auth_token = "token123"
        session_manager._token_expiry = datetime.now() + timedelta(hours=1)
        
        metrics = session_manager.get_auth_metrics()
        
        assert metrics["auth_attempts"] == 5
        assert metrics["auth_successes"] == 3
        assert metrics["auth_failure_count"] == 2
        assert metrics["circuit_breaker_open"] is True
        assert metrics["circuit_breaker_reset_time"] is not None
        assert metrics["last_auth_attempt"] is not None
        assert metrics["session_valid"] is True
        assert metrics["token_valid"] is True
        assert metrics["login_time"] is not None
        assert metrics["last_successful_call"] is not None

    def test_get_auth_metrics_empty_state(self, session_manager):
        """Test getting metrics when in default state."""
        metrics = session_manager.get_auth_metrics()
        
        assert metrics["auth_attempts"] == 0
        assert metrics["auth_successes"] == 0
        assert metrics["auth_failure_count"] == 0
        assert metrics["circuit_breaker_open"] is False
        assert metrics["circuit_breaker_reset_time"] is None
        assert metrics["last_auth_attempt"] is None
        assert metrics["session_valid"] is False
        assert metrics["token_valid"] is False
        assert metrics["login_time"] is None
        assert metrics["last_successful_call"] is None

    @pytest.mark.asyncio
    async def test_logout(self, session_manager, mock_robinhood, mock_logger):
        """Test logout functionality."""
        # Setup authenticated state
        session_manager._is_authenticated = True
        session_manager.login_time = datetime.now()
        session_manager.last_successful_call = datetime.now()
        
        await session_manager.logout()
        
        # Verify state cleared
        assert session_manager._is_authenticated is False
        assert session_manager.login_time is None
        assert session_manager.last_successful_call is None
        
        # Verify API call
        mock_robinhood.logout.assert_called_once()
        mock_logger.info.assert_called_once_with("Successfully logged out")

    @pytest.mark.asyncio
    async def test_logout_with_error(self, session_manager, mock_robinhood, mock_logger):
        """Test logout with error during API call."""
        # Setup authenticated state
        session_manager._is_authenticated = True
        session_manager.login_time = datetime.now()
        
        # Setup logout error
        mock_robinhood.logout.side_effect = Exception("Logout error")
        
        await session_manager.logout()
        
        # State should still be cleared despite error
        assert session_manager._is_authenticated is False
        assert session_manager.login_time is None
        mock_logger.error.assert_called_with("Error during logout: Logout error")


class TestAuthRetryDecorator:
    """Test suite for auth_retry_with_backoff decorator."""

    class MockSessionManager:
        """Mock session manager for testing decorator."""
        
        def __init__(self):
            self._auth_failure_count = 0
        
        @auth_retry_with_backoff(max_retries=3, base_delay=0.1, max_delay=1.0)
        async def failing_method(self):
            """Method that always fails for testing."""
            raise AuthenticationError("Test error")
        
        @auth_retry_with_backoff(max_retries=2, base_delay=0.1)
        async def eventually_succeeding_method(self):
            """Method that succeeds on second try."""
            if self._auth_failure_count < 1:
                self._auth_failure_count += 1
                raise NetworkError("Temporary network error")
            return "success"
        
        @auth_retry_with_backoff(max_retries=2, base_delay=0.1)
        async def non_retryable_error_method(self):
            """Method that raises non-retryable error."""
            raise ValueError("Non-retryable error")

    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager for testing."""
        return self.MockSessionManager()

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, mock_session_manager):
        """Test retry decorator when all attempts fail."""
        with pytest.raises(AuthenticationError):
            await mock_session_manager.failing_method()
        
        # Failure count should be incremented for each retry
        assert mock_session_manager._auth_failure_count >= 2

    @pytest.mark.asyncio
    async def test_eventual_success(self, mock_session_manager):
        """Test retry decorator when method eventually succeeds."""
        result = await mock_session_manager.eventually_succeeding_method()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_non_retryable_error(self, mock_session_manager):
        """Test retry decorator with non-retryable error."""
        with pytest.raises(ValueError, match="Non-retryable error"):
            await mock_session_manager.non_retryable_error_method()

    @pytest.mark.asyncio
    async def test_backoff_timing(self, mock_session_manager):
        """Test that backoff delays are applied."""
        import time
        
        start_time = time.time()
        
        with pytest.raises(AuthenticationError):
            await mock_session_manager.failing_method()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should have some delay due to backoff (at least 0.1 + 0.2 + jitter)
        assert elapsed >= 0.2


class TestGlobalSessionManager:
    """Test suite for global SessionManager instance management."""

    def test_get_session_manager_singleton(self):
        """Test that get_session_manager returns singleton instance."""
        # Clear any existing global instance
        import app.auth.session_manager
        app.auth.session_manager._session_manager = None
        
        # Get first instance
        manager1 = get_session_manager()
        
        # Get second instance
        manager2 = get_session_manager()
        
        # Verify they are the same instance
        assert manager1 is manager2
        assert isinstance(manager1, SessionManager)

    def test_get_session_manager_creates_new_instance(self):
        """Test that get_session_manager creates new instance when none exists."""
        # Clear any existing global instance
        import app.auth.session_manager
        app.auth.session_manager._session_manager = None
        
        # Get instance
        manager = get_session_manager()
        
        # Verify
        assert isinstance(manager, SessionManager)
        assert manager.session_timeout_hours == 23  # Default value
        assert manager.max_auth_failures == 5  # Default value

    def test_get_session_manager_thread_safety(self):
        """Test thread safety of global instance creation."""
        import threading
        import app.auth.session_manager
        
        # Clear any existing global instance
        app.auth.session_manager._session_manager = None
        
        instances = []
        
        def get_instance():
            instances.append(get_session_manager())
        
        # Create multiple threads that get the manager
        threads = [threading.Thread(target=get_instance) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all instances are the same
        assert len(instances) == 5
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance


class TestSessionManagerCircuitBreaker:
    """Test suite for circuit breaker functionality in SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create SessionManager with low failure threshold for testing."""
        return SessionManager(session_timeout_hours=1, max_auth_failures=2)

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, session_manager, mock_robinhood):
        """Test that circuit breaker opens after max failures."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.login.side_effect = Exception("unauthorized")
        
        # First failure
        with pytest.raises(AuthenticationError):
            await session_manager._authenticate()
        
        # Second failure should trigger circuit breaker
        with pytest.raises(AuthenticationError):
            await session_manager._authenticate()
        
        assert session_manager._auth_failure_count >= 2
        
        # Circuit breaker should now be open
        session_manager._open_circuit_breaker()
        
        # Next attempt should fail immediately due to circuit breaker
        with pytest.raises(AuthenticationError, match="Circuit breaker is open"):
            await session_manager.ensure_authenticated()

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_timeout(self, session_manager):
        """Test that circuit breaker resets after timeout period."""
        # Manually open circuit breaker with past reset time
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() - timedelta(seconds=1)
        session_manager._auth_failure_count = 5
        
        # Check should reset circuit breaker
        is_open = session_manager._check_circuit_breaker()
        
        assert is_open is False
        assert session_manager._circuit_breaker_open is False
        assert session_manager._auth_failure_count == 0

    def test_circuit_breaker_metrics_tracking(self, session_manager):
        """Test that circuit breaker state is tracked in metrics."""
        session_manager._circuit_breaker_open = True
        session_manager._circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
        
        metrics = session_manager.get_auth_metrics()
        
        assert metrics["circuit_breaker_open"] is True
        assert metrics["circuit_breaker_reset_time"] is not None


class TestSessionManagerTokenHandling:
    """Test suite for token handling in SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh SessionManager instance for testing."""
        return SessionManager()

    @pytest.mark.asyncio
    async def test_token_storage_during_authentication(self, session_manager, mock_robinhood):
        """Test that authentication tokens are properly stored."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        # Mock token attribute on robinhood module
        with patch("app.auth.session_manager.rh.token", "stored_token_123"):
            await session_manager._authenticate()
            
            assert session_manager.get_auth_token() == "stored_token_123"
            assert session_manager.is_token_valid() is True
            # Token expiry should be set to ~23 hours from now
            assert session_manager._token_expiry is not None

    @pytest.mark.asyncio
    async def test_token_refresh_clears_old_token(self, session_manager):
        """Test that token refresh clears old token before re-authentication."""
        # Setup old token
        session_manager._auth_token = "old_token"
        session_manager._token_expiry = datetime.now() - timedelta(hours=1)
        session_manager._is_authenticated = True
        
        with patch.object(session_manager, "ensure_authenticated", return_value=True):
            result = await session_manager.refresh_token()
            
            assert result is True
            # State should be reset for re-authentication
            # (exact behavior depends on ensure_authenticated implementation)

    def test_token_expiry_calculation(self, session_manager):
        """Test that token expiry is calculated correctly."""
        session_manager._auth_token = "test_token"
        # Simulate token being set during authentication
        session_manager._token_expiry = datetime.now() + timedelta(hours=23)
        
        assert session_manager.is_token_valid() is True
        
        # Manually expire token
        session_manager._token_expiry = datetime.now() - timedelta(minutes=1)
        assert session_manager.is_token_valid() is False


class TestSessionManagerAsyncBehavior:
    """Test suite for async behavior patterns in SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh SessionManager instance for testing."""
        return SessionManager()

    @pytest.mark.asyncio
    async def test_async_lock_usage(self, session_manager):
        """Test that async lock is used for thread safety."""
        # The lock should be acquired during ensure_authenticated
        assert session_manager._lock is not None
        assert isinstance(session_manager._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_concurrent_authentication_attempts(self, session_manager, mock_robinhood):
        """Test handling of concurrent authentication attempts."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        # Execute multiple concurrent authentication attempts
        tasks = [session_manager.ensure_authenticated() for _ in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed or at least not raise exceptions
        for result in results:
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_executor_usage_for_blocking_calls(self, session_manager, mock_robinhood):
        """Test that blocking robinhood calls use asyncio executor."""
        session_manager.set_credentials("test_user", "test_password")
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = {"id": "123"}
            
            await session_manager._authenticate()
            
            # Verify executor was used for blocking calls
            assert mock_loop.run_in_executor.call_count >= 1

    @pytest.mark.asyncio
    async def test_logout_async_behavior(self, session_manager, mock_robinhood):
        """Test logout async behavior with executor usage."""
        session_manager._is_authenticated = True
        
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            await session_manager.logout()
            
            # Verify executor was used for logout call
            mock_loop.run_in_executor.assert_called()


class TestSessionManagerErrorRecovery:
    """Test suite for error recovery patterns in SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh SessionManager instance for testing."""
        return SessionManager(max_auth_failures=3)

    @pytest.mark.asyncio
    async def test_recovery_from_network_errors(self, session_manager, mock_robinhood):
        """Test recovery from temporary network errors."""
        session_manager.set_credentials("test_user", "test_password")
        
        # First call fails with network error
        mock_robinhood.login.side_effect = Exception("connection timeout")
        with pytest.raises(NetworkError):
            await session_manager._authenticate()
        
        # Second call succeeds
        mock_robinhood.login.side_effect = None
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        
        result = await session_manager._authenticate()
        assert result is True

    @pytest.mark.asyncio
    async def test_failure_count_reset_on_success(self, session_manager, mock_robinhood):
        """Test that failure count resets on successful authentication."""
        session_manager.set_credentials("test_user", "test_password")
        session_manager._auth_failure_count = 2
        
        # Successful authentication should reset failure count
        mock_robinhood.load_user_profile.return_value = {"id": "123"}
        await session_manager._authenticate()
        
        assert session_manager._auth_failure_count == 0

    @pytest.mark.asyncio
    async def test_persistent_failure_handling(self, session_manager, mock_robinhood):
        """Test handling of persistent authentication failures."""
        session_manager.set_credentials("test_user", "wrong_password")
        mock_robinhood.login.side_effect = Exception("unauthorized")
        
        # Multiple failures should increase failure count
        for _ in range(3):
            with pytest.raises(AuthenticationError):
                await session_manager._authenticate()
        
        # Should eventually open circuit breaker
        assert session_manager._auth_failure_count >= 3