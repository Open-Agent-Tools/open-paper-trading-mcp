"""Tests for account adapters (DatabaseAccountAdapter and LocalFileSystemAccountAdapter)."""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from app.adapters.accounts import (
    DatabaseAccountAdapter,
    LocalFileSystemAccountAdapter,
    account_factory,
)
from app.schemas.accounts import Account
from app.models.database.trading import Account as DBAccount


class TestDatabaseAccountAdapter:
    """Test DatabaseAccountAdapter functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = MagicMock()
        return mock_session

    @pytest.fixture
    def adapter(self, mock_db_session):
        """Create adapter with mocked database."""
        with patch('app.adapters.accounts.get_sync_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_db_session
            mock_get_session.return_value.__exit__.return_value = None
            adapter = DatabaseAccountAdapter()
        return adapter, mock_db_session

    def test_adapter_initialization(self):
        """Test adapter initialization."""
        with patch('app.adapters.accounts.get_sync_session'):
            adapter = DatabaseAccountAdapter()
        assert adapter is not None

    def test_get_account_success(self, adapter):
        """Test successfully getting an account."""
        adapter_instance, mock_db_session = adapter
        
        # Mock database account
        mock_db_account = Mock(spec=DBAccount)
        mock_db_account.id = "test-id"
        mock_db_account.cash_balance = 100000.0
        mock_db_account.owner = "test-user"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_db_account
        mock_db_session.query.return_value = mock_query
        
        account = adapter_instance.get_account("test-id")
        
        assert account is not None
        assert account.id == "test-id"
        assert account.cash_balance == 100000.0
        assert account.owner == "test-user"
        assert account.name == "Account-test-id"
        assert account.positions == []
        
        mock_db_session.query.assert_called_once_with(DBAccount)

    def test_get_account_not_found(self, adapter):
        """Test getting non-existent account."""
        adapter_instance, mock_db_session = adapter
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        account = adapter_instance.get_account("nonexistent")
        
        assert account is None
        mock_db_session.query.assert_called_once_with(DBAccount)

    def test_put_account_create_new(self, adapter):
        """Test creating new account."""
        adapter_instance, mock_db_session = adapter
        
        # Mock no existing account
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        account = Account(
            id="new-account",
            cash_balance=50000.0,
            positions=[],
            name="New Account",
            owner="new-user"
        )
        
        adapter_instance.put_account(account)
        
        # Verify database operations
        mock_db_session.query.assert_called_with(DBAccount)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Check the account that was added
        add_call = mock_db_session.add.call_args[0][0]
        assert isinstance(add_call, DBAccount)
        assert add_call.id == "new-account"
        assert add_call.cash_balance == 50000.0
        assert add_call.owner == "new-user"
        assert isinstance(add_call.created_at, datetime)
        assert isinstance(add_call.updated_at, datetime)

    def test_put_account_update_existing(self, adapter):
        """Test updating existing account."""
        adapter_instance, mock_db_session = adapter
        
        # Mock existing account
        mock_db_account = Mock(spec=DBAccount)
        mock_db_account.id = "existing-id"
        mock_db_account.cash_balance = 100000.0
        mock_db_account.owner = "original-user"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_db_account
        mock_db_session.query.return_value = mock_query
        
        account = Account(
            id="existing-id",
            cash_balance=75000.0,
            positions=[],
            name="Updated Account",
            owner="updated-user"
        )
        
        adapter_instance.put_account(account)
        
        # Verify account was updated
        assert mock_db_account.cash_balance == 75000.0
        assert mock_db_account.owner == "updated-user"
        assert isinstance(mock_db_account.updated_at, datetime)
        mock_db_session.commit.assert_called_once()
        mock_db_session.add.assert_not_called()  # Should not add new account

    def test_put_account_update_existing_no_owner(self, adapter):
        """Test updating existing account with None owner."""
        adapter_instance, mock_db_session = adapter
        
        # Mock existing account
        mock_db_account = Mock(spec=DBAccount)
        mock_db_account.id = "existing-id"
        mock_db_account.cash_balance = 100000.0
        mock_db_account.owner = "original-user"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_db_account
        mock_db_session.query.return_value = mock_query
        
        account = Account(
            id="existing-id",
            cash_balance=75000.0,
            positions=[],
            name="Updated Account",
            owner=None  # None owner
        )
        
        adapter_instance.put_account(account)
        
        # Verify owner was not updated
        assert mock_db_account.owner == "original-user"  # Should remain unchanged
        assert mock_db_account.cash_balance == 75000.0

    def test_get_account_ids(self, adapter):
        """Test getting all account IDs."""
        adapter_instance, mock_db_session = adapter
        
        # Mock query results
        mock_accounts = [Mock(id="acc1"), Mock(id="acc2"), Mock(id="acc3")]
        mock_query = Mock()
        mock_query.all.return_value = mock_accounts
        mock_db_session.query.return_value = mock_query
        
        ids = adapter_instance.get_account_ids()
        
        assert ids == ["acc1", "acc2", "acc3"]
        mock_db_session.query.assert_called_once_with(DBAccount.id)

    def test_get_account_ids_empty(self, adapter):
        """Test getting account IDs when none exist."""
        adapter_instance, mock_db_session = adapter
        
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        ids = adapter_instance.get_account_ids()
        
        assert ids == []

    def test_account_exists_true(self, adapter):
        """Test checking if account exists (true case)."""
        adapter_instance, mock_db_session = adapter
        
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value = mock_query
        
        exists = adapter_instance.account_exists("existing-id")
        
        assert exists is True
        mock_db_session.query.assert_called_once_with(DBAccount)

    def test_account_exists_false(self, adapter):
        """Test checking if account exists (false case)."""
        adapter_instance, mock_db_session = adapter
        
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 0
        mock_db_session.query.return_value = mock_query
        
        exists = adapter_instance.account_exists("nonexistent")
        
        assert exists is False

    def test_delete_account_success(self, adapter):
        """Test successfully deleting an account."""
        adapter_instance, mock_db_session = adapter
        
        # Mock existing account
        mock_db_account = Mock(spec=DBAccount)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_db_account
        mock_db_session.query.return_value = mock_query
        
        result = adapter_instance.delete_account("test-id")
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_db_account)
        mock_db_session.commit.assert_called_once()

    def test_delete_account_not_found(self, adapter):
        """Test deleting non-existent account."""
        adapter_instance, mock_db_session = adapter
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        result = adapter_instance.delete_account("nonexistent")
        
        assert result is False
        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_called()


class TestLocalFileSystemAccountAdapter:
    """Test LocalFileSystemAccountAdapter functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def adapter(self, temp_dir):
        """Create adapter with temporary directory."""
        return LocalFileSystemAccountAdapter(temp_dir)

    def test_adapter_initialization(self, temp_dir):
        """Test adapter initialization creates directory."""
        test_dir = os.path.join(temp_dir, "test_accounts")
        
        # Directory shouldn't exist initially
        assert not os.path.exists(test_dir)
        
        adapter = LocalFileSystemAccountAdapter(test_dir)
        
        # Directory should be created
        assert os.path.exists(test_dir)
        assert adapter.root_path == test_dir

    def test_adapter_initialization_default_path(self):
        """Test adapter initialization with default path."""
        with patch('os.makedirs') as mock_makedirs:
            adapter = LocalFileSystemAccountAdapter()
        
        assert adapter.root_path == "./data/accounts"
        mock_makedirs.assert_called_once_with("./data/accounts", exist_ok=True)

    def test_get_account_path(self, adapter):
        """Test getting account file path."""
        path = adapter._get_account_path("test-account")
        expected_path = os.path.join(adapter.root_path, "test-account.json")
        assert path == expected_path

    def test_put_and_get_account(self, adapter):
        """Test storing and retrieving an account."""
        account = Account(
            id="test-account",
            cash_balance=100000.0,
            positions=[],
            name="Test Account",
            owner="test-user"
        )
        
        # Store account
        adapter.put_account(account)
        
        # Verify file was created
        account_path = adapter._get_account_path("test-account")
        assert os.path.exists(account_path)
        
        # Retrieve account
        retrieved = adapter.get_account("test-account")
        
        assert retrieved is not None
        assert retrieved.id == "test-account"
        assert retrieved.cash_balance == 100000.0
        assert retrieved.name == "Test Account"
        assert retrieved.owner == "test-user"
        assert retrieved.positions == []

    def test_get_account_not_found(self, adapter):
        """Test getting non-existent account."""
        account = adapter.get_account("nonexistent")
        assert account is None

    def test_get_account_invalid_json(self, adapter, temp_dir):
        """Test getting account with invalid JSON file."""
        # Create invalid JSON file
        account_path = os.path.join(temp_dir, "invalid.json")
        with open(account_path, "w") as f:
            f.write("invalid json content")
        
        account = adapter.get_account("invalid")
        assert account is None

    def test_put_account_overwrites(self, adapter):
        """Test that putting an account overwrites existing file."""
        # Create initial account
        account1 = Account(
            id="test-account",
            cash_balance=50000.0,
            positions=[],
            name="Original Account",
            owner="user1"
        )
        adapter.put_account(account1)
        
        # Update account
        account2 = Account(
            id="test-account",
            cash_balance=75000.0,
            positions=[],
            name="Updated Account",
            owner="user2"
        )
        adapter.put_account(account2)
        
        # Retrieve and verify it was updated
        retrieved = adapter.get_account("test-account")
        assert retrieved.cash_balance == 75000.0
        assert retrieved.name == "Updated Account"
        assert retrieved.owner == "user2"

    def test_get_account_ids(self, adapter):
        """Test getting all account IDs."""
        # Create multiple accounts
        accounts = [
            Account(id="account1", cash_balance=10000.0, positions=[], name="Account 1", owner="user1"),
            Account(id="account2", cash_balance=20000.0, positions=[], name="Account 2", owner="user2"),
            Account(id="account3", cash_balance=30000.0, positions=[], name="Account 3", owner="user3")
        ]
        
        for account in accounts:
            adapter.put_account(account)
        
        ids = adapter.get_account_ids()
        
        assert len(ids) == 3
        assert "account1" in ids
        assert "account2" in ids
        assert "account3" in ids

    def test_get_account_ids_empty(self, adapter):
        """Test getting account IDs when directory is empty."""
        ids = adapter.get_account_ids()
        assert ids == []

    def test_get_account_ids_ignores_non_json(self, adapter, temp_dir):
        """Test that get_account_ids ignores non-JSON files."""
        # Create JSON file
        account = Account(id="valid", cash_balance=10000.0, positions=[], name="Valid", owner="user")
        adapter.put_account(account)
        
        # Create non-JSON files
        with open(os.path.join(temp_dir, "invalid.txt"), "w") as f:
            f.write("not a json file")
        with open(os.path.join(temp_dir, "README.md"), "w") as f:
            f.write("# README")
        
        ids = adapter.get_account_ids()
        
        # Should only return the JSON file account
        assert ids == ["valid"]

    def test_account_exists_true(self, adapter):
        """Test checking if account exists (true case)."""
        account = Account(id="existing", cash_balance=10000.0, positions=[], name="Existing", owner="user")
        adapter.put_account(account)
        
        exists = adapter.account_exists("existing")
        assert exists is True

    def test_account_exists_false(self, adapter):
        """Test checking if account exists (false case)."""
        exists = adapter.account_exists("nonexistent")
        assert exists is False

    def test_delete_account_success(self, adapter):
        """Test successfully deleting an account."""
        # Create account
        account = Account(id="to-delete", cash_balance=10000.0, positions=[], name="To Delete", owner="user")
        adapter.put_account(account)
        
        # Verify it exists
        assert adapter.account_exists("to-delete")
        
        # Delete it
        result = adapter.delete_account("to-delete")
        
        assert result is True
        assert not adapter.account_exists("to-delete")
        assert adapter.get_account("to-delete") is None

    def test_delete_account_not_found(self, adapter):
        """Test deleting non-existent account."""
        result = adapter.delete_account("nonexistent")
        assert result is False

    def test_account_serialization_deserialization(self, adapter):
        """Test that accounts are properly serialized/deserialized."""
        from datetime import datetime
        
        # Create account with various data types
        account = Account(
            id="serialization-test",
            cash_balance=123456.78,
            positions=[],  # Empty list
            name="Serialization Test Account",
            owner="test-user"
        )
        
        # Store and retrieve
        adapter.put_account(account)
        retrieved = adapter.get_account("serialization-test")
        
        assert retrieved is not None
        assert retrieved.id == account.id
        assert retrieved.cash_balance == account.cash_balance
        assert retrieved.positions == account.positions
        assert retrieved.name == account.name
        assert retrieved.owner == account.owner

    def test_concurrent_access_simulation(self, adapter):
        """Test simulated concurrent access (file system should handle it)."""
        # Create multiple accounts quickly
        accounts = []
        for i in range(10):
            account = Account(
                id=f"concurrent-{i}",
                cash_balance=1000.0 * i,
                positions=[],
                name=f"Concurrent Account {i}",
                owner=f"user-{i}"
            )
            accounts.append(account)
            adapter.put_account(account)
        
        # Verify all accounts were stored correctly
        ids = adapter.get_account_ids()
        assert len(ids) == 10
        
        for i in range(10):
            retrieved = adapter.get_account(f"concurrent-{i}")
            assert retrieved is not None
            assert retrieved.cash_balance == 1000.0 * i


class TestAccountFactory:
    """Test account_factory function."""

    def test_account_factory_defaults(self):
        """Test account factory with default values."""
        account = account_factory()
        
        assert account.id is not None
        assert len(account.id) == 8  # Short ID
        assert account.cash_balance == 100000.0
        assert account.positions == []
        assert account.name == f"Account-{account.id}"
        assert account.owner == "default"

    def test_account_factory_custom_values(self):
        """Test account factory with custom values."""
        account = account_factory(
            name="Custom Account",
            owner="custom-user",
            cash=50000.0
        )
        
        assert account.id is not None
        assert len(account.id) == 8
        assert account.cash_balance == 50000.0
        assert account.positions == []
        assert account.name == "Custom Account"
        assert account.owner == "custom-user"

    def test_account_factory_unique_ids(self):
        """Test that account factory generates unique IDs."""
        accounts = [account_factory() for _ in range(10)]
        ids = [account.id for account in accounts]
        
        # All IDs should be unique
        assert len(set(ids)) == len(ids)
        
        # All IDs should be 8 characters
        assert all(len(id_) == 8 for id_ in ids)

    def test_account_factory_partial_custom(self):
        """Test account factory with some custom values."""
        # Only name provided
        account1 = account_factory(name="Custom Name Only")
        assert account1.name == "Custom Name Only"
        assert account1.owner == "default"
        assert account1.cash_balance == 100000.0
        
        # Only owner provided
        account2 = account_factory(owner="custom-owner")
        assert account2.name == f"Account-{account2.id}"
        assert account2.owner == "custom-owner"
        assert account2.cash_balance == 100000.0
        
        # Only cash provided
        account3 = account_factory(cash=75000.0)
        assert account3.name == f"Account-{account3.id}"
        assert account3.owner == "default"
        assert account3.cash_balance == 75000.0

    def test_account_factory_zero_cash(self):
        """Test account factory with zero cash balance."""
        account = account_factory(cash=0.0)
        assert account.cash_balance == 0.0

    def test_account_factory_negative_cash(self):
        """Test account factory with negative cash balance."""
        account = account_factory(cash=-1000.0)
        assert account.cash_balance == -1000.0
