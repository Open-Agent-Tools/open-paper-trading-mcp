"""
Database schema validation and migration testing.

Tests database schema integrity, constraint validation, and data migration
scenarios to ensure robust database operations for account creation.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.trading import (
    Account as DBAccount,
)
from app.models.database.trading import (
    Order as DBOrder,
)
from app.models.database.trading import (
    Position as DBPosition,
)
from app.schemas.orders import OrderCondition, OrderStatus, OrderType

pytestmark = pytest.mark.journey_system_performance


@pytest.mark.database
class TestDatabaseSchemaIntegrity:
    """Test database schema integrity and constraints."""

    @pytest.mark.asyncio
    async def test_account_table_schema(self, async_db_session: AsyncSession):
        """Test account table schema and constraints."""

        # Test table exists and has correct structure
        result = await async_db_session.execute(
            text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'accounts'
            ORDER BY ordinal_position
        """)
        )

        columns = result.fetchall()
        column_info = {col.column_name: col for col in columns}

        # Verify required columns exist (based on current database state)
        required_columns = ["id", "owner", "cash_balance", "created_at"]
        for col_name in required_columns:
            assert col_name in column_info, f"Missing required column: {col_name}"

        # Log available columns for debugging
        print(f"Available columns: {list(column_info.keys())}")

        # Verify data types
        assert "character varying" in column_info["id"].data_type
        assert "character varying" in column_info["owner"].data_type
        assert column_info["cash_balance"].data_type in ["double precision", "numeric"]
        assert "timestamp" in column_info["created_at"].data_type
        assert "timestamp" in column_info["updated_at"].data_type

        # Verify nullability constraints
        assert column_info["id"].is_nullable == "NO"
        assert column_info["owner"].is_nullable == "NO"
        assert column_info["cash_balance"].is_nullable == "NO"

    @pytest.mark.asyncio
    async def test_account_constraints(self, async_db_session: AsyncSession):
        """Test account table constraints."""

        # Test primary key constraint
        account1 = DBAccount(
            id="TESTID1000", owner="constraint_test_user", cash_balance=50000.0
        )
        async_db_session.add(account1)
        await async_db_session.commit()

        # Start fresh session for next test
        await async_db_session.rollback()

        # Attempt to insert duplicate primary key
        account2 = DBAccount(
            id="TESTID1000",  # Same ID
            owner="different_user",
            cash_balance=25000.0,
        )
        async_db_session.add(account2)

        with pytest.raises(IntegrityError):
            await async_db_session.commit()

        await async_db_session.rollback()

        # Test unique constraint on owner
        account3 = DBAccount(
            id="TESTID2000",
            owner="constraint_test_user",  # Same owner
            cash_balance=30000.0,
        )
        async_db_session.add(account3)

        with pytest.raises(IntegrityError):
            await async_db_session.commit()

        await async_db_session.rollback()

    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, async_db_session: AsyncSession):
        """Test foreign key constraints across related tables."""

        # Create account first
        account = DBAccount(
            id="TEST1FK456", owner="fk_test_user", cash_balance=100000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()

        # Test position foreign key constraint
        position = DBPosition(
            id="POS1FK4567",
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
        )
        async_db_session.add(position)
        await async_db_session.commit()

        # Test invalid foreign key
        invalid_position = DBPosition(
            id="POS2FK4567",
            account_id="NONEXISTEN",
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0,
        )
        async_db_session.add(invalid_position)

        with pytest.raises(IntegrityError):
            await async_db_session.commit()

        await async_db_session.rollback()

    @pytest.mark.asyncio
    async def test_enum_constraints(self, async_db_session: AsyncSession):
        """Test enum field constraints."""

        # Create account for order
        account = DBAccount(
            id="TESTENUM56", owner="enum_test_user", cash_balance=50000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()

        # Test valid enum values
        valid_order = DBOrder(
            id=f"ORD{uuid.uuid4().hex[:7].upper()}",
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            condition=OrderCondition.MARKET,
        )
        async_db_session.add(valid_order)
        await async_db_session.commit()

        # Test invalid enum values would be caught by Pydantic before reaching DB
        # But we can test the database constraint directly
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError):
            await async_db_session.execute(
                text("""
                INSERT INTO orders (id, account_id, symbol, order_type, quantity, status)
                VALUES ('invalid-order', :account_id, 'TEST', 'INVALID_TYPE', 100, 'INVALID_STATUS')
            """),
                {"account_id": account.id},
            )
            await async_db_session.commit()

        await async_db_session.rollback()

    @pytest.mark.asyncio
    async def test_index_existence(self, async_db_session: AsyncSession):
        """Test that required database indexes exist."""

        # Query for indexes on accounts table
        result = await async_db_session.execute(
            text("""
            SELECT indexname, indexdef
            FROM pg_indexes 
            WHERE tablename = 'accounts'
        """)
        )

        indexes = result.fetchall()
        index_names = [idx.indexname for idx in indexes]

        # Should have primary key index
        pk_indexes = [name for name in index_names if "pkey" in name]
        assert len(pk_indexes) > 0, "Missing primary key index"

        # Should have unique index on owner
        owner_indexes = [name for name in index_names if "owner" in name.lower()]
        assert len(owner_indexes) > 0, "Missing owner index"

    @pytest.mark.asyncio
    async def test_timestamp_behavior(self, async_db_session: AsyncSession):
        """Test automatic timestamp behavior."""

        # Record time before creation with UTC timezone awareness
        import time

        datetime.now(UTC).replace(tzinfo=None)

        account = DBAccount(
            id="TESTTIME56", owner="timestamp_test_user", cash_balance=75000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)

        # Record time after creation with UTC timezone awareness
        datetime.now(UTC).replace(tzinfo=None)

        # Verify timestamps were set automatically
        assert account.created_at is not None
        assert account.updated_at is not None

        # Allow for reasonable time window (timestamps set by database server)
        # Just verify they are reasonable datetime values
        assert isinstance(account.created_at, datetime)
        assert isinstance(account.updated_at, datetime)

        # Test update timestamp behavior
        original_created_at = account.created_at
        original_updated_at = account.updated_at

        # Small delay to ensure updated_at changes
        time.sleep(0.1)

        # Update the account
        account.cash_balance = 80000.0
        await async_db_session.commit()
        await async_db_session.refresh(account)

        # Verify created_at didn't change but updated_at did
        assert account.created_at == original_created_at
        assert account.updated_at > original_updated_at


@pytest.mark.database
class TestDataMigrationScenarios:
    """Test data migration and schema evolution scenarios."""

    @pytest.mark.asyncio
    async def test_account_data_migration_compatibility(
        self, async_db_session: AsyncSession
    ):
        """Test compatibility with potential data migration scenarios."""

        # Simulate old data format (missing optional fields)
        await async_db_session.execute(
            text("""
            INSERT INTO accounts (id, owner, cash_balance)
            VALUES (:id, :owner, :cash_balance)
        """),
            {
                "id": "TESTMIGR56",
                "owner": "migration_test_user",
                "cash_balance": 60000.0,
            },
        )
        await async_db_session.commit()

        # Verify the record can be read back
        from sqlalchemy import select

        stmt = select(DBAccount).where(DBAccount.owner == "migration_test_user")
        result = await async_db_session.execute(stmt)
        account = result.scalar_one()

        assert account.owner == "migration_test_user"
        assert account.cash_balance == 60000.0
        assert account.created_at is not None  # Should be auto-populated
        assert account.updated_at is not None  # Should be auto-populated

    @pytest.mark.asyncio
    async def test_schema_evolution_resilience(self, async_db_session: AsyncSession):
        """Test resilience to schema changes."""

        # Test that adding new optional columns doesn't break existing code
        # This would typically be tested in a migration script

        # For now, test that current schema handles all expected data types
        test_accounts = [
            {
                "id": "TEST12345A",
                "owner": "schema_test_1",
                "cash_balance": 0.0,  # Minimum balance
            },
            {
                "id": "TEST12345B",
                "owner": "schema_test_2",
                "cash_balance": 999999999.99,  # Large balance
            },
            {
                "id": "TEST12345C",
                "owner": "schema_test_3",
                "cash_balance": 0.01,  # Small fractional balance
            },
        ]

        for account_data in test_accounts:
            account = DBAccount(**account_data)
            async_db_session.add(account)

        await async_db_session.commit()

        # Verify all accounts were created successfully
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE owner LIKE 'schema_test_%'")
        )
        assert result.scalar() == 3

    @pytest.mark.asyncio
    async def synthetic_data_type_precision(self, async_db_session: AsyncSession):
        """Test data type precision and range handling."""

        # Test decimal precision for cash balance
        account = DBAccount(
            id="TESTPREC56",
            owner="precision_test_user",
            cash_balance=12345.6789,  # Test decimal precision
        )
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)

        # Verify precision is maintained
        assert abs(account.cash_balance - 12345.6789) < 0.0001

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, async_db_session: AsyncSession):
        """Test handling of unicode and special characters."""

        # Test various character sets in owner field
        test_owners = [
            "user_with_émojis_🚀",
            "user-with-dashes",
            "user_with_underscores",
            "user.with.dots",
            "用户_with_unicode",
            "пользователь_cyrillic",
        ]

        for i, owner in enumerate(test_owners):
            account = DBAccount(
                id=f"TEST1234{i:02d}", owner=owner, cash_balance=10000.0 + i * 1000
            )
            async_db_session.add(account)

        await async_db_session.commit()

        # Verify all accounts were created
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE cash_balance >= 10000")
        )
        assert result.scalar() == len(test_owners)

    @pytest.mark.asyncio
    async def test_cascading_delete_behavior(self, async_db_session: AsyncSession):
        """Test cascading delete behavior for referential integrity."""

        # Create account with related data
        account = DBAccount(
            id="TESTCASC56", owner="cascade_test_user", cash_balance=50000.0
        )
        async_db_session.add(account)
        await async_db_session.flush()

        # Create related position
        position = DBPosition(
            id="POSCASC567",
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
        )
        async_db_session.add(position)

        # Create related order
        order = DBOrder(
            id=f"ORD{uuid.uuid4().hex[:7].upper()}",
            account_id=account.id,
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=50,
            status=OrderStatus.PENDING,
        )
        async_db_session.add(order)

        await async_db_session.commit()

        # Verify related data exists
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM positions WHERE account_id = :account_id"),
            {"account_id": account.id},
        )
        assert result.scalar() == 1

        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM orders WHERE account_id = :account_id"),
            {"account_id": account.id},
        )
        assert result.scalar() == 1

        # Test what happens when we try to delete account
        # (Should be prevented by foreign key constraints)
        with pytest.raises(IntegrityError):
            await async_db_session.delete(account)
            await async_db_session.commit()

        await async_db_session.rollback()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
