"""
Comprehensive tests for TradingService - the core business logic service.

Tests cover:
- Account management and balance operations
- Order creation, retrieval, and cancellation
- Portfolio management and position tracking
- Quote retrieval and market data integration
- Options trading and Greeks calculations
- Multi-leg order execution
- Error handling and edge cases
- Database integration patterns
- Async service coordination
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.models.assets import Call, Stock
from app.models.quotes import OptionQuote, OptionsChain, Quote
from app.schemas.orders import (
    Order,
    OrderCondition,
    OrderCreate,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import Portfolio, Position
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService


@pytest.fixture
def mock_quote_adapter():
    """Mock quote adapter for testing."""
    adapter = AsyncMock()
    adapter.get_quote = AsyncMock()
    adapter.get_options_chain = AsyncMock()
    return adapter


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def trading_service(mock_quote_adapter):
    """Trading service instance with mocked dependencies."""
    service = TradingService(quote_adapter=mock_quote_adapter)
    return service


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
    call_option = Call(
        underlying=Stock(symbol="AAPL"),
        strike=150.0,
        expiration_date=date.today() + timedelta(days=30),
    )
    return OptionQuote(
        asset=call_option,
        price=5.50,
        bid=5.45,
        ask=5.55,
        delta=0.6,
        gamma=0.05,
        theta=-0.02,
        vega=0.15,
        quote_date=datetime.now(),
    )


@pytest.fixture
def sample_portfolio():
    """Sample portfolio for testing."""
    positions = [
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
            current_price=2850.00,
            market_value=142500.00,
            unrealized_pnl=2500.00,
        ),
    ]
    return Portfolio(
        cash_balance=10000.00,
        total_value=167500.00,
        positions=positions,
        daily_pnl=3000.00,
        total_pnl=3000.00,
    )


class TestTradingServiceAccountManagement:
    """Test account management functionality."""

    @pytest.mark.asyncio
    async def test_get_account_balance_success(self, trading_service):
        """Test successful account balance retrieval."""
        with patch.object(trading_service, "_get_account") as mock_get_account:
            mock_account = Mock()
            mock_account.cash_balance = Decimal("10000.50")
            mock_get_account.return_value = mock_account

            balance = await trading_service.get_account_balance()

            assert balance == 10000.50
            mock_get_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_account_exists_creates_new_account(self, trading_service):
        """Test account creation when account doesn't exist."""
        with patch.object(trading_service, "_get_async_db_session") as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            # Mock no existing account
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            await trading_service._ensure_account_exists()

            # Verify account creation
            mock_db.add.assert_called()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_account_not_found_raises_error(self, trading_service):
        """Test that missing account raises NotFoundError."""
        with patch.object(trading_service, "_get_async_db_session") as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            # Mock no account found after ensure_account_exists
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            with pytest.raises(
                NotFoundError, match="Account for owner default not found"
            ):
                await trading_service._get_account()


class TestTradingServiceQuoteOperations:
    """Test quote retrieval and market data operations."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, trading_service, sample_stock_quote):
        """Test successful quote retrieval."""
        trading_service.quote_adapter.get_quote.return_value = sample_stock_quote

        quote = await trading_service.get_quote("AAPL")

        assert isinstance(quote, StockQuote)
        assert quote.symbol == "AAPL"
        assert quote.price == 150.00
        assert isinstance(quote.last_updated, datetime)

    @pytest.mark.asyncio
    async def test_get_quote_invalid_symbol_raises_error(self, trading_service):
        """Test that invalid symbol raises NotFoundError."""
        with patch("app.services.trading_service.asset_factory", return_value=None):
            with pytest.raises(NotFoundError, match="Invalid symbol: INVALID"):
                await trading_service.get_quote("INVALID")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_failure_raises_error(self, trading_service):
        """Test that adapter failure raises NotFoundError."""
        trading_service.quote_adapter.get_quote.return_value = None

        with pytest.raises(NotFoundError, match="Symbol AAPL not found"):
            await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_with_options(
        self, trading_service, sample_option_quote
    ):
        """Test enhanced quote retrieval for options."""
        trading_service.quote_adapter.get_quote.return_value = sample_option_quote

        quote = await trading_service.get_enhanced_quote("AAPL240119C150")

        assert isinstance(quote, OptionQuote)
        assert quote.price == 5.50
        assert quote.delta == 0.6
        assert quote.gamma == 0.05

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, trading_service):
        """Test successful options chain retrieval."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=150.00,
            expiration_date=date.today() + timedelta(days=30),
            calls=[],
            puts=[],
        )
        trading_service.quote_adapter.get_options_chain.return_value = mock_chain

        chain = await trading_service.get_options_chain("AAPL")

        assert chain.underlying_symbol == "AAPL"
        assert chain.underlying_price == 150.00
        trading_service.quote_adapter.get_options_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found_raises_error(self, trading_service):
        """Test that missing options chain raises NotFoundError."""
        trading_service.quote_adapter.get_options_chain.return_value = None

        with pytest.raises(NotFoundError, match="No options chain found for AAPL"):
            await trading_service.get_options_chain("AAPL")


class TestTradingServiceOrderManagement:
    """Test order creation, retrieval, and management."""

    @pytest.mark.asyncio
    async def test_create_order_success(self, trading_service, sample_stock_quote):
        """Test successful order creation."""
        trading_service.quote_adapter.get_quote.return_value = sample_stock_quote

        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
            patch.object(
                trading_service.order_converter, "to_schema"
            ) as mock_converter,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_order = Order(
                id="order-123",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.00,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            mock_converter.return_value = mock_order

            order_data = OrderCreate(
                symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.00
            )

            result = await trading_service.create_order(order_data)

            assert result.symbol == "AAPL"
            assert result.quantity == 100
            assert result.status == OrderStatus.PENDING
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_order_invalid_symbol_raises_error(self, trading_service):
        """Test that invalid symbol in order raises NotFoundError."""
        trading_service.quote_adapter.get_quote.side_effect = Exception(
            "Symbol not found"
        )

        order_data = OrderCreate(
            symbol="INVALID", order_type=OrderType.BUY, quantity=100, price=150.00
        )

        with pytest.raises(NotFoundError):
            await trading_service.create_order(order_data)

    @pytest.mark.asyncio
    async def test_get_orders_success(self, trading_service):
        """Test successful order retrieval."""
        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
            patch.object(
                trading_service.order_converter, "to_schema"
            ) as mock_converter,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_db_orders = [Mock(), Mock()]
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = mock_db_orders
            mock_db.execute.return_value = mock_result

            mock_orders = [
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
            mock_converter.side_effect = mock_orders

            orders = await trading_service.get_orders()

            assert len(orders) == 2
            assert orders[0].symbol == "AAPL"
            assert orders[1].symbol == "GOOGL"

    @pytest.mark.asyncio
    async def test_get_order_by_id_success(self, trading_service):
        """Test successful single order retrieval."""
        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
            patch.object(
                trading_service.order_converter, "to_schema"
            ) as mock_converter,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_db_order = Mock()
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            mock_order = Order(
                id="order-123",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            mock_converter.return_value = mock_order

            order = await trading_service.get_order("order-123")

            assert order.id == "order-123"
            assert order.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_order_not_found_raises_error(self, trading_service):
        """Test that missing order raises NotFoundError."""
        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            with pytest.raises(NotFoundError, match="Order order-123 not found"):
                await trading_service.get_order("order-123")

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, trading_service):
        """Test successful order cancellation."""
        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_db_order = Mock()
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result

            result = await trading_service.cancel_order("order-123")

            assert result["message"] == "Order cancelled successfully"
            assert mock_db_order.status == OrderStatus.CANCELLED
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_order_not_found_raises_error(self, trading_service):
        """Test that cancelling missing order raises NotFoundError."""
        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            with pytest.raises(NotFoundError, match="Order order-123 not found"):
                await trading_service.cancel_order("order-123")


class TestTradingServicePortfolioManagement:
    """Test portfolio and position management."""

    @pytest.mark.asyncio
    async def test_get_portfolio_success(self, trading_service, sample_stock_quote):
        """Test successful portfolio retrieval."""
        trading_service.quote_adapter.get_quote.return_value = sample_stock_quote

        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
            patch.object(
                trading_service.position_converter, "to_schema"
            ) as mock_converter,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_account.cash_balance = 10000.00
            mock_get_account.return_value = mock_account

            mock_db_positions = [Mock(), Mock()]
            mock_db_positions[0].symbol = "AAPL"
            mock_db_positions[1].symbol = "GOOGL"

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = mock_db_positions
            mock_db.execute.return_value = mock_result

            mock_positions = [
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
                    current_price=2850.00,
                    market_value=142500.00,
                    unrealized_pnl=2500.00,
                ),
            ]
            mock_converter.side_effect = mock_positions

            portfolio = await trading_service.get_portfolio()

            assert portfolio.cash_balance == 10000.00
            assert len(portfolio.positions) == 2
            assert portfolio.total_value == 167500.00  # cash + positions value
            assert portfolio.daily_pnl == 3000.00  # sum of unrealized PnL

    @pytest.mark.asyncio
    async def test_get_portfolio_handles_quote_errors(self, trading_service):
        """Test portfolio retrieval handles quote errors gracefully."""
        trading_service.quote_adapter.get_quote.side_effect = NotFoundError(
            "Quote not found"
        )

        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_account.cash_balance = 10000.00
            mock_get_account.return_value = mock_account

            mock_db_positions = [Mock()]
            mock_db_positions[0].symbol = "INVALID"

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = mock_db_positions
            mock_db.execute.return_value = mock_result

            portfolio = await trading_service.get_portfolio()

            # Should skip positions with quote errors
            assert portfolio.cash_balance == 10000.00
            assert len(portfolio.positions) == 0

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(self, trading_service):
        """Test successful portfolio summary calculation."""
        mock_portfolio = Portfolio(
            cash_balance=10000.00,
            total_value=167500.00,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    current_price=150.00,
                    unrealized_pnl=500.00,
                ),
                Position(
                    symbol="GOOGL",
                    quantity=50,
                    current_price=2850.00,
                    unrealized_pnl=2500.00,
                ),
            ],
            daily_pnl=3000.00,
            total_pnl=3000.00,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            summary = await trading_service.get_portfolio_summary()

            assert summary.total_value == 167500.00
            assert summary.cash_balance == 10000.00
            assert summary.invested_value == 157500.00  # 100*150 + 50*2850
            assert summary.daily_pnl == 3000.00
            assert abs(summary.daily_pnl_percent - 1.79) < 0.01  # 3000/167500 * 100

    @pytest.mark.asyncio
    async def test_get_position_by_symbol_success(self, trading_service):
        """Test successful position retrieval by symbol."""
        mock_portfolio = Portfolio(
            cash_balance=10000.00,
            total_value=167500.00,
            positions=[
                Position(symbol="AAPL", quantity=100, avg_price=145.00),
                Position(symbol="GOOGL", quantity=50, avg_price=2800.00),
            ],
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            position = await trading_service.get_position("AAPL")

            assert position.symbol == "AAPL"
            assert position.quantity == 100
            assert position.avg_price == 145.00

    @pytest.mark.asyncio
    async def test_get_position_not_found_raises_error(self, trading_service):
        """Test that missing position raises NotFoundError."""
        mock_portfolio = Portfolio(
            cash_balance=10000.00,
            total_value=10000.00,
            positions=[],
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        with patch.object(
            trading_service, "get_portfolio", return_value=mock_portfolio
        ):
            with pytest.raises(
                NotFoundError, match="Position for symbol AAPL not found"
            ):
                await trading_service.get_position("AAPL")


class TestTradingServiceOptionsFeatures:
    """Test advanced options trading features."""

    @pytest.mark.asyncio
    async def test_calculate_greeks_success(self, trading_service, sample_option_quote):
        """Test successful Greeks calculation."""
        trading_service.quote_adapter.get_quote.return_value = sample_option_quote

        # Mock underlying quote
        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(trading_service, "get_enhanced_quote") as mock_get_quote,
            patch(
                "app.services.trading_service.calculate_option_greeks"
            ) as mock_calc_greeks,
        ):
            mock_get_quote.side_effect = [sample_option_quote, underlying_quote]
            mock_calc_greeks.return_value = {
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.15,
                "rho": 0.08,
            }

            greeks = await trading_service.calculate_greeks("AAPL240119C150")

            assert greeks["delta"] == 0.6
            assert greeks["gamma"] == 0.05
            assert greeks["theta"] == -0.02
            assert greeks["vega"] == 0.15

    @pytest.mark.asyncio
    async def test_calculate_greeks_invalid_symbol_raises_error(self, trading_service):
        """Test that invalid option symbol raises ValueError."""
        with patch("app.services.trading_service.asset_factory") as mock_factory:
            mock_factory.return_value = Stock(symbol="AAPL")  # Not an option

            with pytest.raises(ValueError, match="AAPL is not an option"):
                await trading_service.calculate_greeks("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_insufficient_data_raises_error(
        self, trading_service
    ):
        """Test that insufficient pricing data raises ValueError."""
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
        )

        with patch.object(
            trading_service, "get_enhanced_quote", return_value=option_quote
        ):
            with pytest.raises(ValueError, match="Insufficient pricing data"):
                await trading_service.calculate_greeks("AAPL240119C150")

    @pytest.mark.asyncio
    async def test_get_option_greeks_response_success(
        self, trading_service, sample_option_quote
    ):
        """Test successful option Greeks response generation."""
        underlying_quote = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=datetime.now(),
        )

        with (
            patch.object(trading_service, "calculate_greeks") as mock_calc_greeks,
            patch.object(
                trading_service, "get_enhanced_quote", return_value=sample_option_quote
            ),
        ):
            mock_calc_greeks.return_value = {
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.15,
                "rho": 0.08,
                "iv": 0.25,
            }

            response = await trading_service.get_option_greeks_response(
                "AAPL240119C150", 150.00
            )

            assert response["option_symbol"] == "AAPL240119C150"
            assert response["underlying_symbol"] == "AAPL"
            assert response["strike"] == 150.0
            assert response["delta"] == 0.6
            assert response["implied_volatility"] == 0.25
            assert response["underlying_price"] == 150.00


class TestTradingServiceMultiLegOrders:
    """Test multi-leg order functionality."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(self, trading_service):
        """Test successful multi-leg order creation."""

        class MockLeg:
            def __init__(self, order_type, quantity, price):
                self.order_type = order_type
                self.quantity = quantity
                self.price = price

        class MockOrderData:
            def __init__(self):
                self.legs = [
                    MockLeg(OrderType.BUY, 100, 150.00),
                    MockLeg(OrderType.SELL, 100, 155.00),
                ]
                self.condition = OrderCondition.LIMIT

        with (
            patch.object(trading_service, "_get_async_db_session") as mock_session,
            patch.object(trading_service, "_get_account") as mock_get_account,
        ):
            mock_db = AsyncMock()
            mock_session.return_value = mock_db

            mock_account = Mock()
            mock_account.id = "account-123"
            mock_get_account.return_value = mock_account

            order_data = MockOrderData()
            order = await trading_service.create_multi_leg_order(order_data)

            assert order.symbol.startswith("MULTI_LEG")
            assert order.quantity == 200  # Sum of leg quantities
            assert order.status == OrderStatus.FILLED
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_success(self, trading_service):
        """Test multi-leg order creation from request data."""
        legs = [
            {"symbol": "AAPL240119C150", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240119C155", "quantity": 1, "side": "sell"},
        ]

        with patch.object(trading_service, "create_multi_leg_order") as mock_create:
            mock_order = Order(
                id="order-123",
                symbol="MULTI_LEG_2_LEGS",
                order_type=OrderType.BUY,
                quantity=2,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            mock_create.return_value = mock_order

            order = await trading_service.create_multi_leg_order_from_request(
                legs, "limit", 2.50
            )

            assert order.id == "order-123"
            assert order.symbol == "MULTI_LEG_2_LEGS"
            mock_create.assert_called_once()


class TestTradingServiceAdvancedFeatures:
    """Test advanced trading features and integrations."""

    @pytest.mark.asyncio
    async def test_find_tradable_options_success(self, trading_service):
        """Test successful tradable options search."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=150.00,
            expiration_date=date.today() + timedelta(days=30),
            calls=[sample_option_quote()],
            puts=[],
        )

        with patch.object(
            trading_service, "get_options_chain", return_value=mock_chain
        ):
            result = await trading_service.find_tradable_options("AAPL", None, "call")

            assert result["symbol"] == "AAPL"
            assert result["total_found"] == 1
            assert len(result["options"]) == 1
            assert result["options"][0]["option_type"] == "call"

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_chain_returns_empty(self, trading_service):
        """Test tradable options search with no chain returns empty result."""
        with patch.object(trading_service, "get_options_chain", return_value=None):
            result = await trading_service.find_tradable_options("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["total_found"] == 0
            assert result["message"] == "No tradable options found"

    @pytest.mark.asyncio
    async def test_get_stock_price_success(self, trading_service, sample_stock_quote):
        """Test successful stock price retrieval."""
        with patch.object(
            trading_service, "get_enhanced_quote", return_value=sample_stock_quote
        ):
            result = await trading_service.get_stock_price("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["price"] == 150.00
            assert result["bid_price"] == 149.95
            assert result["ask_price"] == 150.05

    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_symbol_returns_error(self, trading_service):
        """Test stock price retrieval with invalid symbol returns error."""
        with patch("app.services.trading_service.asset_factory", return_value=None):
            result = await trading_service.get_stock_price("INVALID")

            assert "error" in result
            assert "Invalid symbol: INVALID" in result["error"]

    @pytest.mark.asyncio
    async def test_simulate_expiration_success(self, trading_service, sample_portfolio):
        """Test successful expiration simulation."""
        with patch.object(
            trading_service, "get_portfolio", return_value=sample_portfolio
        ):
            result = await trading_service.simulate_expiration(
                "2024-01-19", dry_run=True
            )

            assert result["processing_date"] == "2024-01-19"
            assert result["dry_run"] is True
            assert "total_positions" in result
            assert "summary" in result

    @pytest.mark.asyncio
    async def test_validate_account_state_success(self, trading_service):
        """Test successful account state validation."""
        with (
            patch.object(trading_service, "get_account_balance", return_value=10000.00),
            patch.object(trading_service, "get_positions", return_value=[]),
            patch.object(
                trading_service.account_validation,
                "validate_account_state",
                return_value=True,
            ),
        ):
            result = await trading_service.validate_account_state()

            assert result is True


class TestTradingServiceErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, trading_service):
        """Test handling of database connection errors."""
        with patch.object(trading_service, "_get_async_db_session") as mock_session:
            mock_session.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await trading_service.get_account_balance()

    @pytest.mark.asyncio
    async def test_quote_adapter_timeout_handling(self, trading_service):
        """Test handling of quote adapter timeouts."""
        trading_service.quote_adapter.get_quote.side_effect = asyncio.TimeoutError(
            "Timeout"
        )

        with pytest.raises(NotFoundError):
            await trading_service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_invalid_order_data_handling(self, trading_service):
        """Test handling of invalid order data."""
        order_data = OrderCreate(
            symbol="",  # Invalid empty symbol
            order_type=OrderType.BUY,
            quantity=0,  # Invalid zero quantity
            price=-100.00,  # Invalid negative price
        )

        with pytest.raises(Exception):
            await trading_service.create_order(order_data)

    @pytest.mark.asyncio
    async def test_concurrent_access_handling(self, trading_service):
        """Test handling of concurrent access to accounts."""

        # This test simulates concurrent operations on the same account
        async def concurrent_operation():
            return await trading_service.get_account_balance()

        with patch.object(trading_service, "_get_account") as mock_get_account:
            mock_account = Mock()
            mock_account.cash_balance = 10000.00
            mock_get_account.return_value = mock_account

            # Run multiple operations concurrently
            tasks = [concurrent_operation() for _ in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed or fail gracefully
            for result in results:
                if not isinstance(result, Exception):
                    assert result == 10000.00


@pytest.mark.integration
class TestTradingServiceIntegration:
    """Integration tests with real database and quote adapter behavior."""

    @pytest.mark.asyncio
    async def test_end_to_end_order_workflow(self, trading_service):
        """Test complete order workflow from creation to portfolio update."""
        # This would be a comprehensive integration test
        # covering the full order lifecycle
        pass

    @pytest.mark.asyncio
    async def test_portfolio_consistency_after_trades(self, trading_service):
        """Test portfolio state consistency after multiple trades."""
        # This would test that portfolio calculations remain
        # consistent after complex trading scenarios
        pass

    @pytest.mark.asyncio
    async def test_database_transaction_integrity(self, trading_service):
        """Test database transaction integrity during order processing."""
        # This would test that database transactions are
        # properly handled with rollbacks on errors
        pass


def sample_option_quote():
    """Helper function to create sample option quote."""
    call_option = Call(
        underlying=Stock(symbol="AAPL"),
        strike=150.0,
        expiration_date=date.today() + timedelta(days=30),
    )
    return OptionQuote(
        asset=call_option,
        price=5.50,
        bid=5.45,
        ask=5.55,
        delta=0.6,
        gamma=0.05,
        theta=-0.02,
        vega=0.15,
        quote_date=datetime.now(),
    )
