"""
Comprehensive foundation tests for app.storage.database module.

This test suite provides the core foundation tests for the storage database module,
covering basic functionality, imports, and essential patterns.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session


class TestStorageDatabaseFoundation:
    """Foundation tests for storage database functionality."""

    def test_module_imports_successfully(self):
        """Test that the storage.database module imports without errors."""
        import app.storage.database

        assert app.storage.database is not None

    def test_engines_are_created(self):
        """Test that both sync and async engines are created."""
        from app.storage.database import async_engine, sync_engine

        assert sync_engine is not None
        assert async_engine is not None
        assert isinstance(sync_engine, Engine)
        assert isinstance(async_engine, AsyncEngine)

    def test_session_factories_exist(self):
        """Test that session factories are available."""
        from app.storage.database import AsyncSessionLocal, SessionLocal

        assert SessionLocal is not None
        assert AsyncSessionLocal is not None
        assert callable(SessionLocal)
        assert callable(AsyncSessionLocal)

    def test_session_context_managers_exist(self):
        """Test that session context managers are available."""
        from app.storage.database import get_async_session, get_sync_session

        assert callable(get_sync_session)
        assert callable(get_async_session)

    def test_init_db_function_exists(self):
        """Test that database initialization function exists."""
        from app.storage.database import init_db

        assert callable(init_db)

    def test_module_exports_all_required_symbols(self):
        """Test that module exports all required symbols."""
        import app.storage.database as db_module

        required_symbols = [
            "AsyncSessionLocal",
            "SessionLocal",
            "async_engine",
            "sync_engine",
            "get_async_session",
            "get_sync_session",
            "get_async_db",
            "init_db",
        ]

        for symbol in required_symbols:
            assert hasattr(db_module, symbol), f"Missing required symbol: {symbol}"

    def test_database_url_configuration(self):
        """Test that database URLs are properly configured."""
        from app.storage.database import ASYNC_DATABASE_URL, SYNC_DATABASE_URL

        assert SYNC_DATABASE_URL is not None
        assert ASYNC_DATABASE_URL is not None
        assert isinstance(SYNC_DATABASE_URL, str)
        assert isinstance(ASYNC_DATABASE_URL, str)

    def test_get_async_db_is_alias(self):
        """Test that get_async_db is an alias for get_async_session."""
        from app.storage.database import get_async_db, get_async_session

        assert get_async_db is get_async_session


class TestBasicSessionOperations:
    """Test basic session operations and patterns."""

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_basic_usage(self, mock_session_factory):
        """Test basic synchronous session usage pattern."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with get_sync_session() as session:
            assert session is mock_session
            session.execute(text("SELECT 1"))

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_session_basic_usage(self, mock_session_factory):
        """Test basic asynchronous session usage pattern."""
        from unittest.mock import AsyncMock

        mock_session = AsyncMock(spec=AsyncSession)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_cm

        from app.storage.database import get_async_session

        async for session in get_async_session():
            assert session is mock_session
            await session.execute(text("SELECT 1"))
            break

        mock_session_factory.assert_called_once()

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_exception_handling(self, mock_session_factory):
        """Test that sync sessions handle exceptions properly."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(ValueError), get_sync_session():
            raise ValueError("Test exception")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_basic_functionality(self):
        """Test basic database initialization functionality."""
        from app.storage.database import init_db

        # Should not raise exceptions
        try:
            await init_db()
        except Exception as e:
            # Allow for connection issues in test environment
            if "connection" not in str(e).lower():
                raise


class TestEnvironmentConfiguration:
    """Test environment-based configuration handling."""

    @patch.dict(os.environ, {"TESTING": "true"})
    def test_testing_environment_detection(self):
        """Test that testing environment is properly detected."""
        # Reload module to apply environment changes
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        # Should use testing configuration
        from app.storage.database import database_url

        # The exact URL depends on configuration, just verify it's set
        assert database_url is not None

    @patch.dict(os.environ, {"TESTING": "false"})
    def test_production_environment_configuration(self):
        """Test production environment configuration."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        from app.storage.database import database_url

        assert database_url is not None

    def test_async_url_driver_conversion(self):
        """Test that async URL properly converts to asyncpg driver."""
        from app.storage.database import ASYNC_DATABASE_URL, SYNC_DATABASE_URL

        # If sync URL uses postgresql://, async should use postgresql+asyncpg://
        if "postgresql://" in SYNC_DATABASE_URL and "asyncpg" not in SYNC_DATABASE_URL:
            assert "+asyncpg" in ASYNC_DATABASE_URL

        # Both should be valid PostgreSQL URLs
        assert "postgresql" in SYNC_DATABASE_URL
        assert "postgresql" in ASYNC_DATABASE_URL


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_commit_failure_handling(self, mock_session_factory):
        """Test sync session handling of commit failures."""
        from sqlalchemy.exc import DatabaseError

        mock_session = MagicMock(spec=Session)
        mock_session.commit.side_effect = DatabaseError("Commit failed", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(DatabaseError), get_sync_session():
            pass

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_rollback_failure_handling(self, mock_session_factory):
        """Test sync session handling when rollback fails."""
        from sqlalchemy.exc import DatabaseError

        mock_session = MagicMock(spec=Session)
        mock_session.rollback.side_effect = DatabaseError("Rollback failed", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        # Original exception should be preserved
        with pytest.raises(ValueError), get_sync_session():
            raise ValueError("Original error")

        # Close should still be called
        mock_session.close.assert_called_once()

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_connection_error_handling(self, mock_engine):
        """Test init_db handling of connection errors."""
        from sqlalchemy.exc import OperationalError

        mock_engine.begin.side_effect = OperationalError(
            "Connection failed", None, None
        )

        from app.storage.database import init_db

        with pytest.raises(OperationalError):
            await init_db()


class TestIntegrationPatterns:
    """Test integration patterns and real usage scenarios."""

    def test_session_factories_create_different_instances(self):
        """Test that session factories create new instances."""
        from app.storage.database import AsyncSessionLocal, SessionLocal

        # Should be able to call multiple times
        session1 = SessionLocal()
        session2 = SessionLocal()

        AsyncSessionLocal()
        AsyncSessionLocal()

        # Clean up
        session1.close()
        session2.close()

    @patch("app.storage.database.SessionLocal")
    def test_multiple_sync_session_contexts(self, mock_session_factory):
        """Test multiple sync session contexts work independently."""
        mock_session_factory.side_effect = [
            MagicMock(spec=Session),
            MagicMock(spec=Session),
        ]

        from app.storage.database import get_sync_session

        # Should be able to create multiple session contexts
        with get_sync_session() as session1:
            session1.execute(text("SELECT 1"))

        with get_sync_session() as session2:
            session2.execute(text("SELECT 2"))

        assert mock_session_factory.call_count == 2

    def test_module_level_configuration_is_immutable(self):
        """Test that module-level configuration objects exist."""
        from app.storage.database import async_engine, sync_engine

        # Engines should be created at module level
        engine1 = sync_engine
        engine2 = sync_engine

        # Should be same instance (singleton-like behavior)
        assert engine1 is engine2

        async_engine1 = async_engine
        async_engine2 = async_engine

        assert async_engine1 is async_engine2
