"""
Comprehensive tests for TradingService - the core business logic service.

Tests cover:
- Service initialization and configuration
- Async database operations
- Quote adapter integration
- Order management (create, get, cancel)
- Portfolio operations (positions, balances, summaries)
- Options trading features (Greeks, chains, strategies)
- Multi-leg order processing
- Risk management integration
- Error handling and edge cases
- Database transaction management
- Schema converter integration
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError
from app.models.assets import Stock, Call, Put, Option
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.models.database.trading import (
    Account as DBAccount,
    Order as DBOrder,
    Position as DBPosition,
)
from app.schemas.orders import (
    Order,
    OrderCreate,
    OrderStatus,
    OrderType,
    OrderCondition,
)
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService
from app.adapters.base import QuoteAdapter


@pytest.fixture
def mock_quote_adapter():
    """Mock quote adapter for testing."""
    adapter = Mock(spec=QuoteAdapter)
    adapter.get_quote = AsyncMock()
    adapter.get_options_chain = AsyncMock()
    adapter.get_test_scenarios = Mock(return_value={})
    adapter.get_available_symbols = Mock(return_value=["AAPL", "GOOGL", "MSFT"])
    adapter.get_sample_data_info = Mock(return_value={})
    adapter.get_expiration_dates = Mock(return_value=[])
    return adapter


@pytest.fixture
def sample_stock_quote():
    """Sample stock quote for testing."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        price=150.00,
        bid=149.95,
        ask=150.05,
        quote_date=datetime.now(),
    )


@pytest.fixture
def sample_option_quote():
    """Sample option quote for testing."""
    return OptionQuote(
        asset=Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today() + timedelta(days=30),
        ),
        price=5.50,
        bid=5.45,
        ask=5.55,
        quote_date=datetime.now(),
        underlying_price=150.00,
        delta=0.6,
        gamma=0.05,
        theta=-0.02,
        vega=0.15,
        iv=0.25,
    )


@pytest.fixture
def sample_order_create():
    """Sample order creation data."""
    return OrderCreate(
        symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.00
    )


@pytest.fixture
def sample_db_account():
    """Sample database account."""
    return DBAccount(id="test-account-id", owner="default", cash_balance=10000.0)


@pytest.fixture
def sample_db_order():
    """Sample database order."""
    return DBOrder(
        id="test-order-id",
        account_id="test-account-id",
        symbol="AAPL",
        order_type=OrderType.BUY,
        quantity=100,
        price=150.00,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_db_position():
    """Sample database position."""
    return DBPosition(
        id="test-position-id",
        account_id="test-account-id",
        symbol="AAPL",
        quantity=100,
        avg_price=145.00,
    )


@pytest.fixture
def mock_async_session():
    """Mock async database session."""
    session = Mock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.add = Mock()

    # Mock result for queries
    result = Mock()
    result.scalar_one_or_none = Mock()
    result.scalars = Mock()
    session.execute.return_value = result

    return session


@pytest.fixture
def trading_service(mock_quote_adapter):
    """Trading service instance for testing."""
    return TradingService(quote_adapter=mock_quote_adapter, account_owner="test_user")


class TestTradingServiceInitialization:
    """Test trading service initialization and configuration."""

    def test_initialization_with_adapter(self, mock_quote_adapter):
        """Test service initialization with provided adapter."""
        service = TradingService(quote_adapter=mock_quote_adapter, account_owner="test")

        assert service.quote_adapter == mock_quote_adapter
        assert service.account_owner == "test"
        assert service.order_execution is not None
        assert service.account_validation is not None
        assert service.strategy_recognition is not None
        assert service.account_converter is not None
        assert service.order_converter is not None
        assert service.position_converter is not None

    def test_initialization_default_adapter(self):
        """Test service initialization with default adapter."""
        with patch("app.services.trading_service.get_adapter_factory") as mock_factory:
            mock_adapter = Mock(spec=QuoteAdapter)
            mock_factory.return_value.create_adapter.return_value = mock_adapter

            service = TradingService()

            assert service.quote_adapter == mock_adapter
            assert service.account_owner == "default"

    def test_initialization_fallback_adapters(self):
        """Test adapter fallback mechanism."""
        with patch("app.services.trading_service.get_adapter_factory") as mock_factory:
            # First adapter returns None
            mock_factory.return_value.create_adapter.side_effect = [None, None]

            with patch(
                "app.services.trading_service.DevDataQuoteAdapter"
            ) as mock_dev_adapter:
                mock_dev_instance = Mock(spec=QuoteAdapter)
                mock_dev_adapter.return_value = mock_dev_instance

                service = TradingService()

                assert service.quote_adapter == mock_dev_instance

    def test_initialization_components(self, trading_service):
        """Test all service components are properly initialized."""
        # Core components
        assert hasattr(trading_service, "quote_adapter")
        assert hasattr(trading_service, "order_execution")
        assert hasattr(trading_service, "account_validation")
        assert hasattr(trading_service, "strategy_recognition")

        # Schema converters
        assert hasattr(trading_service, "account_converter")
        assert hasattr(trading_service, "order_converter")
        assert hasattr(trading_service, "position_converter")

        # Placeholders
        assert trading_service.margin_service is None
        assert trading_service.legs == []


class TestAsyncDatabaseOperations:
    """Test async database operations."""

    @pytest.mark.asyncio
    async def test_get_async_db_session(self, trading_service):
        """Test getting async database session."""
        with patch(
            "app.services.trading_service.get_async_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_async_gen = AsyncMock()
            mock_async_gen.__anext__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value = mock_async_gen

            session = await trading_service._get_async_db_session()

            assert session == mock_session
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_account_exists_new_account(
        self, trading_service, mock_async_session
    ):
        """Test account creation when account doesn't exist."""
        # Mock no existing account
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            await trading_service._ensure_account_exists()

            # Verify account creation
            mock_async_session.add.assert_called()
            mock_async_session.commit.assert_called()
            mock_async_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_ensure_account_exists_existing_account(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test when account already exists."""
        # Mock existing account
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            await trading_service._ensure_account_exists()

            # Verify no account creation
            mock_async_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_account_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successful account retrieval."""
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(
                trading_service, "_ensure_account_exists", new_callable=AsyncMock
            ):
                account = await trading_service._get_account()

                assert account == sample_db_account

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, trading_service, mock_async_session):
        """Test account not found error."""
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(
                trading_service, "_ensure_account_exists", new_callable=AsyncMock
            ):
                with pytest.raises(NotFoundError, match="Account for owner"):
                    await trading_service._get_account()


class TestAccountOperations:
    """Test account-related operations."""

    @pytest.mark.asyncio
    async def test_get_account_balance(self, trading_service, sample_db_account):
        """Test getting account balance."""
        with patch.object(
            trading_service, "_get_account", return_value=sample_db_account
        ):
            balance = await trading_service.get_account_balance()

            assert balance == 10000.0
            assert isinstance(balance, float)


class TestQuoteOperations:
    """Test quote retrieval and processing."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, trading_service, sample_stock_quote):
        """Test successful quote retrieval."""
        trading_service.quote_adapter.get_quote.return_value = sample_stock_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_quote("AAPL")

            assert isinstance(result, StockQuote)
            assert result.symbol == "AAPL"
            assert result.price == 150.00
            assert result.volume == 0  # Default when not available

    @pytest.mark.asyncio
    async def test_get_quote_invalid_symbol(self, trading_service):
        """Test quote retrieval with invalid symbol."""
        with patch("app.services.trading_service.asset_factory", return_value=None):
            with pytest.raises(NotFoundError, match="Invalid symbol"):
                await trading_service.get_quote("INVALID")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_failure(self, trading_service):
        """Test quote retrieval when adapter fails."""
        trading_service.quote_adapter.get_quote.return_value = None

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            with pytest.raises(NotFoundError, match="Symbol AAPL not found"):
                await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_exception(self, trading_service):
        """Test quote retrieval with adapter exception."""
        trading_service.quote_adapter.get_quote.side_effect = Exception("Adapter error")

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            with pytest.raises(
                NotFoundError, match="Symbol AAPL not found: Adapter error"
            ):
                await trading_service.get_quote("AAPL")


class TestOrderOperations:
    """Test order management operations."""

    @pytest.mark.asyncio
    async def test_create_order_success(
        self,
        trading_service,
        sample_order_create,
        sample_db_account,
        sample_stock_quote,
        mock_async_session,
    ):
        """Test successful order creation."""
        # Mock quote validation
        with patch.object(
            trading_service, "get_quote", return_value=sample_stock_quote
        ):
            # Mock database operations
            mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
                sample_db_account
            )

            # Mock order converter
            mock_order = Order(
                id="test-order-id",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )

            with patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ):
                with patch.object(
                    trading_service.order_converter,
                    "to_schema",
                    return_value=mock_order,
                ):
                    result = await trading_service.create_order(sample_order_create)

                    assert isinstance(result, Order)
                    assert result.symbol == "AAPL"
                    assert result.order_type == OrderType.BUY
                    assert result.quantity == 100

                    # Verify database operations
                    mock_async_session.add.assert_called()
                    mock_async_session.commit.assert_called()
                    mock_async_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_create_order_invalid_symbol(
        self, trading_service, sample_order_create
    ):
        """Test order creation with invalid symbol."""
        with patch.object(
            trading_service, "get_quote", side_effect=NotFoundError("Symbol not found")
        ):
            with pytest.raises(NotFoundError):
                await trading_service.create_order(sample_order_create)

    @pytest.mark.asyncio
    async def test_get_orders_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test getting all orders."""
        # Mock database response
        mock_orders = [Mock(spec=DBOrder), Mock(spec=DBOrder)]
        mock_async_session.execute.return_value.scalars.return_value.all.return_value = (
            mock_orders
        )
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )

        # Mock order converter
        mock_converted_orders = [
            Order(
                id="1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
            Order(
                id="2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                status=OrderStatus.FILLED,
                created_at=datetime.now(),
            ),
        ]

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(
                trading_service.order_converter,
                "to_schema",
                side_effect=mock_converted_orders,
            ):
                orders = await trading_service.get_orders()

                assert len(orders) == 2
                assert all(isinstance(order, Order) for order in orders)

    @pytest.mark.asyncio
    async def test_get_order_success(
        self, trading_service, mock_async_session, sample_db_account, sample_db_order
    ):
        """Test getting specific order."""
        mock_async_session.execute.return_value.scalar_one_or_none.side_effect = [
            sample_db_account,
            sample_db_order,
        ]

        mock_converted_order = Order(
            id="test-order-id",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(
                trading_service.order_converter,
                "to_schema",
                return_value=mock_converted_order,
            ):
                order = await trading_service.get_order("test-order-id")

                assert isinstance(order, Order)
                assert order.id == "test-order-id"

    @pytest.mark.asyncio
    async def test_get_order_not_found(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test getting non-existent order."""
        mock_async_session.execute.return_value.scalar_one_or_none.side_effect = [
            sample_db_account,
            None,
        ]

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with pytest.raises(NotFoundError, match="Order .* not found"):
                await trading_service.get_order("non-existent")

    @pytest.mark.asyncio
    async def test_cancel_order_success(
        self, trading_service, mock_async_session, sample_db_account, sample_db_order
    ):
        """Test successful order cancellation."""
        mock_async_session.execute.return_value.scalar_one_or_none.side_effect = [
            sample_db_account,
            sample_db_order,
        ]

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            result = await trading_service.cancel_order("test-order-id")

            assert "message" in result
            assert "cancelled successfully" in result["message"]
            assert sample_db_order.status == OrderStatus.CANCELLED
            mock_async_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test cancelling non-existent order."""
        mock_async_session.execute.return_value.scalar_one_or_none.side_effect = [
            sample_db_account,
            None,
        ]

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with pytest.raises(NotFoundError, match="Order .* not found"):
                await trading_service.cancel_order("non-existent")


class TestPortfolioOperations:
    """Test portfolio-related operations."""

    @pytest.mark.asyncio
    async def test_get_portfolio_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successful portfolio retrieval."""
        # Mock positions
        mock_positions = [
            Mock(symbol="AAPL", quantity=100, avg_price=145.00),
            Mock(symbol="GOOGL", quantity=50, avg_price=2800.00),
        ]

        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )
        mock_async_session.execute.return_value.scalars.return_value.all.return_value = (
            mock_positions
        )

        # Mock quotes
        sample_quotes = {
            "AAPL": StockQuote(
                symbol="AAPL",
                price=150.00,
                change=0,
                change_percent=0,
                volume=0,
                last_updated=datetime.now(),
            ),
            "GOOGL": StockQuote(
                symbol="GOOGL",
                price=2900.00,
                change=0,
                change_percent=0,
                volume=0,
                last_updated=datetime.now(),
            ),
        }

        # Mock position converter
        mock_converted_positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=145.00,
                current_price=150.00,
                market_value=15000.00,
                unrealized_pnl=500.00,
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                avg_price=2800.00,
                current_price=2900.00,
                market_value=145000.00,
                unrealized_pnl=5000.00,
            ),
        ]

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(
                trading_service, "get_quote", side_effect=lambda sym: sample_quotes[sym]
            ):
                with patch.object(
                    trading_service.position_converter,
                    "to_schema",
                    side_effect=mock_converted_positions,
                ):
                    portfolio = await trading_service.get_portfolio()

                    assert isinstance(portfolio, Portfolio)
                    assert portfolio.cash_balance == 10000.0
                    assert len(portfolio.positions) == 2
                    assert portfolio.total_value > 0

    @pytest.mark.asyncio
    async def test_get_portfolio_with_quote_errors(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test portfolio retrieval when some quotes fail."""
        # Mock positions
        mock_positions = [
            Mock(symbol="AAPL", quantity=100, avg_price=145.00),
            Mock(
                symbol="INVALID", quantity=50, avg_price=100.00
            ),  # This will fail quote lookup
        ]

        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )
        mock_async_session.execute.return_value.scalars.return_value.all.return_value = (
            mock_positions
        )

        # Mock quote that succeeds for AAPL but fails for INVALID
        def mock_get_quote(symbol):
            if symbol == "AAPL":
                return StockQuote(
                    symbol="AAPL",
                    price=150.00,
                    change=0,
                    change_percent=0,
                    volume=0,
                    last_updated=datetime.now(),
                )
            else:
                raise NotFoundError("Symbol not found")

        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=145.00,
            current_price=150.00,
            market_value=15000.00,
            unrealized_pnl=500.00,
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with patch.object(trading_service, "get_quote", side_effect=mock_get_quote):
                with patch.object(
                    trading_service.position_converter,
                    "to_schema",
                    return_value=mock_position,
                ):
                    portfolio = await trading_service.get_portfolio()

                    # Should only include positions with valid quotes
                    assert len(portfolio.positions) == 1
                    assert portfolio.positions[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self, trading_service):
        """Test portfolio summary calculation."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=145.00,
                    current_price=150.00,
                    market_value=15000.00,
                    unrealized_pnl=500.00,
                )
            ],
            daily_pnl=500.0,
            total_pnl=500.0,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            summary = await trading_service.get_portfolio_summary()

            assert isinstance(summary, PortfolioSummary)
            assert summary.total_value == 25000.0
            assert summary.cash_balance == 10000.0
            assert summary.invested_value == 15000.0
            assert summary.total_pnl == 500.0

    @pytest.mark.asyncio
    async def test_get_positions(self, trading_service):
        """Test getting positions from portfolio."""
        mock_positions = [
            Position(
                symbol="AAPL", quantity=100, avg_price=145.00, current_price=150.00
            ),
            Position(
                symbol="GOOGL", quantity=50, avg_price=2800.00, current_price=2900.00
            ),
        ]

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=mock_positions,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            positions = await trading_service.get_positions()

            assert len(positions) == 2
            assert all(isinstance(pos, Position) for pos in positions)

    @pytest.mark.asyncio
    async def test_get_position_success(self, trading_service):
        """Test getting specific position."""
        target_position = Position(
            symbol="AAPL", quantity=100, avg_price=145.00, current_price=150.00
        )
        other_position = Position(
            symbol="GOOGL", quantity=50, avg_price=2800.00, current_price=2900.00
        )

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[target_position, other_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            position = await trading_service.get_position("AAPL")

            assert position.symbol == "AAPL"
            assert position.quantity == 100

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, trading_service):
        """Test getting non-existent position."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            with pytest.raises(NotFoundError, match="Position for symbol .* not found"):
                await trading_service.get_position("AAPL")


class TestOptionsOperations:
    """Test options trading features."""

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_success(
        self, trading_service, sample_option_quote
    ):
        """Test enhanced quote retrieval."""
        trading_service.quote_adapter.get_quote.return_value = sample_option_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            )

            result = await trading_service.get_enhanced_quote("AAPL240119C150")

            assert isinstance(result, OptionQuote)
            assert result.price == 5.50
            assert result.delta == 0.6

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_no_quote(self, trading_service):
        """Test enhanced quote when no quote available."""
        trading_service.quote_adapter.get_quote.return_value = None

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            with pytest.raises(NotFoundError, match="No quote available"):
                await trading_service.get_enhanced_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, trading_service):
        """Test options chain retrieval."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=150.00,
            expiration_date=date.today() + timedelta(days=30),
            calls=[],
            puts=[],
        )

        trading_service.quote_adapter.get_options_chain.return_value = mock_chain

        result = await trading_service.get_options_chain("AAPL")

        assert isinstance(result, OptionsChain)
        assert result.underlying_symbol == "AAPL"
        assert result.underlying_price == 150.00

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self, trading_service):
        """Test options chain when not found."""
        trading_service.quote_adapter.get_options_chain.return_value = None

        with pytest.raises(NotFoundError, match="No options chain found"):
            await trading_service.get_options_chain("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_success(self, trading_service, sample_option_quote):
        """Test Greeks calculation."""
        trading_service.quote_adapter.get_quote.side_effect = [
            sample_option_quote,  # Option quote
            Quote(
                asset=Stock(symbol="AAPL"),
                price=150.00,
                bid=149.95,
                ask=150.05,
                quote_date=datetime.now(),
            ),  # Underlying quote
        ]

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_option = Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            )
            mock_factory.return_value = mock_option

            with patch(
                "app.services.trading_service.calculate_option_greeks"
            ) as mock_calc:
                mock_calc.return_value = {
                    "delta": 0.6,
                    "gamma": 0.05,
                    "theta": -0.02,
                    "vega": 0.15,
                    "rho": 0.08,
                }

                result = await trading_service.calculate_greeks("AAPL240119C150")

                assert "delta" in result
                assert "gamma" in result
                assert result["delta"] == 0.6

    @pytest.mark.asyncio
    async def test_calculate_greeks_not_option(self, trading_service):
        """Test Greeks calculation with non-option symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            with pytest.raises(ValueError, match="is not an option"):
                await trading_service.calculate_greeks("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_insufficient_data(self, trading_service):
        """Test Greeks calculation with insufficient pricing data."""
        # Mock option quote with no price
        option_quote = OptionQuote(
            asset=Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            ),
            price=None,  # No price
            bid=5.45,
            ask=5.55,
            quote_date=datetime.now(),
            underlying_price=150.00,
        )

        trading_service.quote_adapter.get_quote.return_value = option_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            )

            with pytest.raises(ValueError, match="Insufficient pricing data"):
                await trading_service.calculate_greeks("AAPL240119C150")


class TestMultiLegOrders:
    """Test multi-leg order processing."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successful multi-leg order creation."""

        # Mock order data with legs
        class MockLeg:
            def __init__(self, symbol, quantity, order_type, price=None):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self):
                self.legs = [
                    MockLeg("AAPL240119C150", 10, OrderType.BUY, 5.50),
                    MockLeg("AAPL240119C160", -10, OrderType.SELL, 2.50),
                ]

        mock_order_data = MockOrderData()
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            result = await trading_service.create_multi_leg_order(mock_order_data)

            assert isinstance(result, Order)
            assert "MULTI_LEG" in result.symbol
            assert result.order_type == OrderType.BUY  # First leg's order type
            assert result.status == OrderStatus.FILLED

            # Verify database operations
            mock_async_session.add.assert_called()
            mock_async_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request(self, trading_service):
        """Test creating multi-leg order from request data."""
        legs = [
            {"symbol": "AAPL240119C150", "quantity": 10, "side": "buy"},
            {"symbol": "AAPL240119C160", "quantity": 10, "side": "sell"},
        ]

        with patch.object(trading_service, "create_multi_leg_order") as mock_create:
            mock_order = Order(
                id="test-multi-leg",
                symbol="MULTI_LEG_2_LEGS",
                order_type=OrderType.BUY,
                quantity=20,
                status=OrderStatus.FILLED,
                created_at=datetime.now(),
            )
            mock_create.return_value = mock_order

            result = await trading_service.create_multi_leg_order_from_request(
                legs, "limit", 3.00
            )

            assert isinstance(result, Order)
            mock_create.assert_called_once()


class TestValidationAndErrorHandling:
    """Test validation and error handling."""

    @pytest.mark.asyncio
    async def test_validate_account_state_success(self, trading_service):
        """Test successful account state validation."""
        mock_positions = [
            Position(
                symbol="AAPL", quantity=100, avg_price=145.00, current_price=150.00
            )
        ]

        with patch.object(trading_service, "get_account_balance", return_value=10000.0):
            with patch.object(
                trading_service, "get_positions", return_value=mock_positions
            ):
                result = await trading_service.validate_account_state()

                assert isinstance(result, bool)
                # Result depends on account validation logic

    @pytest.mark.asyncio
    async def test_database_error_handling(self, trading_service, mock_async_session):
        """Test database error handling."""
        mock_async_session.execute.side_effect = Exception("Database error")

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            with pytest.raises(Exception):
                await trading_service.get_account_balance()

    def test_test_data_methods(self, trading_service):
        """Test test data utility methods."""
        # Test scenarios
        scenarios = trading_service.get_test_scenarios()
        assert isinstance(scenarios, dict)

        # Available symbols
        symbols = trading_service.get_available_symbols()
        assert isinstance(symbols, list)

        # Sample data info
        info = trading_service.get_sample_data_info()
        assert isinstance(info, dict)

        # Expiration dates
        dates = trading_service.get_expiration_dates("AAPL")
        assert isinstance(dates, list)

    def test_set_test_date(self, trading_service):
        """Test setting test data date."""
        # Should not raise exception
        trading_service.set_test_date("2023-01-01")

        # Verify adapter method was called
        trading_service.quote_adapter.set_date.assert_called_with("2023-01-01")


class TestMarketDataMethods:
    """Test market data utility methods."""

    @pytest.mark.asyncio
    async def test_find_tradable_options_success(self, trading_service):
        """Test finding tradable options."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=150.00,
            expiration_date=date.today() + timedelta(days=30),
            calls=[
                OptionQuote(
                    asset=Call(
                        underlying=Stock(symbol="AAPL"),
                        strike=150.0,
                        expiration_date=date.today() + timedelta(days=30),
                    ),
                    price=5.50,
                    bid=5.45,
                    ask=5.55,
                    quote_date=datetime.now(),
                    underlying_price=150.00,
                )
            ],
            puts=[],
        )

        with patch.object(
            trading_service, "get_options_chain", return_value=mock_chain
        ):
            result = await trading_service.find_tradable_options("AAPL")

            assert "symbol" in result
            assert "options" in result
            assert "total_found" in result
            assert result["symbol"] == "AAPL"
            assert isinstance(result["options"], list)

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_chain(self, trading_service):
        """Test finding tradable options when no chain available."""
        with patch.object(
            trading_service, "get_options_chain", side_effect=NotFoundError("No chain")
        ):
            result = await trading_service.find_tradable_options("INVALID")

            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_option_market_data_success(
        self, trading_service, sample_option_quote
    ):
        """Test getting option market data."""
        trading_service.quote_adapter.get_quote.return_value = sample_option_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            )

            result = await trading_service.get_option_market_data("AAPL240119C150")

            assert "option_id" in result
            assert "symbol" in result
            assert "greeks" in result
            assert result["option_id"] == "AAPL240119C150"

    @pytest.mark.asyncio
    async def test_get_option_market_data_invalid_symbol(self, trading_service):
        """Test getting option market data with invalid symbol."""
        with patch(
            "app.services.trading_service.asset_factory",
            return_value=Stock(symbol="AAPL"),
        ):
            result = await trading_service.get_option_market_data("AAPL")

            assert "error" in result
            assert "Invalid option symbol" in result["error"]

    @pytest.mark.asyncio
    async def test_get_stock_price_success(self, trading_service, sample_stock_quote):
        """Test getting stock price."""
        with patch.object(
            trading_service, "get_enhanced_quote", return_value=sample_stock_quote
        ):
            with patch(
                "app.services.trading_service.asset_factory",
                return_value=Stock(symbol="AAPL"),
            ):
                result = await trading_service.get_stock_price("AAPL")

                assert "symbol" in result
                assert "price" in result
                assert "change" in result
                assert result["symbol"] == "AAPL"
                assert result["price"] == 150.00

    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_symbol(self, trading_service):
        """Test getting stock price with invalid symbol."""
        with patch("app.services.trading_service.asset_factory", return_value=None):
            result = await trading_service.get_stock_price("INVALID")

            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_stock_info_with_adapter_method(self, trading_service):
        """Test getting stock info when adapter has the method."""
        mock_info = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
        }

        trading_service.quote_adapter.get_stock_info = AsyncMock(return_value=mock_info)

        with patch(
            "app.services.trading_service.asset_factory",
            return_value=Stock(symbol="AAPL"),
        ):
            result = await trading_service.get_stock_info("AAPL")

            assert result == mock_info

    @pytest.mark.asyncio
    async def test_get_stock_info_fallback(self, trading_service, sample_stock_quote):
        """Test getting stock info with fallback method."""
        # Adapter doesn't have get_stock_info method
        del trading_service.quote_adapter.get_stock_info

        with patch.object(
            trading_service, "get_enhanced_quote", return_value=sample_stock_quote
        ):
            with patch(
                "app.services.trading_service.asset_factory",
                return_value=Stock(symbol="AAPL"),
            ):
                result = await trading_service.get_stock_info("AAPL")

                assert "symbol" in result
                assert "company_name" in result
                assert result["symbol"] == "AAPL"


class TestExpirationSimulation:
    """Test options expiration simulation."""

    @pytest.mark.asyncio
    async def test_simulate_expiration_success(self, trading_service):
        """Test successful expiration simulation."""
        # Mock portfolio with option positions
        mock_positions = [
            Position(
                symbol="AAPL240119C150",  # ITM call
                quantity=10,
                avg_price=3.50,
                current_price=5.50,
            ),
            Position(
                symbol="AAPL240119P140",  # OTM put
                quantity=5,
                avg_price=2.00,
                current_price=0.50,
            ),
        ]

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=mock_positions,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Mock quotes
        option_quotes = {
            "AAPL240119C150": OptionQuote(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=150.0,
                    expiration_date=date.today(),
                ),
                price=5.50,
                bid=5.45,
                ask=5.55,
                quote_date=datetime.now(),
                underlying_price=155.00,
            ),
            "AAPL240119P140": OptionQuote(
                asset=Put(
                    underlying=Stock(symbol="AAPL"),
                    strike=140.0,
                    expiration_date=date.today(),
                ),
                price=0.50,
                bid=0.45,
                ask=0.55,
                quote_date=datetime.now(),
                underlying_price=155.00,
            ),
            "AAPL": Quote(
                asset=Stock(symbol="AAPL"),
                price=155.00,
                bid=154.95,
                ask=155.05,
                quote_date=datetime.now(),
            ),
        }

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            with patch.object(
                trading_service,
                "get_enhanced_quote",
                side_effect=lambda sym: option_quotes[sym],
            ):
                with patch(
                    "app.services.trading_service.asset_factory"
                ) as mock_factory:

                    def asset_side_effect(symbol):
                        if "C150" in symbol:
                            return Call(
                                underlying=Stock(symbol="AAPL"),
                                strike=150.0,
                                expiration_date=date.today(),
                            )
                        elif "P140" in symbol:
                            return Put(
                                underlying=Stock(symbol="AAPL"),
                                strike=140.0,
                                expiration_date=date.today(),
                            )
                        else:
                            return Stock(symbol=symbol)

                    mock_factory.side_effect = asset_side_effect

                    result = await trading_service.simulate_expiration()

                    assert "processing_date" in result
                    assert "expiring_positions" in result
                    assert "expiring_options" in result
                    assert "total_impact" in result
                    assert isinstance(result["expiring_options"], list)

    @pytest.mark.asyncio
    async def test_simulate_expiration_no_options(self, trading_service):
        """Test expiration simulation with no option positions."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[
                Position(
                    symbol="AAPL", quantity=100, avg_price=145.00, current_price=150.00
                )
            ],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            result = await trading_service.simulate_expiration()

            assert result["expiring_positions"] == 0
            assert result["total_impact"] == 0.0

    @pytest.mark.asyncio
    async def test_simulate_expiration_error_handling(self, trading_service):
        """Test expiration simulation error handling."""
        with patch.object(
            trading_service, "get_portfolio", side_effect=Exception("Portfolio error")
        ):
            result = await trading_service.simulate_expiration()

            assert "error" in result
            assert "Simulation failed" in result["error"]


class TestPerformanceAndCaching:
    """Test performance optimizations and caching behavior."""

    @pytest.mark.asyncio
    async def test_multiple_database_calls_efficiency(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test that multiple operations use database efficiently."""
        mock_async_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_db_account
        )

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            # Multiple operations that should reuse database connections
            balance1 = await trading_service.get_account_balance()
            balance2 = await trading_service.get_account_balance()

            assert balance1 == balance2 == 10000.0
            # Verify database session was called multiple times
            assert mock_async_session.close.call_count >= 2

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, trading_service):
        """Test handling of concurrent operations."""
        import asyncio

        # Mock successful operations
        with patch.object(trading_service, "get_account_balance", return_value=10000.0):
            # Run multiple operations concurrently
            tasks = [
                trading_service.get_account_balance(),
                trading_service.get_account_balance(),
                trading_service.get_account_balance(),
            ]

            results = await asyncio.gather(*tasks)

            assert all(result == 10000.0 for result in results)
            assert len(results) == 3
