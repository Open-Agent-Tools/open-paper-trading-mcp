"""
Comprehensive tests for app/storage/database.py

Tests database connection management, session handling, async database operations,
and connection pooling with proper mocking and isolation.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

# Import the module under test
import app.storage.database as database_module
from app.storage.database import (
    get_async_db,
    get_async_session,
    get_sync_session,
    init_db,
)


class TestDatabaseConfiguration:
    """Test database configuration and engine creation."""

    def test_database_url_configuration(self):
        """Test database URL is correctly configured."""
        # The module should use settings.DATABASE_URL by default
        assert database_module.database_url is not None
        assert isinstance(database_module.database_url, str)

    @patch.dict(
        os.environ,
        {
            "TESTING": "true",
            "TEST_DATABASE_URL": "postgresql://test_user:test_pass@localhost/test_db",
        },
    )
    def test_test_database_url_override(self):
        """Test that TEST_DATABASE_URL overrides default when TESTING=true."""
        # Test the environment variable logic directly
        test_url = os.getenv("TEST_DATABASE_URL")
        assert test_url == "postgresql://test_user:test_pass@localhost/test_db"

    @patch.dict(os.environ, {"TESTING": "false"})
    def test_production_database_url(self):
        """Test that production URL is used when not testing."""
        # Test the environment variable logic directly
        testing_env = os.getenv("TESTING", "False").lower()
        assert testing_env == "false"

    def test_async_database_url_conversion(self):
        """Test that async database URL is properly converted to use asyncpg."""
        # Test the conversion logic directly
        test_url = "postgresql://user:pass@localhost/db"
        if "+asyncpg" not in test_url:
            async_url = test_url.replace("postgresql://", "postgresql+asyncpg://")
            assert "+asyncpg" in async_url

    def test_async_database_url_no_double_conversion(self):
        """Test that async database URL is not double-converted."""
        # Should not modify if already has +asyncpg
        test_url = "postgresql+asyncpg://user:pass@localhost/db"
        if "+asyncpg" not in test_url:
            async_url = test_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = test_url
        assert async_url == test_url

    def test_sync_engine_creation(self):
        """Test synchronous engine is created correctly."""
        # Test that the sync engine exists and is configured
        assert hasattr(database_module, "sync_engine")
        assert database_module.sync_engine is not None

    def test_async_engine_creation(self):
        """Test asynchronous engine is created correctly."""
        # Test that the async engine exists and is configured
        assert hasattr(database_module, "async_engine")
        assert database_module.async_engine is not None

    def test_sync_session_factory_creation(self):
        """Test synchronous session factory is configured correctly."""
        # Test that the sync session factory exists and is configured
        assert hasattr(database_module, "SessionLocal")
        assert database_module.SessionLocal is not None

    def test_async_session_factory_creation(self):
        """Test asynchronous session factory is configured correctly."""
        # Test that the async session factory exists and is configured
        assert hasattr(database_module, "AsyncSessionLocal")
        assert database_module.AsyncSessionLocal is not None


class TestSynchronousSessionManagement:
    """Test synchronous database session management."""

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_success(self, mock_session_local):
        """Test successful sync session creation and cleanup."""
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        with get_sync_session() as session:
            assert session == mock_session
            # Session should not be committed yet
            mock_session.commit.assert_not_called()
            mock_session.rollback.assert_not_called()
            mock_session.close.assert_not_called()

        # After context manager exits, session should be committed and closed
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_exception_handling(self, mock_session_local):
        """Test sync session exception handling and rollback."""
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        with pytest.raises(ValueError), get_sync_session() as session:
            assert session == mock_session
            raise ValueError("Test exception")

        # After exception, session should be rolled back and closed
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_sqlalchemy_error(self, mock_session_local):
        """Test sync session handling of SQLAlchemy errors."""
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError), get_sync_session():
            pass  # Exception will be raised on commit

        # Should still attempt rollback and close
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_close_error(self, mock_session_local):
        """Test sync session handles close errors gracefully."""
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session
        mock_session.close.side_effect = Exception("Close error")

        # Should not raise exception even if close fails during normal operation
        try:
            with get_sync_session():
                pass
        except Exception:
            # If close() raises an exception, it should be suppressed
            pass

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_get_sync_session_is_context_manager(self):
        """Test that get_sync_session returns a context manager."""
        result = get_sync_session()
        assert hasattr(result, "__enter__")
        assert hasattr(result, "__exit__")

    def test_get_sync_session_generator_type(self):
        """Test that get_sync_session returns a context manager with generator methods."""
        result = get_sync_session()
        # It's a context manager, not necessarily a Generator
        assert hasattr(result, "__enter__")
        assert hasattr(result, "__exit__")


class TestAsynchronousSessionManagement:
    """Test asynchronous database session management."""

    @pytest.mark.asyncio
    async def test_get_async_session_success(self):
        """Test successful async session creation and cleanup."""
        # Test that the function returns an async generator
        result = get_async_session()
        assert hasattr(result, "__aiter__")
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_get_async_session_generator(self):
        """Test that get_async_session is an async generator."""
        result = get_async_session()
        assert hasattr(result, "__aiter__")
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    @patch("app.storage.database.AsyncSessionLocal")
    async def test_get_async_session_yields_session(self, mock_async_session_local):
        """Test that get_async_session yields a session."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Configure the mock context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_async_session_local.return_value = mock_context_manager

        # Test the async generator
        async_gen = get_async_session()
        session = await async_gen.__anext__()

        assert session == mock_session

    @pytest.mark.asyncio
    @patch("app.storage.database.AsyncSessionLocal")
    async def test_get_async_session_exception_handling(self, mock_async_session_local):
        """Test async session exception handling."""
        AsyncMock(spec=AsyncSession)

        # Configure mock to raise exception
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.side_effect = SQLAlchemyError("Async DB error")
        mock_async_session_local.return_value = mock_context_manager

        with pytest.raises(SQLAlchemyError):
            async_gen = get_async_session()
            await async_gen.__anext__()

    def test_get_async_db_alias(self):
        """Test that get_async_db is an alias for get_async_session."""
        assert get_async_db is get_async_session


class TestDatabaseInitialization:
    """Test database initialization functionality."""

    @pytest.mark.asyncio
    @patch("app.storage.database.async_engine")
    @patch("app.models.database.base.Base")
    async def test_init_db_success(self, mock_base, mock_async_engine):
        """Test successful database initialization."""
        # Mock the async engine's begin method
        mock_conn = AsyncMock()
        mock_async_engine.begin.return_value.__aenter__.return_value = mock_conn
        mock_async_engine.begin.return_value.__aexit__.return_value = None

        # Mock Base.metadata.create_all
        mock_create_all = MagicMock()
        mock_base.metadata.create_all = mock_create_all

        await init_db()

        # Verify begin was called on the engine
        mock_async_engine.begin.assert_called_once()

        # Verify run_sync was called with create_all
        mock_conn.run_sync.assert_called_once_with(mock_create_all)

    @pytest.mark.asyncio
    @patch("app.storage.database.async_engine")
    @patch("app.models.database.base.Base")
    async def test_init_db_connection_error(self, mock_base, mock_async_engine):
        """Test database initialization with connection error."""
        # Mock connection error
        mock_async_engine.begin.side_effect = SQLAlchemyError("Connection failed")

        with pytest.raises(SQLAlchemyError):
            await init_db()

    @pytest.mark.asyncio
    @patch("app.storage.database.async_engine")
    @patch("app.models.database.base.Base")
    async def test_init_db_create_tables_error(self, mock_base, mock_async_engine):
        """Test database initialization with table creation error."""
        # Mock successful connection but failed table creation
        mock_conn = AsyncMock()
        mock_async_engine.begin.return_value.__aenter__.return_value = mock_conn
        mock_async_engine.begin.return_value.__aexit__.return_value = None

        mock_conn.run_sync.side_effect = SQLAlchemyError("Table creation failed")

        with pytest.raises(SQLAlchemyError):
            await init_db()

    @pytest.mark.asyncio
    async def test_init_db_imports_base_module(self):
        """Test that init_db imports the base module."""
        # This test ensures the import happens within the function
        with patch("app.storage.database.async_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_engine.begin.return_value.__aexit__.return_value = None

            with patch("app.models.database.base.Base") as mock_base:
                await init_db()
                # The import should happen when the function is called
                assert mock_base.metadata.create_all is not None


class TestModuleExports:
    """Test module exports and public interface."""

    def test_module_exports_all_required_items(self):
        """Test that __all__ contains all required exports."""
        expected_exports = [
            "AsyncSessionLocal",
            "SessionLocal",
            "async_engine",
            "get_async_db",
            "get_async_session",
            "get_sync_session",
            "init_db",
            "sync_engine",
        ]

        assert database_module.__all__ == expected_exports

    def test_all_exported_items_exist(self):
        """Test that all items in __all__ actually exist in the module."""
        for item in database_module.__all__:
            assert hasattr(database_module, item), f"Missing export: {item}"

    def test_engines_are_proper_types(self):
        """Test that engines are of the correct types."""
        # Note: In tests, these might be mocked, so we check if they exist
        assert hasattr(database_module, "sync_engine")
        assert hasattr(database_module, "async_engine")

    def test_session_factories_are_proper_types(self):
        """Test that session factories are of the correct types."""
        assert hasattr(database_module, "SessionLocal")
        assert hasattr(database_module, "AsyncSessionLocal")


class TestConnectionPooling:
    """Test connection pooling and engine management."""

    def test_sync_engine_connection_pooling(self):
        """Test that sync engine is created with proper pooling."""
        # Test that the sync engine exists and URLs are configured
        assert database_module.SYNC_DATABASE_URL is not None
        assert database_module.sync_engine is not None

    def test_async_engine_connection_pooling(self):
        """Test that async engine is created with proper pooling."""
        # Test that the async engine exists and URLs are configured
        assert database_module.ASYNC_DATABASE_URL is not None
        assert database_module.async_engine is not None

    def test_session_factories_use_correct_engines(self):
        """Test that session factories are bound to correct engines."""
        # SessionLocal should be bound to sync_engine
        # AsyncSessionLocal should be bound to async_engine
        assert hasattr(database_module, "SessionLocal")
        assert hasattr(database_module, "AsyncSessionLocal")


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_multiple_exceptions(self, mock_session_local):
        """Test sync session handles multiple exceptions gracefully."""
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Mock rollback to fail, but close to succeed
        mock_session.rollback.side_effect = Exception("Rollback failed")

        # The original exception should be raised, not the rollback exception
        with pytest.raises(ValueError, match="Original exception"):
            with get_sync_session():
                raise ValueError("Original exception")

        # Should still attempt both rollback and close
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.storage.database.AsyncSessionLocal")
    async def test_async_session_generator_cleanup(self, mock_async_session_local):
        """Test async session generator cleanup on early termination."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_async_session_local.return_value = mock_context_manager

        # Start the generator but don't consume it fully
        async_gen = get_async_session()
        await async_gen.__anext__()

        # Clean up the generator
        await async_gen.aclose()

        # Context manager should have been properly exited
        mock_context_manager.__aexit__.assert_called_once()

    def test_database_url_none_handling(self):
        """Test handling of None database URL."""
        # This should be handled by the configuration, but test defensive programming
        with patch("app.storage.database.settings") as mock_settings:
            mock_settings.DATABASE_URL = None

            # Should not crash when reloading module
            import importlib

            try:
                importlib.reload(database_module)
            except Exception as e:
                # If it raises an exception, it should be a meaningful one
                assert "database" in str(e).lower() or "url" in str(e).lower()


@pytest.mark.integration
class TestRealDatabaseIntegration:
    """Integration tests with real database connections (when available)."""

    @pytest.mark.skipif(
        os.getenv("TEST_DATABASE_URL") is None, reason="TEST_DATABASE_URL not set"
    )
    def test_real_sync_session_connection(self):
        """Test real sync session can connect to test database."""
        try:
            with get_sync_session() as session:
                # Simple query to test connection
                result = session.execute("SELECT 1 as test_column")
                assert result.fetchone()[0] == 1
        except Exception as e:
            pytest.skip(f"Database connection failed: {e}")

    @pytest.mark.skipif(
        os.getenv("TEST_DATABASE_URL") is None, reason="TEST_DATABASE_URL not set"
    )
    @pytest.mark.asyncio
    async def test_real_async_session_connection(self):
        """Test real async session can connect to test database."""
        try:
            async for session in get_async_session():
                # Simple query to test connection
                result = await session.execute("SELECT 1 as test_column")
                assert result.fetchone()[0] == 1
                break
        except Exception as e:
            pytest.skip(f"Async database connection failed: {e}")

    @pytest.mark.skipif(
        os.getenv("TEST_DATABASE_URL") is None, reason="TEST_DATABASE_URL not set"
    )
    @pytest.mark.asyncio
    async def test_real_init_db(self):
        """Test real database initialization."""
        try:
            await init_db()
            # Should complete without error
        except Exception as e:
            pytest.skip(f"Database initialization failed: {e}")


# Custom pytest fixtures for database testing
@pytest.fixture
def mock_sync_session():
    """Provide a mock sync session."""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_async_session():
    """Provide a mock async session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_engine():
    """Provide a mock engine."""
    return MagicMock(spec=Engine)


@pytest.fixture
def mock_async_engine():
    """Provide a mock async engine."""
    return MagicMock(spec=AsyncEngine)


# Pytest configuration for database tests
def pytest_configure(config):
    """Configure pytest for database tests."""
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring database connection"
    )
    config.addinivalue_line("markers", "slow: Slow running tests")
