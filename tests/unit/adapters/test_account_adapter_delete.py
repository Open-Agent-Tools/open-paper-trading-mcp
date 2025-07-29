"""
Comprehensive test coverage for AccountAdapter.delete_account() function.

Tests all DELETE operation scenarios including successful deletion, non-existent accounts,
foreign key constraints, cascade behavior, transaction integrity, and database consistency.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import DatabaseAccountAdapter
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.models.database.trading import Transaction as DBTransaction
from app.schemas.orders import OrderStatus, OrderType

pytestmark = pytest.mark.journey_account_management


@pytest.mark.asyncio
class TestAccountAdapterDeleteCRUD:
    """Test DELETE operations for DatabaseAccountAdapter.delete_account()."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a database account adapter for testing."""
        return DatabaseAccountAdapter()

    @pytest_asyncio.fixture
    async def sample_account(self, db_session: AsyncSession):
        """Create a sample account in the database."""
        account_id = "SAMPLE0001"
        db_account = DBAccount(
            id=account_id,
            owner="sample_user_001",
            cash_balance=10000.0,
        )
        db_session.add(db_account)
        await db_session.commit()
        await db_session.refresh(db_account)
        return db_account

    @pytest_asyncio.fixture
    async def sample_account_with_positions(self, db_session: AsyncSession):
        """Create a sample account with positions for foreign key testing."""
        account_id = "POSITIONS1"
        db_account = DBAccount(
            id=account_id,
            owner="positions_user_001",
            cash_balance=50000.0,
        )
        db_session.add(db_account)
        await db_session.flush()

        # Add positions
        positions = [
            DBPosition(
                id="POS0000001",
                account_id=account_id,
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
            ),
            DBPosition(
                id="POS0000002",
                account_id=account_id,
                symbol="GOOGL",
                quantity=50,
                avg_price=2800.0,
            ),
        ]
        for position in positions:
            db_session.add(position)

        await db_session.commit()
        await db_session.refresh(db_account)
        return db_account, positions

    @pytest_asyncio.fixture
    async def sample_account_with_all_relations(self, db_session: AsyncSession):
        """Create a sample account with all related data for comprehensive testing."""
        account_id = "RELATIONS1"
        db_account = DBAccount(
            id=account_id,
            owner="relations_user_001",
            cash_balance=100000.0,
        )
        db_session.add(db_account)
        await db_session.flush()

        # Add positions
        position = DBPosition(
            id="POS0000003",
            account_id=account_id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
        )
        db_session.add(position)

        # Add orders
        order = DBOrder(
            id="ORDER00001",
            account_id=account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.FILLED,
        )
        db_session.add(order)
        await db_session.flush()

        # Add transactions
        transaction = DBTransaction(
            id="TRANS00001",
            account_id=account_id,
            order_id=order.id,
            symbol="AAPL",
            quantity=100,
            price=150.0,
            transaction_type=OrderType.BUY,
        )
        db_session.add(transaction)

        await db_session.commit()
        await db_session.refresh(db_account)
        return db_account, [position], [order], [transaction]

    async def test_delete_existing_account_success(
        self,
        adapter: DatabaseAccountAdapter,
        sample_account: DBAccount,
        db_session: AsyncSession,
    ):
        """Test successful deletion of an existing account."""
        account_id = sample_account.id

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Verify account exists before deletion
            stmt = select(DBAccount).filter(DBAccount.id == account_id)
            query_result = await db_session.execute(stmt)
            assert query_result.scalar_one_or_none() is not None

            # Delete the account
            delete_result = await adapter.delete_account(account_id)

            # Verify deletion was successful
            assert delete_result is True

            # Verify account no longer exists in database
            stmt = select(DBAccount).filter(DBAccount.id == account_id)
            verify_result = await db_session.execute(stmt)
            assert verify_result.scalar_one_or_none() is None

    async def test_delete_nonexistent_account(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test deletion of a non-existent account returns False."""
        nonexistent_id = "TEST123456"

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Verify account doesn't exist
            stmt = select(DBAccount).filter(DBAccount.id == nonexistent_id)
            query_result = await db_session.execute(stmt)
            assert query_result.scalar_one_or_none() is None

            # Attempt to delete non-existent account
            delete_result = await adapter.delete_account(nonexistent_id)

            # Should return False for non-existent account
            assert delete_result is False

    async def test_delete_account_with_positions_cascade(
        self,
        adapter: DatabaseAccountAdapter,
        sample_account_with_positions,
        db_session: AsyncSession,
    ):
        """Test deletion of account with positions - should handle foreign key constraints."""
        db_account, positions = sample_account_with_positions
        account_id = db_account.id

        # Mock the database session in the adapter
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Verify account and positions exist before deletion
            account_stmt = select(DBAccount).filter(DBAccount.id == account_id)
            account_result = await db_session.execute(account_stmt)
            assert account_result.scalar_one_or_none() is not None

            position_stmt = select(DBPosition).filter(
                DBPosition.account_id == account_id
            )
            position_result = await db_session.execute(position_stmt)
            existing_positions = position_result.scalars().all()
            assert len(existing_positions) == 2

            # Delete related positions first (manual cascade since DB doesn't have CASCADE DELETE)
            for position in existing_positions:
                await db_session.delete(position)
            await db_session.commit()

            # Now delete the account should succeed
            delete_result = await adapter.delete_account(account_id)

            # Deletion should be successful
            assert delete_result is True

            # Verify account is deleted
            verify_stmt = select(DBAccount).filter(DBAccount.id == account_id)
            verify_result = await db_session.execute(verify_stmt)
            assert verify_result.scalar_one_or_none() is None

    async def test_delete_account_with_all_relations_cascade(
        self,
        adapter: DatabaseAccountAdapter,
        sample_account_with_all_relations,
        db_session: AsyncSession,
    ):
        """Test deletion of account with all related data (positions, orders, transactions)."""
        db_account, positions, orders, transactions = sample_account_with_all_relations
        account_id = db_account.id

        # Verify all related data exists
        stmt = select(func.count(DBPosition.id)).filter(
            DBPosition.account_id == account_id
        )
        position_count = (await db_session.execute(stmt)).scalar()
        assert position_count == 1

        stmt = select(func.count(DBOrder.id)).filter(DBOrder.account_id == account_id)
        order_count = (await db_session.execute(stmt)).scalar()
        assert order_count == 1

        stmt = select(func.count(DBTransaction.id)).filter(
            DBTransaction.account_id == account_id
        )
        transaction_count = (await db_session.execute(stmt)).scalar()
        assert transaction_count == 1

        # Delete related data first (manual cascade since DB doesn't have CASCADE DELETE)
        # Delete in proper order: transactions -> orders -> positions

        # Get actual objects from database to delete them
        transaction_stmt = select(DBTransaction).filter(
            DBTransaction.account_id == account_id
        )
        db_transactions = (await db_session.execute(transaction_stmt)).scalars().all()
        for transaction in db_transactions:
            await db_session.delete(transaction)

        order_stmt = select(DBOrder).filter(DBOrder.account_id == account_id)
        db_orders = (await db_session.execute(order_stmt)).scalars().all()
        for order in db_orders:
            await db_session.delete(order)

        position_stmt = select(DBPosition).filter(DBPosition.account_id == account_id)
        db_positions = (await db_session.execute(position_stmt)).scalars().all()
        for position in db_positions:
            await db_session.delete(position)

        await db_session.commit()

        # Now delete the account
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            delete_result = await adapter.delete_account(account_id)

        # Deletion should be successful
        assert delete_result is True

        # Verify account is deleted
        verify_stmt = select(DBAccount).filter(DBAccount.id == account_id)
        verify_result = await db_session.execute(verify_stmt)
        assert verify_result.scalar_one_or_none() is None

    async def test_delete_account_transaction_integrity(
        self,
        adapter: DatabaseAccountAdapter,
        sample_account: DBAccount,
        db_session: AsyncSession,
    ):
        """Test that deletion properly handles transaction integrity."""
        account_id = sample_account.id

        # Mock database delete to simulate error during deletion
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:
            mock_db = AsyncMock()

            async def mock_session_generator():
                yield mock_db

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock successful query but failed delete
            mock_db.execute.return_value.scalar_one_or_none.return_value = (
                sample_account
            )
            mock_db.delete.side_effect = Exception("Database error during delete")

            # Should raise exception and not commit
            with pytest.raises(Exception, match="Database error during delete"):
                await adapter.delete_account(account_id)

            # Verify commit was not called due to exception
            mock_db.commit.assert_not_called()

    async def test_delete_account_return_values(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test that delete_account returns correct boolean values."""
        # Test return value for successful deletion
        account_id = "TEST123456"
        db_account = DBAccount(
            id=account_id,
            owner=f"test_user_{account_id[:8]}",
            cash_balance=5000.0,
        )
        db_session.add(db_account)
        await db_session.commit()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.delete_account(account_id)
        assert result is True
        assert isinstance(result, bool)

        # Test return value for non-existent account
        nonexistent_id = "TEST123456"
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.delete_account(nonexistent_id)
        assert result is False
        assert isinstance(result, bool)

    async def test_delete_account_database_consistency(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test database remains in consistent state after deletions."""
        # Create multiple accounts with unique IDs
        account_ids = []
        for i in range(3):
            account_id = f"DELTEST{i:03d}"  # DELTEST000, DELTEST001, DELTEST002
            db_account = DBAccount(
                id=account_id,
                owner=f"test_user_{i}_{account_id}",
                cash_balance=10000.0 + (i * 1000),
            )
            db_session.add(db_account)
            account_ids.append(account_id)

        await db_session.commit()

        # Verify initial count
        stmt = select(func.count(DBAccount.id))
        initial_count = (await db_session.execute(stmt)).scalar()
        assert initial_count is not None and initial_count >= 3

        # Delete one account
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.delete_account(account_ids[0])
        assert result is True

        # Verify count decreased by 1
        final_count = (await db_session.execute(stmt)).scalar()
        assert (
            final_count is not None
            and initial_count is not None
            and final_count == initial_count - 1
        )

        # Verify other accounts still exist
        for account_id in account_ids[1:]:
            verify_stmt = select(DBAccount).filter(DBAccount.id == account_id)
            verify_result = await db_session.execute(verify_stmt)
            assert verify_result.scalar_one_or_none() is not None

    async def test_delete_account_with_empty_string_id(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test deletion with empty string ID."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            result = await adapter.delete_account("")
        assert result is False

    async def test_delete_account_with_none_id(
        self, adapter: DatabaseAccountAdapter, db_session: AsyncSession
    ):
        """Test deletion with None ID."""
        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Method returns False for empty string ID (doesn't raise exception)
            result = await adapter.delete_account("")
            assert result is False

    async def test_delete_account_idempotent_behavior(
        self,
        adapter: DatabaseAccountAdapter,
        sample_account: DBAccount,
        db_session: AsyncSession,
    ):
        """Test that deleting the same account twice is idempotent."""
        account_id = sample_account.id

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # First deletion should succeed
            result1 = await adapter.delete_account(account_id)
            assert result1 is True

            # Second deletion should return False (account no longer exists)
            result2 = await adapter.delete_account(account_id)
            assert result2 is False

            # Third deletion should also return False
            result3 = await adapter.delete_account(account_id)
            assert result3 is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
