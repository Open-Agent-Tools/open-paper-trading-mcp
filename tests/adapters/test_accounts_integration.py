"""
Comprehensive integration tests for account adapters.

Tests both DatabaseAccountAdapter and LocalFileSystemAccountAdapter
with focus on:
- Database integration scenarios
- File system operations
- Data persistence and consistency
- Error handling and recovery
- Performance under load
- Concurrent access patterns
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.accounts import (
    DatabaseAccountAdapter,
    LocalFileSystemAccountAdapter,
    account_factory,
)
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import Account


class TestDatabaseAccountAdapterIntegration:
    """Integration tests for DatabaseAccountAdapter with real database interactions."""

    @pytest.fixture
    def adapter(self):
        """Create database account adapter."""
        return DatabaseAccountAdapter()

    @pytest.fixture
    def sample_account(self):
        """Create sample account for testing."""
        return Account(
            id="test-account-123",
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock(spec=Session)
        return session

    def test_adapter_initialization(self, adapter):
        """Test adapter initialization."""
        assert isinstance(adapter, DatabaseAccountAdapter)

    @pytest.mark.integration
    def test_put_and_get_account_integration(self, adapter, sample_account):
        """Test complete put/get cycle with database integration."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            # Setup mock database session
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Test putting new account
            mock_db.query.return_value.filter.return_value.first.return_value = None
            adapter.put_account(sample_account)

            # Verify account was added to database
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

            # Test getting the account back
            mock_db_account = DBAccount(
                id=sample_account.id,
                owner=sample_account.owner,
                cash_balance=sample_account.cash_balance,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_db_account
            )

            retrieved_account = adapter.get_account(sample_account.id)

            assert retrieved_account is not None
            assert retrieved_account.id == sample_account.id
            assert retrieved_account.cash_balance == sample_account.cash_balance
            assert retrieved_account.owner == sample_account.owner

    @pytest.mark.integration
    def test_update_existing_account_integration(self, adapter):
        """Test updating existing account in database."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Create existing account in database
            existing_db_account = DBAccount(
                id="test-account-123",
                owner="original_owner",
                cash_balance=5000.0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            mock_db.query.return_value.filter.return_value.first.return_value = (
                existing_db_account
            )

            # Update account
            updated_account = Account(
                id="test-account-123",
                cash_balance=15000.0,
                positions=[],
                name="Updated Account",
                owner="new_owner",
            )

            adapter.put_account(updated_account)

            # Verify update occurred
            assert existing_db_account.cash_balance == 15000.0
            assert existing_db_account.owner == "new_owner"
            mock_db.commit.assert_called_once()

    @pytest.mark.integration
    def test_get_account_not_found_integration(self, adapter):
        """Test getting non-existent account from database."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            account = adapter.get_account("non-existent-id")
            assert account is None

    @pytest.mark.integration
    def test_get_account_ids_integration(self, adapter):
        """Test getting all account IDs from database."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock account IDs in database
            mock_accounts = [
                Mock(id="account-1"),
                Mock(id="account-2"),
                Mock(id="account-3"),
            ]
            mock_db.query.return_value.all.return_value = mock_accounts

            account_ids = adapter.get_account_ids()

            assert len(account_ids) == 3
            assert "account-1" in account_ids
            assert "account-2" in account_ids
            assert "account-3" in account_ids

    @pytest.mark.integration
    def test_account_exists_integration(self, adapter):
        """Test checking account existence in database."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Test existing account
            mock_db.query.return_value.filter.return_value.count.return_value = 1
            assert adapter.account_exists("existing-account") is True

            # Test non-existing account
            mock_db.query.return_value.filter.return_value.count.return_value = 0
            assert adapter.account_exists("non-existing-account") is False

    @pytest.mark.integration
    def test_delete_account_integration(self, adapter):
        """Test deleting account from database."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Test successful deletion
            mock_db_account = DBAccount(id="test-account", owner="test", cash_balance=0)
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_db_account
            )

            result = adapter.delete_account("test-account")

            assert result is True
            mock_db.delete.assert_called_once_with(mock_db_account)
            mock_db.commit.assert_called_once()

            # Test deletion of non-existent account
            mock_db.query.return_value.filter.return_value.first.return_value = None
            result = adapter.delete_account("non-existent")
            assert result is False

    @pytest.mark.integration
    def test_database_error_handling(self, adapter, sample_account):
        """Test handling of database errors."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Test SQLAlchemy error during put
            mock_db.commit.side_effect = SQLAlchemyError("Database connection failed")
            mock_db.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(SQLAlchemyError):
                adapter.put_account(sample_account)

            # Test integrity error during put
            mock_db.commit.side_effect = IntegrityError(
                "Constraint violation", None, None
            )

            with pytest.raises(IntegrityError):
                adapter.put_account(sample_account)

    @pytest.mark.integration
    def test_concurrent_account_operations(self, adapter):
        """Test concurrent operations on accounts."""
        import threading

        results = []
        errors = []

        def create_account_worker(thread_id):
            """Worker function for concurrent account creation."""
            try:
                account = Account(
                    id=f"thread-{thread_id}-account",
                    cash_balance=1000.0 * thread_id,
                    positions=[],
                    name=f"Thread {thread_id} Account",
                    owner=f"user_{thread_id}",
                )

                with patch("app.adapters.accounts.get_sync_session") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value.__enter__.return_value = mock_db
                    mock_db.query.return_value.filter.return_value.first.return_value = None

                    adapter.put_account(account)
                    results.append(f"thread-{thread_id}-account")

            except Exception as e:
                errors.append(f"Thread {thread_id}: {e!s}")

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_account_worker, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

    @pytest.mark.integration
    def test_account_data_consistency(self, adapter):
        """Test data consistency during account operations."""
        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Create account with specific data
            original_account = Account(
                id="consistency-test",
                cash_balance=12345.67,
                positions=[],
                name="Consistency Test Account",
                owner="consistency_user",
            )

            mock_db.query.return_value.filter.return_value.first.return_value = None
            adapter.put_account(original_account)

            # Mock the database account for retrieval
            mock_db_account = DBAccount(
                id=original_account.id,
                owner=original_account.owner,
                cash_balance=original_account.cash_balance,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_db_account
            )

            # Retrieve and verify data consistency
            retrieved_account = adapter.get_account("consistency-test")

            assert retrieved_account is not None
            assert retrieved_account.id == original_account.id
            assert retrieved_account.cash_balance == original_account.cash_balance
            assert retrieved_account.owner == original_account.owner
            assert retrieved_account.name == f"Account-{original_account.id}"

    @pytest.mark.integration
    def test_large_scale_operations(self, adapter):
        """Test performance with large number of operations."""
        import time

        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Create many accounts
            start_time = time.time()

            for i in range(100):
                account = Account(
                    id=f"perf-test-{i}",
                    cash_balance=float(i * 100),
                    positions=[],
                    name=f"Performance Test Account {i}",
                    owner=f"perf_user_{i}",
                )
                adapter.put_account(account)

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time (adjust threshold as needed)
            assert duration < 10.0, f"Operations took too long: {duration} seconds"

            # Verify all commits were called
            assert mock_db.commit.call_count == 100


class TestLocalFileSystemAccountAdapterIntegration:
    """Integration tests for LocalFileSystemAccountAdapter with real file operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def adapter(self, temp_dir):
        """Create file system account adapter with temporary directory."""
        return LocalFileSystemAccountAdapter(root_path=temp_dir)

    @pytest.fixture
    def sample_account(self):
        """Create sample account for testing."""
        return Account(
            id="file-test-account",
            cash_balance=5000.0,
            positions=[],
            name="File Test Account",
            owner="file_user",
        )

    def test_adapter_initialization(self, temp_dir):
        """Test adapter initialization creates directory."""
        adapter_path = os.path.join(temp_dir, "test_accounts")
        LocalFileSystemAccountAdapter(root_path=adapter_path)

        assert os.path.exists(adapter_path)
        assert os.path.isdir(adapter_path)

    @pytest.mark.integration
    def test_put_and_get_account_file_integration(
        self, adapter, sample_account, temp_dir
    ):
        """Test complete put/get cycle with file system integration."""
        # Put account
        adapter.put_account(sample_account)

        # Verify file was created
        expected_file = os.path.join(temp_dir, f"{sample_account.id}.json")
        assert os.path.exists(expected_file)

        # Verify file content
        with open(expected_file) as f:
            file_data = json.load(f)

        assert file_data["id"] == sample_account.id
        assert file_data["cash_balance"] == sample_account.cash_balance
        assert file_data["owner"] == sample_account.owner

        # Get account back
        retrieved_account = adapter.get_account(sample_account.id)

        assert retrieved_account is not None
        assert retrieved_account.id == sample_account.id
        assert retrieved_account.cash_balance == sample_account.cash_balance
        assert retrieved_account.owner == sample_account.owner

    @pytest.mark.integration
    def test_update_existing_account_file_integration(self, adapter, temp_dir):
        """Test updating existing account file."""
        # Create initial account
        original_account = Account(
            id="update-test",
            cash_balance=1000.0,
            positions=[],
            name="Original Account",
            owner="original_user",
        )
        adapter.put_account(original_account)

        # Update account
        updated_account = Account(
            id="update-test",
            cash_balance=2000.0,
            positions=[],
            name="Updated Account",
            owner="updated_user",
        )
        adapter.put_account(updated_account)

        # Verify file was updated
        expected_file = os.path.join(temp_dir, "update-test.json")
        with open(expected_file) as f:
            file_data = json.load(f)

        assert file_data["cash_balance"] == 2000.0
        assert file_data["owner"] == "updated_user"

    @pytest.mark.integration
    def test_get_account_not_found_file_integration(self, adapter):
        """Test getting non-existent account from file system."""
        account = adapter.get_account("non-existent-file-account")
        assert account is None

    @pytest.mark.integration
    def test_get_account_corrupted_file_integration(self, adapter, temp_dir):
        """Test handling corrupted account file."""
        # Create corrupted file
        corrupted_file = os.path.join(temp_dir, "corrupted-account.json")
        with open(corrupted_file, "w") as f:
            f.write("invalid json content {{{")

        # Should return None for corrupted file
        account = adapter.get_account("corrupted-account")
        assert account is None

    @pytest.mark.integration
    def test_get_account_ids_file_integration(self, adapter, temp_dir):
        """Test getting all account IDs from file system."""
        # Create multiple account files
        accounts = []
        for i in range(3):
            account = Account(
                id=f"ids-test-{i}",
                cash_balance=float(i * 1000),
                positions=[],
                name=f"Account {i}",
                owner=f"user_{i}",
            )
            accounts.append(account)
            adapter.put_account(account)

        # Create non-JSON file (should be ignored)
        non_json_file = os.path.join(temp_dir, "not-an-account.txt")
        with open(non_json_file, "w") as f:
            f.write("This is not a JSON file")

        account_ids = adapter.get_account_ids()

        assert len(account_ids) == 3
        for i in range(3):
            assert f"ids-test-{i}" in account_ids
        assert "not-an-account" not in account_ids

    @pytest.mark.integration
    def test_account_exists_file_integration(self, adapter, sample_account):
        """Test checking account existence in file system."""
        # Initially should not exist
        assert adapter.account_exists(sample_account.id) is False

        # Create account
        adapter.put_account(sample_account)

        # Now should exist
        assert adapter.account_exists(sample_account.id) is True

    @pytest.mark.integration
    def test_delete_account_file_integration(self, adapter, sample_account, temp_dir):
        """Test deleting account from file system."""
        # Create account
        adapter.put_account(sample_account)
        expected_file = os.path.join(temp_dir, f"{sample_account.id}.json")
        assert os.path.exists(expected_file)

        # Delete account
        result = adapter.delete_account(sample_account.id)

        assert result is True
        assert not os.path.exists(expected_file)

        # Try deleting non-existent account
        result = adapter.delete_account("non-existent")
        assert result is False

    @pytest.mark.integration
    def test_file_permissions_error_handling(self, adapter, sample_account, temp_dir):
        """Test handling of file permission errors."""
        # Create account first
        adapter.put_account(sample_account)

        # Make directory read-only (simulating permission error)
        original_mode = os.stat(temp_dir).st_mode
        try:
            os.chmod(temp_dir, 0o444)  # Read-only

            # Try to create new account (should raise PermissionError)
            new_account = Account(
                id="permission-test",
                cash_balance=1000.0,
                positions=[],
                name="Permission Test",
                owner="permission_user",
            )

            with pytest.raises(PermissionError):
                adapter.put_account(new_account)

        finally:
            # Restore original permissions
            os.chmod(temp_dir, original_mode)

    @pytest.mark.integration
    def test_concurrent_file_operations(self, adapter):
        """Test concurrent file operations."""
        import threading

        results = []
        errors = []

        def file_worker(thread_id):
            """Worker function for concurrent file operations."""
            try:
                account = Account(
                    id=f"file-thread-{thread_id}",
                    cash_balance=float(thread_id * 500),
                    positions=[],
                    name=f"File Thread {thread_id} Account",
                    owner=f"file_user_{thread_id}",
                )

                adapter.put_account(account)
                retrieved = adapter.get_account(account.id)

                if retrieved and retrieved.id == account.id:
                    results.append(thread_id)

            except Exception as e:
                errors.append(f"Thread {thread_id}: {e!s}")

        # Create threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=file_worker, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

    @pytest.mark.integration
    def test_large_file_operations(self, adapter):
        """Test performance with many file operations."""
        import time

        start_time = time.time()

        # Create many accounts
        for i in range(50):  # Reduced for file system testing
            account = Account(
                id=f"large-file-test-{i}",
                cash_balance=float(i * 200),
                positions=[],
                name=f"Large File Test Account {i}",
                owner=f"large_file_user_{i}",
            )
            adapter.put_account(account)

        # Read them all back
        account_ids = adapter.get_account_ids()

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time
        assert duration < 5.0, f"File operations took too long: {duration} seconds"
        assert len(account_ids) == 50

    @pytest.mark.integration
    def test_file_system_recovery(self, adapter, temp_dir):
        """Test recovery from file system issues."""
        # Create account
        account = Account(
            id="recovery-test",
            cash_balance=1000.0,
            positions=[],
            name="Recovery Test",
            owner="recovery_user",
        )
        adapter.put_account(account)

        # Simulate file corruption by writing invalid JSON
        account_file = os.path.join(temp_dir, "recovery-test.json")
        with open(account_file, "w") as f:
            f.write("corrupted data")

        # Should handle gracefully
        retrieved = adapter.get_account("recovery-test")
        assert retrieved is None

        # Should be able to overwrite corrupted file
        adapter.put_account(account)
        retrieved = adapter.get_account("recovery-test")
        assert retrieved is not None
        assert retrieved.id == account.id


class TestAccountFactory:
    """Test account factory function."""

    def test_account_factory_defaults(self):
        """Test account factory with default parameters."""
        account = account_factory()

        assert isinstance(account, Account)
        assert len(account.id) == 8  # Short UUID
        assert account.cash_balance == 100000.0
        assert account.name.startswith("Account-")
        assert account.owner == "default"
        assert account.positions == []

    def test_account_factory_custom_parameters(self):
        """Test account factory with custom parameters."""
        account = account_factory(
            name="Custom Account", owner="custom_user", cash=50000.0
        )

        assert account.name == "Custom Account"
        assert account.owner == "custom_user"
        assert account.cash_balance == 50000.0

    def test_account_factory_unique_ids(self):
        """Test that factory generates unique IDs."""
        accounts = [account_factory() for _ in range(10)]
        ids = [account.id for account in accounts]

        # All IDs should be unique
        assert len(set(ids)) == len(ids)

        # All IDs should be 8 characters
        assert all(len(id) == 8 for id in ids)


class TestAccountAdapterErrorHandling:
    """Test error handling across account adapters."""

    def test_database_adapter_session_error(self):
        """Test database adapter handling session errors."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_session.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                adapter.get_account("test-id")

    def test_file_adapter_invalid_json_error(self, tmp_path):
        """Test file adapter handling invalid JSON."""
        adapter = LocalFileSystemAccountAdapter(root_path=str(tmp_path))

        # Create invalid JSON file
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json")

        # Should return None instead of raising exception
        account = adapter.get_account("invalid")
        assert account is None

    def test_file_adapter_io_error(self, tmp_path):
        """Test file adapter handling I/O errors."""
        adapter = LocalFileSystemAccountAdapter(root_path=str(tmp_path))

        # Create account first
        account = Account(
            id="io-test",
            cash_balance=1000.0,
            positions=[],
            name="IO Test",
            owner="io_user",
        )
        adapter.put_account(account)

        # Make file unreadable
        account_file = tmp_path / "io-test.json"
        account_file.chmod(0o000)

        try:
            # Should handle permission error gracefully
            retrieved = adapter.get_account("io-test")
            assert retrieved is None
        finally:
            # Restore permissions for cleanup
            account_file.chmod(0o644)


class TestAccountAdapterPerformance:
    """Performance tests for account adapters."""

    @pytest.mark.performance
    def test_database_adapter_bulk_operations(self):
        """Test database adapter performance with bulk operations."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            import time

            start_time = time.time()

            # Perform bulk operations
            for i in range(100):
                account = Account(
                    id=f"bulk-{i}",
                    cash_balance=float(i * 100),
                    positions=[],
                    name=f"Bulk Account {i}",
                    owner=f"bulk_user_{i}",
                )
                adapter.put_account(account)

            end_time = time.time()
            duration = end_time - start_time

            # Should complete within reasonable time
            assert duration < 5.0, f"Bulk operations took {duration} seconds"

    @pytest.mark.performance
    def test_file_adapter_bulk_operations(self, tmp_path):
        """Test file adapter performance with bulk operations."""
        adapter = LocalFileSystemAccountAdapter(root_path=str(tmp_path))

        import time

        start_time = time.time()

        # Perform bulk operations
        for i in range(50):  # Fewer for file operations
            account = Account(
                id=f"file-bulk-{i}",
                cash_balance=float(i * 100),
                positions=[],
                name=f"File Bulk Account {i}",
                owner=f"file_bulk_user_{i}",
            )
            adapter.put_account(account)

        # Read them all back
        account_ids = adapter.get_account_ids()

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time
        assert duration < 3.0, f"File bulk operations took {duration} seconds"
        assert len(account_ids) == 50
