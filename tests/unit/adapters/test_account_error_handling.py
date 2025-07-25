"""
Comprehensive error handling tests for account operations.

Tests all error scenarios, validation failures, database issues, and recovery mechanisms
for account adapters and related operations.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import (
    DatabaseAccountAdapter,
    LocalFileSystemAccountAdapter,
    account_factory,
)
from app.schemas.accounts import Account


class TestAccountValidationErrors:
    """Test input validation errors for account operations."""

    def test_account_schema_invalid_owner_empty(self):
        """Test Account schema validation with empty owner name."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="test-123",
                cash_balance=1000.0,
                positions=[],
                name="Test Account",
                owner="",  # Empty owner should fail validation
            )

        error_details = str(exc_info.value)
        assert "Owner cannot be empty" in error_details

    def test_account_schema_negative_cash_balance(self):
        """Test Account schema validation with negative cash balance."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="test-123",
                cash_balance=-1000.0,  # Negative balance should fail
                positions=[],
                name="Test Account",
                owner="valid_owner",
            )

        error_details = str(exc_info.value)
        assert "Cash balance cannot be negative" in error_details

    def test_account_factory_with_defaults(self):
        """Test account factory with default values."""
        account = account_factory()
        assert account.owner == "default"
        assert account.cash_balance == 100000.0
        assert len(account.id) == 8  # Short UUID format

    def test_account_factory_edge_cases(self):
        """Test account factory with edge case inputs."""
        # Test with zero cash
        account = account_factory(cash=0.0)
        assert account.cash_balance == 0.0

        # Test with very small positive cash
        account = account_factory(cash=0.01)
        assert account.cash_balance == 0.01


@pytest.mark.database
class TestDatabaseAccountAdapterErrors:
    """Test database adapter error handling scenarios."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest_asyncio.fixture
    async def sample_account(self):
        """Create a sample account for testing."""
        return Account(
            id=str(uuid.uuid4()),
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    @pytest.mark.asyncio
    @patch("app.adapters.accounts.get_async_session")
    async def test_get_account_nonexistent_id(self, mock_session, adapter):
        """Test getting a non-existent account."""
        # Mock async context manager
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_session.return_value.__aexit__.return_value = None

        # Mock the execute result chain
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        nonexistent_id = str(uuid.uuid4())
        result = await adapter.get_account(nonexistent_id)
        assert result is None

    @pytest.mark.asyncio
    @patch("app.adapters.accounts.get_async_session")
    async def test_get_account_database_connection_error(self, mock_session, adapter):
        """Test database connection failure during get_account."""
        mock_session.side_effect = OperationalError("Connection failed", None, None)

        with pytest.raises(OperationalError):
            await adapter.get_account("test-id")

    @pytest.mark.asyncio
    async def test_put_account_integrity_error(
        self, adapter, sample_account, db_session: AsyncSession
    ):
        """Test database integrity constraint violation."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:
            # Mock session that will yield our mock database
            mock_db = AsyncMock()

            async def mock_session_generator():
                yield mock_db

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock query to return None (new account scenario)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Mock add and commit to raise IntegrityError
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock(
                side_effect=IntegrityError("Duplicate key", {}, None)
            )

            with pytest.raises(IntegrityError):
                await adapter.put_account(sample_account)

    @pytest.mark.asyncio
    async def test_delete_account_nonexistent(self, adapter):
        """Test deleting a non-existent account."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:
            mock_db = AsyncMock()

            async def mock_session_generator():
                yield mock_db

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock the execute result chain
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            result = await adapter.delete_account("nonexistent-id")
            assert result is False


class TestFileSystemAccountAdapterErrors:
    """Test file system adapter error handling scenarios."""

    @pytest_asyncio.fixture
    async def adapter(self, tmp_path):
        """Create a file system account adapter for testing."""
        return LocalFileSystemAccountAdapter(str(tmp_path))

    @pytest_asyncio.fixture
    async def sample_account(self):
        """Create a sample account for testing."""
        return Account(
            id="test-account",
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    @pytest.mark.asyncio
    async def test_get_account_nonexistent_file(self, adapter):
        """Test getting account from non-existent file."""
        result = await adapter.get_account("nonexistent-account")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_corrupted_json(self, adapter, tmp_path):
        """Test reading corrupted JSON file."""
        # Create corrupted JSON file
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{ invalid json content }")

        result = await adapter.get_account("corrupted")
        assert result is None

    @patch("builtins.open")
    @pytest.mark.asyncio
    async def test_put_account_file_permission_error(
        self, mock_open, adapter, sample_account
    ):
        """Test file permission error during put_account."""
        mock_open.side_effect = PermissionError("Permission denied")

        with pytest.raises(PermissionError):
            await adapter.put_account(sample_account)

    @pytest.mark.asyncio
    async def test_delete_account_nonexistent_file(self, adapter):
        """Test deleting non-existent account file."""
        result = await adapter.delete_account("nonexistent-account")
        assert result is False


class TestErrorMessageAccuracy:
    """Test that error messages are clear and actionable."""

    def test_validation_error_messages_are_specific(self):
        """Test that validation error messages provide specific guidance."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="test-123",
                cash_balance=-100.0,
                positions=[],
                name="Test Account",
                owner="test_user",
            )

        error_msg = str(exc_info.value)
        assert "Cash balance cannot be negative" in error_msg

    @pytest.mark.asyncio
    async def test_database_error_propagation(self):
        """Test that database errors are properly propagated with context."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "Connection to database failed", None, None
            )

            with pytest.raises(OperationalError) as exc_info:
                await adapter.get_account("test-id")

            error_msg = str(exc_info.value)
            assert "Connection to database failed" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
