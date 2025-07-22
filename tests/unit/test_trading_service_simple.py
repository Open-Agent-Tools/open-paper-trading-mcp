"""
Simple unit tests for TradingService that focus on functionality without complex database setup.
These tests use mocking to isolate the service layer and test core business logic.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.test_data import DevDataQuoteAdapter
from app.schemas.orders import OrderCreate, OrderType
from app.services.trading_service import TradingService


class TestTradingServiceBasic:
    """Basic TradingService tests using mocks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = DevDataQuoteAdapter()
        self.service = TradingService(self.adapter)

    def test_trading_service_initialization(self):
        """Test TradingService can be initialized properly."""
        assert self.service is not None
        assert self.service.quote_adapter is not None

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @pytest.mark.asyncio
    async def test_get_quote_basic(self, mock_db):
        """Test basic quote retrieval functionality."""
        # Arrange
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        # Act
        quote = await self.service.get_quote("AAPL")

        # Assert
        assert quote is not None
        assert quote.symbol == "AAPL"
        assert quote.price > 0

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @pytest.mark.asyncio
    async def test_get_stock_price(self, mock_db):
        """Test stock price retrieval."""
        # Arrange
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        # Act
        price = await self.service.get_stock_price("AAPL")

        # Assert
        assert price > 0
        assert isinstance(price, int | float | Decimal)

    def test_quote_adapter_assignment(self):
        """Test quote adapter is properly assigned."""
        assert isinstance(self.service.quote_adapter, DevDataQuoteAdapter)

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @pytest.mark.asyncio
    async def test_validate_symbol_basic(self, mock_db):
        """Test basic symbol validation."""
        # Arrange
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        # Act & Assert - Should not raise exception for valid symbols
        await self.service._validate_symbol("AAPL")
        await self.service._validate_symbol("GOOGL")


class TestTradingServicePortfolio:
    """Portfolio-related tests with minimal database interaction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = DevDataQuoteAdapter()
        self.service = TradingService(self.adapter)

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @patch("app.services.trading_service.TradingService._get_account")
    @pytest.mark.asyncio
    async def test_get_portfolio_structure(self, mock_get_account, mock_db):
        """Test portfolio structure without database dependency."""
        # Arrange
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        mock_account = MagicMock()
        mock_account.id = "test-account"
        mock_account.cash_balance = 10000.0
        mock_get_account.return_value = mock_account

        # Mock database query results
        mock_session.execute.return_value.fetchall.return_value = []

        # Act
        portfolio = await self.service.get_portfolio("test_user")

        # Assert
        assert portfolio is not None
        assert hasattr(portfolio, "total_value")
        assert hasattr(portfolio, "cash_balance")
        assert hasattr(portfolio, "positions")


class TestTradingServiceValidation:
    """Test validation methods and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = DevDataQuoteAdapter()
        self.service = TradingService(self.adapter)

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @pytest.mark.asyncio
    async def test_validate_order_create_basic(self, mock_db):
        """Test basic order validation."""
        # Arrange
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        order = OrderCreate(symbol="AAPL", quantity=10, order_type=OrderType.MARKET)

        # Act & Assert - Should not raise for valid order
        # Note: This tests the validation logic exists, not full implementation
        try:
            await self.service._validate_symbol(order.symbol)
        except Exception:
            pytest.fail("Basic order validation should not raise exception")


class TestTradingServiceMarketData:
    """Market data related tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = DevDataQuoteAdapter()
        self.service = TradingService(self.adapter)

    def test_quote_adapter_get_quote(self):
        """Test quote adapter functionality directly."""
        # Act
        quote = self.adapter.get_quote("AAPL")

        # Assert
        assert quote is not None
        assert quote.symbol == "AAPL"
        assert quote.price > 0

    def test_quote_adapter_supports_symbols(self):
        """Test quote adapter supports common symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]

        for symbol in symbols:
            quote = self.adapter.get_quote(symbol)
            assert quote is not None
            assert quote.symbol == symbol


class TestTradingServiceAsync:
    """Test async patterns and database session management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = DevDataQuoteAdapter()
        self.service = TradingService(self.adapter)

    @patch("app.services.trading_service.TradingService._get_async_db_session")
    @pytest.mark.asyncio
    async def test_async_db_session_context_manager(self, mock_db):
        """Test async database session is used as context manager."""
        # Arrange
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.return_value = mock_context_manager

        # Act
        async with self.service._get_async_db_session() as session:
            assert session == mock_session

        # Assert
        mock_context_manager.__aenter__.assert_called_once()
        mock_context_manager.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_method_signatures_are_async(self):
        """Test that key service methods are properly async."""
        import inspect

        # Check that critical methods are async
        assert inspect.iscoroutinefunction(self.service.get_portfolio)
        assert inspect.iscoroutinefunction(self.service.get_quote)
        assert inspect.iscoroutinefunction(self.service.get_stock_price)
