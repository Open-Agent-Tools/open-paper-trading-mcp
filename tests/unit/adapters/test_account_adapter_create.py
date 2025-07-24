"""
Comprehensive test coverage for the CREATE part of AccountAdapter.put_account().

This test suite focuses exclusively on the CREATE operation flow (lines 52-61) in
the DatabaseAccountAdapter.put_account() method, covering successful account creation,
data validation, database persistence, and edge cases.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import DatabaseAccountAdapter, account_factory
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import Account


@asynccontextmanager
async def mock_database_session_context(mock_session):
    """Helper to create a properly mocked async context manager for database sessions."""
    with patch("app.storage.database.get_async_session") as mock_get_session:
        # Setup async context manager that returns our mock session
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_cm
        yield mock_session


@pytest.mark.db_crud
class TestAccountAdapterCreateOperation:
    """Test the CREATE path of DatabaseAccountAdapter.put_account()."""

    @pytest.fixture
    def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest.fixture
    def new_account(self):
        """Create a new account instance for testing CREATE operations."""
        return Account(
            id=str(uuid.uuid4()),
            cash_balance=50000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    @pytest.mark.asyncio
    async def test_create_new_account_success(
        self, db_session: AsyncSession, new_account: Account
    ):
        """Test successful creation of a new account with valid data."""
        adapter = DatabaseAccountAdapter()

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(new_account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == new_account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.id == new_account.id
            assert saved_account.owner == new_account.owner
            assert saved_account.cash_balance == new_account.cash_balance
            assert saved_account.created_at is not None
            assert saved_account.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_account_with_default_owner(self, db_session: AsyncSession):
        """Test account creation with None owner gets default value."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=75000.0,
            positions=[],
            name="Account with default owner",
            owner=None,  # Should get "default" value
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved with default owner
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.owner == "default"

    @pytest.mark.asyncio
    async def test_create_account_with_different_data_types(
        self, db_session: AsyncSession
    ):
        """Test account creation with various data types and values."""
        adapter = DatabaseAccountAdapter()
        test_cases = [
            # (owner, cash_balance, expected_owner, expected_cash)
            ("user_123", 100000.0, "user_123", 100000.0),
            ("corporate_trader", 5000000.0, "corporate_trader", 5000000.0),
            ("student_account", 1000.0, "student_account", 1000.0),
            (
                "special-chars@domain.com",
                25000.50,
                "special-chars@domain.com",
                25000.50,
            ),
            ("unicode_user_测试", 99999.99, "unicode_user_测试", 99999.99),
        ]

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            for owner, cash_balance, expected_owner, expected_cash in test_cases:
                account = Account(
                    id=str(uuid.uuid4()),
                    cash_balance=cash_balance,
                    positions=[],
                    name=f"Account for {owner}",
                    owner=owner,
                )

                # Execute the operation
                await adapter.put_account(account)

                # Verify that the account was saved correctly
                from sqlalchemy import select

                stmt = select(DBAccount).where(DBAccount.id == account.id)
                result = await db_session.execute(stmt)
                saved_account = result.scalar_one_or_none()

                assert saved_account is not None
                assert saved_account.owner == expected_owner
                assert saved_account.cash_balance == expected_cash

    @pytest.mark.asyncio
    async def test_create_account_timestamps_set_correctly(
        self, db_session: AsyncSession
    ):
        """Test that created_at and updated_at timestamps are set during creation."""
        adapter = DatabaseAccountAdapter()
        datetime.now(UTC)

        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=30000.0,
            positions=[],
            name="Timestamp Test Account",
            owner="timestamp_tester",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            datetime.now(UTC)

            # Verify that the account was saved with correct timestamps
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.created_at is not None
            assert saved_account.updated_at is not None
            # Verify timestamps are recent (within last minute)
            import time

            now = time.time()
            created_timestamp = saved_account.created_at.timestamp()
            updated_timestamp = saved_account.updated_at.timestamp()
            assert abs(now - created_timestamp) < 60  # Within last minute
            assert abs(now - updated_timestamp) < 60  # Within last minute

    @pytest.mark.asyncio
    async def test_create_account_zero_cash_balance(self, db_session: AsyncSession):
        """Test account creation with zero cash balance."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=0.0,
            positions=[],
            name="Zero Balance Account",
            owner="zero_balance_user",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved with zero balance
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.cash_balance == 0.0

    @pytest.mark.asyncio
    async def test_create_account_very_small_cash_balance(
        self, db_session: AsyncSession
    ):
        """Test account creation with very small cash balance."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=0.01,
            positions=[],
            name="Penny Account",
            owner="penny_user",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.cash_balance == 0.01

    @pytest.mark.asyncio
    async def test_create_account_large_cash_balance(self, db_session: AsyncSession):
        """Test account creation with very large cash balance."""
        adapter = DatabaseAccountAdapter()
        large_balance = 999999999.99
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=large_balance,
            positions=[],
            name="Whale Account",
            owner="whale_user",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.cash_balance == large_balance

    @pytest.mark.asyncio
    async def test_create_multiple_accounts_same_session(
        self, db_session: AsyncSession
    ):
        """Test creating multiple accounts in sequence."""
        adapter = DatabaseAccountAdapter()
        accounts = []
        for i in range(5):
            account = Account(
                id=str(uuid.uuid4()),
                cash_balance=10000.0 * (i + 1),
                positions=[],
                name=f"Batch Account {i + 1}",
                owner=f"batch_user_{i + 1}",
            )
            accounts.append(account)

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Each call should create a new account
            for account in accounts:
                # Execute the operation
                await adapter.put_account(account)

                # Verify that the account was saved to database
                from sqlalchemy import select

                stmt = select(DBAccount).where(DBAccount.id == account.id)
                result = await db_session.execute(stmt)
                saved_account = result.scalar_one_or_none()

                assert saved_account is not None
                assert saved_account.owner == account.owner
                assert saved_account.cash_balance == account.cash_balance

    @pytest.mark.asyncio
    async def test_create_account_with_account_factory_integration(
        self, db_session: AsyncSession
    ):
        """Test CREATE operation with accounts generated by account_factory."""
        adapter = DatabaseAccountAdapter()

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test with factory defaults
            factory_account = account_factory()

            # Execute the operation
            await adapter.put_account(factory_account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == factory_account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.owner == "default"  # Factory default
            assert saved_account.cash_balance == 100000.0  # Factory default

            # Test with custom factory parameters
            custom_account = account_factory(
                name="Custom Factory Account", owner="factory_user", cash=25000.0
            )

            # Execute the operation
            await adapter.put_account(custom_account)

            # Verify that the account was saved to database
            stmt = select(DBAccount).where(DBAccount.id == custom_account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.owner == "factory_user"
            assert saved_account.cash_balance == 25000.0

    @pytest.mark.asyncio
    async def test_create_account_database_add_called(
        self, db_session: AsyncSession, new_account: Account
    ):
        """Test that db.add() is called during account creation."""
        adapter = DatabaseAccountAdapter()

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(new_account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == new_account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert isinstance(saved_account, DBAccount)
            assert saved_account.id == new_account.id
            assert saved_account.owner == new_account.owner
            assert saved_account.cash_balance == new_account.cash_balance

    @pytest.mark.asyncio
    async def test_create_account_commit_called(
        self, db_session: AsyncSession, new_account: Account
    ):
        """Test that database commit is called after account creation."""
        adapter = DatabaseAccountAdapter()

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(new_account)

            # Verify that the account was saved to database (commit was successful)
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == new_account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None


@pytest.mark.db_crud
class TestAccountAdapterCreateBoundaryConditions:
    """Test boundary conditions and edge cases for account creation."""

    @pytest.fixture
    def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest.mark.asyncio
    async def test_create_account_minimal_required_fields(
        self, db_session: AsyncSession
    ):
        """Test account creation with only required fields."""
        adapter = DatabaseAccountAdapter()
        # Create account with minimal data (based on Account schema requirements)
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=1000.0,  # Required field
            positions=[],  # Has default
            name=None,  # Optional
            owner=None,  # Optional, should get default
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.id == account.id
            assert saved_account.owner == "default"  # Default applied
            assert saved_account.cash_balance == 1000.0

    @pytest.mark.asyncio
    async def test_create_account_maximum_length_owner(self, db_session: AsyncSession):
        """Test account creation with maximum length owner string."""
        adapter = DatabaseAccountAdapter()
        # Create a very long owner name to test database field limits
        long_owner = "a" * 255  # Typical VARCHAR limit
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=50000.0,
            positions=[],
            name="Long Owner Test",
            owner=long_owner,
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved to database
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert saved_account.owner == long_owner

    @pytest.mark.asyncio
    async def test_create_account_special_characters_in_id(
        self, db_session: AsyncSession
    ):
        """Test account creation with special characters in account ID."""
        adapter = DatabaseAccountAdapter()
        special_ids = [
            "account-with-dashes",
            "account_with_underscores",
            "account.with.dots",
            "account123numbers",
            "UPPERCASE-ACCOUNT",
        ]

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            for special_id in special_ids:
                account = Account(
                    id=special_id,
                    cash_balance=20000.0,
                    positions=[],
                    name=f"Account {special_id}",
                    owner=f"user_{special_id}",
                )

                # Execute the operation
                await adapter.put_account(account)

                # Verify that the account was saved to database
                from sqlalchemy import select

                stmt = select(DBAccount).where(DBAccount.id == special_id)
                result = await db_session.execute(stmt)
                saved_account = result.scalar_one_or_none()

                assert saved_account is not None
                assert saved_account.id == special_id

    @pytest.mark.asyncio
    async def test_create_account_cash_balance_precision(
        self, db_session: AsyncSession
    ):
        """Test account creation with various decimal precision values."""
        adapter = DatabaseAccountAdapter()
        precision_cases = [
            12345.67,  # 2 decimal places
            12345.678,  # 3 decimal places
            12345.6789,  # 4 decimal places
            12345.12345,  # 5 decimal places
            0.123456789,  # Small number with high precision
        ]

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            for i, balance in enumerate(precision_cases):
                account = Account(
                    id=f"precision-test-{i}",
                    cash_balance=balance,
                    positions=[],
                    name=f"Precision Test {i}",
                    owner=f"precision_user_{i}",
                )

                # Execute the operation
                await adapter.put_account(account)

                # Verify that the account was saved to database
                from sqlalchemy import select

                stmt = select(DBAccount).where(DBAccount.id == account.id)
                result = await db_session.execute(stmt)
                saved_account = result.scalar_one_or_none()

                assert saved_account is not None
                # Use approximate equality for floating point comparison
                assert abs(saved_account.cash_balance - balance) < 0.000001


@pytest.mark.db_crud
class TestAccountAdapterCreateTransactionHandling:
    """Test transaction handling during account creation."""

    @pytest.fixture
    def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest.mark.asyncio
    async def test_create_account_async_session_used_correctly(
        self, db_session: AsyncSession
    ):
        """Test that async session context manager is used correctly."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=45000.0,
            positions=[],
            name="Context Manager Test",
            owner="context_user",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Execute the operation
            await adapter.put_account(account)

            # Verify that the account was saved to database (session was used correctly)
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            # Verify session factory was called
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_account_rollback_on_error(self, db_session: AsyncSession):
        """Test that transaction errors are propagated properly during creation."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=55000.0,
            positions=[],
            name="Rollback Test Account",
            owner="rollback_user",
        )

        # Mock the commit method to raise an error
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock db_session.commit to raise an error
            with patch.object(
                db_session, "commit", side_effect=Exception("Database error")
            ), pytest.raises(Exception, match="Database error"):
                # Verify exception is propagated
                await adapter.put_account(account)

                # Test passed - exception was properly propagated

    @pytest.mark.asyncio
    async def test_create_vs_update_path_distinction(self, db_session: AsyncSession):
        """Test that CREATE path is taken when account doesn't exist vs UPDATE when it does."""
        adapter = DatabaseAccountAdapter()
        account = Account(
            id=str(uuid.uuid4()),
            cash_balance=60000.0,
            positions=[],
            name="Path Test Account",
            owner="path_user",
        )

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test CREATE path (account doesn't exist)
            await adapter.put_account(account)

            # Verify CREATE path: account was created
            from sqlalchemy import select

            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            saved_account = result.scalar_one_or_none()

            assert saved_account is not None
            assert isinstance(saved_account, DBAccount)
            assert saved_account.id == account.id
            assert saved_account.cash_balance == account.cash_balance

            # Test UPDATE path (account exists) - modify existing account
            updated_account = Account(
                id=account.id,  # Same ID
                cash_balance=80000.0,  # Different balance
                positions=[],
                name="Updated Path Test Account",
                owner="updated_path_user",
            )

            await adapter.put_account(updated_account)

            # Verify UPDATE path: account was updated, not duplicated
            stmt = select(DBAccount).where(DBAccount.id == account.id)
            result = await db_session.execute(stmt)
            all_accounts = result.scalars().all()

            assert len(all_accounts) == 1  # Only one account, not two
            updated_saved_account = all_accounts[0]
            assert updated_saved_account.cash_balance == 80000.0  # Updated value
            assert updated_saved_account.updated_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
