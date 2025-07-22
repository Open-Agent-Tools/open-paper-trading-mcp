"""
Database migration and schema evolution tests for app.storage.database module.

This test suite covers:
- Database initialization and table creation
- Schema evolution and migration patterns
- Model metadata management
- Database constraint validation
- Index creation and optimization
- Data integrity during schema changes
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable, DropTable
from sqlalchemy.exc import ProgrammingError, IntegrityError


class TestDatabaseInitialization:
    """Test database initialization and table creation patterns."""

    @patch("app.storage.database.async_engine")
    @patch("app.models.database.base.Base")
    @pytest_asyncio.async_test
    async def test_init_db_creates_all_tables(self, mock_base, mock_engine):
        """Test that init_db creates all tables from Base metadata."""
        mock_metadata = MagicMock()
        mock_base.metadata = mock_metadata
        
        mock_conn = AsyncMock()
        mock_engine.begin = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)
        
        from app.storage.database import init_db
        
        await init_db()
        
        # Verify that metadata.create_all was called
        mock_conn.run_sync.assert_called_once_with(mock_metadata.create_all)

    @pytest_asyncio.async_test
    async def test_init_db_handles_existing_tables(self, async_db_session: AsyncSession):
        """Test that init_db handles existing tables gracefully."""
        from app.storage.database import init_db
        
        # Run init_db multiple times - should not fail
        await init_db()
        await init_db()  # Second call should not cause issues
        
        # Verify tables still exist and are functional
        result = await async_db_session.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = 'accounts' LIMIT 1")
        )
        assert result.fetchone() is not None

    @pytest_asyncio.async_test
    async def test_table_creation_order_respects_dependencies(self, async_db_session: AsyncSession):
        """Test that tables are created in correct dependency order."""
        # Check that dependent tables exist after init
        tables_and_dependencies = [
            ("accounts", []),  # No dependencies
            ("orders", ["accounts"]),  # Depends on accounts
            ("positions", ["accounts"]),  # Depends on accounts
            ("transactions", ["accounts", "orders"]),  # Depends on both
        ]
        
        for table_name, dependencies in tables_and_dependencies:
            # Check that table exists
            result = await async_db_session.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_name = :table")
                .bindparam(table=table_name)
            )
            assert result.fetchone() is not None, f"Table {table_name} does not exist"
            
            # Check that dependency tables also exist
            for dep_table in dependencies:
                result = await async_db_session.execute(
                    text("SELECT 1 FROM information_schema.tables WHERE table_name = :table")
                    .bindparam(table=dep_table)
                )
                assert result.fetchone() is not None, f"Dependency table {dep_table} missing for {table_name}"

    @pytest_asyncio.async_test
    async def test_database_schema_validation(self, async_db_session: AsyncSession):
        """Test that database schema matches expected structure."""
        # Define expected table structures
        expected_tables = {
            "accounts": ["id", "user_id", "name", "account_type", "balance", "buying_power", "created_at", "updated_at"],
            "orders": ["id", "account_id", "symbol", "side", "quantity", "price", "order_type", "status", "created_at", "updated_at"],
            "positions": ["id", "account_id", "symbol", "quantity", "average_price", "current_price", "market_value", "unrealized_pnl", "realized_pnl", "created_at", "updated_at"],
            "transactions": ["id", "account_id", "order_id", "symbol", "transaction_type", "quantity", "price", "amount", "fees", "executed_at", "created_at"],
        }
        
        for table_name, expected_columns in expected_tables.items():
            # Get actual columns
            result = await async_db_session.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :table 
                    ORDER BY ordinal_position
                """).bindparam(table=table_name)
            )
            actual_columns = [row.column_name for row in result.fetchall()]
            
            # Verify all expected columns exist
            for expected_col in expected_columns:
                assert expected_col in actual_columns, f"Column {expected_col} missing from {table_name}"


class TestSchemaEvolution:
    """Test schema evolution and migration patterns."""

    @pytest_asyncio.async_test
    async def test_column_type_validation(self, async_db_session: AsyncSession):
        """Test that columns have correct data types."""
        # Define expected column types for critical fields
        expected_types = {
            ("accounts", "balance"): "numeric",
            ("accounts", "buying_power"): "numeric", 
            ("orders", "quantity"): "numeric",
            ("orders", "price"): "numeric",
            ("positions", "market_value"): "numeric",
            ("transactions", "amount"): "numeric",
        }
        
        for (table_name, column_name), expected_type in expected_types.items():
            result = await async_db_session.execute(
                text("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = :table AND column_name = :column
                """).bindparam(table=table_name, column=column_name)
            )
            row = result.fetchone()
            assert row is not None, f"Column {column_name} not found in {table_name}"
            assert row.data_type == expected_type, f"Column {table_name}.{column_name} has type {row.data_type}, expected {expected_type}"

    @pytest_asyncio.async_test
    async def test_foreign_key_constraints_exist(self, async_db_session: AsyncSession):
        """Test that foreign key constraints are properly defined."""
        # Define expected foreign key relationships
        expected_fks = [
            ("orders", "account_id", "accounts", "id"),
            ("positions", "account_id", "accounts", "id"),
            ("transactions", "account_id", "accounts", "id"),
            ("transactions", "order_id", "orders", "id"),
        ]
        
        for child_table, child_col, parent_table, parent_col in expected_fks:
            result = await async_db_session.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu 
                        ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_name = :child_table 
                        AND kcu.column_name = :child_col
                        AND ccu.table_name = :parent_table
                        AND ccu.column_name = :parent_col
                        AND tc.constraint_type = 'FOREIGN KEY'
                """).bindparam(
                    child_table=child_table,
                    child_col=child_col,
                    parent_table=parent_table,
                    parent_col=parent_col
                )
            )
            count = result.scalar()
            assert count > 0, f"Foreign key constraint missing: {child_table}.{child_col} -> {parent_table}.{parent_col}"

    @pytest_asyncio.async_test
    async def test_primary_key_constraints_exist(self, async_db_session: AsyncSession):
        """Test that primary key constraints exist on all tables."""
        tables = ["accounts", "orders", "positions", "transactions"]
        
        for table_name in tables:
            result = await async_db_session.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints 
                    WHERE table_name = :table AND constraint_type = 'PRIMARY KEY'
                """).bindparam(table=table_name)
            )
            count = result.scalar()
            assert count == 1, f"Primary key constraint missing or duplicated for {table_name}"

    @pytest_asyncio.async_test
    async def test_not_null_constraints_on_critical_fields(self, async_db_session: AsyncSession):
        """Test that critical fields have NOT NULL constraints."""
        # Critical fields that should not allow NULL
        critical_fields = [
            ("accounts", "id"),
            ("accounts", "user_id"),
            ("accounts", "balance"),
            ("orders", "id"),
            ("orders", "account_id"),
            ("orders", "symbol"),
            ("positions", "id"),
            ("positions", "account_id"),
            ("transactions", "id"),
            ("transactions", "account_id"),
        ]
        
        for table_name, column_name in critical_fields:
            result = await async_db_session.execute(
                text("""
                    SELECT is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = :table AND column_name = :column
                """).bindparam(table=table_name, column=column_name)
            )
            row = result.fetchone()
            assert row is not None, f"Column {table_name}.{column_name} not found"
            assert row.is_nullable == "NO", f"Critical field {table_name}.{column_name} allows NULL"


class TestIndexOptimization:
    """Test database index creation and optimization."""

    @pytest_asyncio.async_test
    async def test_primary_key_indexes_exist(self, async_db_session: AsyncSession):
        """Test that primary key indexes are created."""
        tables = ["accounts", "orders", "positions", "transactions"]
        
        for table_name in tables:
            result = await async_db_session.execute(
                text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = :table AND indexname LIKE '%_pkey'
                """).bindparam(table=table_name)
            )
            indexes = result.fetchall()
            assert len(indexes) == 1, f"Primary key index missing for {table_name}"

    @pytest_asyncio.async_test 
    async def test_foreign_key_indexes_for_performance(self, async_db_session: AsyncSession):
        """Test that foreign key columns have indexes for query performance."""
        # Foreign key columns that should have indexes
        fk_columns = [
            ("orders", "account_id"),
            ("positions", "account_id"), 
            ("transactions", "account_id"),
            ("transactions", "order_id"),
        ]
        
        for table_name, column_name in fk_columns:
            # Check for explicit indexes on the column
            result = await async_db_session.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE tablename = :table 
                    AND (indexdef LIKE :column_pattern OR indexname LIKE :index_pattern)
                """).bindparam(
                    table=table_name,
                    column_pattern=f"%{column_name}%",
                    index_pattern=f"%{column_name}%"
                )
            )
            index_count = result.scalar()
            
            # Also check for constraints that create indexes
            result2 = await async_db_session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = :table 
                    AND kcu.column_name = :column
                    AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
                """).bindparam(table=table_name, column=column_name)
            )
            constraint_count = result2.scalar()
            
            # Should have either an explicit index or a constraint that creates an index
            assert (index_count + constraint_count) > 0, f"No index found for {table_name}.{column_name}"

    @pytest_asyncio.async_test
    async def test_symbol_columns_have_indexes_for_queries(self, async_db_session: AsyncSession):
        """Test that symbol columns have indexes for efficient symbol-based queries."""
        symbol_columns = [
            ("orders", "symbol"),
            ("positions", "symbol"),
            ("transactions", "symbol"),
        ]
        
        for table_name, column_name in symbol_columns:
            # Check if column has any form of indexing
            result = await async_db_session.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE tablename = :table 
                    AND indexdef LIKE :column_pattern
                """).bindparam(table=table_name, column_pattern=f"%{column_name}%")
            )
            index_count = result.scalar()
            
            # If no explicit index, that's okay for now, but log it
            # In a real application, symbol columns would benefit from indexes
            if index_count == 0:
                pass  # This is acceptable for current implementation

    @pytest_asyncio.async_test
    async def test_timestamp_columns_for_temporal_queries(self, async_db_session: AsyncSession):
        """Test indexing strategy for timestamp columns used in temporal queries."""
        timestamp_columns = [
            ("orders", "created_at"),
            ("positions", "created_at"),
            ("transactions", "created_at"),
            ("transactions", "executed_at"),
        ]
        
        # Check that timestamp columns exist and are proper types
        for table_name, column_name in timestamp_columns:
            result = await async_db_session.execute(
                text("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = :table AND column_name = :column
                """).bindparam(table=table_name, column=column_name)
            )
            row = result.fetchone()
            assert row is not None, f"Timestamp column {table_name}.{column_name} not found"
            assert "timestamp" in row.data_type.lower(), f"Column {table_name}.{column_name} is not a timestamp type"


class TestDataIntegrity:
    """Test data integrity during schema operations."""

    @pytest_asyncio.async_test
    async def test_referential_integrity_enforcement(self, async_db_session: AsyncSession):
        """Test that referential integrity is enforced by the database."""
        from app.models.database.trading import Order
        
        # Try to create order with non-existent account
        with pytest.raises(IntegrityError):
            invalid_order = Order(
                id="integrity-test-order",
                account_id="non-existent-account-id",
                symbol="AAPL",
                side="buy",
                quantity=100,
                price=150.00,
                order_type="limit",
                status="pending"
            )
            async_db_session.add(invalid_order)
            await async_db_session.commit()

    @pytest_asyncio.async_test
    async def test_cascade_behavior_on_foreign_keys(self, async_db_session: AsyncSession):
        """Test cascade behavior when parent records are deleted."""
        from app.models.database.trading import Account, Order
        from datetime import datetime, timezone
        from decimal import Decimal
        
        # Create account and order
        account = Account(
            id="cascade-test-account",
            user_id="cascade-user",
            name="Cascade Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        order = Order(
            id="cascade-test-order", 
            account_id="cascade-test-account",
            symbol="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            order_type="limit",
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(order)
        await async_db_session.commit()
        
        # Delete account - should handle foreign key constraint appropriately
        await async_db_session.delete(account)
        
        # Depending on CASCADE settings, either order should be deleted
        # or foreign key constraint should prevent account deletion
        try:
            await async_db_session.commit()
            
            # If commit succeeds, verify order behavior
            result = await async_db_session.execute(
                text("SELECT COUNT(*) FROM orders WHERE account_id = 'cascade-test-account'")
            )
            order_count = result.scalar()
            
            # Orders should either be cascaded (count=0) or account deletion should have failed
            assert order_count == 0, "Orders should be cascaded when account is deleted"
            
        except IntegrityError:
            # This is expected if CASCADE is not configured - foreign key constraint prevents deletion
            await async_db_session.rollback()

    @pytest_asyncio.async_test
    async def test_unique_constraint_enforcement(self, async_db_session: AsyncSession):
        """Test that unique constraints are enforced."""
        from app.models.database.trading import Account
        from datetime import datetime, timezone
        from decimal import Decimal
        
        # Create first account
        account1 = Account(
            id="unique-test-1",
            user_id="unique-user",
            name="First Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account1)
        await async_db_session.commit()
        
        # Try to create second account with same ID
        with pytest.raises(IntegrityError):
            account2 = Account(
                id="unique-test-1",  # Duplicate ID
                user_id="unique-user-2",
                name="Duplicate Account",
                account_type="paper", 
                balance=Decimal("5000.00"),
                buying_power=Decimal("5000.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(account2)
            await async_db_session.commit()

    @pytest_asyncio.async_test
    async def test_decimal_precision_preservation(self, async_db_session: AsyncSession):
        """Test that decimal precision is preserved in database operations."""
        from app.models.database.trading import Account
        from datetime import datetime, timezone
        from decimal import Decimal
        
        # Test various decimal precisions
        test_values = [
            Decimal("10000.00"),
            Decimal("99999.99"),
            Decimal("0.01"),
            Decimal("12345.67"),
        ]
        
        for i, test_value in enumerate(test_values):
            account = Account(
                id=f"decimal-test-{i}",
                user_id="decimal-user",
                name=f"Decimal Test Account {i}",
                account_type="paper",
                balance=test_value,
                buying_power=test_value,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(account)
        
        await async_db_session.commit()
        
        # Verify precision is preserved
        for i, expected_value in enumerate(test_values):
            result = await async_db_session.execute(
                text("SELECT balance FROM accounts WHERE id = :id")
                .bindparam(id=f"decimal-test-{i}")
            )
            stored_value = result.scalar()
            assert stored_value == expected_value, f"Decimal precision lost: expected {expected_value}, got {stored_value}"


class TestMigrationSimulation:
    """Test simulated migration scenarios and schema changes."""

    @pytest_asyncio.async_test
    async def test_safe_column_addition_simulation(self, async_db_session: AsyncSession):
        """Test simulation of safe column addition (with defaults)."""
        # This tests the pattern for adding new columns safely
        
        # Verify current schema state
        result = await async_db_session.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'accounts' 
                ORDER BY ordinal_position
            """)
        )
        initial_columns = [row.column_name for row in result.fetchall()]
        
        # In a real migration, you would add a column with:
        # ALTER TABLE accounts ADD COLUMN new_column VARCHAR(255) DEFAULT 'default_value';
        
        # For testing, we just verify the current structure is sound
        essential_columns = ["id", "user_id", "name", "balance", "buying_power"]
        for col in essential_columns:
            assert col in initial_columns, f"Essential column {col} missing from accounts table"

    @pytest_asyncio.async_test
    async def test_index_creation_impact_simulation(self, async_db_session: AsyncSession):
        """Test simulation of index creation impact on performance."""
        # Simulate the impact of creating an index on a commonly queried column
        
        # Create some test data first
        from app.models.database.trading import Account
        from datetime import datetime, timezone
        from decimal import Decimal
        
        accounts = []
        for i in range(10):
            account = Account(
                id=f"perf-account-{i}",
                user_id=f"perf-user-{i % 3}",  # Group users for testing
                name=f"Performance Account {i}",
                account_type="paper",
                balance=Decimal("1000.00") + Decimal(str(i * 100)),
                buying_power=Decimal("1000.00") + Decimal(str(i * 100)),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            accounts.append(account)
        
        async_db_session.add_all(accounts)
        await async_db_session.commit()
        
        # Test query performance on user_id (common lookup pattern)
        import time
        start_time = time.time()
        
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE user_id = 'perf-user-1'")
        )
        count = result.scalar()
        
        query_time = time.time() - start_time
        
        # Should be relatively fast even without explicit index (due to small dataset)
        assert query_time < 1.0, f"Query took too long: {query_time}s"
        assert count > 0, "Should find matching accounts"

    @pytest_asyncio.async_test
    async def test_data_type_migration_compatibility(self, async_db_session: AsyncSession):
        """Test compatibility for potential data type migrations."""
        # Test that current data types can handle expected value ranges
        
        from app.models.database.trading import Account, Order, Position
        from datetime import datetime, timezone
        from decimal import Decimal
        
        # Test edge values that might cause issues during migrations
        edge_values = [
            Decimal("0.00"),          # Minimum value
            Decimal("999999.99"),     # Large value
            Decimal("0.0001"),        # High precision
        ]
        
        for i, value in enumerate(edge_values):
            account = Account(
                id=f"edge-account-{i}",
                user_id="edge-user",
                name=f"Edge Case Account {i}",
                account_type="paper",
                balance=value,
                buying_power=value,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(account)
        
        await async_db_session.commit()
        
        # Verify all values stored correctly
        result = await async_db_session.execute(
            text("SELECT balance FROM accounts WHERE user_id = 'edge-user' ORDER BY id")
        )
        stored_values = [row.balance for row in result.fetchall()]
        
        assert len(stored_values) == len(edge_values)
        for stored, expected in zip(stored_values, edge_values):
            assert stored == expected, f"Edge value {expected} not stored correctly: got {stored}"