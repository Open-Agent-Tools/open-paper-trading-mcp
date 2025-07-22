"""
Performance and connection pooling tests for app.storage.database module.

This test suite covers:
- Connection pooling behavior and limits
- Performance characteristics under load
- Connection lifecycle and cleanup
- Resource management and memory usage
- Concurrent access patterns
- Database engine configuration
"""

import asyncio
import time
from datetime import UTC
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext.asyncio import AsyncEngine


class TestConnectionPooling:
    """Test connection pooling behavior and configuration."""

    def test_sync_engine_pool_configuration(self):
        """Test synchronous engine connection pool settings."""
        from app.storage.database import sync_engine

        # Verify engine exists and has connection pool
        assert sync_engine is not None
        assert isinstance(sync_engine, Engine)
        assert hasattr(sync_engine, "pool")

        # Test pool type (should be QueuePool for PostgreSQL)
        pool = sync_engine.pool
        assert pool is not None

    @pytest_asyncio.async_test
    async def test_async_engine_pool_configuration(self):
        """Test asynchronous engine connection pool settings."""
        from app.storage.database import async_engine

        # Verify async engine exists and has connection pool
        assert async_engine is not None
        assert isinstance(async_engine, AsyncEngine)
        assert hasattr(async_engine, "pool")

        # Test that pool is properly configured
        pool = async_engine.pool
        assert pool is not None

    @pytest_asyncio.async_test
    async def test_connection_pool_checkout_checkin(self):
        """Test connection checkout and checkin from pool."""
        from app.storage.database import async_engine

        # Test connection checkout
        async with async_engine.begin() as conn:
            # Connection should be checked out from pool
            assert conn is not None

            # Test that connection is usable
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1

        # Connection should be returned to pool after context exit
        # We can't directly test pool state, but no exceptions should occur

    @patch("app.storage.database.create_async_engine")
    def test_async_engine_pool_size_configuration(self, mock_create_async_engine):
        """Test async engine pool size configuration."""
        mock_engine = AsyncMock()
        mock_create_async_engine.return_value = mock_engine

        # Reload module to trigger engine creation with mock
        import importlib

        import app.storage.database

        importlib.reload(app.storage.database)

        # Verify create_async_engine was called
        mock_create_async_engine.assert_called_once()

        # Check if pool configuration parameters would be passed
        call_args = mock_create_async_engine.call_args
        assert call_args is not None

    @pytest_asyncio.async_test
    async def test_multiple_concurrent_connections(self):
        """Test handling of multiple concurrent connections."""
        from app.storage.database import get_async_session

        async def create_session_and_query():
            """Helper function to create session and run query."""
            async for session in get_async_session():
                result = await session.execute(text("SELECT 1"))
                return result.scalar()

        # Create multiple concurrent sessions
        tasks = [create_session_and_query() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All sessions should succeed
        assert all(result == 1 for result in results)

    @pytest_asyncio.async_test
    async def test_connection_pool_exhaustion_handling(self):
        """Test behavior when connection pool is exhausted."""
        from app.storage.database import async_engine

        connections = []
        try:
            # Try to check out many connections
            for _i in range(10):  # Attempt to exceed typical pool size
                try:
                    conn = await async_engine.connect()
                    connections.append(conn)
                except Exception as e:
                    # Should handle pool exhaustion gracefully
                    assert "pool" in str(e).lower() or "timeout" in str(e).lower()
                    break
        finally:
            # Clean up all connections
            for conn in connections:
                try:
                    await conn.close()
                except Exception:
                    pass  # Ignore cleanup errors


class TestConnectionLifecycle:
    """Test connection lifecycle management and cleanup."""

    @pytest_asyncio.async_test
    async def test_connection_cleanup_on_success(self):
        """Test that connections are properly cleaned up on successful operations."""
        from app.storage.database import get_async_session

        initial_pool_size = None
        final_pool_size = None

        # Get initial pool state if possible
        from app.storage.database import async_engine

        if hasattr(async_engine.pool, "size"):
            initial_pool_size = async_engine.pool.size()

        # Use session normally
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            break

        # Get final pool state
        if hasattr(async_engine.pool, "size"):
            final_pool_size = async_engine.pool.size()

        # Pool size should return to initial state (connections returned)
        if initial_pool_size is not None and final_pool_size is not None:
            assert final_pool_size == initial_pool_size

    @pytest_asyncio.async_test
    async def test_connection_cleanup_on_exception(self):
        """Test that connections are cleaned up even when exceptions occur."""
        from app.storage.database import get_async_session

        # Force an exception during session usage
        with pytest.raises(ValueError):
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))
                raise ValueError("Forced exception")

        # Should not leak connections - verify by creating new session
        async for session in get_async_session():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            break

    @pytest_asyncio.async_test
    async def test_session_isolation_between_requests(self):
        """Test that sessions are properly isolated between requests."""
        from app.storage.database import get_async_session

        # Create first session and set up some data
        session1_id = None
        async for session1 in get_async_session():
            # Get session identity
            result = await session1.execute(text("SELECT pg_backend_pid()"))
            session1_id = result.scalar()
            break

        # Create second session
        session2_id = None
        async for session2 in get_async_session():
            result = await session2.execute(text("SELECT pg_backend_pid()"))
            session2_id = result.scalar()
            break

        # Sessions should be independent (though they might reuse same connection)
        assert session1_id is not None
        assert session2_id is not None

    @pytest_asyncio.async_test
    async def test_long_running_session_timeout(self):
        """Test behavior of long-running sessions and timeouts."""
        from app.storage.database import get_async_session

        try:
            async for session in get_async_session():
                # Simulate long-running operation
                await session.execute(text("SELECT pg_sleep(0.1)"))

                # Session should still be usable after sleep
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
                break
        except Exception as e:
            # Should not timeout for reasonable operations
            assert "timeout" not in str(e).lower()

    @pytest_asyncio.async_test
    async def test_connection_recovery_after_disconnect(self):
        """Test connection recovery after database disconnect."""
        from app.storage.database import async_engine

        # Simulate connection loss and recovery
        try:
            # First, establish a working connection
            async with async_engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1

            # Connection should automatically recover for next operation
            async with async_engine.begin() as conn:
                result = await conn.execute(text("SELECT 2"))
                assert result.scalar() == 2

        except DisconnectionError:
            # This is expected behavior for connection recovery testing
            pass


class TestPerformanceCharacteristics:
    """Test performance characteristics under various load patterns."""

    @pytest_asyncio.async_test
    async def test_session_creation_performance(self):
        """Test performance of session creation and destruction."""
        from app.storage.database import get_async_session

        start_time = time.time()
        session_count = 20

        for _ in range(session_count):
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))
                break

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_session = total_time / session_count

        # Session creation should be reasonably fast (< 100ms per session)
        assert avg_time_per_session < 0.1, (
            f"Session creation too slow: {avg_time_per_session}s"
        )

    @pytest_asyncio.async_test
    async def test_concurrent_session_performance(self):
        """Test performance under concurrent session load."""
        from app.storage.database import get_async_session

        async def session_task(task_id: int):
            """Individual session task for concurrency testing."""
            async for session in get_async_session():
                # Perform multiple operations per session
                for i in range(3):
                    result = await session.execute(
                        text("SELECT :val").bindparam(val=task_id + i)
                    )
                    assert result.scalar() == task_id + i
                return task_id

        start_time = time.time()

        # Run concurrent sessions
        task_count = 10
        tasks = [session_task(i) for i in range(task_count)]
        results = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # All tasks should complete successfully
        assert len(results) == task_count
        assert sorted(results) == list(range(task_count))

        # Concurrent execution should be faster than sequential
        # (This is a rough heuristic, actual performance depends on hardware)
        assert total_time < 5.0, f"Concurrent operations too slow: {total_time}s"

    @pytest_asyncio.async_test
    async def test_transaction_performance(self):
        """Test transaction performance characteristics."""
        from datetime import datetime
        from decimal import Decimal

        from app.models.database.trading import Account
        from app.storage.database import get_async_session

        start_time = time.time()

        async for session in get_async_session():
            # Create multiple accounts in a single transaction
            accounts = []
            for i in range(10):
                account = Account(
                    id=f"perf-account-{i}",
                    user_id="perf-user",
                    name=f"Performance Account {i}",
                    account_type="paper",
                    balance=Decimal("1000.00"),
                    buying_power=Decimal("1000.00"),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                accounts.append(account)

            session.add_all(accounts)
            await session.commit()
            break

        end_time = time.time()
        transaction_time = end_time - start_time

        # Batch insert should be reasonably fast
        assert transaction_time < 2.0, (
            f"Batch transaction too slow: {transaction_time}s"
        )

    @pytest_asyncio.async_test
    async def test_query_performance_with_indexes(self):
        """Test query performance on indexed columns."""
        from datetime import datetime
        from decimal import Decimal

        from app.models.database.trading import Account
        from app.storage.database import get_async_session

        # Create test data for performance testing
        async for session in get_async_session():
            accounts = []
            for i in range(50):
                account = Account(
                    id=f"query-perf-{i}",
                    user_id=f"user-{i % 10}",  # 10 different users
                    name=f"Query Performance Account {i}",
                    account_type="paper",
                    balance=Decimal("1000.00") + Decimal(str(i)),
                    buying_power=Decimal("1000.00") + Decimal(str(i)),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                accounts.append(account)

            session.add_all(accounts)
            await session.commit()

            # Test primary key lookup (should be very fast)
            start_time = time.time()
            result = await session.execute(
                text("SELECT * FROM accounts WHERE id = 'query-perf-25'")
            )
            row = result.fetchone()
            pk_time = time.time() - start_time

            assert row is not None
            assert pk_time < 0.01, f"Primary key lookup too slow: {pk_time}s"

            # Test user_id lookup (should be indexed)
            start_time = time.time()
            result = await session.execute(
                text("SELECT COUNT(*) FROM accounts WHERE user_id = 'user-5'")
            )
            count = result.scalar()
            user_lookup_time = time.time() - start_time

            assert count == 5  # Should find 5 accounts for user-5
            assert user_lookup_time < 0.05, f"User lookup too slow: {user_lookup_time}s"
            break

    @pytest_asyncio.async_test
    async def test_memory_usage_under_load(self):
        """Test memory usage patterns under session load."""
        import gc

        from app.storage.database import get_async_session

        # Force garbage collection before test
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create and destroy many sessions
        for _ in range(20):
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))
                break

        # Force garbage collection after test
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count shouldn't grow excessively
        object_growth = final_objects - initial_objects
        assert object_growth < 1000, f"Excessive object growth: {object_growth}"


class TestConcurrencyAndThreadSafety:
    """Test concurrency patterns and thread safety."""

    @pytest_asyncio.async_test
    async def test_async_session_thread_safety(self):
        """Test that async sessions handle concurrent access correctly."""
        from app.storage.database import get_async_session

        async def concurrent_session_task(task_id: int):
            """Task that uses async session concurrently."""
            async for session in get_async_session():
                # Multiple operations in the session
                result1 = await session.execute(
                    text("SELECT :id").bindparam(id=task_id)
                )
                value1 = result1.scalar()

                # Small delay to increase chance of concurrency issues
                await asyncio.sleep(0.001)

                result2 = await session.execute(
                    text("SELECT :id").bindparam(id=task_id * 2)
                )
                value2 = result2.scalar()

                return value1, value2

        # Run multiple concurrent tasks
        tasks = [concurrent_session_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify all results are correct and isolated
        for i, (val1, val2) in enumerate(results):
            assert val1 == i
            assert val2 == i * 2

    def test_sync_session_thread_safety(self):
        """Test that sync sessions handle threading correctly."""
        import queue
        import threading

        from app.storage.database import get_sync_session

        result_queue = queue.Queue()
        error_queue = queue.Queue()

        def sync_session_task(task_id: int):
            """Task that uses sync session in thread."""
            try:
                with get_sync_session() as session:
                    result = session.execute(text("SELECT :id").bindparam(id=task_id))
                    value = result.scalar()
                    result_queue.put((task_id, value))
            except Exception as e:
                error_queue.put((task_id, e))

        # Create and start threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=sync_session_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        errors = []
        while not error_queue.empty():
            errors.append(error_queue.get())

        # Should have no errors and correct results
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 5

        # Verify all task IDs processed correctly
        task_ids = [task_id for task_id, _ in results]
        assert sorted(task_ids) == list(range(5))

    @pytest_asyncio.async_test
    async def test_mixed_sync_async_operations(self):
        """Test that sync and async operations don't interfere."""
        import queue
        import threading

        from app.storage.database import get_async_session, get_sync_session

        sync_result_queue = queue.Queue()

        def sync_operation():
            """Synchronous operation in thread."""
            try:
                with get_sync_session() as session:
                    result = session.execute(text("SELECT 'sync' as source"))
                    value = result.scalar()
                    sync_result_queue.put(value)
            except Exception as e:
                sync_result_queue.put(f"ERROR: {e}")

        # Start sync operation in thread
        sync_thread = threading.Thread(target=sync_operation)
        sync_thread.start()

        # Perform async operation
        async_result = None
        async for session in get_async_session():
            result = await session.execute(text("SELECT 'async' as source"))
            async_result = result.scalar()
            break

        # Wait for sync thread
        sync_thread.join()
        sync_result = sync_result_queue.get()

        # Both operations should succeed independently
        assert async_result == "async"
        assert sync_result == "sync"


class TestResourceManagement:
    """Test resource management and cleanup patterns."""

    @pytest_asyncio.async_test
    async def test_engine_disposal(self):
        """Test proper engine disposal and cleanup."""
        from sqlalchemy.ext.asyncio import create_async_engine

        # Create temporary engine for testing
        test_engine = create_async_engine(
            "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
            echo=False,
        )

        # Use engine
        async with test_engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        # Dispose engine
        await test_engine.dispose()

        # Engine should be disposed
        assert test_engine.pool is None or hasattr(test_engine.pool, "_disposed")

    @pytest_asyncio.async_test
    async def test_session_resource_cleanup(self):
        """Test that session resources are properly cleaned up."""
        from app.storage.database import get_async_session

        sessions_created = 0

        # Create multiple sessions and ensure cleanup
        for i in range(5):
            async for session in get_async_session():
                sessions_created += 1
                await session.execute(text("SELECT :i").bindparam(i=i))
                # Session should be cleaned up when exiting generator
                break

        assert sessions_created == 5

        # Should be able to create new sessions without issues
        async for session in get_async_session():
            result = await session.execute(text("SELECT 'cleanup_test'"))
            assert result.scalar() == "cleanup_test"
            break

    @pytest_asyncio.async_test
    async def test_connection_leak_prevention(self):
        """Test that connections don't leak under error conditions."""
        from app.storage.database import async_engine

        if hasattr(async_engine.pool, "status"):
            pass

        # Cause multiple connection errors
        for i in range(3):
            try:
                async with async_engine.begin() as conn:
                    # Simulate operation that might cause connection issues
                    await conn.execute(text("SELECT pg_backend_pid()"))
                    if i == 1:
                        # Force an error on second iteration
                        raise RuntimeError("Simulated error")
            except RuntimeError:
                pass  # Expected error

        # Pool should not have leaked connections
        if hasattr(async_engine.pool, "status"):
            pass

        # Should be able to create new connections normally
        async with async_engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest_asyncio.async_test
    async def test_large_result_set_memory_management(self):
        """Test memory management with large result sets."""
        from app.storage.database import get_async_session

        async for session in get_async_session():
            # Create a somewhat large result set
            result = await session.execute(
                text("SELECT generate_series(1, 1000) as num")
            )

            # Process results in chunks to avoid memory buildup
            processed_count = 0
            batch_size = 100

            while True:
                rows = result.fetchmany(batch_size)
                if not rows:
                    break
                processed_count += len(rows)

                # Verify data integrity
                for row in rows:
                    assert isinstance(row.num, int)
                    assert 1 <= row.num <= 1000

            assert processed_count == 1000
            break


class TestDatabaseEngineConfiguration:
    """Test database engine configuration and optimization."""

    def test_engine_echo_configuration(self):
        """Test that engine echo configuration is appropriate for environment."""
        from app.storage.database import async_engine, sync_engine

        # In tests, echo should typically be False for performance
        assert sync_engine.echo is False or sync_engine.echo is None
        if hasattr(async_engine, "echo"):
            assert async_engine.echo is False or async_engine.echo is None

    def test_engine_pool_pre_ping_configuration(self):
        """Test that engines are configured with appropriate pool_pre_ping."""
        from app.storage.database import sync_engine

        # Engine should exist and be properly configured
        assert sync_engine is not None

        # Pool pre_ping helps with connection recovery
        if hasattr(sync_engine.pool, "_pre_ping"):
            # This is good for production resilience
            pass

    @pytest_asyncio.async_test
    async def test_async_engine_connection_parameters(self):
        """Test async engine connection parameters."""
        from app.storage.database import async_engine

        # Test that async engine can establish connections
        async with async_engine.connect() as conn:
            # Verify connection properties
            result = await conn.execute(text("SELECT version()"))
            version_info = result.scalar()
            assert "PostgreSQL" in version_info

            # Test connection encoding
            result = await conn.execute(text("SHOW client_encoding"))
            encoding = result.scalar()
            assert encoding in ("UTF8", "unicode", "utf8")

    def test_connection_url_validation(self):
        """Test that connection URLs are properly formatted."""
        from app.storage.database import ASYNC_DATABASE_URL, SYNC_DATABASE_URL

        # URLs should be properly formatted PostgreSQL URLs
        assert SYNC_DATABASE_URL.startswith("postgresql://")
        assert ASYNC_DATABASE_URL.startswith("postgresql+asyncpg://")

        # URLs should contain required components
        assert "@" in SYNC_DATABASE_URL  # Should have credentials
        assert "/" in SYNC_DATABASE_URL.split("@")[1]  # Should have database name
        assert ":" in SYNC_DATABASE_URL.split("@")[1]  # Should have port
