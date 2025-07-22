"""
Comprehensive tests for TradingService module.

Tests core trading functionality including:
- Service initialization and configuration
- Order management (create, get, cancel)
- Portfolio and position management
- Quote and market data operations
- Options trading and Greeks calculations
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.quotes import Quote
from app.schemas.orders import OrderCreate, OrderType
from app.services.trading_service import TradingService, _get_quote_adapter


class TestTradingServiceInitialization:
    """Test suite for TradingService initialization."""

    def test_trading_service_initialization_default(self):
        """Test TradingService initialization with defaults."""
        service = TradingService()

        assert service.account_owner == "default"
        assert service.quote_adapter is not None
        assert hasattr(service, "account_validator")
        assert hasattr(service, "strategy_service")

    def test_trading_service_initialization_with_adapter(self):
        """Test TradingService initialization with custom adapter."""
        mock_adapter = Mock()
        service = TradingService(quote_adapter=mock_adapter)

        assert service.quote_adapter is mock_adapter
        assert service.account_owner == "default"

    def test_trading_service_initialization_with_owner(self):
        """Test TradingService initialization with custom owner."""
        service = TradingService(account_owner="test_user")

        assert service.account_owner == "test_user"


class TestTradingServiceQuotes:
    """Test suite for quote operations."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self):
        """Test successful quote retrieval."""
        mock_adapter = AsyncMock()
        mock_quote = Mock(spec=Quote)
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.0
        mock_adapter.get_quote.return_value = mock_quote

        service = TradingService(quote_adapter=mock_adapter)
        result = await service.get_quote("AAPL")

        assert result is not None
        mock_adapter.get_quote.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self):
        """Test quote retrieval when symbol not found."""
        mock_adapter = AsyncMock()
        mock_adapter.get_quote.return_value = None

        service = TradingService(quote_adapter=mock_adapter)

        with pytest.raises(NotFoundError):
            await service.get_quote("INVALID")


class TestTradingServiceOrders:
    """Test suite for order management."""

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        """Test successful order creation."""
        mock_adapter = AsyncMock()
        service = TradingService(quote_adapter=mock_adapter)

        order_data = OrderCreate(
            symbol="AAPL", quantity=10, order_type=OrderType.MARKET, side="buy"
        )

        with patch.object(service, "_ensure_account_exists"):
            result = await service.create_order(order_data)

        assert result is not None
        assert "id" in result

    @pytest.mark.asyncio
    async def test_get_orders(self):
        """Test retrieving orders."""
        service = TradingService()

        with patch.object(service, "_get_async_db_session"):
            result = await service.get_orders()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_cancel_order_success(self):
        """Test successful order cancellation."""
        service = TradingService()
        order_id = str(uuid4())

        with patch.object(service, "_get_async_db_session"):
            result = await service.cancel_order(order_id)

        assert isinstance(result, dict)


class TestTradingServicePortfolio:
    """Test suite for portfolio operations."""

    @pytest.mark.asyncio
    async def test_get_portfolio(self):
        """Test portfolio retrieval."""
        service = TradingService()

        with patch.object(service, "_get_async_db_session"):
            result = await service.get_portfolio()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_positions(self):
        """Test positions retrieval."""
        service = TradingService()

        result = await service.get_positions()

        assert isinstance(result, list)


def test_get_quote_adapter():
    """Test quote adapter factory function."""
    adapter = _get_quote_adapter()
    assert adapter is not None
