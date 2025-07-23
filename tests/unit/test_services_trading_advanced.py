"""
Advanced test coverage for TradingService.

This module provides comprehensive testing of the TradingService class,
focusing on async business logic patterns, database integration,
order management workflows, and portfolio calculations.
"""

import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import QuoteAdapter
from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.models.quotes import OptionsChain, Quote
from app.schemas.orders import (
    OrderCreate,
    OrderType,
)
from app.schemas.positions import Portfolio, PortfolioSummary
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing."""

    def __init__(self):
        self._quotes = {}
        self._historical_data = {}

    def set_quote(self, symbol: str, quote: Quote):
        """Set mock quote data."""
        self._quotes[symbol] = quote

    async def get_quote(self, symbol: str) -> Quote:
        """Get mock quote."""
        if symbol not in self._quotes:
            return Quote(
                symbol=symbol,
                current_price=100.0,
                bid=99.5,
                ask=100.5,
                high=102.0,
                low=98.0,
                volume=1000,
                market_cap=1000000.0,
            )
        return self._quotes[symbol]

    async def get_options_chain(
        self, symbol: str, expiration_date: str | None = None
    ) -> OptionsChain:
        """Get mock options chain."""
        return OptionsChain(
            symbol=symbol,
            expiration_dates=["2024-01-19"],
            strikes=[95.0, 100.0, 105.0],
            calls={},
            puts={},
        )

    async def get_historical_data(self, symbol: str, period: str = "1d") -> dict:
        """Get mock historical data."""
        return self._historical_data.get(symbol, {})


@pytest_asyncio.fixture
async def trading_service(async_db_session):
    """Create TradingService instance for testing."""
    mock_adapter = MockQuoteAdapter()
    service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")

    # Set up test quote
    mock_adapter.set_quote(
        "AAPL",
        Quote(
            symbol="AAPL",
            current_price=150.0,
            bid=149.5,
            ask=150.5,
            high=155.0,
            low=145.0,
            volume=1000000,
            market_cap=2500000000.0,
        ),
    )

    return service


@pytest_asyncio.fixture
async def sample_account(async_db_session):
    """Create sample account for testing."""
    account = DBAccount(
        owner="test_user",
        cash_balance=10000.0,
        buying_power=20000.0,
        day_trade_buying_power=25000.0,
    )
    async_db_session.add(account)
    await async_db_session.commit()
    await async_db_session.refresh(account)
    return account


class TestTradingServiceInitialization:
    """Test TradingService initialization and configuration."""

    def test_initialization_with_custom_adapter(self):
        """Test service initializes with custom quote adapter."""
        mock_adapter = MockQuoteAdapter()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test")

        assert service.quote_adapter is mock_adapter
        assert service.account_owner == "test"
        assert service.order_execution is not None
        assert service.account_validation is not None
        assert service.strategy_recognition is not None

    def test_initialization_with_default_adapter(self):
        """Test service initializes with default adapter."""
        with patch("app.adapters.config.get_adapter_factory") as mock_factory:
            mock_adapter_instance = MockQuoteAdapter()
            mock_factory.return_value.create_adapter.return_value = (
                mock_adapter_instance
            )

            service = TradingService(account_owner="test")
            assert service.quote_adapter is not None

    def test_initialization_schema_converters(self):
        """Test schema converters are properly initialized."""
        service = TradingService(quote_adapter=MockQuoteAdapter())

        assert service.account_converter is not None
        assert service.order_converter is not None
        assert service.position_converter is not None


class TestAsyncDatabaseOperations:
    """Test async database operations."""

    @pytest.mark.asyncio
    async def test_get_async_db_session(self, trading_service):
        """Test async database session retrieval."""
        session = await trading_service._get_async_db_session()
        assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_ensure_account_exists_creates_account(self, trading_service):
        """Test account creation when it doesn't exist."""
        # Clean up any existing account first
        db = await trading_service._get_async_db_session()
        from sqlalchemy import delete

        await db.execute(delete(DBAccount).where(DBAccount.owner == "test_user"))
        await db.commit()

        await trading_service._ensure_account_exists()

        # Verify account was created
        from sqlalchemy import select

        stmt = select(DBAccount).where(DBAccount.owner == "test_user")
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        assert account is not None
        assert account.owner == "test_user"
        assert account.cash_balance == 10000.0

    @pytest.mark.asyncio
    async def test_ensure_account_exists_skips_existing(
        self, trading_service, sample_account
    ):
        """Test account creation is skipped when account exists."""
        initial_balance = sample_account.cash_balance

        await trading_service._ensure_account_exists()

        # Verify account wasn't modified
        db = await trading_service._get_async_db_session()
        await db.refresh(sample_account)
        assert sample_account.cash_balance == initial_balance


class TestQuoteOperations:
    """Test quote-related operations."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, trading_service):
        """Test successful quote retrieval."""
        quote = await trading_service.get_quote("AAPL")

        assert quote.symbol == "AAPL"
        assert quote.current_price == 150.0
        assert quote.bid == 149.5
        assert quote.ask == 150.5

    @pytest.mark.asyncio
    async def test_get_quote_fallback(self, trading_service):
        """Test quote retrieval with fallback for unknown symbol."""
        quote = await trading_service.get_quote("UNKNOWN")

        assert quote.symbol == "UNKNOWN"
        assert quote.current_price == 100.0  # Default from mock

    @pytest.mark.asyncio
    async def test_get_options_chain(self, trading_service):
        """Test options chain retrieval."""
        chain = await trading_service.get_options_chain("AAPL")

        assert chain.symbol == "AAPL"
        assert len(chain.expiration_dates) > 0
        assert len(chain.strikes) > 0

    @pytest.mark.asyncio
    async def test_get_stock_quote_conversion(self, trading_service):
        """Test stock quote conversion to StockQuote schema."""
        with patch.object(trading_service, "get_quote") as mock_get_quote:
            mock_quote = Quote(
                symbol="AAPL",
                current_price=150.0,
                bid=149.5,
                ask=150.5,
                high=155.0,
                low=145.0,
                volume=1000000,
                market_cap=2500000000.0,
            )
            mock_get_quote.return_value = mock_quote

            stock_quote = await trading_service.get_stock_quote("AAPL")

            assert isinstance(stock_quote, StockQuote)
            assert stock_quote.symbol == "AAPL"
            assert stock_quote.price == 150.0


class TestOrderManagement:
    """Test order management operations."""

    @pytest.mark.asyncio
    async def test_create_order_success(self, trading_service, sample_account):
        """Test successful order creation."""
        order_create = OrderCreate(
            symbol="AAPL", quantity=10, order_type=OrderType.MARKET, side="buy"
        )

        with patch.object(
            trading_service.order_execution, "execute_order"
        ) as mock_execute:
            mock_execute.return_value.success = True
            mock_execute.return_value.order_id = str(uuid4())

            result = await trading_service.create_order(order_create)

            assert result.success is True
            assert result.order_id is not None
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_order_validation_failure(
        self, trading_service, sample_account
    ):
        """Test order creation with validation failure."""
        order_create = OrderCreate(
            symbol="AAPL",
            quantity=-10,  # Invalid negative quantity
            order_type=OrderType.MARKET,
            side="buy",
        )

        with patch.object(
            trading_service.account_validation, "validate_order"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Invalid quantity")

            with pytest.raises(ValueError, match="Invalid quantity"):
                await trading_service.create_order(order_create)

    @pytest.mark.asyncio
    async def test_get_orders_empty(self, trading_service, sample_account):
        """Test retrieving orders when none exist."""
        orders = await trading_service.get_orders()
        assert len(orders) == 0

    @pytest.mark.asyncio
    async def test_get_orders_with_data(self, trading_service, sample_account):
        """Test retrieving orders with existing data."""
        # Create sample order in database
        db = await trading_service._get_async_db_session()
        sample_order = DBOrder(
            account_id=sample_account.id,
            symbol="AAPL",
            quantity=10,
            order_type="market",
            side="buy",
            status="filled",
            filled_price=150.0,
        )
        db.add(sample_order)
        await db.commit()

        orders = await trading_service.get_orders()
        assert len(orders) == 1
        assert orders[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, trading_service, sample_account):
        """Test successful order cancellation."""
        # Create sample order
        db = await trading_service._get_async_db_session()
        sample_order = DBOrder(
            account_id=sample_account.id,
            symbol="AAPL",
            quantity=10,
            order_type="limit",
            side="buy",
            status="pending",
            limit_price=149.0,
        )
        db.add(sample_order)
        await db.commit()
        await db.refresh(sample_order)

        result = await trading_service.cancel_order(sample_order.id)
        assert result is True

        # Verify order was cancelled
        await db.refresh(sample_order)
        assert sample_order.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, trading_service):
        """Test cancelling non-existent order."""
        with pytest.raises(NotFoundError):
            await trading_service.cancel_order("non-existent-id")


class TestPortfolioOperations:
    """Test portfolio-related operations."""

    @pytest.mark.asyncio
    async def test_get_portfolio_empty(self, trading_service, sample_account):
        """Test portfolio retrieval when empty."""
        portfolio = await trading_service.get_portfolio()

        assert isinstance(portfolio, Portfolio)
        assert portfolio.cash_balance == 10000.0
        assert len(portfolio.positions) == 0
        assert portfolio.total_value == 10000.0

    @pytest.mark.asyncio
    async def test_get_portfolio_with_positions(self, trading_service, sample_account):
        """Test portfolio retrieval with positions."""
        # Create sample position
        db = await trading_service._get_async_db_session()
        sample_position = DBPosition(
            account_id=sample_account.id, symbol="AAPL", quantity=10, average_cost=145.0
        )
        db.add(sample_position)
        await db.commit()

        portfolio = await trading_service.get_portfolio()

        assert len(portfolio.positions) == 1
        position = portfolio.positions[0]
        assert position.symbol == "AAPL"
        assert position.quantity == 10
        assert position.average_cost == 145.0

        # Portfolio value should include position value
        expected_position_value = 10 * 150.0  # 10 shares * $150 current price
        expected_total = 10000.0 + expected_position_value
        assert abs(portfolio.total_value - expected_total) < 0.01

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self, trading_service, sample_account):
        """Test portfolio summary calculation."""
        # Create sample position
        db = await trading_service._get_async_db_session()
        sample_position = DBPosition(
            account_id=sample_account.id, symbol="AAPL", quantity=10, average_cost=145.0
        )
        db.add(sample_position)
        await db.commit()

        summary = await trading_service.get_portfolio_summary()

        assert isinstance(summary, PortfolioSummary)
        assert summary.total_value > 10000.0
        assert summary.cash_balance == 10000.0
        assert summary.positions_count == 1

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, trading_service, sample_account):
        """Test retrieving positions when none exist."""
        positions = await trading_service.get_positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_get_positions_with_data(self, trading_service, sample_account):
        """Test retrieving positions with existing data."""
        # Create sample positions
        db = await trading_service._get_async_db_session()
        positions = [
            DBPosition(
                account_id=sample_account.id,
                symbol="AAPL",
                quantity=10,
                average_cost=145.0,
            ),
            DBPosition(
                account_id=sample_account.id,
                symbol="GOOGL",
                quantity=5,
                average_cost=2500.0,
            ),
        ]
        for pos in positions:
            db.add(pos)
        await db.commit()

        retrieved_positions = await trading_service.get_positions()
        assert len(retrieved_positions) == 2

        symbols = {pos.symbol for pos in retrieved_positions}
        assert symbols == {"AAPL", "GOOGL"}


class TestAsyncConcurrency:
    """Test async concurrency and error handling."""

    @pytest.mark.asyncio
    async def test_concurrent_quote_requests(self, trading_service):
        """Test concurrent quote requests."""
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

        tasks = [trading_service.get_quote(symbol) for symbol in symbols]
        quotes = await asyncio.gather(*tasks)

        assert len(quotes) == len(symbols)
        for i, quote in enumerate(quotes):
            assert quote.symbol == symbols[i]

    @pytest.mark.asyncio
    async def test_concurrent_portfolio_operations(
        self, trading_service, sample_account
    ):
        """Test concurrent portfolio operations."""
        tasks = [
            trading_service.get_portfolio(),
            trading_service.get_portfolio_summary(),
            trading_service.get_positions(),
            trading_service.get_orders(),
        ]

        results = await asyncio.gather(*tasks)
        portfolio, summary, positions, orders = results

        assert isinstance(portfolio, Portfolio)
        assert isinstance(summary, PortfolioSummary)
        assert isinstance(positions, list)
        assert isinstance(orders, list)

    @pytest.mark.asyncio
    async def test_database_session_isolation(self, trading_service, sample_account):
        """Test database session isolation in concurrent operations."""

        async def create_position(symbol: str, quantity: int):
            db = await trading_service._get_async_db_session()
            position = DBPosition(
                account_id=sample_account.id,
                symbol=symbol,
                quantity=quantity,
                average_cost=100.0,
            )
            db.add(position)
            await db.commit()
            return position

        # Create positions concurrently
        tasks = [
            create_position("AAPL", 10),
            create_position("GOOGL", 5),
            create_position("MSFT", 15),
        ]

        positions = await asyncio.gather(*tasks)
        assert len(positions) == 3

        # Verify all positions were created
        final_positions = await trading_service.get_positions()
        assert len(final_positions) == 3


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_quote_adapter_failure(self, trading_service):
        """Test handling of quote adapter failures."""
        with patch.object(trading_service.quote_adapter, "get_quote") as mock_get_quote:
            mock_get_quote.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_database_connection_failure(self, trading_service):
        """Test handling of database connection failures."""
        with patch.object(trading_service, "_get_async_db_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await trading_service.get_portfolio()

    @pytest.mark.asyncio
    async def test_invalid_order_data(self, trading_service, sample_account):
        """Test handling of invalid order data."""
        invalid_order = OrderCreate(
            symbol="",  # Empty symbol
            quantity=0,  # Zero quantity
            order_type=OrderType.MARKET,
            side="buy",
        )

        with pytest.raises(ValueError):
            await trading_service.create_order(invalid_order)

    @pytest.mark.asyncio
    async def test_account_not_found_handling(self):
        """Test handling when account doesn't exist."""
        mock_adapter = MockQuoteAdapter()
        service = TradingService(
            quote_adapter=mock_adapter, account_owner="nonexistent_user"
        )

        # This should create the account automatically
        await service._ensure_account_exists()

        # Verify the account was created
        portfolio = await service.get_portfolio()
        assert portfolio.cash_balance == 10000.0


class TestBusinessLogicValidation:
    """Test business logic validation and rules."""

    @pytest.mark.asyncio
    async def test_buying_power_calculation(self, trading_service, sample_account):
        """Test buying power calculation with positions."""
        # Create leveraged position
        db = await trading_service._get_async_db_session()
        position = DBPosition(
            account_id=sample_account.id,
            symbol="AAPL",
            quantity=100,
            average_cost=150.0,
        )
        db.add(position)
        await db.commit()

        portfolio = await trading_service.get_portfolio()

        # Buying power should account for position value
        position_value = 100 * 150.0  # Current market value
        expected_total_value = 10000.0 + position_value
        assert abs(portfolio.total_value - expected_total_value) < 0.01

    @pytest.mark.asyncio
    async def test_portfolio_diversity_metrics(self, trading_service, sample_account):
        """Test portfolio diversity calculations."""
        # Create diverse positions
        db = await trading_service._get_async_db_session()
        positions = [
            DBPosition(
                account_id=sample_account.id,
                symbol="AAPL",
                quantity=10,
                average_cost=150.0,
            ),
            DBPosition(
                account_id=sample_account.id,
                symbol="GOOGL",
                quantity=2,
                average_cost=2500.0,
            ),
            DBPosition(
                account_id=sample_account.id,
                symbol="MSFT",
                quantity=15,
                average_cost=300.0,
            ),
        ]

        for pos in positions:
            db.add(pos)
        await db.commit()

        portfolio = await trading_service.get_portfolio()

        # Should have multiple positions
        assert len(portfolio.positions) == 3

        # Calculate total position value
        total_position_value = sum(
            pos.quantity * pos.current_price for pos in portfolio.positions
        )

        # Total portfolio value should include cash + positions
        expected_total = 10000.0 + total_position_value
        assert abs(portfolio.total_value - expected_total) < 0.01


class TestPerformanceOptimization:
    """Test performance optimization patterns."""

    @pytest.mark.asyncio
    async def test_batch_quote_operations(self, trading_service):
        """Test batch quote operations for performance."""
        symbols = ["AAPL", "GOOGL", "MSFT"]

        start_time = asyncio.get_event_loop().time()

        # Get quotes concurrently
        quotes = await asyncio.gather(
            *[trading_service.get_quote(symbol) for symbol in symbols]
        )

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        assert len(quotes) == len(symbols)
        # Should complete within reasonable time (allowing for async overhead)
        assert execution_time < 1.0

    @pytest.mark.asyncio
    async def test_database_query_optimization(self, trading_service, sample_account):
        """Test database query optimization."""
        # Create multiple positions
        db = await trading_service._get_async_db_session()
        for i in range(10):
            position = DBPosition(
                account_id=sample_account.id,
                symbol=f"STOCK{i}",
                quantity=10,
                average_cost=100.0,
            )
            db.add(position)
        await db.commit()

        start_time = asyncio.get_event_loop().time()

        # Should efficiently load all positions in single query
        positions = await trading_service.get_positions()

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        assert len(positions) == 10
        # Should complete within reasonable time
        assert execution_time < 0.5
