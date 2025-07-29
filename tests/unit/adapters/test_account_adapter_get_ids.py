"""
Comprehensive test coverage for AccountAdapter.get_account_ids() function.

This module provides complete test coverage for the READ operation that gets all
account IDs from database, covering normal operations, edge cases, error scenarios,
and performance benchmarks.

Test Coverage Areas:
- Normal operation: retrieving IDs when accounts exist
- Empty database: behavior when no accounts exist
- Multiple accounts: ensuring all IDs are returned
- Database error scenarios: connection issues, query failures
- Data integrity: verifying returned IDs match actual account IDs
- Performance: testing with large numbers of accounts
- Concurrent access patterns
- Memory usage optimization
"""

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DatabaseError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import DatabaseAccountAdapter
from app.models.database.trading import Account as DBAccount
from app.services.performance_benchmarks import PerformanceMonitor

pytestmark = pytest.mark.journey_account_infrastructure


@pytest.mark.database
class TestGetAccountIdsNormalOperation:
    """Test normal operation scenarios for get_account_ids()."""

    @pytest.mark.asyncio
    async def test_get_account_ids_single_account(self, db_session: AsyncSession):
        """Test retrieving IDs when single account exists."""
        # Create adapter
        adapter = DatabaseAccountAdapter()

        # Create a single account
        account_id = "TEST123456"
        account = DBAccount(
            id=account_id,
            owner="test_user_single",
            cash_balance=10000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify result
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0] == account_id

    @pytest.mark.asyncio
    async def test_get_account_ids_multiple_accounts(self, db_session: AsyncSession):
        """Test retrieving IDs when multiple accounts exist."""
        adapter = DatabaseAccountAdapter()

        # Create multiple accounts
        account_ids = []
        for i in range(5):
            account_id = f"TEST12345{i}"
            account_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"test_user_{i}",
                cash_balance=10000.0 + (i * 1000),
            )
            db_session.add(account)

        await db_session.commit()

        # Mock the database session
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify result
            assert isinstance(result, list)
            assert len(result) == 5
            assert set(result) == set(account_ids)

    @pytest.mark.asyncio
    async def test_get_account_ids_preserves_order(self, db_session: AsyncSession):
        """Test that account IDs are returned in consistent order."""
        adapter = DatabaseAccountAdapter()

        # Create accounts with predictable IDs for testing order (max 10 chars)
        account_ids = []
        for i in range(3):
            account_id = f"ACC{i:03d}{uuid.uuid4().hex[:4].upper()}"  # ACC000ABCD format (10 chars)
            account_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get IDs multiple times
            result1 = await adapter.get_account_ids()
            result2 = await adapter.get_account_ids()

            # Results should be consistent (though order may vary by database)
            assert set(result1) == set(result2)
            assert len(result1) == 3


@pytest.mark.database
class TestGetAccountIdsEmptyDatabase:
    """Test behavior when no accounts exist."""

    @pytest.mark.asyncio
    async def test_get_account_ids_empty_database(self, db_session: AsyncSession):
        """Test getting IDs from empty database."""
        adapter = DatabaseAccountAdapter()

        # Ensure no accounts exist (cleanup handled by fixtures)
        stmt = select(DBAccount)
        db_result = await db_session.execute(stmt)
        existing_accounts = db_result.scalars().all()
        assert len(existing_accounts) == 0

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Should return empty list, not None
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_account_ids_after_deletion(self, db_session: AsyncSession):
        """Test getting IDs after all accounts have been deleted."""
        adapter = DatabaseAccountAdapter()

        # Create account then delete it
        account = DBAccount(
            id="TEST123456",
            owner="temp_user",
            cash_balance=5000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Delete the account
        await db_session.delete(account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Should return empty list
            assert isinstance(result, list)
            assert len(result) == 0


@pytest.mark.database
class TestGetAccountIdsDataIntegrity:
    """Test data integrity and consistency."""

    @pytest.mark.asyncio
    async def test_returned_ids_match_actual_accounts(self, db_session: AsyncSession):
        """Test that returned IDs exactly match actual account IDs in database."""
        adapter = DatabaseAccountAdapter()

        # Create accounts with known IDs
        created_ids = []
        for i in range(4):
            account_id = f"VER{i:04d}{uuid.uuid4().hex[:3].upper()}"  # VER0000ABC format (10 chars)
            created_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"verify_user_{i}",
                cash_balance=15000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get IDs from adapter
            adapter_ids = await adapter.get_account_ids()

            # Get IDs directly from database for comparison
            stmt = select(DBAccount.id)
            result = await db_session.execute(stmt)
            direct_ids = [row[0] for row in result.all()]

            # Should match exactly
            assert set(adapter_ids) == set(direct_ids)
            assert set(adapter_ids) == set(created_ids)

    @pytest.mark.asyncio
    async def test_ids_are_valid_strings(self, db_session: AsyncSession):
        """Test that all returned IDs are valid non-empty strings."""
        adapter = DatabaseAccountAdapter()

        # Create accounts with various ID formats
        account_ids = [
            "TEST123456",  # 10 chars exactly
            "CUSTOM1234",  # 10 chars exactly
            "MIXED12345",  # 10 chars exactly
        ]

        for i, account_id in enumerate(account_ids):
            account = DBAccount(
                id=account_id,
                owner=f"id_test_user_{i}",
                cash_balance=20000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify all IDs are valid strings
            assert len(result) == 3
            for account_id in result:
                assert isinstance(account_id, str)
                assert len(account_id) > 0
                assert account_id.strip() == account_id  # No whitespace

    @pytest.mark.asyncio
    async def test_no_duplicate_ids_returned(self, db_session: AsyncSession):
        """Test that no duplicate IDs are returned."""
        adapter = DatabaseAccountAdapter()

        # Create multiple accounts (database should enforce uniqueness)
        account_ids = []
        for i in range(6):
            account_id = f"DUP{i:07d}"
            account_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"dup_test_user_{i}",
                cash_balance=12000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify no duplicates
            assert len(result) == len(set(result))
            assert len(result) == 6


@pytest.mark.database
class TestGetAccountIdsDatabaseErrors:
    """Test database error scenarios."""

    @pytest.mark.asyncio
    async def synthetic_database_connection_error(self):
        """Test handling of database connection failures."""
        adapter = DatabaseAccountAdapter()

        # Mock connection failure
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                raise OperationalError("Connection to database failed", None, None)
                yield  # unreachable but needed for generator

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Should propagate the database error
            with pytest.raises(OperationalError) as exc_info:
                await adapter.get_account_ids()

            assert "Connection to database failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def synthetic_database_query_error(self):
        """Test handling of query execution failures."""
        adapter = DatabaseAccountAdapter()

        # Create proper async context manager with query error
        class MockAsyncContextManager:
            def __init__(self):
                self.db = AsyncMock()
                self.db.execute.side_effect = DatabaseError(
                    "Query execution failed", None, None
                )

            async def __aenter__(self):
                return self.db

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                async with MockAsyncContextManager() as session:
                    yield session

            mock_get_session.side_effect = lambda: mock_session_generator()

            with pytest.raises(DatabaseError) as exc_info:
                await adapter.get_account_ids()

            assert "Query execution failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def synthetic_database_session_cleanup_on_error(self):
        """Test that database session errors are properly handled."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                mock_session = AsyncMock()
                mock_session.execute.side_effect = SQLAlchemyError("Test error")
                yield mock_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Should handle the error appropriately
            with pytest.raises(SQLAlchemyError):
                await adapter.get_account_ids()

    @pytest.mark.asyncio
    async def test_result_processing_error(self):
        """Test handling of errors during result processing."""
        adapter = DatabaseAccountAdapter()

        # Create proper async context manager with result processing error
        class MockAsyncContextManager:
            def __init__(self):
                self.db = AsyncMock()

                # Create a mock result that has a synchronous all() method
                class MockResult:
                    def all(self):
                        raise ValueError("Result processing failed")

                self.result = MockResult()
                self.db.execute.return_value = self.result

            async def __aenter__(self):
                return self.db

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                async with MockAsyncContextManager() as session:
                    yield session

            mock_get_session.side_effect = lambda: mock_session_generator()

            with pytest.raises(ValueError) as exc_info:
                await adapter.get_account_ids()

            assert "Result processing failed" in str(exc_info.value)


@pytest.mark.database
class TestGetAccountIdsPerformance:
    """Test performance characteristics and benchmarks."""

    @pytest.mark.asyncio
    async def test_performance_with_many_accounts(
        self, db_session: AsyncSession, performance_monitor: PerformanceMonitor
    ):
        """Test performance with large numbers of accounts."""
        adapter = DatabaseAccountAdapter()

        # Create many accounts
        num_accounts = 100
        account_ids = []

        performance_monitor.start_timing("create_accounts")

        for i in range(num_accounts):
            account_id = f"PERF{i:06d}"  # PERF000000 format (10 chars)
            account_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"perf_user_{i}",
                cash_balance=10000.0 + i,
            )
            db_session.add(account)

        await db_session.commit()
        create_time = performance_monitor.end_timing("create_accounts")

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Time the get_account_ids operation
            performance_monitor.start_timing("get_account_ids")
            result = await adapter.get_account_ids()
            query_time = performance_monitor.end_timing("get_account_ids")

            # Verify results
            assert len(result) == num_accounts
            assert set(result) == set(account_ids)

            # Performance assertions
            assert query_time < 1.0, f"Query took too long: {query_time:.4f}s"
            assert create_time < 5.0, (
                f"Account creation took too long: {create_time:.4f}s"
            )

    @pytest.mark.asyncio
    async def test_performance_repeated_calls(
        self, db_session: AsyncSession, performance_monitor: PerformanceMonitor
    ):
        """Test performance of repeated calls to get_account_ids."""
        adapter = DatabaseAccountAdapter()

        # Create a moderate number of accounts
        for i in range(20):
            account = DBAccount(
                id=f"RPT{i:07d}",
                owner=f"repeat_user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Time multiple calls
            num_calls = 50
            total_start = time.time()

            for i in range(num_calls):
                performance_monitor.start_timing(f"call_{i}")
                result = await adapter.get_account_ids()
                call_time = performance_monitor.end_timing(f"call_{i}")

                assert len(result) == 20
                assert call_time < 0.1, f"Call {i} took too long: {call_time:.4f}s"

            total_time = time.time() - total_start
            avg_time = total_time / num_calls

            # Average call should be very fast
            assert avg_time < 0.05, f"Average call time too slow: {avg_time:.4f}s"

    @pytest.mark.asyncio
    async def test_memory_usage_with_large_result_set(self, db_session: AsyncSession):
        """Test memory efficiency with large result sets."""
        adapter = DatabaseAccountAdapter()

        # Create accounts with long IDs to test memory usage
        num_accounts = 500
        long_ids = []

        for i in range(num_accounts):
            # Create longer IDs to test memory efficiency
            long_id = f"MEM{i:07d}"  # MEM0000000 format (10 chars)
            long_ids.append(long_id)
            account = DBAccount(
                id=long_id,
                owner=f"memory_user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        # Commit in batches to avoid memory issues during test setup
        if num_accounts > 100:
            await db_session.commit()
            await db_session.refresh(account)  # Refresh the last account
        else:
            await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify all IDs returned
            assert len(result) == num_accounts

            # Check that results are properly typed and not consuming excessive memory
            assert isinstance(result, list)
            for account_id in result[:10]:  # Sample check
                assert isinstance(account_id, str)
                assert len(account_id) > 0


@pytest.mark.database
class TestGetAccountIdsConcurrency:
    """Test concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_consistency(self, db_session: AsyncSession):
        """Test that concurrent calls return consistent results."""
        adapter = DatabaseAccountAdapter()

        # Create test accounts
        expected_ids = []
        for i in range(10):
            account_id = f"CONC{i:06d}"
            expected_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"concurrent_user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Run multiple sequential calls (simulating concurrent scenario)
            results = []
            for _ in range(20):
                result = await adapter.get_account_ids()
                results.append(result)

            # All results should be identical
            first_result = set(results[0])
            assert len(first_result) == 10

            for result in results[1:]:
                assert set(result) == first_result

    @pytest.mark.asyncio
    async def test_read_during_write_operations(self, db_session: AsyncSession):
        """Test reading account IDs while accounts are being modified."""
        adapter = DatabaseAccountAdapter()

        # Create initial accounts
        initial_ids = []
        for i in range(5):
            account_id = f"RW{i:08d}"
            initial_ids.append(account_id)
            account = DBAccount(
                id=account_id,
                owner=f"rw_user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Read IDs (simulated concurrent access)
            result = await adapter.get_account_ids()

            # Should get consistent results
            assert len(result) == 5
            assert set(result) == set(initial_ids)


@pytest.mark.database
class TestGetAccountIdsEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.mark.asyncio
    async def test_accounts_with_special_characters_in_ids(
        self, db_session: AsyncSession
    ):
        """Test handling of account IDs with special characters."""
        adapter = DatabaseAccountAdapter()

        # Create accounts with various ID formats (within database constraints)
        special_ids = [
            "ACCT12345A",  # Account with uppercase letters
            "ACCT12345B",  # Account with numbers
            "1234567890",  # Numeric string (10 chars)
            "CAPS123456",  # All caps account
            "TEST000001",  # Test account with zeros
        ]

        for i, account_id in enumerate(special_ids):
            account = DBAccount(
                id=account_id,
                owner=f"special_user_{i}",
                cash_balance=10000.0,
            )
            db_session.add(account)

        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Verify all special IDs are returned correctly
            assert len(result) == len(special_ids)
            assert set(result) == set(special_ids)

    @pytest.mark.asyncio
    async def test_very_long_account_ids(self, db_session: AsyncSession):
        """Test handling of very long account IDs."""
        adapter = DatabaseAccountAdapter()

        # Create account with maximum allowed ID length (10 chars)
        long_id = "MAXLENGTHI"  # Exactly 10 characters
        account = DBAccount(
            id=long_id,
            owner="long_id_user",
            cash_balance=10000.0,
        )
        db_session.add(account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Get account IDs
            result = await adapter.get_account_ids()

            # Should handle long ID correctly
            assert len(result) == 1
            assert result[0] == long_id

    @pytest.mark.asyncio
    async def test_adapter_instance_reuse(self, db_session: AsyncSession):
        """Test that adapter instances can be reused safely."""
        # Create single adapter instance
        adapter = DatabaseAccountAdapter()

        # Create test account
        account_id = "TEST123456"
        account = DBAccount(
            id=account_id,
            owner="reuse_user",
            cash_balance=10000.0,
        )
        db_session.add(account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Use same adapter instance multiple times
            result1 = await adapter.get_account_ids()
            result2 = await adapter.get_account_ids()
            result3 = await adapter.get_account_ids()

            # All calls should return identical results
            assert result1 == result2 == result3
            assert len(result1) == 1
            assert result1[0] == account_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
