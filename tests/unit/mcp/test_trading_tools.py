"""
Comprehensive unit tests for MCP trading tools - Basic Stock Trading.

Tests the buy_stock_market, sell_stock_market, and refactored create_buy_order/create_sell_order functions.
Focuses on market order execution, parameter validation, error handling, and standardized response formats.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.mcp.trading_tools import (
    _trading_service,
    buy_stock_market,
    sell_stock_market,
    set_mcp_trading_service,
)
from app.schemas.orders import OrderCondition, OrderStatus, OrderType
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService


class TestBuyStockMarket:
    """Test buy_stock_market function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_buy_stock_market_success(self):
        """Test successful market buy order execution."""
        # Mock quote response
        mock_quote = StockQuote(
            symbol="AAPL",
            price=150.50,
            change=1.25,
            change_percent=0.84,
            volume=1000000,
            last_updated=datetime(2024, 1, 1, 10, 0, 0),
        )

        # Mock order response
        mock_order = Mock()
        mock_order.id = "buy_order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.50
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.return_value = mock_order

        result = await buy_stock_market(symbol="AAPL", quantity=100)

        # Verify response format
        data = result["result"]["data"]
        assert result["result"]["status"] == "success"
        assert data["order_id"] == "buy_order_123"
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == "buy"
        assert data["quantity"] == 100
        assert data["market_price"] == 150.50
        assert data["total_cost"] == 15050.0  # 150.50 * 100
        assert data["status"] == OrderStatus.FILLED
        assert "Market buy order" in data["message"]

        # Verify service calls
        self.mock_service.get_quote.assert_called_once_with("AAPL")
        self.mock_service.create_order.assert_called_once()

        call_args = self.mock_service.create_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.order_type == OrderType.BUY
        assert call_args.quantity == 100
        assert call_args.price == 150.50
        assert call_args.condition == OrderCondition.MARKET

    @pytest.mark.asyncio
    async def test_buy_stock_market_quote_error(self):
        """Test buy market order when quote fetch fails."""
        self.mock_service.get_quote.side_effect = Exception("Symbol not found")

        result = await buy_stock_market(symbol="INVALID", quantity=100)

        # Verify error response format
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Failed to execute market buy order" in result["result"]["error"]
        assert "Symbol not found" in result["result"]["error"]

        # Verify service calls
        self.mock_service.get_quote.assert_called_once_with("INVALID")
        self.mock_service.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_order_creation_error(self):
        """Test buy market order when order creation fails."""
        mock_quote = StockQuote(
            symbol="AAPL",
            price=150.50,
            change=1.25,
            change_percent=0.84,
            volume=1000000,
            last_updated=datetime(2024, 1, 1, 10, 0, 0),
        )

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.side_effect = Exception("Insufficient funds")

        result = await buy_stock_market(symbol="AAPL", quantity=1000000)

        # Verify error response format
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Failed to execute market buy order" in result["result"]["error"]
        assert "Insufficient funds" in result["result"]["error"]

        # Verify service calls
        self.mock_service.get_quote.assert_called_once_with("AAPL")
        self.mock_service.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_stock_market_different_symbols(self):
        """Test buy market orders for different symbols."""
        symbols_data = [
            ("GOOGL", 2800.00, 5),
            ("MSFT", 350.00, 50),
            ("TSLA", 250.00, 20),
        ]

        for symbol, price, quantity in symbols_data:
            # Mock quote and order for each symbol
            mock_quote = StockQuote(
                symbol=symbol,
                price=price,
                change=0.0,
                change_percent=0.0,
                volume=100000,
                last_updated=datetime.now(),
            )

            mock_order = Mock()
            mock_order.id = f"order_{symbol.lower()}"
            mock_order.symbol = symbol
            mock_order.order_type = OrderType.BUY
            mock_order.quantity = quantity
            mock_order.price = price
            mock_order.status = OrderStatus.FILLED
            mock_order.created_at = datetime.now()

            self.mock_service.get_quote.return_value = mock_quote
            self.mock_service.create_order.return_value = mock_order

            result = await buy_stock_market(symbol=symbol, quantity=quantity)
            data = result["result"]["data"]
            assert result["result"]["status"] == "success"
            assert data["symbol"] == symbol
            assert data["quantity"] == quantity
            assert data["market_price"] == price
            assert data["total_cost"] == price * quantity

    @pytest.mark.asyncio
    async def test_buy_stock_market_fractional_prices(self):
        """Test buy market orders with fractional prices."""
        mock_quote = StockQuote(
            symbol="AAPL",
            price=150.567,  # Fractional price
            change=0.0,
            change_percent=0.0,
            volume=100000,
            last_updated=datetime.now(),
        )

        mock_order = Mock()
        mock_order.id = "fractional_order"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 33
        mock_order.price = 150.567
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime.now()

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.return_value = mock_order

        result = await buy_stock_market(symbol="AAPL", quantity=33)
        data = result["result"]["data"]
        assert result["result"]["status"] == "success"
        assert data["market_price"] == 150.567
        assert data["total_cost"] == 150.567 * 33
        assert "$150.57" in data["message"]  # Should format to 2 decimal places


class TestSellStockMarket:
    """Test sell_stock_market function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_sell_stock_market_success(self):
        """Test successful market sell order execution."""
        # Mock quote response
        mock_quote = StockQuote(
            symbol="GOOGL",
            price=2850.75,
            change=-15.25,
            change_percent=-0.53,
            volume=500000,
            last_updated=datetime(2024, 1, 1, 11, 0, 0),
        )

        # Mock order response
        mock_order = Mock()
        mock_order.id = "sell_order_456"
        mock_order.symbol = "GOOGL"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 25
        mock_order.price = 2850.75
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime(2024, 1, 1, 11, 0, 0)

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.return_value = mock_order

        result = await sell_stock_market(symbol="GOOGL", quantity=25)
        data = result["result"]["data"]
        # Verify response format
        assert result["result"]["status"] == "success"
        assert data["order_id"] == "sell_order_456"
        assert data["symbol"] == "GOOGL"
        assert data["order_type"] == "sell"
        assert data["quantity"] == 25
        assert data["market_price"] == 2850.75
        assert data["total_proceeds"] == 71268.75  # 2850.75 * 25
        assert data["status"] == OrderStatus.FILLED
        assert "Market sell order" in data["message"]

        # Verify service calls
        self.mock_service.get_quote.assert_called_once_with("GOOGL")
        self.mock_service.create_order.assert_called_once()

        call_args = self.mock_service.create_order.call_args[0][0]
        assert call_args.symbol == "GOOGL"
        assert call_args.order_type == OrderType.SELL
        assert call_args.quantity == 25
        assert call_args.price == 2850.75
        assert call_args.condition == OrderCondition.MARKET

    @pytest.mark.asyncio
    async def test_sell_stock_market_quote_error(self):
        """Test sell market order when quote fetch fails."""
        self.mock_service.get_quote.side_effect = Exception("Market closed")

        result = await sell_stock_market(symbol="AAPL", quantity=50)

        # Verify error response format
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Failed to execute market sell order" in result["result"]["error"]
        assert "Market closed" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_sell_stock_market_order_creation_error(self):
        """Test sell market order when order creation fails."""
        mock_quote = StockQuote(
            symbol="TSLA",
            price=250.00,
            change=0.0,
            change_percent=0.0,
            volume=100000,
            last_updated=datetime.now(),
        )

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.side_effect = Exception("Insufficient shares")

        result = await sell_stock_market(symbol="TSLA", quantity=1000)

        # Verify error response format
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Failed to execute market sell order" in result["result"]["error"]
        assert "Insufficient shares" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_sell_stock_market_various_quantities(self):
        """Test sell market orders with various quantities."""
        quantities = [1, 10, 100, 500, 1000]

        for quantity in quantities:
            mock_quote = StockQuote(
                symbol="MSFT",
                price=350.00,
                change=0.0,
                change_percent=0.0,
                volume=100000,
                last_updated=datetime.now(),
            )

            mock_order = Mock()
            mock_order.id = f"sell_order_{quantity}"
            mock_order.symbol = "MSFT"
            mock_order.order_type = OrderType.SELL
            mock_order.quantity = quantity
            mock_order.price = 350.00
            mock_order.status = OrderStatus.FILLED
            mock_order.created_at = datetime.now()

            self.mock_service.get_quote.return_value = mock_quote
            self.mock_service.create_order.return_value = mock_order

            result = await sell_stock_market(symbol="MSFT", quantity=quantity)
            data = result["result"]["data"]
            assert result["result"]["status"] == "success"
            assert data["quantity"] == quantity
            assert data["total_proceeds"] == 350.00 * quantity


class TestInputValidation:
    """Test input validation for both buy and sell functions."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_buy_stock_market_empty_symbol(self):
        """Test buy market order with empty symbol."""
        result = await buy_stock_market(symbol="", quantity=100)

        assert result["result"]["status"] == "error"
        assert "Symbol cannot be empty" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_whitespace_symbol(self):
        """Test buy market order with whitespace-only symbol."""
        result = await buy_stock_market(symbol="   ", quantity=100)

        assert result["result"]["status"] == "error"
        assert "Symbol cannot be empty" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_zero_quantity(self):
        """Test buy market order with zero quantity."""
        result = await buy_stock_market(symbol="AAPL", quantity=0)

        assert result["result"]["status"] == "error"
        assert "Quantity must be positive" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_negative_quantity(self):
        """Test buy market order with negative quantity."""
        result = await buy_stock_market(symbol="AAPL", quantity=-10)

        assert result["result"]["status"] == "error"
        assert "Quantity must be positive" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_stock_market_empty_symbol(self):
        """Test sell market order with empty symbol."""
        result = await sell_stock_market(symbol="", quantity=100)

        assert result["result"]["status"] == "error"
        assert "Symbol cannot be empty" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_stock_market_zero_quantity(self):
        """Test sell market order with zero quantity."""
        result = await sell_stock_market(symbol="AAPL", quantity=0)

        assert result["result"]["status"] == "error"
        assert "Quantity must be positive" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_stock_market_negative_quantity(self):
        """Test sell market order with negative quantity."""
        result = await sell_stock_market(symbol="AAPL", quantity=-50)

        assert result["result"]["status"] == "error"
        assert "Quantity must be positive" in result["result"]["error"]
        self.mock_service.get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_symbol_case_handling(self):
        """Test buy market order properly handles symbol case."""
        mock_quote = StockQuote(
            symbol="AAPL",
            price=150.00,
            change=0.0,
            change_percent=0.0,
            volume=100000,
            last_updated=datetime.now(),
        )

        mock_order = Mock()
        mock_order.id = "case_test_order"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.00
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime.now()

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.return_value = mock_order

        # Test with lowercase input
        result = await buy_stock_market(symbol="aapl", quantity=100)
        data = result["result"]["data"]
        assert result["result"]["status"] == "success"
        assert data["symbol"] == "AAPL"  # Should be uppercase

        # Verify the service was called with uppercase symbol
        self.mock_service.get_quote.assert_called_with("AAPL")

    @pytest.mark.asyncio
    async def test_sell_stock_market_symbol_trimming(self):
        """Test sell market order properly trims whitespace from symbol."""
        mock_quote = StockQuote(
            symbol="GOOGL",
            price=2800.00,
            change=0.0,
            change_percent=0.0,
            volume=100000,
            last_updated=datetime.now(),
        )

        mock_order = Mock()
        mock_order.id = "trim_test_order"
        mock_order.symbol = "GOOGL"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 10
        mock_order.price = 2800.00
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime.now()

        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.create_order.return_value = mock_order

        # Test with whitespace around symbol
        result = await sell_stock_market(symbol="  GOOGL  ", quantity=10)
        data = result["result"]["data"]
        assert result["result"]["status"] == "success"
        assert data["symbol"] == "GOOGL"

        # Verify the service was called with trimmed symbol
        self.mock_service.get_quote.assert_called_with("GOOGL")


class TestPriceValidation:
    """Test price validation scenarios."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_buy_stock_market_zero_price(self):
        """Test buy market order when quote returns zero price."""
        mock_quote = StockQuote(
            symbol="BADSTOCK",
            price=0.0,  # Zero price
            change=0.0,
            change_percent=0.0,
            volume=0,
            last_updated=datetime.now(),
        )

        self.mock_service.get_quote.return_value = mock_quote

        result = await buy_stock_market(symbol="BADSTOCK", quantity=100)

        assert result["result"]["status"] == "error"
        assert "Invalid price for symbol BADSTOCK" in result["result"]["error"]
        self.mock_service.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_stock_market_none_price(self):
        """Test buy market order when quote returns None price."""
        mock_quote = StockQuote(
            symbol="BADSTOCK",
            price=None,  # None price
            change=0.0,
            change_percent=0.0,
            volume=0,
            last_updated=datetime.now(),
        )

        self.mock_service.get_quote.return_value = mock_quote

        result = await buy_stock_market(symbol="BADSTOCK", quantity=100)

        assert result["result"]["status"] == "error"
        assert "Invalid price for symbol BADSTOCK" in result["result"]["error"]
        self.mock_service.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_stock_market_negative_price(self):
        """Test sell market order when quote returns negative price."""
        mock_quote = StockQuote(
            symbol="BADSTOCK",
            price=-10.0,  # Negative price
            change=0.0,
            change_percent=0.0,
            volume=0,
            last_updated=datetime.now(),
        )

        self.mock_service.get_quote.return_value = mock_quote

        result = await sell_stock_market(symbol="BADSTOCK", quantity=50)

        assert result["result"]["status"] == "error"
        assert "Invalid price for symbol BADSTOCK" in result["result"]["error"]
        self.mock_service.create_order.assert_not_called()


class TestErrorHandling:
    """Test error handling scenarios."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_buy_stock_market_service_not_initialized(self):
        """Test buy market order when trading service is not initialized."""
        # Temporarily set service to None
        original_service = _trading_service
        set_mcp_trading_service(None)

        try:
            result = await buy_stock_market(symbol="AAPL", quantity=100)
            assert result["result"]["status"] == "error"
            assert "TradingService not initialized" in result["result"]["error"]
        finally:
            # Restore original service
            set_mcp_trading_service(original_service)

    @pytest.mark.asyncio
    async def test_sell_stock_market_service_not_initialized(self):
        """Test sell market order when trading service is not initialized."""
        # Temporarily set service to None
        original_service = _trading_service
        set_mcp_trading_service(None)

        try:
            result = await sell_stock_market(symbol="AAPL", quantity=50)
            assert result["result"]["status"] == "error"
            assert "TradingService not initialized" in result["result"]["error"]
        finally:
            # Restore original service
            set_mcp_trading_service(original_service)

    @pytest.mark.asyncio
    async def test_buy_stock_market_generic_exception(self):
        """Test buy market order with generic exception."""
        # Simulate an unexpected error in the trading service
        self.mock_service.get_quote.side_effect = RuntimeError(
            "Unexpected system error"
        )

        result = await buy_stock_market(symbol="AAPL", quantity=100)

        assert result["result"]["status"] == "error"
        assert (
            "Failed to execute market buy order for AAPL" in result["result"]["error"]
        )
        assert "Unexpected system error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_sell_stock_market_generic_exception(self):
        """Test sell market order with generic exception."""
        # Simulate an unexpected error in the trading service
        self.mock_service.get_quote.side_effect = RuntimeError(
            "Database connection failed"
        )

        result = await sell_stock_market(symbol="GOOGL", quantity=25)

        assert result["result"]["status"] == "error"
        assert (
            "Failed to execute market sell order for GOOGL" in result["result"]["error"]
        )
        assert "Database connection failed" in result["result"]["error"]
