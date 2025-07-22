"""
Advanced unit tests for core MCP tools implementation.

Tests async patterns, parameter validation, response formatting,
service integration, and error handling in MCP trading tools.
"""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.mcp.tools import (
    CancelOrderArgs,
    CreateOrderArgs,
    GetOrderArgs,
    GetPositionArgs,
    GetQuoteArgs,
    cancel_order,
    create_buy_order,
    create_sell_order,
    get_all_orders,
    get_all_positions,
    get_mcp_trading_service,
    get_order,
    get_portfolio,
    get_portfolio_summary,
    get_position,
    get_stock_quote,
    set_mcp_trading_service,
)
from app.schemas.orders import OrderCondition, OrderStatus, OrderType
from app.services.trading_service import TradingService


class TestMCPToolParameterValidation:
    """Test parameter validation for MCP tools."""

    def test_get_quote_args_validation(self):
        """Test GetQuoteArgs parameter validation."""
        # Valid args
        args = GetQuoteArgs(symbol="AAPL")
        assert args.symbol == "AAPL"

        # Test required field
        with pytest.raises(ValidationError):
            GetQuoteArgs()  # Missing required symbol

    def test_create_order_args_validation(self):
        """Test CreateOrderArgs parameter validation."""
        # Valid args
        args = CreateOrderArgs(
            symbol="GOOGL", order_type=OrderType.BUY, quantity=100, price=2500.50
        )
        assert args.symbol == "GOOGL"
        assert args.order_type == OrderType.BUY
        assert args.quantity == 100
        assert args.price == 2500.50

        # Test quantity validation (must be positive)
        with pytest.raises(ValidationError):
            CreateOrderArgs(
                symbol="GOOGL",
                order_type=OrderType.BUY,
                quantity=0,  # Invalid
                price=2500.50,
            )

        # Test price validation (must be positive)
        with pytest.raises(ValidationError):
            CreateOrderArgs(
                symbol="GOOGL",
                order_type=OrderType.BUY,
                quantity=100,
                price=-10.0,  # Invalid
            )

    def test_get_order_args_validation(self):
        """Test GetOrderArgs parameter validation."""
        args = GetOrderArgs(order_id="order-123")
        assert args.order_id == "order-123"

        with pytest.raises(ValidationError):
            GetOrderArgs()  # Missing required order_id

    def test_cancel_order_args_validation(self):
        """Test CancelOrderArgs parameter validation."""
        args = CancelOrderArgs(order_id="order-456")
        assert args.order_id == "order-456"

        with pytest.raises(ValidationError):
            CancelOrderArgs()  # Missing required order_id

    def test_get_position_args_validation(self):
        """Test GetPositionArgs parameter validation."""
        args = GetPositionArgs(symbol="TSLA")
        assert args.symbol == "TSLA"

        with pytest.raises(ValidationError):
            GetPositionArgs()  # Missing required symbol


class TestMCPCoreToolsAsync:
    """Test async behavior of core MCP trading tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for testing."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.mark.asyncio
    async def test_get_stock_quote_async(self, mock_trading_service):
        """Test get_stock_quote async execution."""
        # Setup mock
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.75
        mock_quote.change = 2.25
        mock_quote.change_percent = 1.52
        mock_quote.volume = 45000000
        mock_quote.last_updated = Mock()
        mock_quote.last_updated.isoformat.return_value = "2024-01-15T16:00:00Z"

        mock_trading_service.get_quote.return_value = mock_quote
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Verify async call was made
        mock_trading_service.get_quote.assert_called_once_with("AAPL")

        # Verify JSON response format
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert data["price"] == 150.75
        assert data["change"] == 2.25
        assert data["change_percent"] == 1.52
        assert data["volume"] == 45000000
        assert data["last_updated"] == "2024-01-15T16:00:00Z"

    @pytest.mark.asyncio
    async def test_create_buy_order_async(self, mock_trading_service):
        """Test create_buy_order async execution."""
        # Setup mock order response
        mock_order = Mock()
        mock_order.id = "order-buy-123"
        mock_order.symbol = "NVDA"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 50
        mock_order.price = 800.00
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = Mock()
        mock_order.created_at.isoformat.return_value = "2024-01-15T10:30:00Z"

        mock_trading_service.create_order.return_value = mock_order
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = CreateOrderArgs(
            symbol="NVDA", order_type=OrderType.BUY, quantity=50, price=800.00
        )
        result = await create_buy_order(args)

        # Verify service call
        mock_trading_service.create_order.assert_called_once()
        call_args = mock_trading_service.create_order.call_args[0][0]
        assert call_args.symbol == "NVDA"
        assert call_args.order_type == OrderType.BUY
        assert call_args.quantity == 50
        assert call_args.price == 800.00
        assert call_args.condition == OrderCondition.MARKET

        # Verify response format
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["id"] == "order-buy-123"
        assert data["symbol"] == "NVDA"
        assert data["order_type"] == OrderType.BUY
        assert data["quantity"] == 50
        assert data["price"] == 800.00
        assert data["status"] == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_sell_order_async(self, mock_trading_service):
        """Test create_sell_order async execution."""
        # Setup mock order response
        mock_order = Mock()
        mock_order.id = "order-sell-456"
        mock_order.symbol = "MSFT"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 25
        mock_order.price = 350.00
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = Mock()
        mock_order.created_at.isoformat.return_value = "2024-01-15T14:45:00Z"

        mock_trading_service.create_order.return_value = mock_order
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = CreateOrderArgs(
            symbol="MSFT", order_type=OrderType.SELL, quantity=25, price=350.00
        )
        result = await create_sell_order(args)

        # Verify service call with SELL order type
        call_args = mock_trading_service.create_order.call_args[0][0]
        assert call_args.order_type == OrderType.SELL

        # Verify response
        data = json.loads(result)
        assert data["order_type"] == OrderType.SELL

    @pytest.mark.asyncio
    async def test_get_all_orders_async(self, mock_trading_service):
        """Test get_all_orders async execution."""
        # Setup mock orders
        mock_orders = []
        for i in range(3):
            order = Mock()
            order.id = f"order-{i}"
            order.symbol = f"TEST{i}"
            order.order_type = OrderType.BUY if i % 2 == 0 else OrderType.SELL
            order.quantity = 100 + i * 10
            order.price = 50.0 + i * 5.0
            order.status = OrderStatus.PENDING
            order.created_at = Mock()
            order.created_at.isoformat.return_value = f"2024-01-15T{10 + i}:00:00Z"
            order.filled_at = None
            mock_orders.append(order)

        mock_trading_service.get_orders.return_value = mock_orders
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_all_orders()

        # Verify service call
        mock_trading_service.get_orders.assert_called_once()

        # Verify response format
        assert isinstance(result, str)
        data = json.loads(result)
        assert len(data) == 3

        for i, order_data in enumerate(data):
            assert order_data["id"] == f"order-{i}"
            assert order_data["symbol"] == f"TEST{i}"
            assert order_data["quantity"] == 100 + i * 10

    @pytest.mark.asyncio
    async def test_get_order_async(self, mock_trading_service):
        """Test get_order async execution."""
        # Setup mock order
        mock_order = Mock()
        mock_order.id = "order-specific-789"
        mock_order.symbol = "AMZN"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 15
        mock_order.price = 3200.50
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = Mock()
        mock_order.created_at.isoformat.return_value = "2024-01-15T09:30:00Z"
        mock_order.filled_at = Mock()
        mock_order.filled_at.isoformat.return_value = "2024-01-15T09:35:00Z"

        mock_trading_service.get_order.return_value = mock_order
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetOrderArgs(order_id="order-specific-789")
        result = await get_order(args)

        # Verify service call
        mock_trading_service.get_order.assert_called_once_with("order-specific-789")

        # Verify response
        data = json.loads(result)
        assert data["id"] == "order-specific-789"
        assert data["filled_at"] == "2024-01-15T09:35:00Z"

    @pytest.mark.asyncio
    async def test_cancel_order_async(self, mock_trading_service):
        """Test cancel_order async execution."""
        # Setup mock cancellation result
        mock_result = {"status": "cancelled", "order_id": "order-cancel-999"}

        mock_trading_service.cancel_order.return_value = mock_result
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = CancelOrderArgs(order_id="order-cancel-999")
        result = await cancel_order(args)

        # Verify service call
        mock_trading_service.cancel_order.assert_called_once_with("order-cancel-999")

        # Verify response
        data = json.loads(result)
        assert data["status"] == "cancelled"
        assert data["order_id"] == "order-cancel-999"


class TestMCPPortfolioTools:
    """Test portfolio-related MCP tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for portfolio testing."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.mark.asyncio
    async def test_get_portfolio_async(self, mock_trading_service):
        """Test get_portfolio async execution."""
        # Setup mock portfolio
        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 100
        mock_position.avg_price = 150.00
        mock_position.current_price = 155.00
        mock_position.unrealized_pnl = 500.00
        mock_position.realized_pnl = 0.00

        mock_portfolio = Mock()
        mock_portfolio.positions = [mock_position]
        mock_portfolio.cash_balance = 25000.00
        mock_portfolio.total_value = 40500.00
        mock_portfolio.daily_pnl = 250.00
        mock_portfolio.total_pnl = 1200.00

        mock_trading_service.get_portfolio.return_value = mock_portfolio
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_portfolio()

        # Verify service call
        mock_trading_service.get_portfolio.assert_called_once()

        # Verify response
        data = json.loads(result)
        assert data["cash_balance"] == 25000.00
        assert data["total_value"] == 40500.00
        assert data["daily_pnl"] == 250.00
        assert data["total_pnl"] == 1200.00
        assert len(data["positions"]) == 1

        position_data = data["positions"][0]
        assert position_data["symbol"] == "AAPL"
        assert position_data["quantity"] == 100
        assert position_data["unrealized_pnl"] == 500.00

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_async(self, mock_trading_service):
        """Test get_portfolio_summary async execution."""
        # Setup mock summary
        mock_summary = Mock()
        mock_summary.total_value = 75000.00
        mock_summary.cash_balance = 15000.00
        mock_summary.invested_value = 60000.00
        mock_summary.daily_pnl = 750.00
        mock_summary.daily_pnl_percent = 1.0
        mock_summary.total_pnl = 5000.00
        mock_summary.total_pnl_percent = 7.14

        mock_trading_service.get_portfolio_summary.return_value = mock_summary
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_portfolio_summary()

        # Verify service call
        mock_trading_service.get_portfolio_summary.assert_called_once()

        # Verify response
        data = json.loads(result)
        assert data["total_value"] == 75000.00
        assert data["cash_balance"] == 15000.00
        assert data["invested_value"] == 60000.00
        assert data["daily_pnl_percent"] == 1.0
        assert data["total_pnl_percent"] == 7.14

    @pytest.mark.asyncio
    async def test_get_all_positions_async(self, mock_trading_service):
        """Test get_all_positions async execution."""
        # Setup mock positions
        mock_positions = []
        symbols = ["AAPL", "GOOGL", "MSFT"]

        for i, symbol in enumerate(symbols):
            position = Mock()
            position.symbol = symbol
            position.quantity = 50 + i * 25
            position.avg_price = 100.0 + i * 50.0
            position.current_price = 105.0 + i * 55.0
            position.unrealized_pnl = (
                position.current_price - position.avg_price
            ) * position.quantity
            position.realized_pnl = i * 100.0
            mock_positions.append(position)

        mock_trading_service.get_positions.return_value = mock_positions
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_all_positions()

        # Verify service call
        mock_trading_service.get_positions.assert_called_once()

        # Verify response
        data = json.loads(result)
        assert len(data) == 3

        for i, position_data in enumerate(data):
            assert position_data["symbol"] == symbols[i]
            assert position_data["quantity"] == 50 + i * 25

    @pytest.mark.asyncio
    async def test_get_position_async(self, mock_trading_service):
        """Test get_position async execution."""
        # Setup mock position
        mock_position = Mock()
        mock_position.symbol = "TSLA"
        mock_position.quantity = 30
        mock_position.avg_price = 850.00
        mock_position.current_price = 900.00
        mock_position.unrealized_pnl = 1500.00
        mock_position.realized_pnl = 200.00

        mock_trading_service.get_position.return_value = mock_position
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetPositionArgs(symbol="TSLA")
        result = await get_position(args)

        # Verify service call
        mock_trading_service.get_position.assert_called_once_with("TSLA")

        # Verify response
        data = json.loads(result)
        assert data["symbol"] == "TSLA"
        assert data["quantity"] == 30
        assert data["avg_price"] == 850.00
        assert data["current_price"] == 900.00
        assert data["unrealized_pnl"] == 1500.00
        assert data["realized_pnl"] == 200.00


class TestMCPToolErrorHandling:
    """Test error handling in MCP tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for error testing."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.mark.asyncio
    async def test_get_stock_quote_error_handling(self, mock_trading_service):
        """Test error handling in get_stock_quote."""
        # Setup service to raise exception
        mock_trading_service.get_quote.side_effect = Exception(
            "Quote service unavailable"
        )
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetQuoteArgs(symbol="INVALID")
        result = await get_stock_quote(args)

        # Should return error string, not raise
        assert isinstance(result, str)
        assert "Error getting quote" in result
        assert "Quote service unavailable" in result

    @pytest.mark.asyncio
    async def test_create_order_error_handling(self, mock_trading_service):
        """Test error handling in order creation."""
        # Setup service to raise exception
        mock_trading_service.create_order.side_effect = ValueError("Invalid symbol")
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = CreateOrderArgs(
            symbol="INVALID", order_type=OrderType.BUY, quantity=100, price=50.0
        )
        result = await create_buy_order(args)

        # Should return error string
        assert isinstance(result, str)
        assert "Error creating buy order" in result
        assert "Invalid symbol" in result

    @pytest.mark.asyncio
    async def test_portfolio_error_handling(self, mock_trading_service):
        """Test error handling in portfolio operations."""
        # Setup service to raise exception
        mock_trading_service.get_portfolio.side_effect = RuntimeError(
            "Database connection failed"
        )
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_portfolio()

        # Should return error string
        assert isinstance(result, str)
        assert "Error getting portfolio" in result
        assert "Database connection failed" in result

    @pytest.mark.asyncio
    async def test_json_serialization_edge_cases(self, mock_trading_service):
        """Test JSON serialization with edge case data."""
        # Setup mock with special numeric values
        mock_quote = Mock()
        mock_quote.symbol = "TEST"
        mock_quote.price = float("inf")  # Edge case
        mock_quote.change = 0.0
        mock_quote.change_percent = float("nan")  # Edge case
        mock_quote.volume = 1000000
        mock_quote.last_updated = Mock()
        mock_quote.last_updated.isoformat.return_value = "2024-01-15T16:00:00Z"

        mock_trading_service.get_quote.return_value = mock_quote
        set_mcp_trading_service(mock_trading_service)

        # Execute tool - should handle inf/nan gracefully
        args = GetQuoteArgs(symbol="TEST")
        result = await get_stock_quote(args)

        # Should either serialize correctly or return error string
        assert isinstance(result, str)
        # If error, should contain error message
        if "Error" in result:
            assert "getting quote" in result
        else:
            # If successful, should be valid JSON
            try:
                json.loads(result)
            except json.JSONDecodeError:
                pytest.fail("Should return valid JSON or error string")


class TestMCPServiceDependencyManagement:
    """Test service dependency management in MCP tools."""

    def test_mcp_trading_service_singleton_pattern(self):
        """Test MCP trading service follows singleton pattern."""

        # Initially should be None
        import app.mcp.tools

        original_service = app.mcp.tools._trading_service

        try:
            # Clear service
            app.mcp.tools._trading_service = None

            # Set a service
            mock_service = Mock()
            set_mcp_trading_service(mock_service)

            # Get should return same instance
            retrieved = get_mcp_trading_service()
            assert retrieved is mock_service

            # Set different service
            different_service = Mock()
            set_mcp_trading_service(different_service)

            # Should now return the new service
            retrieved = get_mcp_trading_service()
            assert retrieved is different_service
            assert retrieved is not mock_service

        finally:
            # Restore original service
            app.mcp.tools._trading_service = original_service

    def test_mcp_trading_service_thread_safety_consideration(self):
        """Test considerations for thread safety in service management."""
        # This test documents the current behavior - global variable approach
        # In production, consider thread-local storage or dependency injection

        mock_service_1 = Mock(id=1)
        mock_service_2 = Mock(id=2)

        # Set service 1
        set_mcp_trading_service(mock_service_1)
        assert get_mcp_trading_service().id == 1

        # Set service 2 - overwrites globally
        set_mcp_trading_service(mock_service_2)
        assert get_mcp_trading_service().id == 2

        # This demonstrates that the current implementation uses global state
        # which could be problematic in multi-threaded environments


class TestMCPResponseFormatting:
    """Test response formatting in MCP tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for response testing."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.mark.asyncio
    async def test_json_response_formatting(self, mock_trading_service):
        """Test JSON response formatting consistency."""
        # Setup mock with complex data
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = Decimal("150.75")  # Test Decimal handling
        mock_quote.change = -2.25
        mock_quote.change_percent = -1.47
        mock_quote.volume = 45000000
        mock_quote.last_updated = datetime.fromisoformat("2024-01-15T16:00:00")

        mock_trading_service.get_quote.return_value = mock_quote
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Verify JSON formatting
        assert isinstance(result, str)
        data = json.loads(result)

        # Check indentation (should be formatted with indent=2)
        lines = result.split("\n")
        assert len(lines) > 1, "Should be multi-line formatted JSON"

        # Check data types in response
        assert isinstance(data["price"], int | float)  # Decimal converted to number
        assert isinstance(data["change"], int | float)
        assert isinstance(data["volume"], int)
        assert isinstance(data["last_updated"], str)  # datetime converted to string

    @pytest.mark.asyncio
    async def test_null_value_handling(self, mock_trading_service):
        """Test handling of None/null values in responses."""
        # Setup mock order with None filled_at
        mock_order = Mock()
        mock_order.id = "order-123"
        mock_order.symbol = "TEST"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 50.0
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = Mock()
        mock_order.created_at.isoformat.return_value = "2024-01-15T10:00:00Z"
        mock_order.filled_at = None  # Should be handled gracefully

        mock_trading_service.get_order.return_value = mock_order
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        args = GetOrderArgs(order_id="order-123")
        result = await get_order(args)

        # Verify null handling
        data = json.loads(result)
        assert data["filled_at"] is None

    @pytest.mark.asyncio
    async def test_empty_collections_formatting(self, mock_trading_service):
        """Test formatting of empty collections."""
        # Setup mock with empty orders list
        mock_trading_service.get_orders.return_value = []
        set_mcp_trading_service(mock_trading_service)

        # Execute tool
        result = await get_all_orders()

        # Verify empty array formatting
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 0

        # Should still be formatted JSON
        assert result.strip() == "[]"
