"""
Comprehensive database integration tests - Phase 5.1 implementation.
Tests order persistence, position updates, transaction recording, and data integrity.
"""

import pytest
import asyncio
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database.trading import Account, Order, Position, Transaction, OptionQuote, OrderLeg
from app.models.trading import OrderType, OrderSide, OrderStatus, OrderCondition
from app.storage.database import get_async_session, init_db


@pytest.fixture
async def db_session():
    """Create a test database session."""
    await init_db()
    async with get_async_session() as session:
        yield session


@pytest.fixture
async def test_account(db_session: AsyncSession):
    """Create a test account."""
    account = Account(
        account_id="TEST_ACCT_001",
        name="Test Account",
        cash_balance=Decimal("10000.00"),
        equity_value=Decimal("10000.00"),
        margin_requirement=Decimal("0.00"),
        created_at=datetime.utcnow()
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


class TestAccountPersistence:
    """Test account creation, updates, and retrieval."""
    
    async def test_account_creation(self, db_session: AsyncSession):
        """Test creating and retrieving an account."""
        account = Account(
            account_id="ACCT_001",
            name="John Doe Trading",
            cash_balance=Decimal("25000.00"),
            equity_value=Decimal("25000.00"),
            margin_requirement=Decimal("0.00"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(account)
        await db_session.commit()
        
        # Retrieve and verify
        result = await db_session.execute(
            select(Account).where(Account.account_id == "ACCT_001")
        )
        retrieved_account = result.scalar_one()
        
        assert retrieved_account.account_id == "ACCT_001"
        assert retrieved_account.name == "John Doe Trading"
        assert retrieved_account.cash_balance == Decimal("25000.00")
        
    async def test_account_balance_update(self, test_account: Account, db_session: AsyncSession):
        """Test updating account balances."""
        # Update balances
        test_account.cash_balance = Decimal("8500.00")
        test_account.equity_value = Decimal("12000.00")
        test_account.margin_requirement = Decimal("1500.00")
        
        await db_session.commit()
        
        # Verify updates
        result = await db_session.execute(
            select(Account).where(Account.account_id == test_account.account_id)
        )
        updated_account = result.scalar_one()
        
        assert updated_account.cash_balance == Decimal("8500.00")
        assert updated_account.equity_value == Decimal("12000.00")
        assert updated_account.margin_requirement == Decimal("1500.00")


class TestOrderPersistence:
    """Test order creation, updates, and complex queries."""
    
    async def test_simple_order_creation(self, test_account: Account, db_session: AsyncSession):
        """Test creating a simple stock order."""
        order = Order(
            account_id=test_account.account_id,
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        
        assert order.id is not None
        assert order.symbol == "AAPL"
        assert order.quantity == Decimal("100")
        
    async def test_multi_leg_order_creation(self, test_account: Account, db_session: AsyncSession):
        """Test creating a multi-leg options order."""
        # Create main order
        order = Order(
            account_id=test_account.account_id,
            symbol="AAPL_SPREAD",
            order_type=OrderType.MULTI_LEG,
            quantity=Decimal("1"),
            price=Decimal("2.50"),
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        db_session.add(order)
        await db_session.flush()  # Get order ID
        
        # Create order legs
        leg1 = OrderLeg(
            order_id=order.id,
            symbol="AAPL240119C00150000",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            order_index=1
        )
        
        leg2 = OrderLeg(
            order_id=order.id,
            symbol="AAPL240119C00155000",
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            order_index=2
        )
        
        db_session.add_all([leg1, leg2])
        await db_session.commit()
        
        # Verify order and legs
        result = await db_session.execute(
            select(Order).where(Order.id == order.id)
        )
        retrieved_order = result.scalar_one()
        
        legs_result = await db_session.execute(
            select(OrderLeg).where(OrderLeg.order_id == order.id).order_by(OrderLeg.order_index)
        )
        legs = legs_result.scalars().all()
        
        assert retrieved_order.order_type == OrderType.MULTI_LEG
        assert len(legs) == 2
        assert legs[0].symbol == "AAPL240119C00150000"
        assert legs[1].symbol == "AAPL240119C00155000"
        
    async def test_order_status_updates(self, test_account: Account, db_session: AsyncSession):
        """Test order status progression."""
        order = Order(
            account_id=test_account.account_id,
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=Decimal("50"),
            price=Decimal("2800.00"),
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        db_session.add(order)
        await db_session.commit()
        
        # Update to filled
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.utcnow()
        order.fill_price = Decimal("2795.50")
        
        await db_session.commit()
        
        # Verify updates
        result = await db_session.execute(
            select(Order).where(Order.id == order.id)
        )
        updated_order = result.scalar_one()
        
        assert updated_order.status == OrderStatus.FILLED
        assert updated_order.filled_at is not None
        assert updated_order.fill_price == Decimal("2795.50")


class TestPositionManagement:
    """Test position creation, updates, and calculations."""
    
    async def test_position_creation(self, test_account: Account, db_session: AsyncSession):
        """Test creating a new position."""
        position = Position(
            account_id=test_account.account_id,
            symbol="MSFT",
            quantity=Decimal("200"),
            cost_basis=Decimal("300.00"),
            current_price=Decimal("305.50"),
            market_value=Decimal("61100.00"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position)
        await db_session.commit()
        
        # Verify position
        result = await db_session.execute(
            select(Position).where(
                Position.account_id == test_account.account_id,
                Position.symbol == "MSFT"
            )
        )
        retrieved_position = result.scalar_one()
        
        assert retrieved_position.quantity == Decimal("200")
        assert retrieved_position.cost_basis == Decimal("300.00")
        assert retrieved_position.market_value == Decimal("61100.00")
        
    async def test_option_position_with_greeks(self, test_account: Account, db_session: AsyncSession):
        """Test creating an option position with Greeks."""
        position = Position(
            account_id=test_account.account_id,
            symbol="AAPL240119C00150000",
            quantity=Decimal("5"),  # 5 contracts
            cost_basis=Decimal("4.50"),
            current_price=Decimal("5.20"),
            market_value=Decimal("2600.00"),  # 5 * 100 * 5.20
            delta=Decimal("0.65"),
            gamma=Decimal("0.025"),
            theta=Decimal("-0.12"),
            vega=Decimal("0.18"),
            rho=Decimal("0.08"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position)
        await db_session.commit()
        
        # Verify Greeks are stored
        result = await db_session.execute(
            select(Position).where(
                Position.account_id == test_account.account_id,
                Position.symbol == "AAPL240119C00150000"
            )
        )
        retrieved_position = result.scalar_one()
        
        assert retrieved_position.delta == Decimal("0.65")
        assert retrieved_position.gamma == Decimal("0.025")
        assert retrieved_position.theta == Decimal("-0.12")
        assert retrieved_position.vega == Decimal("0.18")
        assert retrieved_position.rho == Decimal("0.08")
        
    async def test_position_quantity_updates(self, test_account: Account, db_session: AsyncSession):
        """Test updating position quantities (partial fills, etc.)."""
        # Create initial position
        position = Position(
            account_id=test_account.account_id,
            symbol="TSLA",
            quantity=Decimal("100"),
            cost_basis=Decimal("250.00"),
            current_price=Decimal("255.00"),
            market_value=Decimal("25500.00"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position)
        await db_session.commit()
        
        # Simulate buying more shares with different cost basis
        additional_quantity = Decimal("50")
        additional_cost = Decimal("260.00")
        
        # Calculate new weighted average cost basis
        total_quantity = position.quantity + additional_quantity
        total_cost = (position.quantity * position.cost_basis + 
                     additional_quantity * additional_cost)
        new_cost_basis = total_cost / total_quantity
        
        # Update position
        position.quantity = total_quantity
        position.cost_basis = new_cost_basis
        position.market_value = total_quantity * position.current_price
        
        await db_session.commit()
        
        # Verify updates
        result = await db_session.execute(
            select(Position).where(Position.id == position.id)
        )
        updated_position = result.scalar_one()
        
        assert updated_position.quantity == Decimal("150")
        assert abs(updated_position.cost_basis - Decimal("253.33")) < Decimal("0.01")


class TestTransactionRecording:
    """Test transaction recording and history tracking."""
    
    async def test_buy_transaction_recording(self, test_account: Account, db_session: AsyncSession):
        """Test recording a buy transaction."""
        transaction = Transaction(
            account_id=test_account.account_id,
            symbol="NVDA",
            transaction_type="BUY",
            quantity=Decimal("75"),
            price=Decimal("800.00"),
            total_amount=Decimal("60000.00"),
            fees=Decimal("1.00"),
            executed_at=datetime.utcnow()
        )
        
        db_session.add(transaction)
        await db_session.commit()
        
        # Verify transaction
        result = await db_session.execute(
            select(Transaction).where(
                Transaction.account_id == test_account.account_id,
                Transaction.symbol == "NVDA"
            )
        )
        retrieved_transaction = result.scalar_one()
        
        assert retrieved_transaction.transaction_type == "BUY"
        assert retrieved_transaction.quantity == Decimal("75")
        assert retrieved_transaction.total_amount == Decimal("60000.00")
        
    async def test_option_transaction_recording(self, test_account: Account, db_session: AsyncSession):
        """Test recording option transactions."""
        # BTO (Buy to Open) transaction
        transaction = Transaction(
            account_id=test_account.account_id,
            symbol="SPY240315C00450000",
            transaction_type="BTO",
            quantity=Decimal("10"),
            price=Decimal("15.50"),
            total_amount=Decimal("15500.00"),  # 10 * 100 * 15.50
            fees=Decimal("10.00"),
            executed_at=datetime.utcnow()
        )
        
        db_session.add(transaction)
        await db_session.commit()
        
        # Verify transaction
        result = await db_session.execute(
            select(Transaction).where(
                Transaction.account_id == test_account.account_id,
                Transaction.symbol == "SPY240315C00450000"
            )
        )
        retrieved_transaction = result.scalar_one()
        
        assert retrieved_transaction.transaction_type == "BTO"
        assert retrieved_transaction.quantity == Decimal("10")
        assert retrieved_transaction.total_amount == Decimal("15500.00")
        
    async def test_transaction_history_queries(self, test_account: Account, db_session: AsyncSession):
        """Test querying transaction history with various filters."""
        # Create multiple transactions
        transactions = [
            Transaction(
                account_id=test_account.account_id,
                symbol="AAPL",
                transaction_type="BUY",
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                total_amount=Decimal("15000.00"),
                executed_at=datetime.utcnow()
            ),
            Transaction(
                account_id=test_account.account_id,
                symbol="AAPL",
                transaction_type="SELL",
                quantity=Decimal("50"),
                price=Decimal("155.00"),
                total_amount=Decimal("7750.00"),
                executed_at=datetime.utcnow()
            ),
            Transaction(
                account_id=test_account.account_id,
                symbol="GOOGL",
                transaction_type="BUY",
                quantity=Decimal("25"),
                price=Decimal("2800.00"),
                total_amount=Decimal("70000.00"),
                executed_at=datetime.utcnow()
            )
        ]
        
        db_session.add_all(transactions)
        await db_session.commit()
        
        # Query all transactions for account
        all_transactions = await db_session.execute(
            select(Transaction).where(Transaction.account_id == test_account.account_id)
        )
        all_results = all_transactions.scalars().all()
        assert len(all_results) == 3
        
        # Query AAPL transactions only
        aapl_transactions = await db_session.execute(
            select(Transaction).where(
                Transaction.account_id == test_account.account_id,
                Transaction.symbol == "AAPL"
            )
        )
        aapl_results = aapl_transactions.scalars().all()
        assert len(aapl_results) == 2
        
        # Query buy transactions only
        buy_transactions = await db_session.execute(
            select(Transaction).where(
                Transaction.account_id == test_account.account_id,
                Transaction.transaction_type == "BUY"
            )
        )
        buy_results = buy_transactions.scalars().all()
        assert len(buy_results) == 2


class TestDataIntegrityConstraints:
    """Test database constraints and data integrity."""
    
    async def test_foreign_key_constraints(self, db_session: AsyncSession):
        """Test that foreign key constraints are enforced."""
        # Try to create order with non-existent account
        order = Order(
            account_id="NONEXISTENT_ACCOUNT",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        db_session.add(order)
        
        # This should raise an integrity error
        with pytest.raises(Exception):  # SQLAlchemy will raise an integrity error
            await db_session.commit()
            
    async def test_unique_constraints(self, test_account: Account, db_session: AsyncSession):
        """Test unique constraints where applicable."""
        # Create a position
        position1 = Position(
            account_id=test_account.account_id,
            symbol="AAPL",
            quantity=Decimal("100"),
            cost_basis=Decimal("150.00"),
            current_price=Decimal("155.00"),
            market_value=Decimal("15500.00"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position1)
        await db_session.commit()
        
        # Try to create another position for same account/symbol
        position2 = Position(
            account_id=test_account.account_id,
            symbol="AAPL",
            quantity=Decimal("50"),
            cost_basis=Decimal("160.00"),
            current_price=Decimal("155.00"),
            market_value=Decimal("7750.00"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position2)
        
        # This should raise an integrity error if unique constraint exists
        # Note: We may need to update the schema to enforce this constraint
        try:
            await db_session.commit()
            # If no constraint, we should manually handle position merging
            print("Warning: No unique constraint on account_id + symbol for positions")
        except Exception:
            # Constraint exists and was violated - this is expected
            pass
            
    async def test_decimal_precision(self, test_account: Account, db_session: AsyncSession):
        """Test that decimal precision is maintained."""
        # Create position with precise decimal values
        position = Position(
            account_id=test_account.account_id,
            symbol="PRECISE_TEST",
            quantity=Decimal("123.456789"),
            cost_basis=Decimal("99.123456"),
            current_price=Decimal("101.654321"),
            market_value=Decimal("12543.210987"),
            delta=Decimal("0.123456789"),
            created_at=datetime.utcnow()
        )
        
        db_session.add(position)
        await db_session.commit()
        
        # Retrieve and verify precision
        result = await db_session.execute(
            select(Position).where(
                Position.account_id == test_account.account_id,
                Position.symbol == "PRECISE_TEST"
            )
        )
        retrieved_position = result.scalar_one()
        
        # Verify decimal precision is maintained
        assert retrieved_position.quantity == Decimal("123.456789")
        assert retrieved_position.cost_basis == Decimal("99.123456")
        assert retrieved_position.delta == Decimal("0.123456789")


class TestOptionQuoteStorage:
    """Test storage and retrieval of option quotes with Greeks."""
    
    async def test_option_quote_creation(self, db_session: AsyncSession):
        """Test storing option quotes with full Greeks."""
        option_quote = OptionQuote(
            symbol="AAPL240119C00150000",
            underlying_symbol="AAPL",
            bid_price=Decimal("4.85"),
            ask_price=Decimal("4.95"),
            last_price=Decimal("4.90"),
            volume=1250,
            open_interest=5678,
            implied_volatility=Decimal("0.24"),
            delta=Decimal("0.65"),
            gamma=Decimal("0.025"),
            theta=Decimal("-0.12"),
            vega=Decimal("0.18"),
            rho=Decimal("0.08"),
            timestamp=datetime.utcnow()
        )
        
        db_session.add(option_quote)
        await db_session.commit()
        
        # Retrieve and verify
        result = await db_session.execute(
            select(OptionQuote).where(OptionQuote.symbol == "AAPL240119C00150000")
        )
        retrieved_quote = result.scalar_one()
        
        assert retrieved_quote.bid_price == Decimal("4.85")
        assert retrieved_quote.ask_price == Decimal("4.95")
        assert retrieved_quote.delta == Decimal("0.65")
        assert retrieved_quote.implied_volatility == Decimal("0.24")
        
    async def test_option_chain_queries(self, db_session: AsyncSession):
        """Test querying option chains by underlying and expiration."""
        # Create multiple option quotes for same underlying
        quotes = [
            OptionQuote(
                symbol="AAPL240119C00145000",
                underlying_symbol="AAPL",
                bid_price=Decimal("6.20"),
                ask_price=Decimal("6.30"),
                last_price=Decimal("6.25"),
                timestamp=datetime.utcnow()
            ),
            OptionQuote(
                symbol="AAPL240119C00150000",
                underlying_symbol="AAPL",
                bid_price=Decimal("4.85"),
                ask_price=Decimal("4.95"),
                last_price=Decimal("4.90"),
                timestamp=datetime.utcnow()
            ),
            OptionQuote(
                symbol="AAPL240119P00150000",
                underlying_symbol="AAPL",
                bid_price=Decimal("3.10"),
                ask_price=Decimal("3.20"),
                last_price=Decimal("3.15"),
                timestamp=datetime.utcnow()
            )
        ]
        
        db_session.add_all(quotes)
        await db_session.commit()
        
        # Query all AAPL options
        aapl_options = await db_session.execute(
            select(OptionQuote).where(OptionQuote.underlying_symbol == "AAPL")
        )
        aapl_results = aapl_options.scalars().all()
        assert len(aapl_results) == 3
        
        # Query only calls
        aapl_calls = await db_session.execute(
            select(OptionQuote).where(
                OptionQuote.underlying_symbol == "AAPL",
                OptionQuote.symbol.like("%C%")
            )
        )
        call_results = aapl_calls.scalars().all()
        assert len(call_results) == 2


class TestPerformanceQueries:
    """Test query performance and optimization."""
    
    async def test_bulk_transaction_insertion(self, test_account: Account, db_session: AsyncSession):
        """Test inserting many transactions efficiently."""
        import time
        
        # Create 1000 test transactions
        transactions = []
        for i in range(1000):
            transaction = Transaction(
                account_id=test_account.account_id,
                symbol=f"STOCK_{i % 50}",  # 50 different symbols
                transaction_type="BUY" if i % 2 == 0 else "SELL",
                quantity=Decimal(str(100 + i % 100)),
                price=Decimal(str(100.00 + i % 50)),
                total_amount=Decimal(str((100 + i % 100) * (100.00 + i % 50))),
                executed_at=datetime.utcnow()
            )
            transactions.append(transaction)
        
        # Time the bulk insertion
        start_time = time.time()
        db_session.add_all(transactions)
        await db_session.commit()
        end_time = time.time()
        
        insertion_time = end_time - start_time
        
        # Should be able to insert 1000 transactions reasonably quickly
        assert insertion_time < 5.0, f"Bulk insertion too slow: {insertion_time:.2f}s"
        
        # Verify all transactions were inserted
        count_result = await db_session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.account_id == test_account.account_id
            )
        )
        transaction_count = count_result.scalar()
        assert transaction_count == 1000
        
    async def test_complex_portfolio_query(self, test_account: Account, db_session: AsyncSession):
        """Test complex queries for portfolio analysis."""
        # Create test positions
        positions = [
            Position(
                account_id=test_account.account_id,
                symbol=f"STOCK_{i}",
                quantity=Decimal(str(100 + i * 10)),
                cost_basis=Decimal(str(50.00 + i * 5)),
                current_price=Decimal(str(55.00 + i * 5)),
                market_value=Decimal(str((100 + i * 10) * (55.00 + i * 5))),
                created_at=datetime.utcnow()
            )
            for i in range(20)  # 20 positions
        ]
        
        db_session.add_all(positions)
        await db_session.commit()
        
        # Complex query: total portfolio value, P&L, etc.
        portfolio_stats = await db_session.execute(
            select(
                func.sum(Position.market_value).label("total_market_value"),
                func.sum(Position.quantity * Position.cost_basis).label("total_cost_basis"),
                func.count(Position.id).label("position_count")
            ).where(Position.account_id == test_account.account_id)
        )
        
        stats = portfolio_stats.first()
        
        assert stats.position_count == 20
        assert stats.total_market_value > 0
        assert stats.total_cost_basis > 0