"""
Database schema validation and migration testing.

Tests database schema integrity, constraint validation, and data migration
scenarios to ensure robust database operations for account creation.
"""

import uuid
from datetime import datetime, date
from typing import Any, Dict

import pytest
import pytest_asyncio
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, DataError

from app.models.database.trading import (
    Account as DBAccount,
    Position as DBPosition, 
    Order as DBOrder,
    Transaction as DBTransaction,
)
from app.schemas.orders import OrderType, OrderStatus, OrderCondition


class TestDatabaseSchemaIntegrity:
    """Test database schema integrity and constraints."""

    @pytest.mark.asyncio
    async def test_account_table_schema(self, async_db_session: AsyncSession):
        """Test account table schema and constraints."""
        
        # Test table exists and has correct structure
        result = await async_db_session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'accounts'
            ORDER BY ordinal_position
        """))
        
        columns = result.fetchall()
        column_info = {col.column_name: col for col in columns}
        
        # Verify required columns exist (based on current database state)
        required_columns = ['id', 'owner', 'cash_balance', 'created_at']
        for col_name in required_columns:
            assert col_name in column_info, f"Missing required column: {col_name}"
        
        # Log available columns for debugging
        print(f"Available columns: {list(column_info.keys())}")
        
        # Verify data types
        assert 'character varying' in column_info['id'].data_type
        assert 'character varying' in column_info['owner'].data_type
        assert column_info['cash_balance'].data_type in ['double precision', 'numeric']
        assert 'timestamp' in column_info['created_at'].data_type
        assert 'timestamp' in column_info['updated_at'].data_type
        
        # Verify nullability constraints
        assert column_info['id'].is_nullable == 'NO'
        assert column_info['owner'].is_nullable == 'NO'
        assert column_info['cash_balance'].is_nullable == 'NO'

    @pytest.mark.asyncio
    async def test_account_constraints(self, async_db_session: AsyncSession):
        """Test account table constraints."""
        
        # Test primary key constraint
        account1 = DBAccount(
            id="test-id-1",
            owner="constraint_test_user",
            cash_balance=50000.0
        )
        async_db_session.add(account1)
        await async_db_session.commit()
        
        # Attempt to insert duplicate primary key
        account2 = DBAccount(
            id="test-id-1",  # Same ID
            owner="different_user",
            cash_balance=25000.0
        )
        async_db_session.add(account2)
        
        with pytest.raises(IntegrityError):
            await async_db_session.commit()
        
        await async_db_session.rollback()
        
        # Test unique constraint on owner
        account3 = DBAccount(
            id="test-id-2",
            owner="constraint_test_user",  # Same owner
            cash_balance=30000.0
        )
        async_db_session.add(account3)
        
        with pytest.raises(IntegrityError):
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, async_db_session: AsyncSession):
        """Test foreign key constraints across related tables."""
        
        # Create account first
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="fk_test_user",
            cash_balance=100000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test position foreign key constraint
        position = DBPosition(
            id=str(uuid.uuid4()),
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        async_db_session.add(position)
        await async_db_session.commit()
        
        # Test invalid foreign key
        invalid_position = DBPosition(
            id=str(uuid.uuid4()),
            account_id="nonexistent-account-id",
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0
        )
        async_db_session.add(invalid_position)
        
        with pytest.raises(IntegrityError):
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_enum_constraints(self, async_db_session: AsyncSession):
        """Test enum field constraints."""
        
        # Create account for order
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="enum_test_user",
            cash_balance=50000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test valid enum values
        valid_order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account.id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            condition=OrderCondition.MARKET
        )
        async_db_session.add(valid_order)
        await async_db_session.commit()
        
        # Test invalid enum values would be caught by Pydantic before reaching DB
        # But we can test the database constraint directly
        with pytest.raises((IntegrityError, DataError)):
            await async_db_session.execute(text("""
                INSERT INTO orders (id, account_id, symbol, order_type, quantity, status)
                VALUES ('invalid-order', :account_id, 'TEST', 'INVALID_TYPE', 100, 'INVALID_STATUS')
            """), {"account_id": account.id})
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_index_existence(self, async_db_session: AsyncSession):
        """Test that required database indexes exist."""
        
        # Query for indexes on accounts table
        result = await async_db_session.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes 
            WHERE tablename = 'accounts'
        """))
        
        indexes = result.fetchall()
        index_names = [idx.indexname for idx in indexes]
        
        # Should have primary key index
        pk_indexes = [name for name in index_names if 'pkey' in name]
        assert len(pk_indexes) > 0, "Missing primary key index"
        
        # Should have unique index on owner
        owner_indexes = [name for name in index_names if 'owner' in name.lower()]
        assert len(owner_indexes) > 0, "Missing owner index"

    @pytest.mark.asyncio
    async def test_timestamp_behavior(self, async_db_session: AsyncSession):
        """Test automatic timestamp behavior."""
        
        # Record time before creation
        before_creation = datetime.now()
        
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="timestamp_test_user",
            cash_balance=75000.0
        )
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)
        
        # Record time after creation
        after_creation = datetime.now()
        
        # Verify timestamps were set automatically
        assert account.created_at is not None
        assert account.updated_at is not None
        assert before_creation <= account.created_at <= after_creation
        assert before_creation <= account.updated_at <= after_creation
        
        # Test update timestamp behavior
        original_created_at = account.created_at
        original_updated_at = account.updated_at
        
        # Update the account
        account.cash_balance = 80000.0
        await async_db_session.commit()
        await async_db_session.refresh(account)
        
        # Verify created_at didn't change but updated_at did
        assert account.created_at == original_created_at
        assert account.updated_at > original_updated_at


class TestDataMigrationScenarios:
    """Test data migration and schema evolution scenarios."""

    @pytest.mark.asyncio
    async def test_account_data_migration_compatibility(
        self, 
        async_db_session: AsyncSession
    ):
        """Test compatibility with potential data migration scenarios."""
        
        # Simulate old data format (missing optional fields)
        await async_db_session.execute(text("""
            INSERT INTO accounts (id, owner, cash_balance)
            VALUES (:id, :owner, :cash_balance)
        """), {
            "id": str(uuid.uuid4()),
            "owner": "migration_test_user",
            "cash_balance": 60000.0
        })
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
    async def test_schema_evolution_resilience(
        self,
        async_db_session: AsyncSession
    ):
        """Test resilience to schema changes."""
        
        # Test that adding new optional columns doesn't break existing code
        # This would typically be tested in a migration script
        
        # For now, test that current schema handles all expected data types
        test_accounts = [
            {
                "id": str(uuid.uuid4()),
                "owner": "schema_test_1",
                "cash_balance": 0.0,  # Minimum balance
            },
            {
                "id": str(uuid.uuid4()),
                "owner": "schema_test_2", 
                "cash_balance": 999999999.99,  # Large balance
            },
            {
                "id": str(uuid.uuid4()),
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
    async def test_data_type_precision(self, async_db_session: AsyncSession):
        """Test data type precision and range handling."""
        
        # Test decimal precision for cash balance
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="precision_test_user",
            cash_balance=12345.6789  # Test decimal precision
        )
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)
        
        # Verify precision is maintained
        assert abs(account.cash_balance - 12345.6789) < 0.0001

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(
        self,
        async_db_session: AsyncSession
    ):
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
                id=str(uuid.uuid4()),
                owner=owner,
                cash_balance=10000.0 + i * 1000
            )
            async_db_session.add(account)
        
        await async_db_session.commit()
        
        # Verify all accounts were created
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE cash_balance >= 10000")
        )
        assert result.scalar() == len(test_owners)

    @pytest.mark.asyncio
    async def test_cascading_delete_behavior(
        self,
        async_db_session: AsyncSession
    ):
        """Test cascading delete behavior for referential integrity."""
        
        # Create account with related data
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="cascade_test_user",
            cash_balance=50000.0
        )
        async_db_session.add(account)
        await async_db_session.flush()
        
        # Create related position
        position = DBPosition(
            id=str(uuid.uuid4()),
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        async_db_session.add(position)
        
        # Create related order
        order = DBOrder(
            id=f"order_{uuid.uuid4().hex[:8]}",
            account_id=account.id,
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=50,
            status=OrderStatus.PENDING
        )
        async_db_session.add(order)
        
        await async_db_session.commit()
        
        # Verify related data exists
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM positions WHERE account_id = :account_id"),
            {"account_id": account.id}
        )
        assert result.scalar() == 1
        
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM orders WHERE account_id = :account_id"),
            {"account_id": account.id}
        )
        assert result.scalar() == 1
        
        # Test what happens when we try to delete account
        # (Should be prevented by foreign key constraints)
        with pytest.raises(IntegrityError):
            await async_db_session.delete(account)
            await async_db_session.commit()


class TestPerformanceOptimization:
    """Test database performance optimization features."""

    @pytest.mark.asyncio
    async def test_query_performance_with_indexes(
        self, 
        async_db_session: AsyncSession,
        performance_monitor
    ):
        """Test query performance with proper indexes."""
        
        # Create multiple test accounts
        test_accounts = []
        for i in range(100):
            account = DBAccount(
                id=str(uuid.uuid4()),
                owner=f"perf_user_{i:03d}",
                cash_balance=10000.0 + i * 100
            )
            test_accounts.append(account)
            async_db_session.add(account)
        
        await async_db_session.commit()
        
        # Test indexed query performance (by owner)
        performance_monitor.start_timing("owner_lookup")
        
        result = await async_db_session.execute(
            text("SELECT * FROM accounts WHERE owner = 'perf_user_050'")
        )
        account = result.fetchone()
        
        owner_lookup_time = performance_monitor.end_timing("owner_lookup")
        
        assert account is not None
        assert owner_lookup_time < 0.1  # Should be fast with index
        
        # Test range query performance
        performance_monitor.start_timing("balance_range")
        
        result = await async_db_session.execute(text("""
            SELECT COUNT(*) FROM accounts 
            WHERE cash_balance BETWEEN 15000 AND 25000
        """))
        count = result.scalar()
        
        range_query_time = performance_monitor.end_timing("balance_range")
        
        assert count > 0
        assert range_query_time < 0.2  # Range queries should be reasonable

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(
        self,
        async_db_session: AsyncSession,
        performance_monitor
    ):
        """Test performance of bulk database operations."""
        
        # Test bulk insert performance
        performance_monitor.start_timing("bulk_insert")
        
        accounts = []
        for i in range(500):
            account = DBAccount(
                id=str(uuid.uuid4()),
                owner=f"bulk_user_{i:04d}",
                cash_balance=5000.0 + i
            )
            accounts.append(account)
        
        async_db_session.add_all(accounts)
        await async_db_session.commit()
        
        bulk_insert_time = performance_monitor.end_timing("bulk_insert")
        
        # Should handle 500 inserts in reasonable time
        assert bulk_insert_time < 2.0
        
        # Test bulk query performance
        performance_monitor.start_timing("bulk_query")
        
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE owner LIKE 'bulk_user_%'")
        )
        count = result.scalar()
        
        bulk_query_time = performance_monitor.end_timing("bulk_query")
        
        assert count == 500
        assert bulk_query_time < 0.5

    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self, performance_monitor):
        """Test connection pool efficiency under concurrent load."""
        
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        import os
        
        database_url = os.getenv("TEST_DATABASE_URL")
        
        # Create engine with specific pool settings
        engine = create_async_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=10,
            pool_recycle=300
        )
        
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
        
        async def perform_db_operation(operation_id: int) -> float:
            """Perform a database operation and measure time."""
            import time
            start = time.time()
            
            async with SessionLocal() as session:
                # Simple operation to test connection efficiency
                result = await session.execute(text("SELECT CAST(:id AS INTEGER)"), {"id": operation_id})
                assert result.scalar() == operation_id
            
            return time.time() - start
        
        try:
            performance_monitor.start_timing("concurrent_operations")
            
            # Run 20 concurrent operations
            timings = await asyncio.gather(*[
                perform_db_operation(i) for i in range(20)
            ])
            
            total_time = performance_monitor.end_timing("concurrent_operations")
            
            # Verify operations completed efficiently
            assert max(timings) < 1.0  # No single operation should take too long
            assert total_time < 3.0    # All operations should complete quickly
            assert len(timings) == 20  # All operations should complete
            
        finally:
            await engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])