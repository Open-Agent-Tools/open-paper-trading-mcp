"""
Comprehensive tests for DatabaseAccountAdapter.

Tests all CRUD operations, edge cases, and database interactions
for the database-backed account adapter.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import DatabaseAccountAdapter
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import Account

pytestmark = pytest.mark.journey_account_infrastructure


@pytest.mark.database
class TestDatabaseAccountAdapter:
    """Test the DatabaseAccountAdapter with real database operations."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest_asyncio.fixture
    async def sample_account(self):
        """Create a sample account for testing."""
        return Account(
            id="TEST123456",
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    @pytest.mark.asyncio
    async def test_get_account_success(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test successful account retrieval."""
        # Create account in database
        db_account = DBAccount(
            id="TEST123456",
            owner="test_owner",
            cash_balance=50000.0,
        )
        db_session.add(db_account)
        await db_session.commit()

        # Mock get_async_session to return our test session
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test retrieval
            result = await adapter.get_account("TEST123456")

            assert result is not None
            assert result.id == "TEST123456"
            assert result.owner == "test_owner"
            assert result.cash_balance == 50000.0
            assert result.name == "Account-TEST123456"
            assert result.positions == []

    @pytest.mark.asyncio
    async def test_get_account_not_found(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account retrieval when account doesn't exist."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.get_account("NOTEXIST01")
            assert result is None

    @pytest.mark.asyncio
    async def test_put_account_new(
        self,
        adapter: DatabaseAccountAdapter,
        db_session: AsyncSession,
        sample_account: Account,
    ):
        """Test creating a new account."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Put the account
            await adapter.put_account(sample_account)

            # Verify it was created
            result = await adapter.get_account(sample_account.id)
            assert result is not None
            assert result.id == sample_account.id
            assert result.owner == sample_account.owner
            assert result.cash_balance == sample_account.cash_balance

    @pytest.mark.asyncio
    async def test_put_account_update_existing(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test updating an existing account."""
        # Create initial account
        original_account = Account(
            id="UPDATE0123",
            cash_balance=5000.0,
            positions=[],
            name="Original Account",
            owner="original_owner",
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(original_account)

            # Update the account
            updated_account = Account(
                id="UPDATE0123",
                cash_balance=15000.0,
                positions=[],
                name="Updated Account",
                owner="updated_owner",
            )

            await adapter.put_account(updated_account)

            # Verify the update
            result = await adapter.get_account("UPDATE0123")
            assert result is not None
            assert result.cash_balance == 15000.0
            assert result.owner == "updated_owner"

    @pytest.mark.asyncio
    async def test_put_account_with_default_owner(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test creating account with None owner uses default."""
        account_with_none_owner = Account(
            id="DEFAULT001",
            cash_balance=1000.0,
            positions=[],
            name="Test Account",
            owner=None,  # This should use "default"
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(account_with_none_owner)

            # Verify default owner was used
            result = await adapter.get_account("DEFAULT001")
            assert result is not None
            assert result.owner == "default"

    @pytest.mark.asyncio
    async def test_get_account_ids(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test retrieving all account IDs."""
        # Create multiple accounts
        accounts = [
            DBAccount(id="ACCOUNT001", owner="user1", cash_balance=1000.0),
            DBAccount(id="ACCOUNT002", owner="user2", cash_balance=2000.0),
            DBAccount(id="ACCOUNT003", owner="user3", cash_balance=3000.0),
        ]

        for account in accounts:
            db_session.add(account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.get_account_ids()

            assert len(result) == 3
            assert "ACCOUNT001" in result
            assert "ACCOUNT002" in result
            assert "ACCOUNT003" in result

    @pytest.mark.asyncio
    async def test_get_account_ids_empty(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test retrieving account IDs when no accounts exist."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.get_account_ids()
            assert result == []

    @pytest.mark.asyncio
    async def test_account_exists_true(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account_exists returns True for existing account."""
        # Create account
        db_account = DBAccount(
            id="EXISTS0001",
            owner="test_user",
            cash_balance=1000.0,
        )
        db_session.add(db_account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.account_exists("EXISTS0001")
            assert result is True

    @pytest.mark.asyncio
    async def test_account_exists_false(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account_exists returns False for non-existent account."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.account_exists("NOTEXIST02")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_account_success(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test successful account deletion."""
        # Create account
        db_account = DBAccount(
            id="DELETE0001",
            owner="test_user",
            cash_balance=1000.0,
        )
        db_session.add(db_account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Delete the account
            result = await adapter.delete_account("DELETE0001")
            assert result is True

            # Verify it's gone
            exists = await adapter.account_exists("DELETE0001")
            assert exists is False

    @pytest.mark.asyncio
    async def test_delete_account_not_found(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test deleting non-existent account returns False."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.delete_account("NOTEXIST03")
            assert result is False


@pytest.mark.database
class TestDatabaseAccountAdapterEdgeCases:
    """Test edge cases and boundary conditions for DatabaseAccountAdapter."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest.mark.asyncio
    async def test_account_with_zero_balance(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account with zero cash balance."""
        zero_balance_account = Account(
            id="ZEROBAL001",
            cash_balance=0.0,
            positions=[],
            name="Zero Balance Account",
            owner="test_user",
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(zero_balance_account)

            result = await adapter.get_account("ZEROBAL001")
            assert result is not None
            assert result.cash_balance == 0.0

    @pytest.mark.asyncio
    async def test_account_with_very_large_balance(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account with very large cash balance."""
        large_balance_account = Account(
            id="LARGEBAL01",
            cash_balance=999999999.99,
            positions=[],
            name="Large Balance Account",
            owner="test_user",
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(large_balance_account)

            result = await adapter.get_account("LARGEBAL01")
            assert result is not None
            assert result.cash_balance == 999999999.99

    @pytest.mark.asyncio
    async def test_account_with_long_id(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account with very long ID."""
        long_id = "A123456789"  # Valid 10-char ID for database constraint
        long_id_account = Account(
            id=long_id,
            cash_balance=1000.0,
            positions=[],
            name="Long ID Account",
            owner="test_user",
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(long_id_account)

            result = await adapter.get_account(long_id)
            assert result is not None
            assert result.id == long_id

    @pytest.mark.asyncio
    async def test_account_with_special_characters_in_owner(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test account with special characters in owner name."""
        special_chars_account = Account(
            id="SPECIAL001",
            cash_balance=1000.0,
            positions=[],
            name="Special Chars Account",
            owner="user@example.com!#$%",
        )

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            await adapter.put_account(special_chars_account)

            result = await adapter.get_account("SPECIAL001")
            assert result is not None
            assert result.owner == "user@example.com!#$%"

    @pytest.mark.asyncio
    async def test_rapid_account_operations(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test rapid creation, update, and deletion of accounts."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Create multiple accounts rapidly
            accounts = []
            for i in range(10):
                account = Account(
                    id=f"RAPID{i:05d}",
                    cash_balance=1000.0 * i,
                    positions=[],
                    name=f"Rapid Test Account {i}",
                    owner=f"user_{i}",
                )
                accounts.append(account)
                await adapter.put_account(account)

            # Verify all were created
            account_ids = await adapter.get_account_ids()
            for i in range(10):
                assert f"RAPID{i:05d}" in account_ids

            # Update all accounts
            for i, account in enumerate(accounts):
                account.cash_balance = 2000.0 * i
                await adapter.put_account(account)

            # Verify updates
            for i in range(10):
                result = await adapter.get_account(f"RAPID{i:05d}")
                assert result is not None
                assert result.cash_balance == 2000.0 * i

            # Delete all accounts
            for i in range(10):
                deleted = await adapter.delete_account(f"RAPID{i:05d}")
                assert deleted is True

            # Verify all are gone
            for i in range(10):
                exists = await adapter.account_exists(f"RAPID{i:05d}")
                assert exists is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
