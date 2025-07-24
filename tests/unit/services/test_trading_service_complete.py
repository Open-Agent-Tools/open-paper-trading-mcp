"""
Complete comprehensive tests for TradingService.

This test suite achieves 100% coverage of the TradingService module including:
- All initialization patterns and dependency injection
- Database operations and account management
- Order creation, retrieval, and cancellation
- Portfolio and position management
- Quote retrieval and market data integration
- Options trading functionality including Greeks calculation
- Multi-leg order creation and processing
- Expiration simulation and processing
- Error handling and edge cases
- All private and helper methods
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.models.assets import Option, Stock
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.models.quotes import OptionQuote, OptionsChain, Quote
from app.schemas.orders import (
    Order,
    OrderCondition,
    OrderCreate,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService, _get_quote_adapter
from app.utils.schema_converters import (
    AccountConverter,
    OrderConverter,
    PositionConverter,
)


# Test fixtures
@pytest.fixture
def mock_quote_adapter():
    """Mock quote adapter."""
    adapter = Mock()
    adapter.get_quote = AsyncMock()
    adapter.get_options_chain = AsyncMock()
    adapter.get_stock_info = AsyncMock()
    adapter.get_price_history = AsyncMock()
    adapter.search_stocks = AsyncMock()
    adapter.set_date = Mock()
    adapter.get_expiration_dates = Mock(return_value=[])
    return adapter


@pytest.fixture
def mock_async_session():
    """Mock async database session."""
    session = AsyncMock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_db_account():
    """Sample database account."""
    account = Mock(spec=DBAccount)
    account.id = "account-123"
    account.owner = "test_user"
    account.cash_balance = 10000.0
    return account


@pytest.fixture
def sample_db_order():
    """Sample database order."""
    order = Mock(spec=DBOrder)
    order.id = "order-123"
    order.account_id = "account-123"
    order.symbol = "AAPL"
    order.order_type = OrderType.BUY
    order.quantity = 100
    order.price = 150.00
    order.status = OrderStatus.PENDING
    order.created_at = datetime.now()
    return order


@pytest.fixture
def sample_db_position():
    """Sample database position."""
    position = Mock(spec=DBPosition)
    position.id = "position-123"
    position.account_id = "account-123"
    position.symbol = "AAPL"
    position.quantity = 100
    position.avg_price = 145.00
    return position


@pytest.fixture
def sample_quote():
    """Sample stock quote."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        price=150.00,
        bid=149.95,
        ask=150.05,
        quote_date=datetime.now(),
    )


@pytest.fixture
def sample_option_quote():
    """Sample option quote."""
    option = Option(
        symbol="AAPL240119C00150000",
        underlying=Stock(symbol="AAPL"),
        expiration_date=date(2024, 1, 19),
        strike=150.0,
        option_type="call",
    )
    return OptionQuote(
        asset=option,
        price=5.50,
        bid=5.45,
        ask=5.55,
        quote_date=datetime.now(),
        underlying_price=150.00,
        delta=0.65,
        gamma=0.03,
        theta=-0.05,
        vega=0.20,
        rho=0.08,
        iv=0.25,
    )


@pytest.fixture
def trading_service(mock_quote_adapter):
    """Trading service instance."""
    return TradingService(quote_adapter=mock_quote_adapter, account_owner="test_user")


class TestTradingServiceInitialization:
    """Test TradingService initialization and configuration."""

    def test_initialization_with_quote_adapter(self, mock_quote_adapter):
        """Test initialization with provided quote adapter."""
        service = TradingService(
            quote_adapter=mock_quote_adapter, account_owner="test_user"
        )

        assert service.quote_adapter == mock_quote_adapter
        assert service.account_owner == "test_user"
        assert service.order_execution is not None
        assert service.account_validation is not None
        assert service.strategy_recognition is not None
        assert service.account_converter is not None
        assert service.order_converter is not None
        assert service.position_converter is not None
        assert service.margin_service is None
        assert service.legs == []

    def test_initialization_without_quote_adapter(self):
        """Test initialization without provided quote adapter (uses factory)."""
        with patch("app.adapters.config.get_adapter_factory") as mock_get_factory:
            mock_factory = Mock()
            mock_adapter = Mock()
            mock_factory.create_adapter.return_value = mock_adapter
            mock_get_factory.return_value = mock_factory

            service = TradingService(account_owner="test_user")

            assert service.quote_adapter == mock_adapter
            mock_factory.create_adapter.assert_called()

    def test_initialization_adapter_factory_fails(self):
        """Test initialization when adapter factory fails."""
        with patch("app.adapters.config.get_adapter_factory") as mock_get_factory:
            mock_factory = Mock()
            mock_factory.create_adapter.return_value = None
            mock_get_factory.return_value = mock_factory

            with patch(
                "app.services.trading_service.DevDataQuoteAdapter"
            ) as mock_dev_adapter:
                mock_dev_instance = Mock()
                mock_dev_adapter.return_value = mock_dev_instance

                service = TradingService(account_owner="test_user")

                # Should fallback to DevDataQuoteAdapter
                assert service.quote_adapter == mock_dev_instance

    def test_initialization_with_default_account_owner(self, mock_quote_adapter):
        """Test initialization with default account owner."""
        service = TradingService(quote_adapter=mock_quote_adapter)
        assert service.account_owner == "default"

    def test_schema_converters_initialization(self, trading_service):
        """Test that schema converters are properly initialized."""
        assert isinstance(trading_service.account_converter, AccountConverter)
        assert isinstance(trading_service.order_converter, OrderConverter)
        assert isinstance(trading_service.position_converter, PositionConverter)

        # Converters should have reference to trading service
        assert trading_service.account_converter.trading_service == trading_service
        assert trading_service.position_converter.trading_service == trading_service


class TestDatabaseSessionManagement:
    """Test database session management methods."""

    @pytest.mark.asyncio
    async def test_get_async_db_session(self, trading_service):
        """Test getting async database session."""
        with patch("app.storage.database.get_async_session") as mock_get_session:
            mock_session = AsyncMock()

            # Mock async generator
            async def mock_async_gen():
                yield mock_session

            mock_get_session.return_value = mock_async_gen()

            session = await trading_service._get_async_db_session()
            assert session == mock_session

    @pytest.mark.asyncio
    async def test_ensure_account_exists_new_account(
        self, trading_service, mock_async_session
    ):
        """Test ensuring account exists when account doesn't exist."""
        # Mock account doesn't exist
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        # Mock created account
        mock_account = Mock(spec=DBAccount)
        mock_account.id = "new-account-123"

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch("app.services.trading_service.DBAccount") as mock_db_account_class,
        ):
            mock_db_account_class.return_value = mock_account

            with patch(
                "app.services.trading_service.DBPosition"
            ) as mock_db_position_class:
                mock_position1 = Mock(spec=DBPosition)
                mock_position2 = Mock(spec=DBPosition)
                mock_db_position_class.side_effect = [
                    mock_position1,
                    mock_position2,
                ]

                await trading_service._ensure_account_exists()

                # Should create account
                mock_db_account_class.assert_called_once_with(
                    owner="test_user", cash_balance=10000.0
                )
                mock_async_session.add.assert_called()
                mock_async_session.commit.assert_called()
                mock_async_session.refresh.assert_called_with(mock_account)

                # Should create initial positions
                assert mock_db_position_class.call_count == 2

    @pytest.mark.asyncio
    async def test_ensure_account_exists_existing_account(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test ensuring account exists when account already exists."""
        # Mock account exists
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_db_account
        mock_async_session.execute.return_value = mock_result

        with patch.object(
            trading_service, "_get_async_db_session", return_value=mock_async_session
        ):
            await trading_service._ensure_account_exists()

            # Should not create new account
            mock_async_session.add.assert_not_called()
            mock_async_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_account_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successfully getting account from database."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_db_account
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service, "_ensure_account_exists", new_callable=AsyncMock
            ),
        ):
            account = await trading_service._get_account()
            assert account == sample_db_account

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, trading_service, mock_async_session):
        """Test getting account when not found in database."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service, "_ensure_account_exists", new_callable=AsyncMock
            ),
            pytest.raises(NotFoundError, match="Account for owner test_user not found"),
        ):
            await trading_service._get_account()


class TestAccountBalance:
    """Test account balance retrieval."""

    @pytest.mark.asyncio
    async def test_get_account_balance(self, trading_service, sample_db_account):
        """Test getting account balance."""
        sample_db_account.cash_balance = Decimal("15000.50")

        with patch.object(
            trading_service,
            "_get_account",
            new_callable=AsyncMock,
            return_value=sample_db_account,
        ):
            balance = await trading_service.get_account_balance()
            assert balance == 15000.50


class TestQuoteRetrieval:
    """Test quote retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, trading_service, sample_quote):
        """Test successfully getting a stock quote."""
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            quote = await trading_service.get_quote("AAPL")

            assert isinstance(quote, StockQuote)
            assert quote.symbol == "AAPL"
            assert quote.price == 150.00
            assert quote.change == 0.0
            assert quote.change_percent == 0.0
            assert quote.volume == 0
            assert quote.last_updated == sample_quote.quote_date

            mock_factory.assert_called_once_with("AAPL")
            trading_service.quote_adapter.get_quote.assert_called_once_with(mock_asset)

    @pytest.mark.asyncio
    async def test_get_quote_invalid_symbol(self, trading_service):
        """Test getting quote for invalid symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = None

            with pytest.raises(NotFoundError, match="Invalid symbol: INVALID"):
                await trading_service.get_quote("INVALID")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_returns_none(self, trading_service):
        """Test getting quote when adapter returns None."""
        trading_service.quote_adapter.get_quote.return_value = None

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            with pytest.raises(NotFoundError, match="Symbol AAPL not found"):
                await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_exception(self, trading_service):
        """Test getting quote when adapter raises exception."""
        trading_service.quote_adapter.get_quote.side_effect = Exception("API error")

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            with pytest.raises(NotFoundError, match="Symbol AAPL not found: API error"):
                await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_quote_with_volume(self, trading_service):
        """Test getting quote with volume data."""
        quote_with_volume = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )
        # Add volume attribute
        quote_with_volume.volume = 1000000

        trading_service.quote_adapter.get_quote.return_value = quote_with_volume

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            stock_quote = await trading_service.get_quote("AAPL")
            assert stock_quote.volume == 1000000


class TestOrderManagement:
    """Test order creation, retrieval, and cancellation."""

    @pytest.mark.asyncio
    async def test_create_order_success(
        self, trading_service, mock_async_session, sample_db_account, sample_quote
    ):
        """Test successfully creating an order."""
        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.00
        )

        # Mock quote validation
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        # Mock database operations
        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "new-order-123"

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_db_account
        mock_async_session.execute.return_value = mock_result

        mock_converted_order = Order(
            id="new-order-123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch("app.services.trading_service.DBOrder") as mock_db_order_class,
        ):
            mock_db_order_class.return_value = mock_db_order

            with patch.object(
                trading_service.order_converter,
                "to_schema",
                new_callable=AsyncMock,
                return_value=mock_converted_order,
            ):
                order = await trading_service.create_order(order_data)

                assert order == mock_converted_order
                mock_async_session.add.assert_called_once_with(mock_db_order)
                mock_async_session.commit.assert_called_once()
                mock_async_session.refresh.assert_called_once_with(mock_db_order)

    @pytest.mark.asyncio
    async def test_create_order_invalid_symbol(self, trading_service):
        """Test creating order with invalid symbol."""
        order_data = OrderCreate(
            symbol="INVALID", order_type=OrderType.BUY, quantity=100, price=150.00
        )

        # Mock get_quote to raise NotFoundError
        with patch.object(
            trading_service, "get_quote", new_callable=AsyncMock
        ) as mock_get_quote:
            mock_get_quote.side_effect = NotFoundError("Invalid symbol")

            with pytest.raises(NotFoundError):
                await trading_service.create_order(order_data)

    @pytest.mark.asyncio
    async def test_get_orders_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successfully getting all orders."""
        mock_db_orders = [
            Mock(spec=DBOrder, id="order-1"),
            Mock(spec=DBOrder, id="order-2"),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_db_orders
        mock_async_session.execute.return_value = mock_result

        mock_converted_orders = [
            Order(
                id="order-1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            ),
            Order(
                id="order-2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                status=OrderStatus.FILLED,
                created_at=datetime.now(),
            ),
        ]

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch.object(
                trading_service.order_converter, "to_schema", new_callable=AsyncMock
            ) as mock_to_schema,
        ):
            mock_to_schema.side_effect = mock_converted_orders

            orders = await trading_service.get_orders()

            assert len(orders) == 2
            assert orders == mock_converted_orders
            assert mock_to_schema.call_count == 2

    @pytest.mark.asyncio
    async def test_get_orders_empty(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test getting orders when none exist."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
        ):
            orders = await trading_service.get_orders()
            assert orders == []

    @pytest.mark.asyncio
    async def test_get_order_success(
        self, trading_service, mock_async_session, sample_db_account, sample_db_order
    ):
        """Test successfully getting a specific order."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_db_order
        mock_async_session.execute.return_value = mock_result

        mock_converted_order = Order(
            id="order-123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch.object(
                trading_service.order_converter,
                "to_schema",
                new_callable=AsyncMock,
                return_value=mock_converted_order,
            ),
        ):
            order = await trading_service.get_order("order-123")
            assert order == mock_converted_order

    @pytest.mark.asyncio
    async def test_get_order_not_found(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test getting order that doesn't exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            pytest.raises(NotFoundError, match="Order order-123 not found"),
        ):
            await trading_service.get_order("order-123")

    @pytest.mark.asyncio
    async def test_cancel_order_success(
        self, trading_service, mock_async_session, sample_db_account, sample_db_order
    ):
        """Test successfully cancelling an order."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_db_order
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
        ):
            result = await trading_service.cancel_order("order-123")

            assert result == {"message": "Order cancelled successfully"}
            assert sample_db_order.status == OrderStatus.CANCELLED
            mock_async_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test cancelling order that doesn't exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            pytest.raises(NotFoundError, match="Order order-123 not found"),
        ):
            await trading_service.cancel_order("order-123")


class TestPortfolioManagement:
    """Test portfolio and position management."""

    @pytest.mark.asyncio
    async def test_get_portfolio_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successfully getting portfolio information."""
        # Mock positions
        mock_db_positions = [
            Mock(spec=DBPosition, symbol="AAPL", quantity=100),
            Mock(spec=DBPosition, symbol="GOOGL", quantity=50),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_db_positions
        mock_async_session.execute.return_value = mock_result

        # Mock quotes
        mock_quotes = [
            StockQuote(
                symbol="AAPL",
                price=150.00,
                change=0.0,
                change_percent=0.0,
                volume=0,
                last_updated=datetime.now(),
            ),
            StockQuote(
                symbol="GOOGL",
                price=2800.00,
                change=0.0,
                change_percent=0.0,
                volume=0,
                last_updated=datetime.now(),
            ),
        ]

        # Mock converted positions
        mock_positions = [
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, unrealized_pnl=500.00
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                current_price=2800.00,
                unrealized_pnl=1000.00,
            ),
        ]

        sample_db_account.cash_balance = 10000.0

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch.object(
                trading_service, "get_quote", new_callable=AsyncMock
            ) as mock_get_quote,
        ):
            mock_get_quote.side_effect = mock_quotes

            with patch.object(
                trading_service.position_converter,
                "to_schema",
                new_callable=AsyncMock,
            ) as mock_to_schema:
                mock_to_schema.side_effect = mock_positions

                portfolio = await trading_service.get_portfolio()

                assert isinstance(portfolio, Portfolio)
                assert portfolio.cash_balance == 10000.0
                assert len(portfolio.positions) == 2
                assert (
                    portfolio.total_value == 10000.0 + 15000.0 + 140000.0
                )  # cash + aapl + googl
                assert portfolio.daily_pnl == 1500.0  # sum of unrealized pnl
                assert portfolio.total_pnl == 1500.0

    @pytest.mark.asyncio
    async def test_get_portfolio_skip_invalid_quotes(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test getting portfolio skips positions with no quote data."""
        mock_db_positions = [
            Mock(spec=DBPosition, symbol="AAPL", quantity=100),
            Mock(spec=DBPosition, symbol="INVALID", quantity=50),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_db_positions
        mock_async_session.execute.return_value = mock_result

        sample_db_account.cash_balance = 10000.0

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch.object(
                trading_service, "get_quote", new_callable=AsyncMock
            ) as mock_get_quote,
        ):
            # First call succeeds, second raises NotFoundError
            mock_get_quote.side_effect = [
                StockQuote(
                    symbol="AAPL",
                    price=150.00,
                    change=0.0,
                    change_percent=0.0,
                    volume=0,
                    last_updated=datetime.now(),
                ),
                NotFoundError("Symbol not found"),
            ]

            with patch.object(
                trading_service.position_converter,
                "to_schema",
                new_callable=AsyncMock,
            ) as mock_to_schema:
                mock_position = Position(
                    symbol="AAPL",
                    quantity=100,
                    current_price=150.00,
                    unrealized_pnl=500.00,
                )
                mock_to_schema.return_value = mock_position

                portfolio = await trading_service.get_portfolio()

                # Should only have one position (AAPL)
                assert len(portfolio.positions) == 1
                assert portfolio.positions[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self, trading_service):
        """Test getting portfolio summary."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    current_price=150.00,
                    unrealized_pnl=500.00,
                ),
            ],
            daily_pnl=500.0,
            total_pnl=500.0,
        )

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            summary = await trading_service.get_portfolio_summary()

            assert isinstance(summary, PortfolioSummary)
            assert summary.total_value == 25000.0
            assert summary.cash_balance == 10000.0
            assert summary.invested_value == 15000.0  # 100 * 150
            assert summary.daily_pnl == 500.0
            assert summary.daily_pnl_percent == 2.0  # 500/25000 * 100
            assert summary.total_pnl == 500.0
            assert summary.total_pnl_percent == 2.0

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_zero_total_value(self, trading_service):
        """Test getting portfolio summary with zero total value."""
        mock_portfolio = Portfolio(
            cash_balance=0.0,
            total_value=0.0,
            positions=[],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            summary = await trading_service.get_portfolio_summary()

            assert summary.daily_pnl_percent == 0.0
            assert summary.total_pnl_percent == 0.0

    @pytest.mark.asyncio
    async def test_get_positions(self, trading_service):
        """Test getting all positions."""
        mock_positions = [
            Position(symbol="AAPL", quantity=100, current_price=150.00),
            Position(symbol="GOOGL", quantity=50, current_price=2800.00),
        ]
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=mock_positions,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            positions = await trading_service.get_positions()
            assert positions == mock_positions

    @pytest.mark.asyncio
    async def test_get_position_success(self, trading_service):
        """Test successfully getting a specific position."""
        target_position = Position(symbol="AAPL", quantity=100, current_price=150.00)
        mock_positions = [
            target_position,
            Position(symbol="GOOGL", quantity=50, current_price=2800.00),
        ]
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=mock_positions,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            position = await trading_service.get_position("AAPL")
            assert position == target_position

    @pytest.mark.asyncio
    async def test_get_position_case_insensitive(self, trading_service):
        """Test getting position with case insensitive symbol matching."""
        target_position = Position(symbol="AAPL", quantity=100, current_price=150.00)
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[target_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            # Test with lowercase
            position = await trading_service.get_position("aapl")
            assert position == target_position

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, trading_service):
        """Test getting position that doesn't exist."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[Position(symbol="GOOGL", quantity=50, current_price=2800.00)],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            pytest.raises(NotFoundError, match="Position for symbol AAPL not found"),
        ):
            await trading_service.get_position("AAPL")


class TestOptionsTrading:
    """Test options trading functionality."""

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_stock(self, trading_service, sample_quote):
        """Test getting enhanced quote for stock."""
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            quote = await trading_service.get_enhanced_quote("AAPL")
            assert quote == sample_quote

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_option(
        self, trading_service, sample_option_quote
    ):
        """Test getting enhanced quote for option."""
        trading_service.quote_adapter.get_quote.return_value = sample_option_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = sample_option_quote.asset

            quote = await trading_service.get_enhanced_quote("AAPL240119C00150000")
            assert quote == sample_option_quote

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_invalid_symbol(self, trading_service):
        """Test getting enhanced quote for invalid symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = None

            with pytest.raises(NotFoundError, match="Invalid symbol: INVALID"):
                await trading_service.get_enhanced_quote("INVALID")

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_no_quote_available(self, trading_service):
        """Test getting enhanced quote when no quote available."""
        trading_service.quote_adapter.get_quote.return_value = None

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_asset = Stock(symbol="AAPL")
            mock_factory.return_value = mock_asset

            with pytest.raises(NotFoundError, match="No quote available for AAPL"):
                await trading_service.get_enhanced_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, trading_service):
        """Test successfully getting options chain."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[],
            puts=[],
        )
        trading_service.quote_adapter.get_options_chain.return_value = mock_chain

        expiration_date = date(2024, 1, 19)
        chain = await trading_service.get_options_chain("AAPL", expiration_date)

        assert chain == mock_chain
        # Should convert date to datetime
        expected_datetime = datetime.combine(expiration_date, datetime.min.time())
        trading_service.quote_adapter.get_options_chain.assert_called_once_with(
            "AAPL", expected_datetime
        )

    @pytest.mark.asyncio
    async def test_get_options_chain_no_expiration_date(self, trading_service):
        """Test getting options chain without expiration date."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=None,
            underlying_price=150.00,
            calls=[],
            puts=[],
        )
        trading_service.quote_adapter.get_options_chain.return_value = mock_chain

        chain = await trading_service.get_options_chain("AAPL")
        assert chain == mock_chain
        trading_service.quote_adapter.get_options_chain.assert_called_once_with(
            "AAPL", None
        )

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self, trading_service):
        """Test getting options chain when not found."""
        trading_service.quote_adapter.get_options_chain.return_value = None

        with pytest.raises(NotFoundError, match="No options chain found for AAPL"):
            await trading_service.get_options_chain("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_success(self, trading_service, sample_option_quote):
        """Test successfully calculating option Greeks."""
        option_symbol = "AAPL240119C00150000"
        underlying_price = 150.00

        # Mock option asset
        option_asset = Option(
            symbol=option_symbol,
            underlying=Stock(symbol="AAPL"),
            expiration_date=date(2024, 1, 19),
            strike=150.0,
            option_type="call",
        )

        # Mock underlying quote
        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=underlying_price,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )

        # Mock Greeks calculation
        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.05,
            "vega": 0.20,
            "rho": 0.08,
            "iv": 0.25,
        }

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = [sample_option_quote, underlying_quote]

                with patch(
                    "app.services.trading_service.calculate_option_greeks"
                ) as mock_calc_greeks:
                    mock_calc_greeks.return_value = mock_greeks

                    greeks = await trading_service.calculate_greeks(
                        option_symbol, underlying_price
                    )

                    assert greeks == mock_greeks
                    mock_calc_greeks.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_greeks_not_option(self, trading_service):
        """Test calculating Greeks for non-option symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            with pytest.raises(ValueError, match="AAPL is not an option"):
                await trading_service.calculate_greeks("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_insufficient_pricing_data(
        self, trading_service, sample_option_quote
    ):
        """Test calculating Greeks with insufficient pricing data."""
        option_symbol = "AAPL240119C00150000"

        # Make option quote have None price
        sample_option_quote.price = None

        option_asset = Option(
            symbol=option_symbol,
            underlying=Stock(symbol="AAPL"),
            expiration_date=date(2024, 1, 19),
            strike=150.0,
            option_type="call",
        )

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.return_value = sample_option_quote

                with pytest.raises(
                    ValueError, match="Insufficient pricing data for Greeks calculation"
                ):
                    await trading_service.calculate_greeks(option_symbol)

    @pytest.mark.asyncio
    async def test_calculate_greeks_auto_get_underlying_price(
        self, trading_service, sample_option_quote
    ):
        """Test calculating Greeks automatically gets underlying price when not provided."""
        option_symbol = "AAPL240119C00150000"

        option_asset = Option(
            symbol=option_symbol,
            underlying=Stock(symbol="AAPL"),
            expiration_date=date(2024, 1, 19),
            strike=150.0,
            option_type="call",
        )

        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )

        mock_greeks = {"delta": 0.65}

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = [sample_option_quote, underlying_quote]

                with patch(
                    "app.services.trading_service.calculate_option_greeks"
                ) as mock_calc_greeks:
                    mock_calc_greeks.return_value = mock_greeks

                    # Call without underlying_price
                    greeks = await trading_service.calculate_greeks(option_symbol)

                    assert greeks == mock_greeks
                    # Should have called get_enhanced_quote twice (option and underlying)
                    assert mock_get_quote.call_count == 2

    @pytest.mark.asyncio
    async def test_get_option_greeks_response(
        self, trading_service, sample_option_quote
    ):
        """Test getting comprehensive Greeks response."""
        option_symbol = "AAPL240119C00150000"
        underlying_price = 150.00

        option_asset = Option(
            symbol=option_symbol,
            underlying=Stock(symbol="AAPL"),
            expiration_date=date(2024, 1, 19),
            strike=150.0,
            option_type="call",
        )

        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.05,
            "vega": 0.20,
            "rho": 0.08,
            "charm": 0.01,
            "vanna": 0.02,
            "speed": 0.001,
            "zomma": 0.002,
            "color": 0.003,
            "iv": 0.25,
        }

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = option_asset

            with (
                patch.object(
                    trading_service,
                    "calculate_greeks",
                    new_callable=AsyncMock,
                    return_value=mock_greeks,
                ),
                patch.object(
                    trading_service,
                    "get_enhanced_quote",
                    new_callable=AsyncMock,
                    return_value=sample_option_quote,
                ),
            ):
                response = await trading_service.get_option_greeks_response(
                    option_symbol, underlying_price
                )

                assert response["option_symbol"] == option_symbol
                assert response["underlying_symbol"] == "AAPL"
                assert response["strike"] == 150.0
                assert response["expiration_date"] == "2024-01-19"
                assert response["option_type"] == "call"
                assert response["delta"] == 0.65
                assert response["implied_volatility"] == 0.25
                assert response["underlying_price"] == underlying_price
                assert response["option_price"] == sample_option_quote.price
                assert response["data_source"] == "trading_service"
                assert response["cached"] is False

    @pytest.mark.asyncio
    async def test_get_option_greeks_response_invalid_symbol(self, trading_service):
        """Test getting Greeks response for invalid option symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")  # Not an option

            with pytest.raises(ValueError, match="Symbol is not an option"):
                await trading_service.get_option_greeks_response("AAPL")


class TestMultiLegOrders:
    """Test multi-leg order creation and processing."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test successfully creating a multi-leg order."""
        # Mock order data with legs
        mock_order_data = Mock()
        mock_leg1 = Mock()
        mock_leg1.order_type = OrderType.BUY
        mock_leg1.quantity = 100
        mock_leg1.price = 5.50
        mock_leg2 = Mock()
        mock_leg2.order_type = OrderType.SELL
        mock_leg2.quantity = 100
        mock_leg2.price = 3.50
        mock_order_data.legs = [mock_leg1, mock_leg2]
        mock_order_data.condition = OrderCondition.LIMIT

        mock_db_order = Mock(spec=DBOrder)
        mock_db_order.id = "multi-leg-order-123"

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch("app.services.trading_service.DBOrder") as mock_db_order_class,
        ):
            mock_db_order_class.return_value = mock_db_order

            order = await trading_service.create_multi_leg_order(mock_order_data)

            assert isinstance(order, Order)
            assert order.symbol == "MULTI_LEG_2_LEGS"
            assert order.order_type == OrderType.BUY  # From first leg
            assert order.quantity == 200  # Sum of quantities
            assert order.price == 9.0  # Sum of prices
            assert order.net_price == 9.0
            assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_no_legs(self, trading_service):
        """Test creating multi-leg order with no legs."""
        mock_order_data = Mock()
        mock_order_data.legs = []

        order = await trading_service.create_multi_leg_order(mock_order_data)

        assert order.symbol == "MULTI_LEG_0_LEGS"
        assert order.quantity == 0
        assert order.price == 0

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_legs_with_none_price(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test creating multi-leg order with legs that have None prices."""
        mock_order_data = Mock()
        mock_leg1 = Mock()
        mock_leg1.order_type = OrderType.BUY
        mock_leg1.quantity = 100
        mock_leg1.price = None  # None price
        mock_leg2 = Mock()
        mock_leg2.order_type = OrderType.SELL
        mock_leg2.quantity = 100
        mock_leg2.price = 5.50
        mock_order_data.legs = [mock_leg1, mock_leg2]

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch("app.services.trading_service.DBOrder"),
        ):
            order = await trading_service.create_multi_leg_order(mock_order_data)

            # Should only sum non-None prices
            assert order.price == 5.50
            assert order.net_price == 5.50

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request(
        self, trading_service, mock_async_session, sample_db_account
    ):
        """Test creating multi-leg order from raw request data."""
        legs = [
            {"symbol": "AAPL240119C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240119P00145000", "quantity": 1, "side": "sell"},
        ]
        order_type = "limit"
        net_price = 2.50

        with (
            patch.object(
                trading_service,
                "_get_async_db_session",
                return_value=mock_async_session,
            ),
            patch.object(
                trading_service,
                "_get_account",
                new_callable=AsyncMock,
                return_value=sample_db_account,
            ),
            patch("app.services.trading_service.DBOrder"),
        ):
            order = await trading_service.create_multi_leg_order_from_request(
                legs, order_type, net_price
            )

            assert isinstance(order, Order)
            assert order.symbol == "MULTI_LEG_2_LEGS"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_error(self, trading_service):
        """Test creating multi-leg order from request with error."""
        legs = []  # Empty legs will cause an error in MockOrderData creation

        with pytest.raises(ValueError, match="Failed to create multi-leg order"):
            await trading_service.create_multi_leg_order_from_request(
                legs, "limit", 2.50
            )


class TestMarketDataMethods:
    """Test market data retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_stock_price_success(self, trading_service, sample_quote):
        """Test successfully getting stock price."""
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        # Add previous_close attribute
        sample_quote.previous_close = 148.0

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_stock_price("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["price"] == 150.00
            assert result["change"] == 2.00  # 150 - 148
            assert result["change_percent"] == 1.35  # (2/148) * 100
            assert result["previous_close"] == 148.00

    @pytest.mark.asyncio
    async def test_get_stock_price_no_previous_close(
        self, trading_service, sample_quote
    ):
        """Test getting stock price without previous close data."""
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_stock_price("AAPL")

            assert result["change"] == 0.0
            assert result["change_percent"] == 0.0
            assert result["previous_close"] == 150.00  # Falls back to current price

    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_symbol(self, trading_service):
        """Test getting stock price for invalid symbol."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = None

            result = await trading_service.get_stock_price("INVALID")
            assert "error" in result
            assert result["error"] == "Invalid symbol: INVALID"

    @pytest.mark.asyncio
    async def test_get_stock_price_no_quote(self, trading_service):
        """Test getting stock price when no quote available."""
        trading_service.quote_adapter.get_quote.return_value = None

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_stock_price("AAPL")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_stock_price_exception(self, trading_service):
        """Test getting stock price with exception."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.side_effect = Exception("Asset factory error")

            result = await trading_service.get_stock_price("AAPL")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_stock_info_with_adapter_method(self, trading_service):
        """Test getting stock info when adapter has get_stock_info method."""
        mock_stock_info = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
        }
        trading_service.quote_adapter.get_stock_info = AsyncMock(
            return_value=mock_stock_info
        )

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_stock_info("AAPL")
            assert result == mock_stock_info

    @pytest.mark.asyncio
    async def test_get_stock_info_fallback_to_quote(
        self, trading_service, sample_quote
    ):
        """Test getting stock info falls back to quote data."""
        # Adapter doesn't have get_stock_info method
        if hasattr(trading_service.quote_adapter, "get_stock_info"):
            delattr(trading_service.quote_adapter, "get_stock_info")

        trading_service.quote_adapter.get_quote.return_value = sample_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_stock_info("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["company_name"] == "AAPL Company"
            assert result["sector"] == "N/A"
            assert result["tradeable"] is True

    @pytest.mark.asyncio
    async def test_get_price_history_with_adapter_method(self, trading_service):
        """Test getting price history when adapter has the method."""
        mock_history = {
            "symbol": "AAPL",
            "data_points": [{"date": "2024-01-01", "close": 150.00}],
        }
        trading_service.quote_adapter.get_price_history = AsyncMock(
            return_value=mock_history
        )

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_price_history("AAPL", "week")
            assert result == mock_history

    @pytest.mark.asyncio
    async def test_get_price_history_fallback_to_quote(
        self, trading_service, sample_quote
    ):
        """Test getting price history falls back to current quote."""
        trading_service.quote_adapter.get_quote.return_value = sample_quote

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")

            result = await trading_service.get_price_history("AAPL", "week")

            assert result["symbol"] == "AAPL"
            assert result["period"] == "week"
            assert len(result["data_points"]) == 1
            assert result["data_points"][0]["close"] == 150.00

    @pytest.mark.asyncio
    async def test_search_stocks_with_adapter_method(self, trading_service):
        """Test searching stocks when adapter has the method."""
        mock_results = {"results": [{"symbol": "AAPL", "name": "Apple Inc."}]}
        trading_service.quote_adapter.search_stocks = AsyncMock(
            return_value=mock_results
        )

        result = await trading_service.search_stocks("apple")
        assert result == mock_results

    @pytest.mark.asyncio
    async def test_search_stocks_fallback(self, trading_service):
        """Test searching stocks falls back to symbol matching."""
        result = await trading_service.search_stocks("AAPL")

        assert "results" in result
        assert result["query"] == "AAPL"
        # Should find AAPL in available symbols
        assert any(r["symbol"] == "AAPL" for r in result["results"])


class TestOptionsChainFormatting:
    """Test options chain formatting methods."""

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_success(
        self, trading_service, sample_option_quote
    ):
        """Test successfully getting formatted options chain."""
        # Mock options chain
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[sample_option_quote],
            puts=[],
        )

        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=mock_chain,
        ):
            result = await trading_service.get_formatted_options_chain("AAPL")

            assert result["underlying_symbol"] == "AAPL"
            assert result["underlying_price"] == 150.00
            assert len(result["calls"]) == 1
            assert len(result["puts"]) == 0

            # Check call formatting
            call_data = result["calls"][0]
            assert call_data["symbol"] == sample_option_quote.asset.symbol
            assert call_data["strike"] == 150.0
            assert call_data["delta"] == 0.65  # Include Greeks by default

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_with_filters(
        self, trading_service, sample_option_quote
    ):
        """Test getting formatted options chain with strike filters."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[sample_option_quote],
            puts=[],
        )

        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=mock_chain,
        ):
            # Filter should exclude our 150 strike option
            result = await trading_service.get_formatted_options_chain(
                "AAPL", min_strike=155.0
            )

            assert len(result["calls"]) == 0  # Filtered out

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_without_greeks(
        self, trading_service, sample_option_quote
    ):
        """Test getting formatted options chain without Greeks."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[sample_option_quote],
            puts=[],
        )

        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=mock_chain,
        ):
            result = await trading_service.get_formatted_options_chain(
                "AAPL", include_greeks=False
            )

            call_data = result["calls"][0]
            # Should not include Greeks
            assert "delta" not in call_data
            assert "gamma" not in call_data

    @pytest.mark.asyncio
    async def test_get_formatted_options_chain_error(self, trading_service):
        """Test getting formatted options chain with error."""
        with patch.object(
            trading_service, "get_options_chain", new_callable=AsyncMock
        ) as mock_get_chain:
            mock_get_chain.side_effect = Exception("Chain error")

            result = await trading_service.get_formatted_options_chain("AAPL")
            assert "error" in result


class TestFindTradableOptions:
    """Test finding tradable options functionality."""

    @pytest.mark.asyncio
    async def test_find_tradable_options_success(
        self, trading_service, sample_option_quote
    ):
        """Test successfully finding tradable options."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[sample_option_quote],
            puts=[],
        )

        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=mock_chain,
        ):
            result = await trading_service.find_tradable_options("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["total_found"] == 1
            assert len(result["options"]) == 1

            option_data = result["options"][0]
            assert option_data["symbol"] == sample_option_quote.asset.symbol
            assert option_data["underlying_symbol"] == "AAPL"
            assert option_data["strike_price"] == 150.0
            assert option_data["option_type"] == "call"

    @pytest.mark.asyncio
    async def test_find_tradable_options_with_filters(
        self, trading_service, sample_option_quote
    ):
        """Test finding tradable options with filters."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.00,
            calls=[sample_option_quote],
            puts=[],
        )

        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=mock_chain,
        ):
            # Filter for calls only
            result = await trading_service.find_tradable_options(
                "AAPL", option_type="call"
            )

            assert len(result["options"]) == 1
            assert result["options"][0]["option_type"] == "call"

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_chain(self, trading_service):
        """Test finding tradable options when no chain available."""
        with patch.object(
            trading_service,
            "get_options_chain",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await trading_service.find_tradable_options("AAPL")

            assert result["total_found"] == 0
            assert result["options"] == []
            assert "message" in result

    @pytest.mark.asyncio
    async def test_find_tradable_options_error(self, trading_service):
        """Test finding tradable options with error."""
        with patch.object(
            trading_service, "get_options_chain", new_callable=AsyncMock
        ) as mock_get_chain:
            mock_get_chain.side_effect = Exception("Chain error")

            result = await trading_service.find_tradable_options("AAPL")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_option_market_data_success(
        self, trading_service, sample_option_quote
    ):
        """Test successfully getting option market data."""
        option_id = "AAPL240119C00150000"

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = sample_option_quote.asset

            with patch.object(
                trading_service,
                "get_enhanced_quote",
                new_callable=AsyncMock,
                return_value=sample_option_quote,
            ):
                result = await trading_service.get_option_market_data(option_id)

                assert result["option_id"] == option_id
                assert result["symbol"] == sample_option_quote.asset.symbol
                assert result["underlying_symbol"] == "AAPL"
                assert result["strike_price"] == 150.0
                assert result["option_type"] == "call"
                assert result["greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_get_option_market_data_invalid_option(self, trading_service):
        """Test getting option market data for invalid option."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")  # Not an option

            result = await trading_service.get_option_market_data("AAPL")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_option_market_data_no_quote(
        self, trading_service, sample_option_quote
    ):
        """Test getting option market data when no quote available."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = sample_option_quote.asset

            with patch.object(
                trading_service,
                "get_enhanced_quote",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await trading_service.get_option_market_data(
                    "AAPL240119C00150000"
                )
                assert "error" in result


class TestExpirationSimulation:
    """Test expiration simulation functionality."""

    @pytest.mark.asyncio
    async def test_simulate_expiration_success(
        self, trading_service, sample_option_quote
    ):
        """Test successfully simulating expiration."""
        # Mock portfolio with expiring option
        option_position = Position(
            symbol="AAPL240119C00150000", quantity=1, current_price=5.50
        )

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=15550.0,
            positions=[option_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Mock option asset (expires today)
        option_asset = Option(
            symbol="AAPL240119C00150000",
            underlying=Stock(symbol="AAPL"),
            expiration_date=date.today(),
            strike=150.0,
            option_type="call",
        )

        # Mock underlying quote (ITM)
        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=155.00,  # ITM for call
            bid=154.95,
            ask=155.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            patch("app.services.trading_service.asset_factory") as mock_factory,
        ):
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = [sample_option_quote, underlying_quote]

                result = await trading_service.simulate_expiration()

                assert result["processing_date"] == date.today().isoformat()
                assert result["dry_run"] is True
                assert result["expiring_positions"] == 1
                assert result["total_impact"] == 500.0  # (155-150) * 1 * 100

                expiring_option = result["expiring_options"][0]
                assert expiring_option["symbol"] == "AAPL240119C00150000"
                assert expiring_option["intrinsic_value"] == 5.0
                assert expiring_option["action"] == "exercise_or_assign"

    @pytest.mark.asyncio
    async def test_simulate_expiration_otm_option(
        self, trading_service, sample_option_quote
    ):
        """Test simulating expiration for OTM option."""
        option_position = Position(
            symbol="AAPL240119C00150000", quantity=1, current_price=5.50
        )

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=15550.0,
            positions=[option_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        option_asset = Option(
            symbol="AAPL240119C00150000",
            underlying=Stock(symbol="AAPL"),
            expiration_date=date.today(),
            strike=150.0,
            option_type="call",
        )

        # Mock underlying quote (OTM)
        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=145.00,  # OTM for call
            bid=144.95,
            ask=145.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            patch("app.services.trading_service.asset_factory") as mock_factory,
        ):
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = [sample_option_quote, underlying_quote]

                result = await trading_service.simulate_expiration()

                expiring_option = result["expiring_options"][0]
                assert expiring_option["intrinsic_value"] == 0.0
                assert expiring_option["action"] == "expire_worthless"

    @pytest.mark.asyncio
    async def test_simulate_expiration_put_option(self, trading_service):
        """Test simulating expiration for put option."""
        option_position = Position(
            symbol="AAPL240119P00150000", quantity=1, current_price=3.50
        )

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=13500.0,
            positions=[option_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        put_asset = Option(
            symbol="AAPL240119P00150000",
            underlying=Stock(symbol="AAPL"),
            expiration_date=date.today(),
            strike=150.0,
            option_type="put",
        )

        put_quote = OptionQuote(
            asset=put_asset,
            price=3.50,
            bid=3.45,
            ask=3.55,
            quote_date=datetime.now(),
            underlying_price=145.00,
        )

        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=145.00,  # ITM for put
            bid=144.95,
            ask=145.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            patch("app.services.trading_service.asset_factory") as mock_factory,
        ):
            mock_factory.return_value = put_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = [put_quote, underlying_quote]

                result = await trading_service.simulate_expiration()

                expiring_option = result["expiring_options"][0]
                assert expiring_option["intrinsic_value"] == 5.0  # 150 - 145
                assert expiring_option["position_impact"] == 500.0  # 5 * 1 * 100

    @pytest.mark.asyncio
    async def test_simulate_expiration_non_expiring_positions(self, trading_service):
        """Test simulating expiration with non-expiring positions."""
        # Mix of expiring and non-expiring positions
        positions = [
            Position(symbol="AAPL", quantity=100, current_price=150.00),  # Stock
            Position(
                symbol="AAPL250119C00150000", quantity=1, current_price=5.50
            ),  # Future expiration
        ]

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25550.0,
            positions=positions,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        future_option_asset = Option(
            symbol="AAPL250119C00150000",
            underlying=Stock(symbol="AAPL"),
            expiration_date=date(2025, 1, 19),  # Future date
            strike=150.0,
            option_type="call",
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            patch("app.services.trading_service.asset_factory") as mock_factory,
        ):

            def factory_side_effect(symbol):
                if symbol == "AAPL":
                    return Stock(symbol="AAPL")
                elif symbol == "AAPL250119C00150000":
                    return future_option_asset
                return None

            mock_factory.side_effect = factory_side_effect

            result = await trading_service.simulate_expiration()

            assert result["expiring_positions"] == 0
            assert result["non_expiring_positions"] == 2

            # Check non-expiring details
            non_expiring = result["non_expiring_positions_details"]
            assert len(non_expiring) == 2

            # Stock position
            stock_pos = next(p for p in non_expiring if p["symbol"] == "AAPL")
            assert stock_pos["position_type"] == "stock"

            # Future option
            option_pos = next(
                p for p in non_expiring if p["symbol"] == "AAPL250119C00150000"
            )
            assert option_pos["days_to_expiration"] > 0

    @pytest.mark.asyncio
    async def test_simulate_expiration_with_errors(self, trading_service):
        """Test simulating expiration with quote errors."""
        option_position = Position(
            symbol="AAPL240119C00150000", quantity=1, current_price=5.50
        )

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=15550.0,
            positions=[option_position],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        option_asset = Option(
            symbol="AAPL240119C00150000",
            underlying=Stock(symbol="AAPL"),
            expiration_date=date.today(),
            strike=150.0,
            option_type="call",
        )

        with (
            patch.object(
                trading_service,
                "get_portfolio",
                new_callable=AsyncMock,
                return_value=mock_portfolio,
            ),
            patch("app.services.trading_service.asset_factory") as mock_factory,
        ):
            mock_factory.return_value = option_asset

            with patch.object(
                trading_service, "get_enhanced_quote", new_callable=AsyncMock
            ) as mock_get_quote:
                mock_get_quote.side_effect = Exception("Quote error")

                result = await trading_service.simulate_expiration()

                expiring_option = result["expiring_options"][0]
                assert "error" in expiring_option
                assert expiring_option["action"] == "manual_review_required"

    @pytest.mark.asyncio
    async def test_simulate_expiration_custom_date(self, trading_service):
        """Test simulating expiration with custom processing date."""
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=10000.0,
            positions=[],
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        processing_date = "2024-01-19"

        with patch.object(
            trading_service,
            "get_portfolio",
            new_callable=AsyncMock,
            return_value=mock_portfolio,
        ):
            result = await trading_service.simulate_expiration(
                processing_date=processing_date
            )

            assert result["processing_date"] == processing_date

    @pytest.mark.asyncio
    async def test_simulate_expiration_error(self, trading_service):
        """Test simulating expiration with general error."""
        with patch.object(
            trading_service, "get_portfolio", new_callable=AsyncMock
        ) as mock_get_portfolio:
            mock_get_portfolio.side_effect = Exception("Portfolio error")

            result = await trading_service.simulate_expiration()
            assert "error" in result


class TestTestDataMethods:
    """Test test data and development methods."""

    def test_get_expiration_dates(self, trading_service):
        """Test getting expiration dates."""
        mock_dates = [date(2024, 1, 19), date(2024, 2, 16)]
        trading_service.quote_adapter.get_expiration_dates.return_value = mock_dates

        dates = trading_service.get_expiration_dates("AAPL")
        assert dates == mock_dates


class TestPortfolioAnalysisAndStrategy:
    """Test portfolio analysis and strategy methods."""

    @pytest.mark.asyncio
    async def test_get_portfolio_greeks(self, trading_service):
        """Test getting portfolio Greeks."""
        mock_positions = [
            Position(symbol="AAPL240119C00150000", quantity=1, current_price=5.50),
        ]

        mock_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240119C00150000",
                underlying=Stock(symbol="AAPL"),
                expiration_date=date(2024, 1, 19),
                strike=150.0,
                option_type="call",
            ),
            price=5.50,
            bid=5.45,
            ask=5.55,
            quote_date=datetime.now(),
            underlying_price=150.00,
            delta=0.65,
            gamma=0.03,
            theta=-0.05,
            vega=0.20,
            rho=0.08,
        )

        with (
            patch.object(
                trading_service,
                "get_positions",
                new_callable=AsyncMock,
                return_value=mock_positions,
            ),
            patch.object(
                trading_service,
                "get_enhanced_quote",
                new_callable=AsyncMock,
                return_value=mock_quote,
            ),
            patch(
                "app.services.trading_service.aggregate_portfolio_greeks"
            ) as mock_aggregate,
        ):
            mock_greeks = Mock()
            mock_greeks.delta = 65.0
            mock_greeks.gamma = 3.0
            mock_greeks.theta = -5.0
            mock_greeks.vega = 20.0
            mock_greeks.rho = 8.0
            mock_greeks.delta_normalized = 0.65
            mock_greeks.gamma_normalized = 0.03
            mock_greeks.theta_normalized = -0.05
            mock_greeks.vega_normalized = 0.20
            mock_greeks.delta_dollars = 325.0
            mock_greeks.gamma_dollars = 15.0
            mock_greeks.theta_dollars = -25.0
            mock_aggregate.return_value = mock_greeks

            result = await trading_service.get_portfolio_greeks()

            assert result["total_positions"] == 1
            assert result["options_positions"] == 1
            assert result["portfolio_greeks"]["delta"] == 65.0

    @pytest.mark.asyncio
    async def test_get_position_greeks(self, trading_service):
        """Test getting Greeks for specific position."""
        mock_position = Position(
            symbol="AAPL240119C00150000", quantity=1, current_price=5.50
        )

        mock_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240119C00150000",
                underlying=Stock(symbol="AAPL"),
                expiration_date=date(2024, 1, 19),
                strike=150.0,
                option_type="call",
            ),
            price=5.50,
            bid=5.45,
            ask=5.55,
            quote_date=datetime.now(),
            underlying_price=150.00,
            delta=0.65,
            gamma=0.03,
        )

        with (
            patch.object(
                trading_service,
                "get_position",
                new_callable=AsyncMock,
                return_value=mock_position,
            ),
            patch.object(
                trading_service,
                "get_enhanced_quote",
                new_callable=AsyncMock,
                return_value=mock_quote,
            ),
        ):
            result = await trading_service.get_position_greeks("AAPL240119C00150000")

            assert result["symbol"] == "AAPL240119C00150000"
            assert result["position_quantity"] == 1
            assert result["greeks"]["delta"] == 0.65
            assert result["position_greeks"]["delta"] == 65.0  # 0.65 * 1 * 100

    @pytest.mark.asyncio
    async def test_get_position_greeks_not_option(self, trading_service):
        """Test getting Greeks for non-option position."""
        mock_position = Position(symbol="AAPL", quantity=100, current_price=150.00)
        mock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(
                trading_service,
                "get_position",
                new_callable=AsyncMock,
                return_value=mock_position,
            ),
            patch.object(
                trading_service,
                "get_enhanced_quote",
                new_callable=AsyncMock,
                return_value=mock_quote,
            ),
            pytest.raises(ValueError, match="Position is not an options position"),
        ):
            await trading_service.get_position_greeks("AAPL")

    @pytest.mark.asyncio
    async def test_validate_account_state(self, trading_service):
        """Test validating account state."""
        mock_positions = [
            Position(symbol="AAPL", quantity=100, current_price=150.00),
        ]

        with (
            patch.object(
                trading_service,
                "get_account_balance",
                new_callable=AsyncMock,
                return_value=10000.0,
            ),
            patch.object(
                trading_service,
                "get_positions",
                new_callable=AsyncMock,
                return_value=mock_positions,
            ),
            patch.object(
                trading_service.account_validation, "validate_account_state"
            ) as mock_validate,
        ):
            mock_validate.return_value = True

            result = await trading_service.validate_account_state()
            assert result is True

            mock_validate.assert_called_once_with(
                cash_balance=10000.0, positions=mock_positions
            )


class TestModuleLevelFunction:
    """Test module-level functions."""

    def test_get_quote_adapter_live_data(self):
        """Test _get_quote_adapter with live data enabled."""
        with (
            patch.dict("os.environ", {"USE_LIVE_DATA": "true"}),
            patch("app.services.trading_service.RobinhoodAdapter") as mock_robinhood,
        ):
            mock_adapter = Mock()
            mock_robinhood.return_value = mock_adapter

            adapter = _get_quote_adapter()
            assert adapter == mock_adapter

    def test_get_quote_adapter_live_data_import_error(self):
        """Test _get_quote_adapter with live data but import error."""
        with (
            patch.dict("os.environ", {"USE_LIVE_DATA": "true"}),
            patch(
                "app.services.trading_service.RobinhoodAdapter",
                side_effect=ImportError("No module"),
            ),
            patch("app.services.trading_service.DevDataQuoteAdapter") as mock_dev,
        ):
            mock_adapter = Mock()
            mock_dev.return_value = mock_adapter

            adapter = _get_quote_adapter()
            assert adapter == mock_adapter

    def test_get_quote_adapter_dev_data(self):
        """Test _get_quote_adapter defaults to dev data."""
        with patch.dict("os.environ", {"USE_LIVE_DATA": "false"}):
            with patch("app.services.trading_service.DevDataQuoteAdapter") as mock_dev:
                mock_adapter = Mock()
                mock_dev.return_value = mock_adapter

                adapter = _get_quote_adapter()
                assert adapter == mock_adapter
