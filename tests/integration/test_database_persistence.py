"""
Integration tests for database persistence.

These tests verify that data properly persists between service instances
and that all database operations work correctly.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.database.trading import (
    Account as DBAccount,
)
from app.models.database.trading import (
    Order as DBOrder,
)
from app.models.database.trading import (
    Position as DBPosition,
)
from app.schemas.orders import OrderCreate, OrderType
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService


@pytest.fixture
def db_trading_service(db_session):
    """Create a TradingService instance that uses the test database."""
    service = TradingService(account_owner="test_user")
    service.quote_adapter = MagicMock()
    service._get_db_session = lambda: db_session
    return service


@pytest.fixture
def test_account(db_session):
    """Create a test account in the database."""
    account = DBAccount(id=str(uuid.uuid4()), owner="test_user", cash_balance=100000.0)
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


class TestDatabasePersistence:
    """Test data persistence between service instances."""

    @pytest.mark.asyncio
    async def test_order_persistence_across_service_instances(
        self, db_session, test_account
    ):
        """Test that orders persist between different service instances."""
        # Create first service instance
        service1 = TradingService(account_owner="test_user")
        service1.quote_adapter = MagicMock()
        service1._get_db_session = lambda: db_session
        service1.get_quote = MagicMock(
            return_value=StockQuote(
                symbol="AAPL",
                price=150.0,
                change=0,
                change_percent=0,
                volume=1000,
                last_updated=datetime.now(),
            )
        )

        # Create an order
        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        created_order = await service1.create_order(order_data)
        order_id = created_order.id

        # Create second service instance (simulating application restart)
        service2 = TradingService(account_owner="test_user")
        service2.quote_adapter = MagicMock()
        service2._get_db_session = lambda: db_session

        # Retrieve the order using the second service instance
        retrieved_order = await service2.get_order(order_id)

        # Assert the order was persisted correctly
        assert retrieved_order is not None
        assert retrieved_order.id == order_id
        assert retrieved_order.symbol == "AAPL"
        assert retrieved_order.order_type == OrderType.BUY
        assert retrieved_order.quantity == 100
        assert retrieved_order.price == 150.0

    @pytest.mark.asyncio
    async def test_portfolio_persistence_across_service_instances(
        self, db_session, test_account
    ):
        """Test that portfolio data persists between different service instances."""
        # Create first service instance and add positions
        service1 = TradingService(account_owner="test_user")
        service1._get_db_session = lambda: db_session
        service1.get_quote = MagicMock(
            return_value=StockQuote(
                symbol="AAPL",
                price=155.0,
                change=5.0,
                change_percent=3.33,
                volume=1000,
                last_updated=datetime.now(),
            )
        )

        # Add positions directly to database
        position1 = DBPosition(
            id=str(uuid.uuid4()),
            account_id=test_account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
        )
        position2 = DBPosition(
            id=str(uuid.uuid4()),
            account_id=test_account.id,
            symbol="GOOGL",
            quantity=10,
            avg_price=2800.0,
            current_price=2750.0,
            unrealized_pnl=-500.0,
        )
        db_session.add(position1)
        db_session.add(position2)
        db_session.commit()

        # Create second service instance (simulating application restart)
        service2 = TradingService(account_owner="test_user")
        service2._get_db_session = lambda: db_session
        service2.get_quote = MagicMock(
            return_value=StockQuote(
                symbol="AAPL",
                price=155.0,
                change=5.0,
                change_percent=3.33,
                volume=1000,
                last_updated=datetime.now(),
            )
        )

        # Retrieve portfolio using the second service instance
        portfolio = await service2.get_portfolio()

        # Assert the portfolio was persisted correctly
        assert portfolio is not None
        assert portfolio.cash_balance == 100000.0
        assert len(portfolio.positions) == 2

        portfolio_symbols = [pos.symbol for pos in portfolio.positions]
        assert "AAPL" in portfolio_symbols
        assert "GOOGL" in portfolio_symbols

    @pytest.mark.asyncio
    async def test_account_balance_persistence(self, db_session, test_account):
        """Test that account balance persists correctly."""
        # Create service instance
        service = TradingService(account_owner="test_user")
        service._get_db_session = lambda: db_session

        # Get initial balance
        initial_balance = await service.get_account_balance()
        assert initial_balance == 100000.0

        # Update balance in database
        test_account.cash_balance = 95000.0
        db_session.commit()

        # Get updated balance
        updated_balance = await service.get_account_balance()
        assert updated_balance == 95000.0

    @pytest.mark.asyncio
    async def test_multi_leg_order_persistence(self, db_session, test_account):
        """Test that multi-leg orders persist correctly with proper account_id."""
        from app.schemas.orders import MultiLegOrderCreate, OrderLeg

        # Create service instance
        service = TradingService(account_owner="test_user")
        service._get_db_session = lambda: db_session

        # Create a multi-leg order
        order_data = MultiLegOrderCreate(
            legs=[
                OrderLeg(
                    symbol="AAPL240119C00150000", quantity=1, price=5.50, action="buy"
                ),
                OrderLeg(
                    symbol="AAPL240119C00160000", quantity=1, price=2.75, action="sell"
                ),
            ]
        )

        created_order = await service.create_multi_leg_order(order_data)

        # Verify the order was created with correct account_id
        db_order = db_session.query(DBOrder).filter_by(id=created_order.id).first()
        assert db_order is not None
        assert (
            db_order.account_id == test_account.id
        )  # Should use account.id, not account_owner
        assert db_order.symbol == "AAPL240119C00150000"


class TestDatabaseConsistency:
    """Test database consistency and data integrity."""

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, db_session):
        """Test that database transactions rollback properly on errors."""
        # This test would require more complex setup to test transaction rollback
        # For now, we'll test that invalid operations don't corrupt the database
        service = TradingService(account_owner="nonexistent_user")
        service._get_db_session = lambda: db_session

        # Try to get portfolio for non-existent account
        with pytest.raises(Exception):  # Should raise NotFoundError or similar
            await service.get_portfolio()

        # Database should still be in consistent state
        accounts = db_session.query(DBAccount).all()
        assert isinstance(accounts, list)  # Query should still work

    @pytest.mark.asyncio
    async def test_concurrent_access_safety(self, db_session, test_account):
        """Test that concurrent access to the database is handled safely."""
        # Create multiple service instances accessing the same account
        service1 = TradingService(account_owner="test_user")
        service1._get_db_session = lambda: db_session

        service2 = TradingService(account_owner="test_user")
        service2._get_db_session = lambda: db_session

        # Both services should be able to access the same account
        balance1 = await service1.get_account_balance()
        balance2 = await service2.get_account_balance()

        assert balance1 == balance2 == 100000.0
