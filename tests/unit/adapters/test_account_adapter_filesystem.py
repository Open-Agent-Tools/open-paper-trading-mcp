"""
Comprehensive tests for LocalFileSystemAccountAdapter.

Tests all CRUD operations, file handling, and edge cases
for the filesystem-backed account adapter.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from app.adapters.accounts import LocalFileSystemAccountAdapter
from app.schemas.accounts import Account


class TestLocalFileSystemAccountAdapter:
    """Test the LocalFileSystemAccountAdapter with file operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def adapter(self, temp_dir):
        """Create a filesystem account adapter for testing."""
        return LocalFileSystemAccountAdapter(temp_dir)

    @pytest.fixture
    def sample_account(self):
        """Create a sample account for testing."""
        return Account(
            id="test-account-123",
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    def test_init_creates_directory(self):
        """Test that adapter creates root directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = os.path.join(temp_dir, "new_accounts")

            adapter = LocalFileSystemAccountAdapter(non_existent_path)

            assert os.path.exists(non_existent_path)
            assert adapter.root_path == non_existent_path

    def test_get_account_path(self, adapter, temp_dir):
        """Test _get_account_path method."""
        expected_path = os.path.join(temp_dir, "test-account.json")
        actual_path = adapter._get_account_path("test-account")

        assert actual_path == expected_path

    @pytest.mark.asyncio
    async def test_put_account_success(self, adapter, sample_account, temp_dir):
        """Test successful account storage."""
        await adapter.put_account(sample_account)

        # Verify file was created
        expected_path = os.path.join(temp_dir, f"{sample_account.id}.json")
        assert os.path.exists(expected_path)

        # Verify file contents
        with open(expected_path) as f:
            data = json.load(f)

        assert data["id"] == sample_account.id
        assert data["cash_balance"] == sample_account.cash_balance
        assert data["owner"] == sample_account.owner
        assert data["positions"] == []

    @pytest.mark.asyncio
    async def test_get_account_success(self, adapter, sample_account):
        """Test successful account retrieval."""
        # First store the account
        await adapter.put_account(sample_account)

        # Then retrieve it
        result = await adapter.get_account(sample_account.id)

        assert result is not None
        assert result.id == sample_account.id
        assert result.cash_balance == sample_account.cash_balance
        assert result.owner == sample_account.owner
        assert result.positions == sample_account.positions

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, adapter):
        """Test get_account when file doesn't exist."""
        result = await adapter.get_account("nonexistent-account")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_corrupted_json(self, adapter, temp_dir):
        """Test get_account with corrupted JSON file."""
        # Create corrupted JSON file
        corrupted_file = os.path.join(temp_dir, "corrupted.json")
        with open(corrupted_file, "w") as f:
            f.write("{ invalid json content }")

        result = await adapter.get_account("corrupted")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_empty_file(self, adapter, temp_dir):
        """Test get_account with empty file."""
        # Create empty file
        empty_file = os.path.join(temp_dir, "empty.json")
        with open(empty_file, "w") as f:
            f.write("")

        result = await adapter.get_account("empty")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_ids_empty(self, adapter):
        """Test get_account_ids when no accounts exist."""
        result = await adapter.get_account_ids()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_account_ids_with_accounts(self, adapter, temp_dir):
        """Test get_account_ids with multiple accounts."""
        # Create multiple account files
        account_ids = ["acc-1", "acc-2", "acc-3"]

        for account_id in account_ids:
            account = Account(
                id=account_id,
                cash_balance=1000.0,
                positions=[],
                name=f"Account {account_id}",
                owner="test_user",
            )
            await adapter.put_account(account)

        result = await adapter.get_account_ids()

        assert len(result) == 3
        assert set(result) == set(account_ids)

    @pytest.mark.asyncio
    async def test_get_account_ids_ignores_non_json_files(self, adapter, temp_dir):
        """Test get_account_ids ignores non-JSON files."""
        # Create account files
        account = Account(
            id="valid-account",
            cash_balance=1000.0,
            positions=[],
            name="Valid Account",
            owner="test_user",
        )
        await adapter.put_account(account)

        # Create non-JSON files
        with open(os.path.join(temp_dir, "not-json.txt"), "w") as f:
            f.write("This is not a JSON file")

        with open(os.path.join(temp_dir, "no-extension"), "w") as f:
            f.write("{}")

        result = await adapter.get_account_ids()

        assert len(result) == 1
        assert result[0] == "valid-account"

    @pytest.mark.asyncio
    async def test_account_exists_true(self, adapter, sample_account):
        """Test account_exists returns True for existing account."""
        await adapter.put_account(sample_account)

        result = await adapter.account_exists(sample_account.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_account_exists_false(self, adapter):
        """Test account_exists returns False for non-existent account."""
        result = await adapter.account_exists("does-not-exist")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_account_success(self, adapter, sample_account):
        """Test successful account deletion."""
        # First create the account
        await adapter.put_account(sample_account)
        assert await adapter.account_exists(sample_account.id) is True

        # Delete the account
        result = await adapter.delete_account(sample_account.id)
        assert result is True

        # Verify it's gone
        assert await adapter.account_exists(sample_account.id) is False

    @pytest.mark.asyncio
    async def test_delete_account_not_found(self, adapter):
        """Test deleting non-existent account returns False."""
        result = await adapter.delete_account("does-not-exist")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_existing_account(self, adapter):
        """Test updating an existing account overwrites the file."""
        # Create initial account
        original_account = Account(
            id="update-test",
            cash_balance=5000.0,
            positions=[],
            name="Original Account",
            owner="original_owner",
        )
        await adapter.put_account(original_account)

        # Update the account
        updated_account = Account(
            id="update-test",
            cash_balance=15000.0,
            positions=[],
            name="Updated Account",
            owner="updated_owner",
        )
        await adapter.put_account(updated_account)

        # Verify the update
        result = await adapter.get_account("update-test")
        assert result is not None
        assert result.cash_balance == 15000.0
        assert result.owner == "updated_owner"

    @pytest.mark.asyncio
    @patch("builtins.open")
    async def test_put_account_file_permission_error(
        self, mock_open, adapter, sample_account
    ):
        """Test file permission error during put_account."""
        mock_open.side_effect = PermissionError("Permission denied")

        with pytest.raises(PermissionError):
            await adapter.put_account(sample_account)

    @pytest.mark.asyncio
    @patch("builtins.open")
    async def test_get_account_file_permission_error(self, mock_open, adapter):
        """Test file permission error during get_account."""
        mock_open.side_effect = PermissionError("Permission denied")

        # Should return None on any exception
        result = await adapter.get_account("test-account")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_serialization_with_datetime(self, adapter, temp_dir):
        """Test JSON serialization handles datetime objects properly."""

        # Create account with datetime in positions (if they had timestamps)
        account = Account(
            id="datetime-test",
            cash_balance=1000.0,
            positions=[],
            name="DateTime Test Account",
            owner="test_user",
        )

        # This should not raise an error
        await adapter.put_account(account)

        # Verify it can be read back
        result = await adapter.get_account("datetime-test")
        assert result is not None
        assert result.id == "datetime-test"


class TestLocalFileSystemAccountAdapterEdgeCases:
    """Test edge cases and boundary conditions for LocalFileSystemAccountAdapter."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def adapter(self, temp_dir):
        """Create a filesystem account adapter for testing."""
        return LocalFileSystemAccountAdapter(temp_dir)

    @pytest.mark.asyncio
    async def test_account_with_zero_balance(self, adapter):
        """Test account with zero cash balance."""
        zero_balance_account = Account(
            id="zero-balance-test",
            cash_balance=0.0,
            positions=[],
            name="Zero Balance Account",
            owner="test_user",
        )

        await adapter.put_account(zero_balance_account)
        result = await adapter.get_account("zero-balance-test")

        assert result is not None
        assert result.cash_balance == 0.0

    @pytest.mark.asyncio
    async def test_account_with_special_characters_in_id(self, adapter):
        """Test account with special characters in ID."""
        # Note: Some special characters might not be valid in filenames
        special_id = "test-account_123"
        special_account = Account(
            id=special_id,
            cash_balance=1000.0,
            positions=[],
            name="Special ID Account",
            owner="test_user",
        )

        await adapter.put_account(special_account)
        result = await adapter.get_account(special_id)

        assert result is not None
        assert result.id == special_id

    @pytest.mark.asyncio
    async def test_account_with_unicode_characters(self, adapter):
        """Test account with unicode characters in owner name."""
        unicode_account = Account(
            id="unicode-test",
            cash_balance=1000.0,
            positions=[],
            name="Unicode Test Account",
            owner="用户测试",  # Chinese characters
        )

        await adapter.put_account(unicode_account)
        result = await adapter.get_account("unicode-test")

        assert result is not None
        assert result.owner == "用户测试"

    @pytest.mark.asyncio
    async def test_large_number_of_accounts(self, adapter):
        """Test handling a large number of accounts."""
        num_accounts = 100

        # Create many accounts
        for i in range(num_accounts):
            account = Account(
                id=f"account-{i:03d}",
                cash_balance=1000.0 + i,
                positions=[],
                name=f"Account {i}",
                owner=f"user_{i}",
            )
            await adapter.put_account(account)

        # Verify all were created
        account_ids = await adapter.get_account_ids()
        assert len(account_ids) == num_accounts

        # Verify we can retrieve them all
        for i in range(num_accounts):
            result = await adapter.get_account(f"account-{i:03d}")
            assert result is not None
            assert result.cash_balance == 1000.0 + i

    @pytest.mark.asyncio
    async def test_concurrent_file_operations(self, adapter):
        """Test that file operations don't interfere with each other."""
        # This is a basic test - true concurrency testing would require threading
        accounts = []

        # Create accounts rapidly
        for i in range(10):
            account = Account(
                id=f"concurrent-{i}",
                cash_balance=1000.0 * i,
                positions=[],
                name=f"Concurrent Account {i}",
                owner=f"user_{i}",
            )
            accounts.append(account)
            await adapter.put_account(account)

        # Verify all were created correctly
        for i, account in enumerate(accounts):
            result = await adapter.get_account(account.id)
            assert result is not None
            assert result.cash_balance == 1000.0 * i
            assert result.owner == f"user_{i}"

    @pytest.mark.asyncio
    async def test_file_corruption_recovery(self, adapter, temp_dir):
        """Test behavior when file gets corrupted after creation."""
        # Create account normally
        account = Account(
            id="corruption-test",
            cash_balance=1000.0,
            positions=[],
            name="Corruption Test Account",
            owner="test_user",
        )
        await adapter.put_account(account)

        # Verify it exists
        assert await adapter.account_exists("corruption-test") is True

        # Corrupt the file
        corrupted_path = os.path.join(temp_dir, "corruption-test.json")
        with open(corrupted_path, "w") as f:
            f.write("{ corrupted json ")

        # Getting the account should return None (graceful handling)
        result = await adapter.get_account("corruption-test")
        assert result is None

        # But file still exists, so account_exists should return True
        assert await adapter.account_exists("corruption-test") is True

        # We can overwrite the corrupted file
        await adapter.put_account(account)

        # Now it should work again
        result = await adapter.get_account("corruption-test")
        assert result is not None
        assert result.id == "corruption-test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
