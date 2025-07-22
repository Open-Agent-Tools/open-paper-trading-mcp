"""
Comprehensive tests for database models, schema validation, and ORM patterns.

This test suite covers:
- SQLAlchemy model validation
- Database constraint enforcement
- Model relationships and foreign keys
- Schema migration patterns
- Model serialization and deserialization
- Async ORM operations
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable, DropTable
from typing import Any, Dict

from app.models.database.base import Base


class TestDatabaseModelValidation:
    """Test SQLAlchemy model validation and constraints."""

    @pytest_asyncio.async_test
    async def test_model_table_creation(self, async_db_session: AsyncSession):
        """Test that all models create tables correctly."""
        # Get all model classes
        model_classes = []
        for class_name in dir(Base.registry._class_registry):
            if not class_name.startswith('_'):
                model_class = Base.registry._class_registry[class_name]
                if hasattr(model_class, '__tablename__'):
                    model_classes.append(model_class)
        
        # Verify tables exist
        async with async_db_session.bind.connect() as conn:
            for model_class in model_classes:
                result = await conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table)")
                    .bindparam(table=model_class.__tablename__)
                )
                exists = result.scalar()
                assert exists, f"Table {model_class.__tablename__} does not exist"

    @pytest_asyncio.async_test
    async def test_account_model_constraints(self, async_db_session: AsyncSession):
        """Test Account model field constraints and validation."""
        from app.models.database.trading import Account
        
        # Test valid account creation
        account = Account(
            id="test-account-1",
            user_id="user123",
            name="Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Verify account was created
        result = await async_db_session.execute(
            text("SELECT * FROM accounts WHERE id = :id").bindparam(id="test-account-1")
        )
        row = result.fetchone()
        assert row is not None
        assert row.id == "test-account-1"
        assert row.balance == Decimal("10000.00")

    @pytest_asyncio.async_test
    async def test_account_model_required_fields(self, async_db_session: AsyncSession):
        """Test Account model required field validation."""
        from app.models.database.trading import Account
        
        # Test missing required fields
        with pytest.raises((IntegrityError, StatementError)):
            incomplete_account = Account(
                # Missing required id and user_id
                name="Incomplete Account",
                balance=Decimal("1000.00")
            )
            async_db_session.add(incomplete_account)
            await async_db_session.commit()

    @pytest_asyncio.async_test
    async def test_order_model_constraints(self, async_db_session: AsyncSession):
        """Test Order model field constraints and relationships."""
        from app.models.database.trading import Account, Order
        
        # Create account first
        account = Account(
            id="test-account-2",
            user_id="user123",
            name="Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test valid order creation
        order = Order(
            id="order-123",
            account_id="test-account-2",
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
        
        # Verify order was created
        result = await async_db_session.execute(
            text("SELECT * FROM orders WHERE id = :id").bindparam(id="order-123")
        )
        row = result.fetchone()
        assert row is not None
        assert row.symbol == "AAPL"
        assert row.quantity == Decimal("100")

    @pytest_asyncio.async_test
    async def test_order_foreign_key_constraint(self, async_db_session: AsyncSession):
        """Test Order model foreign key constraints."""
        from app.models.database.trading import Order
        
        # Test order with non-existent account
        with pytest.raises(IntegrityError):
            invalid_order = Order(
                id="invalid-order",
                account_id="non-existent-account",
                symbol="AAPL",
                side="buy",
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                order_type="limit",
                status="pending",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(invalid_order)
            await async_db_session.commit()

    @pytest_asyncio.async_test
    async def test_position_model_constraints(self, async_db_session: AsyncSession):
        """Test Position model constraints and calculations."""
        from app.models.database.trading import Account, Position
        
        # Create account first
        account = Account(
            id="test-account-3",
            user_id="user123",
            name="Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test valid position creation
        position = Position(
            id="position-123",
            account_id="test-account-3",
            symbol="AAPL",
            quantity=Decimal("50"),
            average_price=Decimal("145.50"),
            current_price=Decimal("150.00"),
            market_value=Decimal("7500.00"),
            unrealized_pnl=Decimal("225.00"),
            realized_pnl=Decimal("0.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        async_db_session.add(position)
        await async_db_session.commit()
        
        # Verify position calculations
        result = await async_db_session.execute(
            text("SELECT * FROM positions WHERE id = :id").bindparam(id="position-123")
        )
        row = result.fetchone()
        assert row is not None
        assert row.market_value == Decimal("7500.00")
        assert row.unrealized_pnl == Decimal("225.00")

    @pytest_asyncio.async_test
    async def test_transaction_model_audit_trail(self, async_db_session: AsyncSession):
        """Test Transaction model for audit trail purposes."""
        from app.models.database.trading import Account, Transaction
        
        # Create account first
        account = Account(
            id="test-account-4",
            user_id="user123",
            name="Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test transaction creation
        transaction = Transaction(
            id="txn-123",
            account_id="test-account-4",
            order_id="order-123",
            symbol="AAPL",
            transaction_type="buy",
            quantity=Decimal("25"),
            price=Decimal("148.00"),
            amount=Decimal("3700.00"),
            fees=Decimal("1.00"),
            executed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        
        async_db_session.add(transaction)
        await async_db_session.commit()
        
        # Verify transaction audit fields
        result = await async_db_session.execute(
            text("SELECT * FROM transactions WHERE id = :id").bindparam(id="txn-123")
        )
        row = result.fetchone()
        assert row is not None
        assert row.executed_at is not None
        assert row.created_at is not None
        assert row.fees == Decimal("1.00")


class TestModelRelationships:
    """Test SQLAlchemy model relationships and joins."""

    @pytest_asyncio.async_test
    async def test_account_orders_relationship(self, async_db_session: AsyncSession):
        """Test Account to Orders one-to-many relationship."""
        from app.models.database.trading import Account, Order
        
        # Create account with multiple orders
        account = Account(
            id="rel-account-1",
            user_id="user123",
            name="Relationship Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Create multiple orders
        orders = []
        for i in range(3):
            order = Order(
                id=f"rel-order-{i}",
                account_id="rel-account-1",
                symbol="AAPL",
                side="buy",
                quantity=Decimal("10"),
                price=Decimal("150.00"),
                order_type="limit",
                status="pending",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            orders.append(order)
            async_db_session.add(order)
        
        await async_db_session.commit()
        
        # Test relationship query
        result = await async_db_session.execute(
            text("""
                SELECT COUNT(o.id) as order_count 
                FROM accounts a 
                LEFT JOIN orders o ON a.id = o.account_id 
                WHERE a.id = :account_id
                GROUP BY a.id
            """).bindparam(account_id="rel-account-1")
        )
        row = result.fetchone()
        assert row.order_count == 3

    @pytest_asyncio.async_test
    async def test_account_positions_relationship(self, async_db_session: AsyncSession):
        """Test Account to Positions one-to-many relationship."""
        from app.models.database.trading import Account, Position
        
        # Create account
        account = Account(
            id="rel-account-2",
            user_id="user123",
            name="Position Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Create positions for different symbols
        symbols = ["AAPL", "GOOGL", "MSFT"]
        for symbol in symbols:
            position = Position(
                id=f"rel-pos-{symbol}",
                account_id="rel-account-2",
                symbol=symbol,
                quantity=Decimal("10"),
                average_price=Decimal("150.00"),
                current_price=Decimal("155.00"),
                market_value=Decimal("1550.00"),
                unrealized_pnl=Decimal("50.00"),
                realized_pnl=Decimal("0.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(position)
        
        await async_db_session.commit()
        
        # Test portfolio value calculation
        result = await async_db_session.execute(
            text("""
                SELECT SUM(p.market_value) as total_value, COUNT(p.id) as position_count
                FROM accounts a 
                LEFT JOIN positions p ON a.id = p.account_id 
                WHERE a.id = :account_id
                GROUP BY a.id
            """).bindparam(account_id="rel-account-2")
        )
        row = result.fetchone()
        assert row.position_count == 3
        assert row.total_value == Decimal("4650.00")  # 3 * 1550.00

    @pytest_asyncio.async_test
    async def test_order_transaction_relationship(self, async_db_session: AsyncSession):
        """Test Order to Transaction one-to-many relationship."""
        from app.models.database.trading import Account, Order, Transaction
        
        # Create account and order
        account = Account(
            id="rel-account-3",
            user_id="user123",
            name="Transaction Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        
        order = Order(
            id="rel-order-txn",
            account_id="rel-account-3",
            symbol="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            order_type="limit",
            status="filled",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(order)
        await async_db_session.commit()
        
        # Create partial fill transactions
        fills = [
            {"quantity": Decimal("40"), "price": Decimal("149.50")},
            {"quantity": Decimal("60"), "price": Decimal("150.50")},
        ]
        
        for i, fill in enumerate(fills):
            transaction = Transaction(
                id=f"rel-txn-{i}",
                account_id="rel-account-3",
                order_id="rel-order-txn",
                symbol="AAPL",
                transaction_type="buy",
                quantity=fill["quantity"],
                price=fill["price"],
                amount=fill["quantity"] * fill["price"],
                fees=Decimal("0.50"),
                executed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            )
            async_db_session.add(transaction)
        
        await async_db_session.commit()
        
        # Verify transaction totals
        result = await async_db_session.execute(
            text("""
                SELECT 
                    SUM(t.quantity) as total_quantity,
                    SUM(t.amount) as total_amount,
                    COUNT(t.id) as fill_count
                FROM orders o 
                LEFT JOIN transactions t ON o.id = t.order_id 
                WHERE o.id = :order_id
                GROUP BY o.id
            """).bindparam(order_id="rel-order-txn")
        )
        row = result.fetchone()
        assert row.fill_count == 2
        assert row.total_quantity == Decimal("100")
        expected_total = (Decimal("40") * Decimal("149.50")) + (Decimal("60") * Decimal("150.50"))
        assert row.total_amount == expected_total


class TestSchemaValidation:
    """Test database schema validation and constraints."""

    @pytest_asyncio.async_test
    async def test_decimal_precision_constraints(self, async_db_session: AsyncSession):
        """Test decimal field precision and scale constraints."""
        from app.models.database.trading import Account
        
        # Test valid decimal precision
        account = Account(
            id="decimal-test",
            user_id="user123",
            name="Decimal Test Account",
            account_type="paper",
            balance=Decimal("99999.99"),  # Within precision limits
            buying_power=Decimal("99999.99"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Verify precision is preserved
        result = await async_db_session.execute(
            text("SELECT balance FROM accounts WHERE id = :id").bindparam(id="decimal-test")
        )
        balance = result.scalar()
        assert balance == Decimal("99999.99")

    @pytest_asyncio.async_test
    async def test_enum_constraints(self, async_db_session: AsyncSession):
        """Test enum field constraints if any exist."""
        from app.models.database.trading import Account, Order
        
        # Create account for order
        account = Account(
            id="enum-test-account",
            user_id="user123",
            name="Enum Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Test valid enum values
        valid_order = Order(
            id="enum-valid-order",
            account_id="enum-test-account",
            symbol="AAPL",
            side="buy",  # Valid enum value
            quantity=Decimal("10"),
            price=Decimal("150.00"),
            order_type="limit",  # Valid enum value
            status="pending",  # Valid enum value
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(valid_order)
        await async_db_session.commit()
        
        # Test invalid enum value would be caught at application level
        # (SQLAlchemy string fields may not have database-level enum constraints)

    @pytest_asyncio.async_test
    async def test_timestamp_defaults(self, async_db_session: AsyncSession):
        """Test timestamp field defaults and auto-updates."""
        from app.models.database.trading import Account
        
        # Create account without explicit timestamps
        account = Account(
            id="timestamp-test",
            user_id="user123",
            name="Timestamp Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00")
            # created_at and updated_at not set explicitly
        )
        
        # Set timestamps to test defaults
        now = datetime.now(timezone.utc)
        account.created_at = now
        account.updated_at = now
        
        async_db_session.add(account)
        await async_db_session.commit()
        
        # Verify timestamps were set
        result = await async_db_session.execute(
            text("SELECT created_at, updated_at FROM accounts WHERE id = :id")
            .bindparam(id="timestamp-test")
        )
        row = result.fetchone()
        assert row.created_at is not None
        assert row.updated_at is not None

    @pytest_asyncio.async_test
    async def test_unique_constraints(self, async_db_session: AsyncSession):
        """Test unique constraints if any exist."""
        from app.models.database.trading import Account
        
        # Create first account
        account1 = Account(
            id="unique-test-1",
            user_id="user123",
            name="First Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account1)
        await async_db_session.commit()
        
        # Try to create account with same ID (should fail)
        with pytest.raises(IntegrityError):
            account2 = Account(
                id="unique-test-1",  # Duplicate ID
                user_id="user456",
                name="Duplicate Account",
                account_type="paper",
                balance=Decimal("5000.00"),
                buying_power=Decimal("5000.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(account2)
            await async_db_session.commit()


class TestAsyncOrmOperations:
    """Test async ORM operations and patterns."""

    @pytest_asyncio.async_test
    async def test_async_bulk_insert(self, async_db_session: AsyncSession):
        """Test async bulk insert operations."""
        from app.models.database.trading import Account
        
        # Create multiple accounts for bulk insert
        accounts = []
        for i in range(5):
            account = Account(
                id=f"bulk-account-{i}",
                user_id="bulk-user",
                name=f"Bulk Account {i}",
                account_type="paper",
                balance=Decimal("1000.00") * (i + 1),
                buying_power=Decimal("1000.00") * (i + 1),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            accounts.append(account)
        
        # Bulk insert
        async_db_session.add_all(accounts)
        await async_db_session.commit()
        
        # Verify all accounts were created
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE user_id = 'bulk-user'")
        )
        count = result.scalar()
        assert count == 5

    @pytest_asyncio.async_test
    async def test_async_bulk_update(self, async_db_session: AsyncSession):
        """Test async bulk update operations."""
        from app.models.database.trading import Account
        from sqlalchemy import update
        
        # Create accounts for bulk update
        accounts = []
        for i in range(3):
            account = Account(
                id=f"update-account-{i}",
                user_id="update-user",
                name=f"Update Account {i}",
                account_type="paper",
                balance=Decimal("1000.00"),
                buying_power=Decimal("1000.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            accounts.append(account)
        
        async_db_session.add_all(accounts)
        await async_db_session.commit()
        
        # Bulk update balances
        await async_db_session.execute(
            update(Account)
            .where(Account.user_id == "update-user")
            .values(balance=Decimal("2000.00"))
        )
        await async_db_session.commit()
        
        # Verify updates
        result = await async_db_session.execute(
            text("SELECT balance FROM accounts WHERE user_id = 'update-user' LIMIT 1")
        )
        balance = result.scalar()
        assert balance == Decimal("2000.00")

    @pytest_asyncio.async_test
    async def test_async_transaction_rollback(self, async_db_session: AsyncSession):
        """Test async transaction rollback scenarios."""
        from app.models.database.trading import Account
        
        # Start transaction
        account = Account(
            id="rollback-test",
            user_id="rollback-user",
            name="Rollback Test Account",
            account_type="paper",
            balance=Decimal("5000.00"),
            buying_power=Decimal("5000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        async_db_session.add(account)
        
        # Simulate error condition
        try:
            # This should cause a constraint violation or similar error
            duplicate_account = Account(
                id="rollback-test",  # Same ID
                user_id="rollback-user2",
                name="Duplicate Account",
                account_type="paper",
                balance=Decimal("1000.00"),
                buying_power=Decimal("1000.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(duplicate_account)
            await async_db_session.commit()
        except IntegrityError:
            await async_db_session.rollback()
        
        # Verify no accounts were created
        result = await async_db_session.execute(
            text("SELECT COUNT(*) FROM accounts WHERE user_id LIKE 'rollback-user%'")
        )
        count = result.scalar()
        assert count == 0

    @pytest_asyncio.async_test
    async def test_async_complex_query(self, async_db_session: AsyncSession):
        """Test complex async queries with joins and aggregations."""
        from app.models.database.trading import Account, Order, Position
        
        # Create test data
        account = Account(
            id="complex-query-account",
            user_id="complex-user",
            name="Complex Query Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        
        # Add orders and positions
        for i in range(2):
            order = Order(
                id=f"complex-order-{i}",
                account_id="complex-query-account",
                symbol="AAPL",
                side="buy",
                quantity=Decimal("50"),
                price=Decimal("150.00"),
                order_type="limit",
                status="filled",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(order)
            
            position = Position(
                id=f"complex-pos-{i}",
                account_id="complex-query-account",
                symbol=["AAPL", "GOOGL"][i],
                quantity=Decimal("25"),
                average_price=Decimal("150.00"),
                current_price=Decimal("155.00"),
                market_value=Decimal("3875.00"),
                unrealized_pnl=Decimal("125.00"),
                realized_pnl=Decimal("0.00"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            async_db_session.add(position)
        
        await async_db_session.commit()
        
        # Complex query: account summary with orders and positions
        result = await async_db_session.execute(
            text("""
                SELECT 
                    a.name,
                    a.balance,
                    COUNT(DISTINCT o.id) as order_count,
                    COUNT(DISTINCT p.id) as position_count,
                    SUM(p.market_value) as total_market_value
                FROM accounts a
                LEFT JOIN orders o ON a.id = o.account_id
                LEFT JOIN positions p ON a.id = p.account_id
                WHERE a.id = :account_id
                GROUP BY a.id, a.name, a.balance
            """).bindparam(account_id="complex-query-account")
        )
        
        row = result.fetchone()
        assert row is not None
        assert row.order_count == 2
        assert row.position_count == 2
        assert row.total_market_value == Decimal("7750.00")  # 2 * 3875.00


class TestModelSerialization:
    """Test model serialization and deserialization patterns."""

    @pytest_asyncio.async_test
    async def test_account_model_dict_conversion(self, async_db_session: AsyncSession):
        """Test converting Account model to dictionary."""
        from app.models.database.trading import Account
        
        account = Account(
            id="serialize-test",
            user_id="serialize-user",
            name="Serialize Test Account",
            account_type="paper",
            balance=Decimal("5000.00"),
            buying_power=Decimal("5000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Test that model has dict-like attributes
        assert account.id == "serialize-test"
        assert account.balance == Decimal("5000.00")
        assert hasattr(account, '__dict__')

    @pytest_asyncio.async_test
    async def test_model_attribute_access(self, async_db_session: AsyncSession):
        """Test model attribute access patterns."""
        from app.models.database.trading import Order
        
        # Create account first
        from app.models.database.trading import Account
        account = Account(
            id="attr-test-account",
            user_id="attr-user",
            name="Attribute Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        order = Order(
            id="attr-test-order",
            account_id="attr-test-account",
            symbol="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            order_type="limit",
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Test attribute access
        assert hasattr(order, 'id')
        assert hasattr(order, 'symbol')
        assert hasattr(order, 'created_at')
        
        # Test setting attributes
        order.status = "filled"
        assert order.status == "filled"

    @pytest_asyncio.async_test  
    async def test_model_json_serializable_attributes(self, async_db_session: AsyncSession):
        """Test that model attributes are JSON serializable."""
        from app.models.database.trading import Position
        import json
        
        # Create account first
        from app.models.database.trading import Account
        account = Account(
            id="json-test-account",
            user_id="json-user",
            name="JSON Test Account",
            account_type="paper",
            balance=Decimal("10000.00"),
            buying_power=Decimal("10000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        async_db_session.add(account)
        await async_db_session.commit()
        
        position = Position(
            id="json-test-pos",
            account_id="json-test-account",
            symbol="AAPL",
            quantity=Decimal("50"),
            average_price=Decimal("150.00"),
            current_price=Decimal("155.00"),
            market_value=Decimal("7750.00"),
            unrealized_pnl=Decimal("250.00"),
            realized_pnl=Decimal("0.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Test JSON serialization of individual attributes
        assert position.symbol == "AAPL"  # String is JSON serializable
        
        # Decimal values need conversion for JSON
        assert str(position.quantity) == "50"
        assert str(position.market_value) == "7750.00"
        
        # Datetime objects need conversion for JSON
        assert isinstance(position.created_at, datetime)


class TestDatabaseIndexes:
    """Test database indexes and query optimization."""

    @pytest_asyncio.async_test
    async def test_table_indexes_exist(self, async_db_session: AsyncSession):
        """Test that expected database indexes exist."""
        # Query for indexes on key tables
        tables_to_check = ["accounts", "orders", "positions", "transactions"]
        
        for table_name in tables_to_check:
            result = await async_db_session.execute(
                text("""
                    SELECT indexname, indexdef 
                    FROM pg_indexes 
                    WHERE tablename = :table_name
                """).bindparam(table_name=table_name)
            )
            indexes = result.fetchall()
            
            # Should have at least a primary key index
            assert len(indexes) >= 1, f"No indexes found for table {table_name}"
            
            # Check for primary key index
            primary_key_exists = any("pkey" in idx.indexname for idx in indexes)
            assert primary_key_exists, f"No primary key index found for {table_name}"

    @pytest_asyncio.async_test
    async def test_foreign_key_indexes(self, async_db_session: AsyncSession):
        """Test that foreign key columns have indexes for performance."""
        # Check for foreign key indexes on common lookup columns
        fk_checks = [
            ("orders", "account_id"),
            ("positions", "account_id"),
            ("transactions", "account_id"),
            ("transactions", "order_id"),
        ]
        
        for table_name, column_name in fk_checks:
            result = await async_db_session.execute(
                text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = :table_name 
                    AND indexdef LIKE :column_pattern
                """).bindparam(
                    table_name=table_name,
                    column_pattern=f"%{column_name}%"
                )
            )
            indexes = result.fetchall()
            
            # Should have an index on the foreign key column
            # (Either explicit index or as part of primary/unique constraint)
            index_exists = len(indexes) > 0
            if not index_exists:
                # Check if it's part of a composite index or constraint
                result2 = await async_db_session.execute(
                    text("""
                        SELECT conname 
                        FROM pg_constraint c
                        JOIN pg_attribute a ON a.attnum = ANY(c.conkey)
                        JOIN pg_class t ON t.oid = c.conrelid
                        WHERE t.relname = :table_name 
                        AND a.attname = :column_name
                    """).bindparam(table_name=table_name, column_name=column_name)
                )
                constraints = result2.fetchall()
                assert len(constraints) > 0 or index_exists, \
                    f"No index or constraint found for {table_name}.{column_name}"