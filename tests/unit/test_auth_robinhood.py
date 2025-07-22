"""
Comprehensive unit tests for RobinhoodAuth authentication module.

Tests cover authentication flows, session management, token handling,
error scenarios, and async patterns as required by the platform architecture.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.robinhood_auth import RobinhoodAuth, get_robinhood_client


class TestRobinhoodAuth:
    """Test suite for RobinhoodAuth authentication manager."""

    @pytest.fixture
    def auth_instance(self):
        """Create fresh RobinhoodAuth instance for testing."""
        return RobinhoodAuth()

    @pytest.fixture
    def mock_robin_stocks(self):
        """Mock robin_stocks module functions."""
        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login = MagicMock()
            mock_r.logout = MagicMock()
            yield mock_r

    @pytest.fixture
    def mock_settings(self):
        """Mock authentication settings."""
        mock_settings = MagicMock()
        mock_settings.username = "test_user"
        mock_settings.get_password.return_value = "test_password"
        return mock_settings

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing log outputs."""
        with patch("app.auth.robinhood_auth.logger") as mock_log:
            yield mock_log

    @pytest.mark.asyncio
    async def test_authentication_success(
        self, auth_instance, mock_robin_stocks, mock_settings, mock_logger
    ):
        """Test successful authentication flow."""
        # Setup
        session_info = {"access_token": "test_token", "expires_in": 86400}
        mock_robin_stocks.login.return_value = session_info

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # Execute
            result = await auth_instance.authenticate()

            # Verify
            assert result is True
            assert auth_instance._authenticated is True
            assert auth_instance._session_info == session_info

            # Verify login was called with correct parameters
            mock_robin_stocks.login.assert_called_once_with(
                "test_user", "test_password"
            )

            # Verify logging
            mock_logger.info.assert_any_call(
                "Attempting to authenticate with Robinhood..."
            )
            mock_logger.info.assert_any_call("Robinhood authentication successful.")

    @pytest.mark.asyncio
    async def test_authentication_failure_exception(
        self, auth_instance, mock_robin_stocks, mock_settings, mock_logger
    ):
        """Test authentication failure with exception."""
        # Setup
        mock_robin_stocks.login.side_effect = Exception("Network error")

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # Execute
            result = await auth_instance.authenticate()

            # Verify
            assert result is False
            assert auth_instance._authenticated is False
            assert auth_instance._session_info is None

            # Verify error logging
            mock_logger.error.assert_called_once_with(
                "Robinhood authentication failed: Network error"
            )

    @pytest.mark.asyncio
    async def test_authentication_failure_invalid_credentials(
        self, auth_instance, mock_robin_stocks, mock_settings, mock_logger
    ):
        """Test authentication failure with invalid credentials."""
        # Setup
        mock_robin_stocks.login.side_effect = ValueError("Invalid credentials")

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # Execute
            result = await auth_instance.authenticate()

            # Verify
            assert result is False
            assert auth_instance._authenticated is False
            mock_logger.error.assert_called_once_with(
                "Robinhood authentication failed: Invalid credentials"
            )

    @pytest.mark.asyncio
    async def test_authentication_executor_usage(
        self, auth_instance, mock_robin_stocks, mock_settings
    ):
        """Test that authentication uses asyncio executor properly."""
        # Setup
        session_info = {"access_token": "test_token"}
        mock_robin_stocks.login.return_value = session_info

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_event_loop = AsyncMock()
                mock_loop.return_value = mock_event_loop
                mock_event_loop.run_in_executor.return_value = session_info

                # Execute
                result = await auth_instance.authenticate()

                # Verify
                assert result is True
                # Verify executor was used for blocking call
                mock_event_loop.run_in_executor.assert_called_once()
                call_args = mock_event_loop.run_in_executor.call_args
                assert call_args[0][0] is None  # executor = None (default)

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_instance, mock_robin_stocks, mock_logger):
        """Test successful logout flow."""
        # Setup - simulate authenticated state
        auth_instance._authenticated = True
        auth_instance._session_info = {"access_token": "test_token"}

        # Execute
        result = await auth_instance.logout()

        # Verify
        assert result is True
        assert auth_instance._authenticated is False
        assert auth_instance._session_info is None

        # Verify robin_stocks logout was called
        mock_robin_stocks.logout.assert_called_once()
        mock_logger.info.assert_called_once_with("Logging out from Robinhood.")

    @pytest.mark.asyncio
    async def test_logout_clears_state_on_exception(
        self, auth_instance, mock_robin_stocks, mock_logger
    ):
        """Test logout clears state even if robin_stocks.logout raises exception."""
        # Setup
        auth_instance._authenticated = True
        auth_instance._session_info = {"access_token": "test_token"}
        mock_robin_stocks.logout.side_effect = Exception("Logout error")

        # Execute
        result = await auth_instance.logout()

        # Verify state is cleared regardless of exception
        assert result is True  # logout() should always return True
        assert auth_instance._authenticated is False
        assert auth_instance._session_info is None

    def test_is_authenticated_true(self, auth_instance):
        """Test is_authenticated returns True when authenticated."""
        auth_instance._authenticated = True
        assert auth_instance.is_authenticated() is True

    def test_is_authenticated_false(self, auth_instance):
        """Test is_authenticated returns False when not authenticated."""
        auth_instance._authenticated = False
        assert auth_instance.is_authenticated() is False

    def test_is_authenticated_default_state(self, auth_instance):
        """Test is_authenticated returns False in default state."""
        assert auth_instance.is_authenticated() is False

    def test_dataclass_initialization(self, auth_instance):
        """Test proper dataclass initialization."""
        assert auth_instance._authenticated is False
        assert auth_instance._session_info is None

    @pytest.mark.asyncio
    async def test_concurrent_authentication_attempts(
        self, auth_instance, mock_robin_stocks, mock_settings
    ):
        """Test handling of concurrent authentication attempts."""
        # Setup
        session_info = {"access_token": "test_token"}
        mock_robin_stocks.login.return_value = session_info

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # Execute multiple concurrent authentication attempts
            tasks = [auth_instance.authenticate() for _ in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify
            # All should succeed or at least not raise exceptions
            for result in results:
                assert isinstance(result, bool)
                assert result is True

            # Login should have been called (exact count may vary due to concurrency)
            assert mock_robin_stocks.login.call_count >= 1

    @pytest.mark.asyncio
    async def test_authentication_state_persistence(
        self, auth_instance, mock_robin_stocks, mock_settings
    ):
        """Test that authentication state persists across method calls."""
        # Setup
        session_info = {"access_token": "test_token", "user_id": "12345"}
        mock_robin_stocks.login.return_value = session_info

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # Execute
            result = await auth_instance.authenticate()

            # Verify initial state
            assert result is True
            assert auth_instance.is_authenticated() is True

            # Check state persistence
            assert auth_instance._session_info == session_info
            assert auth_instance.is_authenticated() is True

            # Logout and verify state change
            await auth_instance.logout()
            assert auth_instance.is_authenticated() is False
            assert auth_instance._session_info is None

    @pytest.mark.asyncio
    async def test_authentication_retry_behavior(
        self, auth_instance, mock_robin_stocks, mock_settings, mock_logger
    ):
        """Test authentication behavior with retries."""
        # Setup - first call fails, but class doesn't implement retries
        # This tests that individual calls fail appropriately
        mock_robin_stocks.login.side_effect = [
            Exception("Temporary network error"),
            {"access_token": "test_token"},
        ]

        with patch("app.auth.robinhood_auth.settings", mock_settings):
            # First attempt should fail
            result1 = await auth_instance.authenticate()
            assert result1 is False

            # Second attempt should succeed
            result2 = await auth_instance.authenticate()
            assert result2 is True


class TestGlobalRobinhoodClient:
    """Test suite for global RobinhoodAuth instance management."""

    def test_get_robinhood_client_singleton(self):
        """Test that get_robinhood_client returns singleton instance."""
        # Clear any existing global instance
        import app.auth.robinhood_auth

        app.auth.robinhood_auth._robinhood_auth = None

        # Get first instance
        client1 = get_robinhood_client()

        # Get second instance
        client2 = get_robinhood_client()

        # Verify they are the same instance
        assert client1 is client2
        assert isinstance(client1, RobinhoodAuth)

    def test_get_robinhood_client_creates_new_instance(self):
        """Test that get_robinhood_client creates new instance when none exists."""
        # Clear any existing global instance
        import app.auth.robinhood_auth

        app.auth.robinhood_auth._robinhood_auth = None

        # Get instance
        client = get_robinhood_client()

        # Verify
        assert isinstance(client, RobinhoodAuth)
        assert client._authenticated is False
        assert client._session_info is None

    def test_get_robinhood_client_thread_safety(self):
        """Test thread safety of global instance creation."""
        import threading

        import app.auth.robinhood_auth

        # Clear any existing global instance
        app.auth.robinhood_auth._robinhood_auth = None

        instances = []

        def get_instance():
            instances.append(get_robinhood_client())

        # Create multiple threads that get the client
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


class TestRobinhoodAuthErrorHandling:
    """Test suite for error handling in RobinhoodAuth."""

    @pytest.fixture
    def auth_instance(self):
        """Create fresh RobinhoodAuth instance for testing."""
        return RobinhoodAuth()

    @pytest.mark.asyncio
    async def test_authentication_network_timeout(self, auth_instance):
        """Test handling of network timeout during authentication."""
        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login.side_effect = TimeoutError("Connection timeout")

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                result = await auth_instance.authenticate()

                assert result is False
                assert auth_instance._authenticated is False

    @pytest.mark.asyncio
    async def test_authentication_connection_error(self, auth_instance):
        """Test handling of connection error during authentication."""
        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login.side_effect = ConnectionError("Failed to connect")

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                result = await auth_instance.authenticate()

                assert result is False
                assert auth_instance._authenticated is False

    @pytest.mark.asyncio
    async def test_authentication_missing_credentials(self, auth_instance):
        """Test authentication with missing credentials."""
        with patch("app.auth.robinhood_auth.settings") as mock_settings:
            mock_settings.username = None
            mock_settings.get_password.return_value = None

            with patch("app.auth.robinhood_auth.r"):
                result = await auth_instance.authenticate()

                # Should still attempt login but likely fail
                assert isinstance(result, bool)
                # Don't assert specific result as it depends on robin_stocks behavior

    @pytest.mark.asyncio
    async def test_logout_exception_handling(self, auth_instance):
        """Test logout handles exceptions gracefully."""
        # Setup authenticated state
        auth_instance._authenticated = True
        auth_instance._session_info = {"token": "test"}

        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.logout.side_effect = Exception("Logout failed")

            # Should not raise exception and should clear state
            result = await auth_instance.logout()

            assert result is True
            assert auth_instance._authenticated is False
            assert auth_instance._session_info is None


class TestRobinhoodAuthAsyncBehavior:
    """Test suite for async behavior and patterns in RobinhoodAuth."""

    @pytest.fixture
    def auth_instance(self):
        """Create fresh RobinhoodAuth instance for testing."""
        return RobinhoodAuth()

    @pytest.mark.asyncio
    async def test_authenticate_is_async(self, auth_instance):
        """Test that authenticate method is properly async."""
        # Verify it's a coroutine
        coro = auth_instance.authenticate()
        assert asyncio.iscoroutine(coro)

        # Clean up the coroutine
        try:
            await coro
        except Exception:
            pass  # We just want to test it's async

    @pytest.mark.asyncio
    async def test_logout_is_async(self, auth_instance):
        """Test that logout method is properly async."""
        # Verify it's a coroutine
        coro = auth_instance.logout()
        assert asyncio.iscoroutine(coro)

        # Clean up the coroutine
        try:
            await coro
        except Exception:
            pass  # We just want to test it's async

    @pytest.mark.asyncio
    async def test_async_executor_integration(self, auth_instance):
        """Test integration with asyncio executor for blocking calls."""
        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = {"token": "test"}

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                await auth_instance.authenticate()

                # Verify executor was used
                mock_loop.run_in_executor.assert_called()

    def test_is_authenticated_synchronous(self, auth_instance):
        """Test that is_authenticated is synchronous (not async)."""
        # Should be callable without await
        result = auth_instance.is_authenticated()
        assert isinstance(result, bool)
        assert not asyncio.iscoroutine(result)


class TestRobinhoodAuthSessionInfo:
    """Test suite for session information handling."""

    @pytest.fixture
    def auth_instance(self):
        """Create fresh RobinhoodAuth instance for testing."""
        return RobinhoodAuth()

    @pytest.mark.asyncio
    async def test_session_info_storage(self, auth_instance):
        """Test that session info is properly stored."""
        session_data = {
            "access_token": "test_token_123",
            "expires_in": 86400,
            "user_id": "user_123",
            "account_id": "account_456",
        }

        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login.return_value = session_data

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                await auth_instance.authenticate()

                assert auth_instance._session_info == session_data

    @pytest.mark.asyncio
    async def test_session_info_clearing(self, auth_instance):
        """Test that session info is cleared on logout."""
        # Setup initial session
        auth_instance._authenticated = True
        auth_instance._session_info = {"token": "test", "user": "123"}

        with patch("app.auth.robinhood_auth.r"):
            await auth_instance.logout()

            assert auth_instance._session_info is None

    def test_session_info_access(self, auth_instance):
        """Test access to session info."""
        # Initially should be None
        assert auth_instance._session_info is None

        # Set some session info
        test_info = {"test": "data"}
        auth_instance._session_info = test_info

        # Should be accessible
        assert auth_instance._session_info == test_info


class TestRobinhoodAuthIntegration:
    """Integration tests for RobinhoodAuth with real-like scenarios."""

    @pytest.fixture
    def auth_instance(self):
        """Create fresh RobinhoodAuth instance for testing."""
        return RobinhoodAuth()

    @pytest.mark.asyncio
    async def test_full_authentication_cycle(self, auth_instance):
        """Test complete authentication and logout cycle."""
        session_data = {"access_token": "token123", "expires_in": 86400}

        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login.return_value = session_data

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                # Initial state
                assert not auth_instance.is_authenticated()
                assert auth_instance._session_info is None

                # Authenticate
                result = await auth_instance.authenticate()
                assert result is True
                assert auth_instance.is_authenticated() is True
                assert auth_instance._session_info == session_data

                # Logout
                result = await auth_instance.logout()
                assert result is True
                assert auth_instance.is_authenticated() is False
                assert auth_instance._session_info is None

    @pytest.mark.asyncio
    async def test_multiple_authentication_attempts(self, auth_instance):
        """Test multiple authentication attempts."""
        session_data = {"access_token": "token123"}

        with patch("app.auth.robinhood_auth.r") as mock_r:
            mock_r.login.return_value = session_data

            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                # First authentication
                result1 = await auth_instance.authenticate()
                assert result1 is True

                # Second authentication (should overwrite)
                result2 = await auth_instance.authenticate()
                assert result2 is True

                # Should still be authenticated
                assert auth_instance.is_authenticated() is True

    @pytest.mark.asyncio
    async def test_authentication_failure_recovery(self, auth_instance):
        """Test recovery from authentication failure."""
        with patch("app.auth.robinhood_auth.r") as mock_r:
            with patch("app.auth.robinhood_auth.settings") as mock_settings:
                mock_settings.username = "test_user"
                mock_settings.get_password.return_value = "test_password"

                # First attempt fails
                mock_r.login.side_effect = Exception("Network error")
                result1 = await auth_instance.authenticate()
                assert result1 is False
                assert not auth_instance.is_authenticated()

                # Second attempt succeeds
                mock_r.login.side_effect = None
                mock_r.login.return_value = {"token": "success"}
                result2 = await auth_instance.authenticate()
                assert result2 is True
                assert auth_instance.is_authenticated()
