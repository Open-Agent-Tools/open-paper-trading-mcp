"""
Advanced comprehensive tests for app.storage.database module.

This test suite covers:
- Database connection and engine creation
- Session management (sync and async)
- Transaction handling and rollback scenarios
- Connection pooling and error recovery
- Database initialization patterns
- Environment-based configuration
"""

import builtins
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import (
    DatabaseError,
    DisconnectionError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


class TestDatabaseEngineCreation:
    """Test database engine creation and configuration."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host:5432/db"})
    @patch("app.storage.database.create_engine")
    @patch("app.storage.database.create_async_engine")
    def test_engine_creation_with_postgresql_url(
        self, mock_async_engine, mock_sync_engine
    ):
        """Test that engines are created correctly with PostgreSQL URL."""
        # Reload the module to apply environment changes
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        # Verify sync engine creation
        mock_sync_engine.assert_called_once_with("postgresql://user:pass@host:5432/db")

        # Verify async engine creation with asyncpg driver
        mock_async_engine.assert_called_once_with(
            "postgresql+asyncpg://user:pass@host:5432/db"
        )

    @patch.dict(
        os.environ, {"DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/db"}
    )
    @patch("app.storage.database.create_engine")
    @patch("app.storage.database.create_async_engine")
    def test_engine_creation_with_asyncpg_url(
        self, mock_async_engine, mock_sync_engine
    ):
        """Test that async engine doesn't duplicate asyncpg driver."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        # Should use the URL as-is when asyncpg is already present
        mock_async_engine.assert_called_once_with(
            "postgresql+asyncpg://user:pass@host:5432/db"
        )

    @patch.dict(
        os.environ,
        {
            "TESTING": "true",
            "TEST_DATABASE_URL": "postgresql://test:pass@testhost:5432/testdb",
        },
    )
    @patch("app.storage.database.create_engine")
    @patch("app.storage.database.create_async_engine")
    def test_testing_environment_uses_test_database(
        self, mock_async_engine, mock_sync_engine
    ):
        """Test that testing environment uses TEST_DATABASE_URL."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        mock_sync_engine.assert_called_once_with(
            "postgresql://test:pass@testhost:5432/testdb"
        )
        mock_async_engine.assert_called_once_with(
            "postgresql+asyncpg://test:pass@testhost:5432/testdb"
        )

    @patch.dict(os.environ, {"TESTING": "true"}, clear=False)
    @patch("app.storage.database.create_engine")
    def test_testing_without_test_database_url_uses_default(self, mock_sync_engine):
        """Test that testing without TEST_DATABASE_URL falls back to default."""
        if "TEST_DATABASE_URL" in os.environ:
            del os.environ["TEST_DATABASE_URL"]

        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        # Should use the default DATABASE_URL from settings
        assert mock_sync_engine.called

    def test_session_factory_creation(self):
        """Test that session factories are created correctly."""
        from app.storage.database import AsyncSessionLocal, SessionLocal

        # Verify session factories exist and are callable
        assert SessionLocal is not None
        assert AsyncSessionLocal is not None
        assert callable(SessionLocal)
        assert callable(AsyncSessionLocal)

    def test_module_exports(self):
        """Test that all expected symbols are exported."""
        import app.storage.database as db_module

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

        for export in expected_exports:
            assert hasattr(db_module, export), f"Missing export: {export}"
            assert export in db_module.__all__, f"Export {export} not in __all__"


class TestSyncSessionManagement:
    """Test synchronous session management patterns."""

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_normal_flow(self, mock_session_factory):
        """Test successful sync session creation and commit."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with get_sync_session() as session:
            assert session is mock_session
            # Simulate some database work
            session.execute(text("SELECT 1"))

        # Verify session lifecycle
        mock_session_factory.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_exception_handling(self, mock_session_factory):
        """Test sync session rollback on exception."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(ValueError), get_sync_session() as session:
            assert session is mock_session
            raise ValueError("Test exception")

        # Verify rollback occurred
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_commit_failure(self, mock_session_factory):
        """Test sync session handling when commit fails."""
        mock_session = MagicMock(spec=Session)
        mock_session.commit.side_effect = DatabaseError("Commit failed", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(DatabaseError), get_sync_session() as session:
            session.execute(text("SELECT 1"))

        # Verify rollback was called after commit failure
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.SessionLocal")
    def test_get_sync_session_close_always_called(self, mock_session_factory):
        """Test that session close is always called even if rollback fails."""
        mock_session = MagicMock(spec=Session)
        mock_session.rollback.side_effect = DatabaseError("Rollback failed", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(ValueError), get_sync_session():
            raise ValueError("Original error")

        # Verify close was called despite rollback failure
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestAsyncSessionManagement:
    """Test asynchronous session management patterns."""

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_get_async_session_normal_flow(self, mock_session_factory):
        """Test successful async session creation and management."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_async_session

        async for session in get_async_session():
            assert session is mock_session
            # Simulate some async database work
            await session.execute(text("SELECT 1"))
            break  # Only test first iteration

        # Verify session factory was called
        mock_session_factory.assert_called_once()
        mock_session.__aenter__.assert_called_once()
        mock_session.__aexit__.assert_called_once()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_get_async_session_context_manager(self, mock_session_factory):
        """Test async session as context manager."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_async_cm = AsyncMock()
        mock_async_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_async_cm

        from app.storage.database import get_async_session

        # Use async context manager pattern
        session_gen = get_async_session()
        session = await session_gen.__anext__()

        assert session is mock_session
        mock_session_factory.assert_called_once()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_get_async_session_exception_propagation(self, mock_session_factory):
        """Test that exceptions are properly propagated from async sessions."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = OperationalError("DB error", None, None)
        mock_async_cm = AsyncMock()
        mock_async_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_async_cm

        from app.storage.database import get_async_session

        with pytest.raises(OperationalError):
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))

    def test_get_async_db_alias(self):
        """Test that get_async_db is an alias for get_async_session."""
        from app.storage.database import get_async_db, get_async_session

        assert get_async_db is get_async_session


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, mock_engine):
        """Test that init_db creates all tables."""
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()
        mock_engine.begin = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.storage.database import init_db

        await init_db()

        # Verify engine.begin() was called
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()

        # Verify the run_sync was called with Base.metadata.create_all
        args, kwargs = mock_conn.run_sync.call_args
        assert len(args) == 1
        # The function should be Base.metadata.create_all
        from app.models.database.base import Base

        assert args[0] == Base.metadata.create_all

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_handles_connection_errors(self, mock_engine):
        """Test that init_db properly handles connection errors."""
        mock_engine.begin.side_effect = DisconnectionError("Connection lost")

        from app.storage.database import init_db

        with pytest.raises(DisconnectionError):
            await init_db()

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_handles_metadata_errors(self, mock_engine):
        """Test that init_db handles metadata creation errors."""
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock(
            side_effect=DatabaseError("Table creation failed", None, None)
        )
        mock_engine.begin = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.storage.database import init_db

        with pytest.raises(DatabaseError):
            await init_db()

    @patch("app.models.database.base.Base")
    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_imports_base_correctly(self, mock_engine, mock_base):
        """Test that init_db imports Base from correct location."""
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()
        mock_engine.begin = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.storage.database import init_db

        await init_db()

        # Verify that Base was imported and used
        mock_conn.run_sync.assert_called_once()


class TestConnectionPoolingAndRecovery:
    """Test connection pooling, error recovery, and resilience patterns."""

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_connection_recovery(self, mock_session_factory):
        """Test sync session handles connection recovery."""
        # First call fails with connection error, second succeeds
        failing_session = MagicMock(spec=Session)
        failing_session.execute.side_effect = DisconnectionError("Connection lost")

        working_session = MagicMock(spec=Session)
        mock_session_factory.side_effect = [failing_session, working_session]

        from app.storage.database import get_sync_session

        # First attempt should fail
        with pytest.raises(DisconnectionError), get_sync_session() as session:
            session.execute(text("SELECT 1"))

        # Second attempt should work
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))

        # Verify both sessions were created
        assert mock_session_factory.call_count == 2
        failing_session.rollback.assert_called_once()
        failing_session.close.assert_called_once()
        working_session.commit.assert_called_once()
        working_session.close.assert_called_once()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_session_connection_recovery(self, mock_session_factory):
        """Test async session handles connection recovery."""
        # Setup failing session
        failing_session = AsyncMock(spec=AsyncSession)
        failing_session.execute.side_effect = DisconnectionError("Connection lost")
        failing_cm = AsyncMock()
        failing_cm.__aenter__ = AsyncMock(return_value=failing_session)
        failing_cm.__aexit__ = AsyncMock(return_value=None)

        # Setup working session
        working_session = AsyncMock(spec=AsyncSession)
        working_cm = AsyncMock()
        working_cm.__aenter__ = AsyncMock(return_value=working_session)
        working_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory.side_effect = [failing_cm, working_cm]

        from app.storage.database import get_async_session

        # First attempt should fail
        with pytest.raises(DisconnectionError):
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))

        # Second attempt should work
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            break

        # Verify both session factories were called
        assert mock_session_factory.call_count == 2

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_integrity_error_handling(self, mock_session_factory):
        """Test sync session handles integrity constraint violations."""
        mock_session = MagicMock(spec=Session)
        mock_session.execute.side_effect = IntegrityError("Duplicate key", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(IntegrityError), get_sync_session() as session:
            session.execute(text("INSERT INTO test VALUES (1, 'duplicate')"))

        # Verify rollback was called for integrity error
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_session_integrity_error_handling(self, mock_session_factory):
        """Test async session handles integrity constraint violations."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = IntegrityError("Duplicate key", None, None)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_cm

        from app.storage.database import get_async_session

        with pytest.raises(IntegrityError):
            async for session in get_async_session():
                await session.execute(text("INSERT INTO test VALUES (1, 'duplicate')"))


class TestTransactionManagement:
    """Test transaction handling patterns and rollback scenarios."""

    @patch("app.storage.database.SessionLocal")
    def test_sync_transaction_commit_success(self, mock_session_factory):
        """Test successful transaction commit in sync session."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with get_sync_session() as session:
            # Simulate multiple operations in a transaction
            session.execute(text("INSERT INTO accounts (id) VALUES (1)"))
            session.execute(text("INSERT INTO orders (account_id) VALUES (1)"))
            session.flush()  # Explicit flush before commit

        # Verify transaction was committed
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch("app.storage.database.SessionLocal")
    def test_sync_transaction_rollback_on_error(self, mock_session_factory):
        """Test transaction rollback when error occurs."""
        mock_session = MagicMock(spec=Session)
        mock_session.execute.side_effect = [
            None,
            DatabaseError("Constraint violation", None, None),
        ]
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with pytest.raises(DatabaseError), get_sync_session() as session:
            session.execute(text("INSERT INTO accounts (id) VALUES (1)"))
            session.execute(
                text("INSERT INTO orders (account_id) VALUES (999)")
            )  # This fails

        # Verify rollback occurred, commit did not
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_transaction_with_savepoints(self, mock_session_factory):
        """Test async transaction with savepoint simulation."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.begin = AsyncMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock()
        mock_session.begin.return_value.__aexit__ = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_cm

        from app.storage.database import get_async_session

        async for session in get_async_session():
            # Simulate nested transaction with savepoint
            async with session.begin():
                await session.execute(text("INSERT INTO accounts (id) VALUES (1)"))
                async with session.begin():  # Nested/savepoint
                    await session.execute(
                        text("INSERT INTO orders (account_id) VALUES (1)")
                    )
            break

        # Verify nested transaction calls
        assert mock_session.begin.call_count >= 1

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_manual_transaction_control(self, mock_session_factory):
        """Test manual transaction control in sync session."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        with get_sync_session() as session:
            # Manual transaction control
            session.begin()
            session.execute(text("INSERT INTO accounts (id) VALUES (1)"))
            session.commit()

            session.begin()
            session.execute(text("INSERT INTO accounts (id) VALUES (2)"))
            session.rollback()  # Manual rollback

        # Verify manual transaction calls
        assert mock_session.begin.call_count == 2
        # Note: The context manager will also call commit once more
        assert mock_session.commit.call_count >= 1
        mock_session.rollback.assert_called()

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_session_concurrent_transactions(self, mock_session_factory):
        """Test handling of concurrent transaction patterns."""
        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session2 = AsyncMock(spec=AsyncSession)

        mock_cm1 = AsyncMock()
        mock_cm1.__aenter__ = AsyncMock(return_value=mock_session1)
        mock_cm1.__aexit__ = AsyncMock(return_value=None)

        mock_cm2 = AsyncMock()
        mock_cm2.__aenter__ = AsyncMock(return_value=mock_session2)
        mock_cm2.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory.side_effect = [mock_cm1, mock_cm2]

        from app.storage.database import get_async_session

        # Simulate concurrent sessions
        session1_gen = get_async_session()
        session2_gen = get_async_session()

        session1 = await session1_gen.__anext__()
        session2 = await session2_gen.__anext__()

        # Both sessions should be different instances
        assert session1 is not session2
        assert mock_session_factory.call_count == 2


class TestEnvironmentConfiguration:
    """Test environment-based configuration and settings."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.core.config.settings")
    def test_database_url_from_settings(self, mock_settings):
        """Test database URL is taken from settings when env vars not set."""
        mock_settings.DATABASE_URL = (
            "postgresql://settings:pass@settings:5432/settings_db"
        )

        # Clear any cached modules and reload
        import sys

        modules_to_reload = [k for k in sys.modules if k.startswith("app.storage")]
        for module in modules_to_reload:
            if module in sys.modules:
                del sys.modules[module]

        # Import should use settings
        from app.storage import database

        assert "settings" in database.database_url

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://env:pass@env:5432/env_db"})
    def test_database_url_from_environment(self):
        """Test that environment variables override settings."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        from app.storage import database

        assert database.database_url == "postgresql://env:pass@env:5432/env_db"

    @patch.dict(
        os.environ,
        {
            "TESTING": "TRUE",  # Test case insensitivity
            "TEST_DATABASE_URL": "postgresql://test:pass@test:5432/test_db",
        },
    )
    def test_testing_environment_case_insensitive(self):
        """Test that TESTING environment variable is case insensitive."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        from app.storage import database

        assert database.database_url == "postgresql://test:pass@test:5432/test_db"

    @patch.dict(os.environ, {"TESTING": "false"})
    def test_testing_false_uses_production_database(self):
        """Test that TESTING=false uses production database."""
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        from app.storage import database

        # Should not use test database URL
        assert "test" not in database.database_url.lower()

    def test_sync_and_async_urls_consistency(self):
        """Test that sync and async URLs are consistent."""
        from app.storage.database import ASYNC_DATABASE_URL, SYNC_DATABASE_URL

        # Async URL should be sync URL with asyncpg driver
        if "postgresql://" in SYNC_DATABASE_URL:
            expected_async_url = SYNC_DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            assert expected_async_url == ASYNC_DATABASE_URL
        elif "postgresql+asyncpg://" in SYNC_DATABASE_URL:
            # If already has asyncpg, they should be the same
            assert ASYNC_DATABASE_URL == SYNC_DATABASE_URL

    def test_engine_instances_are_singletons(self):
        """Test that engine instances are created once and reused."""
        from app.storage.database import async_engine, sync_engine
        from app.storage.database import async_engine as async_engine2

        # Import again to verify same instances
        from app.storage.database import sync_engine as sync_engine2

        assert sync_engine is sync_engine2
        assert async_engine is async_engine2


class TestErrorHandlingAndResilience:
    """Test error handling, resilience patterns, and edge cases."""

    @patch("app.storage.database.create_engine")
    def test_sync_engine_creation_failure(self, mock_create_engine):
        """Test handling of sync engine creation failure."""
        mock_create_engine.side_effect = SQLAlchemyError("Engine creation failed")

        with pytest.raises(SQLAlchemyError):
            import importlib

            import app.storage.database

            importlib.reload(app.storage.database)

    @patch("app.storage.database.create_async_engine")
    def test_async_engine_creation_failure(self, mock_create_async_engine):
        """Test handling of async engine creation failure."""
        mock_create_async_engine.side_effect = SQLAlchemyError(
            "Async engine creation failed"
        )

        with pytest.raises(SQLAlchemyError):
            import importlib

            import app.storage.database

            importlib.reload(app.storage.database)

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_creation_failure(self, mock_session_factory):
        """Test handling of sync session creation failure."""
        mock_session_factory.side_effect = SQLAlchemyError("Session creation failed")

        from app.storage.database import get_sync_session

        with pytest.raises(SQLAlchemyError), get_sync_session():
            pass

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_async_session_creation_failure(self, mock_session_factory):
        """Test handling of async session creation failure."""
        mock_session_factory.side_effect = SQLAlchemyError(
            "Async session creation failed"
        )

        from app.storage.database import get_async_session

        with pytest.raises(SQLAlchemyError):
            async for _session in get_async_session():
                pass

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_close_failure(self, mock_session_factory):
        """Test that session close failures don't mask original exceptions."""
        mock_session = MagicMock(spec=Session)
        mock_session.close.side_effect = DatabaseError("Close failed", None, None)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        # Original exception should be preserved even if close fails
        with pytest.raises(ValueError, match="Original error"):
            with get_sync_session():
                raise ValueError("Original error")

        # Close should still have been attempted
        mock_session.close.assert_called_once()

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_connection_timeout(self, mock_engine):
        """Test init_db handling of connection timeouts."""
        from asyncio import TimeoutError

        mock_engine.begin.side_effect = builtins.TimeoutError("Connection timeout")

        from app.storage.database import init_db

        with pytest.raises(TimeoutError):
            await init_db()

    @patch("app.storage.database.async_engine")
    @pytest.mark.asyncio
    async def test_init_db_partial_failure_recovery(self, mock_engine):
        """Test init_db recovery from partial failures."""
        # First call fails, second succeeds
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_engine.begin.side_effect = [
            OperationalError("Temporary failure", None, None),
            MockAsyncContext(mock_conn),
        ]

        from app.storage.database import init_db

        # First call should fail
        with pytest.raises(OperationalError):
            await init_db()

        # Second call should succeed
        await init_db()

        assert mock_engine.begin.call_count == 2


class MockAsyncContext:
    """Mock async context manager for testing."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class TestSessionLifecycleIntegration:
    """Integration tests for session lifecycle management."""

    @patch("app.storage.database.SessionLocal")
    def test_nested_sync_session_usage(self, mock_session_factory):
        """Test nested usage of sync sessions."""
        mock_session = MagicMock(spec=Session)
        mock_session_factory.return_value = mock_session

        from app.storage.database import get_sync_session

        def inner_function():
            with get_sync_session() as inner_session:
                inner_session.execute(text("SELECT 2"))
                return inner_session.scalar(text("SELECT 1"))

        with get_sync_session() as outer_session:
            outer_session.execute(text("SELECT 1"))
            inner_function()
            outer_session.execute(text("SELECT 3"))

        # Should create two separate sessions
        assert mock_session_factory.call_count == 2

    @patch("app.storage.database.AsyncSessionLocal")
    @pytest.mark.asyncio
    async def test_nested_async_session_usage(self, mock_session_factory):
        """Test nested usage of async sessions."""
        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session2 = AsyncMock(spec=AsyncSession)

        mock_cm1 = AsyncMock()
        mock_cm1.__aenter__ = AsyncMock(return_value=mock_session1)
        mock_cm1.__aexit__ = AsyncMock(return_value=None)

        mock_cm2 = AsyncMock()
        mock_cm2.__aenter__ = AsyncMock(return_value=mock_session2)
        mock_cm2.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory.side_effect = [mock_cm1, mock_cm2]

        from app.storage.database import get_async_session

        async def inner_function():
            async for inner_session in get_async_session():
                await inner_session.execute(text("SELECT 2"))
                return await inner_session.scalar(text("SELECT 1"))

        async for outer_session in get_async_session():
            await outer_session.execute(text("SELECT 1"))
            await inner_function()
            await outer_session.execute(text("SELECT 3"))
            break

        # Should create two separate sessions
        assert mock_session_factory.call_count == 2

    @patch("app.storage.database.SessionLocal")
    def test_sync_session_reentrance_safety(self, mock_session_factory):
        """Test that sync sessions handle reentrant calls safely."""
        call_count = 0
        original_session_method = None

        def side_effect():
            nonlocal call_count, original_session_method
            call_count += 1
            session = MagicMock(spec=Session)

            # Mock a method that might call get_sync_session again
            def mock_method():
                if call_count < 3:  # Prevent infinite recursion
                    with get_sync_session():
                        pass

            session.some_method = mock_method
            return session

        mock_session_factory.side_effect = side_effect

        from app.storage.database import get_sync_session

        with get_sync_session() as session:
            session.some_method()

        # Should handle reentrant calls
        assert call_count >= 1
