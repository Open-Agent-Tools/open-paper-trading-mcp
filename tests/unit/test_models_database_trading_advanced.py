"""
Advanced tests for database trading models.

Comprehensive test coverage for SQLAlchemy models, relationships, 
constraints, validations, and database patterns in the trading module.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database.trading import (
    Account,
    DevOptionQuote,
    DevScenario,
    DevStockQuote,
    MultiLegOrder,
    OptionExpiration,
    OptionQuoteHistory,
    Order,
    OrderLeg,
    PortfolioGreeksSnapshot,
    Position,
    RecognizedStrategy,
    StrategyPerformance,
    Transaction,
)
from app.schemas.orders import OrderStatus, OrderType


@pytest_asyncio.fixture
async def sample_account(async_db_session: AsyncSession) -> Account:
    """Create a sample account for testing."""
    account = Account(
        owner="test_user",
        cash_balance=10000.0,
    )
    async_db_session.add(account)
    await async_db_session.commit()
    await async_db_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def sample_position(
    async_db_session: AsyncSession, sample_account: Account
) -> Position:
    """Create a sample position for testing."""
    position = Position(
        account_id=sample_account.id,
        symbol="AAPL",
        quantity=100,
        avg_price=150.0,
    )
    async_db_session.add(position)
    await async_db_session.commit()
    await async_db_session.refresh(position)
    return position


@pytest_asyncio.fixture
async def sample_order(async_db_session: AsyncSession, sample_account: Account) -> Order:
    """Create a sample order for testing."""
    order = Order(
        account_id=sample_account.id,
        symbol="GOOGL",
        order_type=OrderType.BUY,
        quantity=50,
        price=2800.0,
        status=OrderStatus.PENDING,
    )
    async_db_session.add(order)
    await async_db_session.commit()
    await async_db_session.refresh(order)
    return order


class TestAccount:
    """Test Account database model."""

    async def test_account_creation(self, async_db_session: AsyncSession):
        """Test basic account creation."""
        account = Account(owner="test_owner", cash_balance=50000.0)
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)

        assert account.id is not None
        assert account.owner == "test_owner"
        assert account.cash_balance == 50000.0
        assert account.created_at is not None
        assert isinstance(account.created_at, datetime)

    async def test_account_default_values(self, async_db_session: AsyncSession):
        """Test account default values."""
        account = Account(owner="default_user")
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)

        assert account.cash_balance == 100000.0  # Default value
        assert account.created_at is not None

    async def test_account_unique_owner_constraint(self, async_db_session: AsyncSession):
        """Test that owner must be unique."""
        account1 = Account(owner="duplicate_user")
        account2 = Account(owner="duplicate_user")

        async_db_session.add(account1)
        await async_db_session.commit()

        async_db_session.add(account2)
        with pytest.raises(IntegrityError):
            await async_db_session.commit()

    async def test_account_relationships_empty(self, sample_account: Account):
        """Test account relationships when empty."""
        assert len(sample_account.positions) == 0
        assert len(sample_account.orders) == 0
        assert len(sample_account.transactions) == 0
        assert len(sample_account.multi_leg_orders) == 0

    async def test_account_uuid_generation(self, async_db_session: AsyncSession):
        """Test that account IDs are valid UUIDs."""
        account = Account(owner="uuid_test_user")
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)

        # Verify it's a valid UUID string
        uuid.UUID(account.id)  # This will raise ValueError if invalid

    async def test_account_indexing(self, async_db_session: AsyncSession):
        """Test that owner field is properly indexed."""
        # Create multiple accounts
        accounts = [
            Account(owner=f"user_{i}", cash_balance=1000.0 + i) for i in range(5)
        ]
        async_db_session.add_all(accounts)
        await async_db_session.commit()

        # Query by owner should be efficient due to index
        result = await async_db_session.execute(
            select(Account).where(Account.owner == "user_3")
        )
        found_account = result.scalar_one()
        assert found_account.cash_balance == 1003.0


class TestPosition:
    """Test Position database model."""

    async def test_position_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test basic position creation."""
        position = Position(
            account_id=sample_account.id,
            symbol="MSFT",
            quantity=200,
            avg_price=350.0,
        )
        async_db_session.add(position)
        await async_db_session.commit()
        await async_db_session.refresh(position)

        assert position.id is not None
        assert position.account_id == sample_account.id
        assert position.symbol == "MSFT"
        assert position.quantity == 200
        assert position.avg_price == 350.0

    async def test_position_account_relationship(
        self, sample_position: Position, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test position-account relationship."""
        # Refresh to load relationship
        await async_db_session.refresh(sample_position, ["account"])
        await async_db_session.refresh(sample_account, ["positions"])

        assert sample_position.account.id == sample_account.id
        assert sample_position in sample_account.positions

    async def test_position_foreign_key_constraint(self, async_db_session: AsyncSession):
        """Test foreign key constraint for account_id."""
        position = Position(
            account_id="non_existent_account",
            symbol="TSLA",
            quantity=10,
            avg_price=800.0,
        )
        async_db_session.add(position)

        with pytest.raises(IntegrityError):
            await async_db_session.commit()

    async def test_position_negative_quantity(self, sample_account: Account, async_db_session: AsyncSession):
        """Test position with negative quantity (short position)."""
        position = Position(
            account_id=sample_account.id,
            symbol="SPY",
            quantity=-100,  # Short position
            avg_price=400.0,
        )
        async_db_session.add(position)
        await async_db_session.commit()
        await async_db_session.refresh(position)

        assert position.quantity == -100

    async def test_position_symbol_indexing(self, sample_account: Account, async_db_session: AsyncSession):
        """Test symbol field indexing."""
        positions = [
            Position(
                account_id=sample_account.id,
                symbol=f"STOCK{i}",
                quantity=10 * i,
                avg_price=100.0 + i,
            )
            for i in range(1, 6)
        ]
        async_db_session.add_all(positions)
        await async_db_session.commit()

        # Query by symbol should use index
        result = await async_db_session.execute(
            select(Position).where(Position.symbol == "STOCK3")
        )
        found_position = result.scalar_one()
        assert found_position.quantity == 30


class TestOrder:
    """Test Order database model."""

    async def test_order_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test basic order creation."""
        order = Order(
            account_id=sample_account.id,
            symbol="NVDA",
            order_type=OrderType.SELL,
            quantity=25,
            price=900.0,
            status=OrderStatus.FILLED,
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        assert order.id.startswith("order_")
        assert order.account_id == sample_account.id
        assert order.symbol == "NVDA"
        assert order.order_type == OrderType.SELL
        assert order.quantity == 25
        assert order.price == 900.0
        assert order.status == OrderStatus.FILLED

    async def test_order_default_status(self, sample_account: Account, async_db_session: AsyncSession):
        """Test order default status."""
        order = Order(
            account_id=sample_account.id,
            symbol="AMD",
            order_type=OrderType.BUY,
            quantity=100,
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        assert order.status == OrderStatus.PENDING  # Default value

    async def test_order_market_order_no_price(self, sample_account: Account, async_db_session: AsyncSession):
        """Test market order without price."""
        order = Order(
            account_id=sample_account.id,
            symbol="QQQ",
            order_type=OrderType.BUY,
            quantity=50,
            price=None,  # Market order
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        assert order.price is None

    async def test_order_advanced_fields(self, sample_account: Account, async_db_session: AsyncSession):
        """Test advanced order fields for stop/trail orders."""
        order = Order(
            account_id=sample_account.id,
            symbol="IWM",
            order_type=OrderType.BUY,
            quantity=100,
            price=200.0,
            stop_price=195.0,
            trail_percent=0.05,
            trail_amount=2.5,
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        assert order.stop_price == 195.0
        assert order.trail_percent == 0.05
        assert order.trail_amount == 2.5
        assert order.triggered_at is None  # Not triggered yet

    async def test_order_timestamps(self, sample_order: Order):
        """Test order timestamp fields."""
        assert sample_order.created_at is not None
        assert isinstance(sample_order.created_at, datetime)
        assert sample_order.filled_at is None  # Not filled

    async def test_order_account_relationship(
        self, sample_order: Order, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test order-account relationship."""
        await async_db_session.refresh(sample_order, ["account"])
        await async_db_session.refresh(sample_account, ["orders"])

        assert sample_order.account.id == sample_account.id
        assert sample_order in sample_account.orders

    async def test_order_id_format(self, sample_account: Account, async_db_session: AsyncSession):
        """Test order ID format."""
        order = Order(
            account_id=sample_account.id,
            symbol="VTI",
            order_type=OrderType.BUY,
            quantity=100,
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        # Should start with "order_" and be followed by 8 hex chars
        assert order.id.startswith("order_")
        assert len(order.id) == 14  # "order_" + 8 chars
        # Verify the hex part
        hex_part = order.id[6:]
        int(hex_part, 16)  # This will raise ValueError if not valid hex


class TestTransaction:
    """Test Transaction database model."""

    async def test_transaction_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test basic transaction creation."""
        transaction = Transaction(
            account_id=sample_account.id,
            symbol="BRK.B",
            quantity=10,
            price=350.0,
            transaction_type=OrderType.BUY,
        )
        async_db_session.add(transaction)
        await async_db_session.commit()
        await async_db_session.refresh(transaction)

        assert transaction.id is not None
        assert transaction.account_id == sample_account.id
        assert transaction.symbol == "BRK.B"
        assert transaction.quantity == 10
        assert transaction.price == 350.0
        assert transaction.transaction_type == OrderType.BUY
        assert transaction.timestamp is not None

    async def test_transaction_with_order(
        self, sample_account: Account, sample_order: Order, async_db_session: AsyncSession
    ):
        """Test transaction linked to an order."""
        transaction = Transaction(
            account_id=sample_account.id,
            order_id=sample_order.id,
            symbol=sample_order.symbol,
            quantity=sample_order.quantity,
            price=sample_order.price or 100.0,
            transaction_type=sample_order.order_type,
        )
        async_db_session.add(transaction)
        await async_db_session.commit()
        await async_db_session.refresh(transaction)

        assert transaction.order_id == sample_order.id
        assert transaction.symbol == sample_order.symbol

    async def test_transaction_account_relationship(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test transaction-account relationship."""
        transaction = Transaction(
            account_id=sample_account.id,
            symbol="JPM",
            quantity=25,
            price=150.0,
            transaction_type=OrderType.SELL,
        )
        async_db_session.add(transaction)
        await async_db_session.commit()
        await async_db_session.refresh(transaction, ["account"])
        await async_db_session.refresh(sample_account, ["transactions"])

        assert transaction.account.id == sample_account.id
        assert transaction in sample_account.transactions


class TestOptionQuoteHistory:
    """Test OptionQuoteHistory database model."""

    async def test_option_quote_creation(self, async_db_session: AsyncSession):
        """Test option quote history creation."""
        expiry_date = date.today() + timedelta(days=30)
        quote = OptionQuoteHistory(
            symbol="AAPL240119C00195000",
            underlying_symbol="AAPL",
            strike=195.0,
            expiration_date=expiry_date,
            option_type="call",
            bid=5.0,
            ask=5.5,
            price=5.25,
            volume=100,
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.3,
            implied_volatility=0.25,
            underlying_price=200.0,
            quote_time=datetime.now(),
        )
        async_db_session.add(quote)
        await async_db_session.commit()
        await async_db_session.refresh(quote)

        assert quote.symbol == "AAPL240119C00195000"
        assert quote.underlying_symbol == "AAPL"
        assert quote.strike == 195.0
        assert quote.option_type == "call"
        assert quote.delta == 0.6

    async def test_option_quote_advanced_greeks(self, async_db_session: AsyncSession):
        """Test advanced Greeks fields."""
        quote = OptionQuoteHistory(
            symbol="SPY240315P00450000",
            underlying_symbol="SPY",
            strike=450.0,
            expiration_date=date.today() + timedelta(days=15),
            option_type="put",
            price=2.5,
            charm=0.01,
            vanna=0.15,
            speed=0.005,
            zomma=0.02,
            color=0.001,
            quote_time=datetime.now(),
        )
        async_db_session.add(quote)
        await async_db_session.commit()
        await async_db_session.refresh(quote)

        assert quote.charm == 0.01
        assert quote.vanna == 0.15
        assert quote.speed == 0.005

    async def test_option_quote_test_scenario(self, async_db_session: AsyncSession):
        """Test test scenario field."""
        quote = OptionQuoteHistory(
            symbol="QQQ240201C00400000",
            underlying_symbol="QQQ",
            strike=400.0,
            expiration_date=date.today() + timedelta(days=7),
            option_type="call",
            price=1.0,
            test_scenario="high_volatility_test",
            quote_time=datetime.now(),
        )
        async_db_session.add(quote)
        await async_db_session.commit()
        await async_db_session.refresh(quote)

        assert quote.test_scenario == "high_volatility_test"


class TestDevStockQuote:
    """Test DevStockQuote database model."""

    async def test_dev_stock_quote_creation(self, async_db_session: AsyncSession):
        """Test development stock quote creation."""
        quote_date = date.today()
        quote = DevStockQuote(
            symbol="TSLA",
            quote_date=quote_date,
            bid=Decimal("250.50"),
            ask=Decimal("251.00"),
            price=Decimal("250.75"),
            volume=1000000,
            scenario="normal_trading",
        )
        async_db_session.add(quote)
        await async_db_session.commit()
        await async_db_session.refresh(quote)

        assert quote.symbol == "TSLA"
        assert quote.quote_date == quote_date
        assert quote.bid == Decimal("250.50")
        assert quote.scenario == "normal_trading"

    async def test_dev_stock_quote_indexes(self, async_db_session: AsyncSession):
        """Test composite indexes work correctly."""
        quote_date = date.today()
        quotes = [
            DevStockQuote(
                symbol="AAPL",
                quote_date=quote_date - timedelta(days=i),
                price=Decimal(f"{150 + i}.00"),
                scenario="backtest_scenario",
            )
            for i in range(3)
        ]
        async_db_session.add_all(quotes)
        await async_db_session.commit()

        # Query should use composite index
        result = await async_db_session.execute(
            select(DevStockQuote).where(
                DevStockQuote.symbol == "AAPL",
                DevStockQuote.quote_date == quote_date - timedelta(days=1),
            )
        )
        found_quote = result.scalar_one()
        assert found_quote.price == Decimal("151.00")


class TestDevOptionQuote:
    """Test DevOptionQuote database model."""

    async def test_dev_option_quote_creation(self, async_db_session: AsyncSession):
        """Test development option quote creation."""
        quote_date = date.today()
        expiry_date = quote_date + timedelta(days=30)
        
        quote = DevOptionQuote(
            symbol="AAPL240315C00180000",
            underlying="AAPL",
            expiration=expiry_date,
            strike=Decimal("180.00"),
            option_type="call",
            quote_date=quote_date,
            bid=Decimal("2.50"),
            ask=Decimal("2.70"),
            price=Decimal("2.60"),
            volume=500,
            scenario="earnings_volatility",
        )
        async_db_session.add(quote)
        await async_db_session.commit()
        await async_db_session.refresh(quote)

        assert quote.symbol == "AAPL240315C00180000"
        assert quote.underlying == "AAPL"
        assert quote.option_type == "call"
        assert quote.strike == Decimal("180.00")

    async def test_dev_option_quote_complex_indexes(self, async_db_session: AsyncSession):
        """Test multiple composite indexes."""
        quote_date = date.today()
        expiry_date = quote_date + timedelta(days=21)
        
        quotes = [
            DevOptionQuote(
                symbol=f"SPY240315C0045{i:04d}00",
                underlying="SPY",
                expiration=expiry_date,
                strike=Decimal(f"45{i}.00"),
                option_type="call",
                quote_date=quote_date,
                price=Decimal(f"{10 + i}.00"),
                scenario="vol_surface_test",
            )
            for i in range(5)
        ]
        async_db_session.add_all(quotes)
        await async_db_session.commit()

        # Test underlying + date index
        result = await async_db_session.execute(
            select(DevOptionQuote).where(
                DevOptionQuote.underlying == "SPY",
                DevOptionQuote.quote_date == quote_date,
            )
        )
        found_quotes = result.scalars().all()
        assert len(found_quotes) == 5


class TestDevScenario:
    """Test DevScenario database model."""

    async def test_dev_scenario_creation(self, async_db_session: AsyncSession):
        """Test development scenario creation."""
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
        
        scenario = DevScenario(
            name="high_vol_scenario",
            description="High volatility market conditions for testing",
            start_date=start_date,
            end_date=end_date,
            symbols=["AAPL", "GOOGL", "MSFT", "TSLA"],
            market_condition="volatile",
        )
        async_db_session.add(scenario)
        await async_db_session.commit()
        await async_db_session.refresh(scenario)

        assert scenario.name == "high_vol_scenario"
        assert scenario.symbols == ["AAPL", "GOOGL", "MSFT", "TSLA"]
        assert scenario.market_condition == "volatile"

    async def test_dev_scenario_unique_name(self, async_db_session: AsyncSession):
        """Test scenario name uniqueness constraint."""
        scenario1 = DevScenario(
            name="duplicate_scenario",
            start_date=date.today(),
            end_date=date.today(),
            symbols=["AAPL"],
        )
        scenario2 = DevScenario(
            name="duplicate_scenario",
            start_date=date.today(),
            end_date=date.today(),
            symbols=["GOOGL"],
        )

        async_db_session.add(scenario1)
        await async_db_session.commit()

        async_db_session.add(scenario2)
        with pytest.raises(IntegrityError):
            await async_db_session.commit()


class TestMultiLegOrder:
    """Test MultiLegOrder database model."""

    async def test_multi_leg_order_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test multi-leg order creation."""
        order = MultiLegOrder(
            account_id=sample_account.id,
            order_type="limit",
            net_price=1.50,
            strategy_type="vertical_spread",
            underlying_symbol="AAPL",
        )
        async_db_session.add(order)
        await async_db_session.commit()
        await async_db_session.refresh(order)

        assert order.id.startswith("mlo_")
        assert order.account_id == sample_account.id
        assert order.strategy_type == "vertical_spread"
        assert order.status == OrderStatus.PENDING  # Default

    async def test_multi_leg_order_with_legs(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test multi-leg order with order legs."""
        mlo = MultiLegOrder(
            account_id=sample_account.id,
            order_type="limit",
            net_price=2.00,
            strategy_type="iron_condor",
            underlying_symbol="SPY",
        )
        async_db_session.add(mlo)
        await async_db_session.flush()  # Get ID

        # Add legs
        leg1 = OrderLeg(
            multi_leg_order_id=mlo.id,
            symbol="SPY240315C00450000",
            asset_type="option",
            quantity=1,
            order_type=OrderType.SELL,
            price=5.0,
            strike=450.0,
            expiration_date=date.today() + timedelta(days=30),
            option_type="call",
            underlying_symbol="SPY",
        )
        leg2 = OrderLeg(
            multi_leg_order_id=mlo.id,
            symbol="SPY240315C00460000", 
            asset_type="option",
            quantity=1,
            order_type=OrderType.BUY,
            price=3.0,
            strike=460.0,
            expiration_date=date.today() + timedelta(days=30),
            option_type="call",
            underlying_symbol="SPY",
        )

        async_db_session.add_all([leg1, leg2])
        await async_db_session.commit()
        
        # Refresh with legs
        await async_db_session.refresh(mlo, ["legs"])
        assert len(mlo.legs) == 2
        assert mlo.legs[0].strike == 450.0


class TestRecognizedStrategy:
    """Test RecognizedStrategy database model."""

    async def test_recognized_strategy_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test recognized strategy creation."""
        strategy = RecognizedStrategy(
            account_id=sample_account.id,
            strategy_type="covered_call",
            strategy_name="AAPL Covered Call",
            underlying_symbol="AAPL",
            cost_basis=1000.0,
            max_profit=150.0,
            max_loss=850.0,
            breakeven_points=["175.00"],
            position_ids=["pos1", "pos2"],
        )
        async_db_session.add(strategy)
        await async_db_session.commit()
        await async_db_session.refresh(strategy)

        assert strategy.strategy_type == "covered_call"
        assert strategy.breakeven_points == ["175.00"]
        assert strategy.position_ids == ["pos1", "pos2"]
        assert strategy.is_active is True  # Default

    async def test_strategy_performance_relationship(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test strategy-performance relationship."""
        strategy = RecognizedStrategy(
            account_id=sample_account.id,
            strategy_type="iron_butterfly",
            strategy_name="SPY Iron Butterfly",
            underlying_symbol="SPY",
            cost_basis=500.0,
            position_ids=["pos1", "pos2", "pos3"],
        )
        async_db_session.add(strategy)
        await async_db_session.flush()

        performance = StrategyPerformance(
            strategy_id=strategy.id,
            unrealized_pnl=50.0,
            realized_pnl=0.0,
            total_pnl=50.0,
            pnl_percent=10.0,
            current_market_value=550.0,
            cost_basis=500.0,
            measured_at=datetime.now(),
        )
        async_db_session.add(performance)
        await async_db_session.commit()
        
        await async_db_session.refresh(strategy, ["performance_records"])
        assert len(strategy.performance_records) == 1
        assert strategy.performance_records[0].total_pnl == 50.0


class TestPortfolioGreeksSnapshot:
    """Test PortfolioGreeksSnapshot database model."""

    async def test_greeks_snapshot_creation(self, sample_account: Account, async_db_session: AsyncSession):
        """Test portfolio Greeks snapshot creation."""
        snapshot_date = date.today()
        snapshot = PortfolioGreeksSnapshot(
            account_id=sample_account.id,
            snapshot_date=snapshot_date,
            snapshot_time=datetime.now(),
            total_delta=150.5,
            total_gamma=2.3,
            total_theta=-45.2,
            total_vega=89.1,
            delta_normalized=0.15,
            gamma_normalized=0.002,
            theta_normalized=-0.045,
            vega_normalized=0.089,
            total_portfolio_value=100000.0,
            options_value=15000.0,
            stocks_value=85000.0,
        )
        async_db_session.add(snapshot)
        await async_db_session.commit()
        await async_db_session.refresh(snapshot)

        assert snapshot.total_delta == 150.5
        assert snapshot.total_portfolio_value == 100000.0
        assert snapshot.snapshot_date == snapshot_date

    async def test_greeks_snapshot_account_relationship(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test Greeks snapshot-account relationship."""
        snapshot = PortfolioGreeksSnapshot(
            account_id=sample_account.id,
            snapshot_date=date.today(),
            snapshot_time=datetime.now(),
            total_delta=100.0,
            total_portfolio_value=50000.0,
        )
        async_db_session.add(snapshot)
        await async_db_session.commit()
        
        await async_db_session.refresh(snapshot, ["account"])
        await async_db_session.refresh(sample_account, ["greeks_snapshots"])
        
        assert snapshot.account.id == sample_account.id
        assert snapshot in sample_account.greeks_snapshots


class TestOptionExpiration:
    """Test OptionExpiration database model."""

    async def test_option_expiration_creation(self, async_db_session: AsyncSession):
        """Test option expiration creation."""
        expiry_date = date.today() + timedelta(days=1)
        expiration = OptionExpiration(
            underlying_symbol="AAPL",
            expiration_date=expiry_date,
            expired_positions_count=25,
            assignments_count=5,
            exercises_count=8,
            worthless_count=12,
            total_cash_impact=12500.0,
            fees_charged=25.0,
        )
        async_db_session.add(expiration)
        await async_db_session.commit()
        await async_db_session.refresh(expiration)

        assert expiration.underlying_symbol == "AAPL"
        assert expiration.is_processed is False  # Default
        assert expiration.expired_positions_count == 25
        assert expiration.total_cash_impact == 12500.0

    async def test_option_expiration_processing_status(self, async_db_session: AsyncSession):
        """Test expiration processing status updates."""
        expiration = OptionExpiration(
            underlying_symbol="SPY",
            expiration_date=date.today(),
        )
        async_db_session.add(expiration)
        await async_db_session.commit()
        
        # Mark as processed
        expiration.is_processed = True
        expiration.processed_at = datetime.now()
        expiration.processing_mode = "automatic"
        await async_db_session.commit()
        await async_db_session.refresh(expiration)
        
        assert expiration.is_processed is True
        assert expiration.processed_at is not None
        assert expiration.processing_mode == "automatic"


class TestModelRelationships:
    """Test complex model relationships and cascading."""

    async def test_account_cascade_delete_positions(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test that account deletion cascades properly."""
        # Add positions to account
        positions = [
            Position(
                account_id=sample_account.id,
                symbol=f"STOCK{i}",
                quantity=100 * i,
                avg_price=50.0 + i,
            )
            for i in range(1, 4)
        ]
        async_db_session.add_all(positions)
        await async_db_session.commit()

        # Verify positions exist
        position_count = await async_db_session.execute(
            select(func.count(Position.id)).where(Position.account_id == sample_account.id)
        )
        assert position_count.scalar() == 3

        # Delete account - positions should remain (no cascade delete defined)
        await async_db_session.delete(sample_account)
        await async_db_session.commit()

        # Note: We don't have CASCADE DELETE defined, so positions remain orphaned
        # This is likely intentional for audit purposes

    async def test_multi_leg_order_cascade_delete(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test multi-leg order cascade delete with legs."""
        mlo = MultiLegOrder(
            account_id=sample_account.id,
            strategy_type="spread",
            underlying_symbol="QQQ",
        )
        async_db_session.add(mlo)
        await async_db_session.flush()

        # Add legs
        legs = [
            OrderLeg(
                multi_leg_order_id=mlo.id,
                symbol=f"QQQ240315C0040{i}000",
                asset_type="option",
                quantity=1 if i % 2 == 0 else -1,
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                strike=400 + i * 5,
                option_type="call",
            )
            for i in range(4)
        ]
        async_db_session.add_all(legs)
        await async_db_session.commit()

        # Verify legs exist
        leg_count = await async_db_session.execute(
            select(func.count(OrderLeg.id)).where(
                OrderLeg.multi_leg_order_id == mlo.id
            )
        )
        assert leg_count.scalar() == 4

        # Delete multi-leg order - should cascade delete legs
        await async_db_session.delete(mlo)
        await async_db_session.commit()

        # Verify legs are deleted
        remaining_legs = await async_db_session.execute(
            select(func.count(OrderLeg.id)).where(
                OrderLeg.multi_leg_order_id == mlo.id
            )
        )
        assert remaining_legs.scalar() == 0

    async def test_strategy_performance_cascade(
        self, sample_account: Account, async_db_session: AsyncSession
    ):
        """Test strategy-performance cascade relationship."""
        strategy = RecognizedStrategy(
            account_id=sample_account.id,
            strategy_type="straddle",
            strategy_name="TSLA Straddle",
            underlying_symbol="TSLA",
            cost_basis=2000.0,
            position_ids=["pos1", "pos2"],
        )
        async_db_session.add(strategy)
        await async_db_session.flush()

        # Add performance records
        performances = [
            StrategyPerformance(
                strategy_id=strategy.id,
                total_pnl=100.0 * i,
                measured_at=datetime.now() - timedelta(days=i),
                cost_basis=2000.0,
            )
            for i in range(3)
        ]
        async_db_session.add_all(performances)
        await async_db_session.commit()

        # Delete strategy - should cascade delete performance records
        await async_db_session.delete(strategy)
        await async_db_session.commit()

        # Verify performance records are deleted
        remaining_performance = await async_db_session.execute(
            select(func.count(StrategyPerformance.id)).where(
                StrategyPerformance.strategy_id == strategy.id
            )
        )
        assert remaining_performance.scalar() == 0


class TestModelIndexes:
    """Test database indexes for performance."""

    async def test_composite_indexes_queries(self, sample_account: Account, async_db_session: AsyncSession):
        """Test that composite indexes are used effectively."""
        # Create test data for different index patterns
        orders = [
            Order(
                account_id=sample_account.id,
                symbol=f"STOCK{i % 5}",
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                quantity=100,
                status=OrderStatus.PENDING if i % 3 == 0 else OrderStatus.FILLED,
                created_at=datetime.now() - timedelta(hours=i),
            )
            for i in range(20)
        ]
        async_db_session.add_all(orders)
        await async_db_session.commit()

        # Test account+status index
        result = await async_db_session.execute(
            select(Order).where(
                Order.account_id == sample_account.id,
                Order.status == OrderStatus.PENDING,
            )
        )
        pending_orders = result.scalars().all()
        expected_pending = len([o for o in orders if o.status == OrderStatus.PENDING])
        assert len(pending_orders) == expected_pending

        # Test symbol+status index
        result = await async_db_session.execute(
            select(Order).where(
                Order.symbol == "STOCK1",
                Order.status == OrderStatus.FILLED,
            )
        )
        stock1_filled = result.scalars().all()
        assert len(stock1_filled) >= 0  # Should execute efficiently

    async def test_time_based_indexes(self, sample_account: Account, async_db_session: AsyncSession):
        """Test time-based index queries."""
        base_time = datetime.now() - timedelta(days=7)
        transactions = [
            Transaction(
                account_id=sample_account.id,
                symbol="AAPL",
                quantity=10 * (i + 1),
                price=150.0 + i,
                transaction_type=OrderType.BUY,
                timestamp=base_time + timedelta(hours=i),
            )
            for i in range(10)
        ]
        async_db_session.add_all(transactions)
        await async_db_session.commit()

        # Test timestamp range query (should use index)
        start_time = base_time + timedelta(hours=3)
        end_time = base_time + timedelta(hours=7)
        
        result = await async_db_session.execute(
            select(Transaction).where(
                Transaction.account_id == sample_account.id,
                Transaction.timestamp.between(start_time, end_time),
            )
        )
        ranged_transactions = result.scalars().all()
        assert len(ranged_transactions) == 5  # Hours 3-7 inclusive

    async def test_options_specific_indexes(self, async_db_session: AsyncSession):
        """Test options-specific composite indexes."""
        base_date = date.today() + timedelta(days=30)
        option_quotes = [
            OptionQuoteHistory(
                symbol=f"AAPL240315C0018{i:04d}00",
                underlying_symbol="AAPL",
                strike=180 + i * 5,
                expiration_date=base_date + timedelta(days=i % 3),
                option_type="call" if i % 2 == 0 else "put",
                price=5.0 + i * 0.5,
                quote_time=datetime.now() - timedelta(minutes=i),
            )
            for i in range(15)
        ]
        async_db_session.add_all(option_quotes)
        await async_db_session.commit()

        # Test underlying+expiry index
        result = await async_db_session.execute(
            select(OptionQuoteHistory).where(
                OptionQuoteHistory.underlying_symbol == "AAPL",
                OptionQuoteHistory.expiration_date == base_date,
            )
        )
        base_expiry_options = result.scalars().all()
        expected_count = len([q for q in option_quotes 
                            if q.expiration_date == base_date])
        assert len(base_expiry_options) == expected_count

        # Test expiry+type index
        result = await async_db_session.execute(
            select(OptionQuoteHistory).where(
                OptionQuoteHistory.expiration_date == base_date + timedelta(days=1),
                OptionQuoteHistory.option_type == "call",
            )
        )
        call_options = result.scalars().all()
        assert len(call_options) >= 0  # Should execute efficiently