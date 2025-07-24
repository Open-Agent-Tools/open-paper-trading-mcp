"""
Comprehensive unit tests for MCP order cancellation tools.

Tests all order cancellation functionality:
- cancel_stock_order_by_id: Cancel specific stock orders by ID
- cancel_option_order_by_id: Cancel specific option orders by ID
- cancel_all_stock_orders_tool: Cancel all pending/triggered stock orders
- cancel_all_option_orders_tool: Cancel all pending/triggered option orders

Ensures proper validation, error handling, and standardized response formats.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from app.mcp.trading_tools import (
    cancel_all_option_orders_tool,
    cancel_all_stock_orders_tool,
    cancel_option_order_by_id,
    cancel_stock_order_by_id,
    set_mcp_trading_service,
)
from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.trading_service import TradingService


class TestCancelStockOrderById:
    """Test cancel_stock_order_by_id function."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service."""
        service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(service)
        return service

    @pytest.fixture
    def sample_stock_order(self):
        """Create a sample stock order."""
        return Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @pytest.fixture
    def sample_option_order(self):
        """Create a sample option order."""
        return Order(
            id="order456",
            symbol="AAPL240119C00150000",
            order_type=OrderType.BTO,
            quantity=1,
            price=5.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_cancel_stock_order_success(
        self, mock_trading_service, sample_stock_order
    ):
        """Test successful stock order cancellation."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_stock_order
        mock_trading_service.cancel_order.return_value = {
            "message": "Order cancelled successfully"
        }

        # Execute
        result = await cancel_stock_order_by_id("order123")

        # Verify
        assert result["result"]["status"] == "success"
        assert (
            result["result"]["data"]["message"] == "Stock order cancelled successfully"
        )
        assert result["result"]["data"]["order_id"] == "order123"
        assert result["result"]["data"]["symbol"] == "AAPL"

        mock_trading_service.get_order.assert_called_once_with("order123")
        mock_trading_service.cancel_order.assert_called_once_with("order123")

    @pytest.mark.asyncio
    async def test_cancel_non_stock_order_error(
        self, mock_trading_service, sample_option_order
    ):
        """Test error when trying to cancel non-stock order as stock order."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_option_order

        # Execute
        result = await cancel_stock_order_by_id("order456")

        # Verify
        assert result["result"]["status"] == "error"
        assert "is not a stock order" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("order456")
        mock_trading_service.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_stock_order_not_found(self, mock_trading_service):
        """Test error when order is not found."""
        # Setup mocks
        mock_trading_service.get_order.side_effect = NotFoundError("Order not found")

        # Execute
        result = await cancel_stock_order_by_id("nonexistent")

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_stock_order_by_id" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("nonexistent")
        mock_trading_service.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_stock_order_service_error(
        self, mock_trading_service, sample_stock_order
    ):
        """Test handling of service errors during cancellation."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_stock_order
        mock_trading_service.cancel_order.side_effect = Exception("Database error")

        # Execute
        result = await cancel_stock_order_by_id("order123")

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_stock_order_by_id" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("order123")
        mock_trading_service.cancel_order.assert_called_once_with("order123")


class TestCancelOptionOrderById:
    """Test cancel_option_order_by_id function."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service."""
        service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(service)
        return service

    @pytest.fixture
    def sample_option_order(self):
        """Create a sample option order."""
        return Order(
            id="option123",
            symbol="AAPL240119C00150000",
            order_type=OrderType.BTO,
            quantity=2,
            price=7.50,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @pytest.fixture
    def sample_stock_order(self):
        """Create a sample stock order."""
        return Order(
            id="stock123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_cancel_option_order_success(
        self, mock_trading_service, sample_option_order
    ):
        """Test successful option order cancellation."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_option_order
        mock_trading_service.cancel_order.return_value = {
            "message": "Order cancelled successfully"
        }

        # Execute
        result = await cancel_option_order_by_id("option123")

        # Verify
        assert result["result"]["status"] == "success"
        assert (
            result["result"]["data"]["message"] == "Option order cancelled successfully"
        )
        assert result["result"]["data"]["order_id"] == "option123"
        assert result["result"]["data"]["symbol"] == "AAPL240119C00150000"
        assert "option_details" in result["result"]["data"]

        option_details = result["result"]["data"]["option_details"]
        assert option_details["underlying"] == "AAPL"
        assert option_details["strike"] == 150.0
        assert option_details["option_type"] == "call"

        mock_trading_service.get_order.assert_called_once_with("option123")
        mock_trading_service.cancel_order.assert_called_once_with("option123")

    @pytest.mark.asyncio
    async def test_cancel_non_option_order_error(
        self, mock_trading_service, sample_stock_order
    ):
        """Test error when trying to cancel non-option order as option order."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_stock_order

        # Execute
        result = await cancel_option_order_by_id("stock123")

        # Verify
        assert result["result"]["status"] == "error"
        assert "is not an option order" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("stock123")
        mock_trading_service.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_option_order_not_found(self, mock_trading_service):
        """Test error when option order is not found."""
        # Setup mocks
        mock_trading_service.get_order.side_effect = NotFoundError("Order not found")

        # Execute
        result = await cancel_option_order_by_id("nonexistent")

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_option_order_by_id" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("nonexistent")
        mock_trading_service.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_option_order_service_error(
        self, mock_trading_service, sample_option_order
    ):
        """Test handling of service errors during option cancellation."""
        # Setup mocks
        mock_trading_service.get_order.return_value = sample_option_order
        mock_trading_service.cancel_order.side_effect = Exception("Database error")

        # Execute
        result = await cancel_option_order_by_id("option123")

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_option_order_by_id" in result["result"]["error"]

        mock_trading_service.get_order.assert_called_once_with("option123")
        mock_trading_service.cancel_order.assert_called_once_with("option123")


class TestCancelAllStockOrdersTool:
    """Test cancel_all_stock_orders_tool function."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service."""
        service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(service)
        return service

    @pytest.mark.asyncio
    async def test_cancel_all_stock_orders_success(self, mock_trading_service):
        """Test successful cancellation of all stock orders."""
        # Setup mock response
        cancel_result = {
            "message": "Cancelled 3 stock orders",
            "cancelled_orders": [
                {
                    "id": "order1",
                    "symbol": "AAPL",
                    "order_type": "buy",
                    "quantity": 100,
                    "price": 150.0,
                },
                {
                    "id": "order2",
                    "symbol": "GOOGL",
                    "order_type": "sell",
                    "quantity": 50,
                    "price": 2500.0,
                },
                {
                    "id": "order3",
                    "symbol": "MSFT",
                    "order_type": "buy",
                    "quantity": 200,
                    "price": 300.0,
                },
            ],
            "total_cancelled": 3,
        }
        mock_trading_service.cancel_all_stock_orders.return_value = cancel_result

        # Execute
        result = await cancel_all_stock_orders_tool()

        # Verify
        assert result["result"]["status"] == "success"
        assert (
            result["result"]["data"]["message"] == "Stock order cancellation completed"
        )
        assert result["result"]["data"]["result"]["total_cancelled"] == 3
        assert len(result["result"]["data"]["result"]["cancelled_orders"]) == 3

        mock_trading_service.cancel_all_stock_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_all_stock_orders_none_found(self, mock_trading_service):
        """Test when no stock orders are found to cancel."""
        # Setup mock response
        cancel_result = {
            "message": "Cancelled 0 stock orders",
            "cancelled_orders": [],
            "total_cancelled": 0,
        }
        mock_trading_service.cancel_all_stock_orders.return_value = cancel_result

        # Execute
        result = await cancel_all_stock_orders_tool()

        # Verify
        assert result["result"]["status"] == "success"
        assert result["result"]["data"]["result"]["total_cancelled"] == 0
        assert result["result"]["data"]["result"]["cancelled_orders"] == []

        mock_trading_service.cancel_all_stock_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_all_stock_orders_service_error(self, mock_trading_service):
        """Test handling of service errors during bulk stock cancellation."""
        # Setup mocks
        mock_trading_service.cancel_all_stock_orders.side_effect = Exception(
            "Database connection failed"
        )

        # Execute
        result = await cancel_all_stock_orders_tool()

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_all_stock_orders_tool" in result["result"]["error"]

        mock_trading_service.cancel_all_stock_orders.assert_called_once()


class TestCancelAllOptionOrdersTool:
    """Test cancel_all_option_orders_tool function."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service."""
        service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(service)
        return service

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_success(self, mock_trading_service):
        """Test successful cancellation of all option orders."""
        # Setup mock response
        cancel_result = {
            "message": "Cancelled 2 option orders",
            "cancelled_orders": [
                {
                    "id": "opt1",
                    "symbol": "AAPL240119C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": 5.0,
                },
                {
                    "id": "opt2",
                    "symbol": "GOOGL240119P02500000",
                    "order_type": "sell_to_open",
                    "quantity": 2,
                    "price": 50.0,
                },
            ],
            "total_cancelled": 2,
        }
        mock_trading_service.cancel_all_option_orders.return_value = cancel_result

        # Execute
        result = await cancel_all_option_orders_tool()

        # Verify
        assert result["result"]["status"] == "success"
        assert (
            result["result"]["data"]["message"] == "Option order cancellation completed"
        )
        assert result["result"]["data"]["result"]["total_cancelled"] == 2
        assert len(result["result"]["data"]["result"]["cancelled_orders"]) == 2

        mock_trading_service.cancel_all_option_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_none_found(self, mock_trading_service):
        """Test when no option orders are found to cancel."""
        # Setup mock response
        cancel_result = {
            "message": "Cancelled 0 option orders",
            "cancelled_orders": [],
            "total_cancelled": 0,
        }
        mock_trading_service.cancel_all_option_orders.return_value = cancel_result

        # Execute
        result = await cancel_all_option_orders_tool()

        # Verify
        assert result["result"]["status"] == "success"
        assert result["result"]["data"]["result"]["total_cancelled"] == 0
        assert result["result"]["data"]["result"]["cancelled_orders"] == []

        mock_trading_service.cancel_all_option_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_service_error(self, mock_trading_service):
        """Test handling of service errors during bulk option cancellation."""
        # Setup mocks
        mock_trading_service.cancel_all_option_orders.side_effect = Exception(
            "Database transaction failed"
        )

        # Execute
        result = await cancel_all_option_orders_tool()

        # Verify
        assert result["result"]["status"] == "error"
        assert "Error in cancel_all_option_orders_tool" in result["result"]["error"]

        mock_trading_service.cancel_all_option_orders.assert_called_once()


class TestCancellationIntegration:
    """Integration tests for cancellation tools."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create a mock trading service."""
        service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(service)
        return service

    @pytest.mark.asyncio
    async def test_mixed_order_types_validation(self, mock_trading_service):
        """Test that tools properly validate order types."""
        # Create orders with different types
        stock_order = Order(
            id="stock1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
        )
        option_order = Order(
            id="option1",
            symbol="AAPL240119C00150000",
            order_type=OrderType.BTO,
            quantity=1,
            price=5.0,
            status=OrderStatus.PENDING,
        )

        # Test stock cancellation with stock order (should succeed)
        mock_trading_service.get_order.return_value = stock_order
        mock_trading_service.cancel_order.return_value = {"message": "Success"}

        result = await cancel_stock_order_by_id("stock1")
        assert result["result"]["status"] == "success"

        # Test stock cancellation with option order (should fail)
        mock_trading_service.get_order.return_value = option_order

        result = await cancel_stock_order_by_id("option1")
        assert result["result"]["status"] == "error"
        assert "is not a stock order" in result["result"]["error"]

        # Test option cancellation with option order (should succeed)
        mock_trading_service.get_order.return_value = option_order
        mock_trading_service.cancel_order.return_value = {"message": "Success"}

        result = await cancel_option_order_by_id("option1")
        assert result["result"]["status"] == "success"

        # Test option cancellation with stock order (should fail)
        mock_trading_service.get_order.return_value = stock_order

        result = await cancel_option_order_by_id("stock1")
        assert result["result"]["status"] == "error"
        assert "is not an option order" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_bulk_cancellation_edge_cases(self, mock_trading_service):
        """Test bulk cancellation with edge cases."""
        # Test with empty results
        empty_result = {
            "message": "Cancelled 0 stock orders",
            "cancelled_orders": [],
            "total_cancelled": 0,
        }

        mock_trading_service.cancel_all_stock_orders.return_value = empty_result
        result = await cancel_all_stock_orders_tool()
        assert result["result"]["status"] == "success"
        assert result["result"]["data"]["result"]["total_cancelled"] == 0

        mock_trading_service.cancel_all_option_orders.return_value = empty_result.copy()
        mock_trading_service.cancel_all_option_orders.return_value["message"] = (
            "Cancelled 0 option orders"
        )
        result = await cancel_all_option_orders_tool()
        assert result["result"]["status"] == "success"
        assert result["result"]["data"]["result"]["total_cancelled"] == 0

    @pytest.mark.asyncio
    async def test_response_format_consistency(self, mock_trading_service):
        """Test that all cancellation tools return consistent response formats."""
        # Setup basic mocks
        stock_order = Order(
            id="test1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
        )
        option_order = Order(
            id="test2",
            symbol="AAPL240119C00150000",
            order_type=OrderType.BTO,
            quantity=1,
            price=5.0,
            status=OrderStatus.PENDING,
        )

        cancel_response = {"message": "Order cancelled successfully"}
        bulk_response = {
            "message": "Cancelled 1 stock orders",
            "cancelled_orders": [],
            "total_cancelled": 1,
        }

        # Test all functions return proper format
        mock_trading_service.get_order.return_value = stock_order
        mock_trading_service.cancel_order.return_value = cancel_response

        result = await cancel_stock_order_by_id("test1")
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]

        mock_trading_service.get_order.return_value = option_order
        result = await cancel_option_order_by_id("test2")
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]

        mock_trading_service.cancel_all_stock_orders.return_value = bulk_response
        result = await cancel_all_stock_orders_tool()
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]

        bulk_response["message"] = "Cancelled 1 option orders"
        mock_trading_service.cancel_all_option_orders.return_value = bulk_response
        result = await cancel_all_option_orders_tool()
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]
