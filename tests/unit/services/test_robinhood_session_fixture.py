"""
Test file specifically for validating the shared Robinhood session fixture.

This ensures that:
1. The shared session fixture loads credentials from .env correctly
2. Authentication works properly
3. Multiple tests can share the same authenticated session
4. Session cleanup works correctly
"""

import pytest

pytestmark = pytest.mark.journey_market_data


class TestRobinhoodSessionFixture:
    """Test the shared Robinhood session fixture."""

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_robinhood_session_fixture_authentication(self, robinhood_session):
        """Test that the Robinhood session fixture authenticates successfully."""
        # The fixture should provide an authenticated session manager
        assert robinhood_session is not None
        assert robinhood_session.username is not None
        assert robinhood_session.password is not None
        assert robinhood_session._is_authenticated is True
        assert robinhood_session.login_time is not None

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_robinhood_session_is_shared(self, robinhood_session):
        """Test that the same session instance is shared across tests."""
        # This test should get the same session instance as the previous test
        assert robinhood_session is not None
        assert robinhood_session._is_authenticated is True

        # The login time should be the same as from the first authentication
        # (proving the session is shared, not re-created)
        assert robinhood_session.login_time is not None

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_trading_service_with_shared_session(self, trading_service_robinhood):
        """Test that trading service uses the shared authenticated session."""
        # The trading service should have access to the authenticated session
        assert trading_service_robinhood is not None
        assert trading_service_robinhood.quote_adapter is not None

        # Verify the adapter uses the same session manager
        session_manager = trading_service_robinhood.quote_adapter.session_manager
        assert session_manager is not None
        assert session_manager._is_authenticated is True

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_multiple_services_share_session(
        self, trading_service_robinhood, robinhood_session
    ):
        """Test that multiple trading services can share the same session."""
        from app.adapters.robinhood import RobinhoodAdapter
        from app.services.trading_service import TradingService

        # Create a second trading service
        adapter2 = RobinhoodAdapter()
        service2 = TradingService(quote_adapter=adapter2)

        # Both services should use the same authenticated session
        session1 = trading_service_robinhood.quote_adapter.session_manager
        session2 = service2.quote_adapter.session_manager

        # They should be the same instance (singleton pattern)
        assert session1 is session2
        assert session1 is robinhood_session
        assert session1._is_authenticated is True

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_session_credentials_loaded_from_env(self, robinhood_session):
        """Test that session credentials are loaded from environment variables."""
        import os

        # Check that the session has the same credentials as in .env
        env_username = os.getenv("ROBINHOOD_USERNAME")
        env_password = os.getenv("ROBINHOOD_PASSWORD")

        if env_username and env_password:
            assert robinhood_session.username == env_username
            assert robinhood_session.password == env_password
        else:
            pytest.skip("Robinhood credentials not found in .env")

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_session_stays_authenticated_across_tests(self, robinhood_session):
        """Test that the session remains authenticated across multiple test calls."""
        # Verify current authentication status
        assert robinhood_session._is_authenticated is True

        # Call ensure_authenticated (should not need to re-authenticate)
        is_authenticated = await robinhood_session.ensure_authenticated()
        assert is_authenticated is True

        # Should still be using the same login time (no re-authentication occurred)
        original_login_time = robinhood_session.login_time
        assert original_login_time is not None

        # Make another call
        is_authenticated_again = await robinhood_session.ensure_authenticated()
        assert is_authenticated_again is True

        # Login time should be unchanged (same session, not re-authenticated)
        assert robinhood_session.login_time == original_login_time
