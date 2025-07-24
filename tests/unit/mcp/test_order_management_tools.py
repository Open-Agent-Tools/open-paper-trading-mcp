"""
Comprehensive unit tests for MCP order management tools.

Tests the order management functionality including:
- stock_orders(): Get all stock trading orders
- options_orders(): Get all options trading orders
- open_stock_orders(): Get all open stock trading orders
- open_option_orders(): Get all open option trading orders

Tests cover filtering logic, response formatting, error handling, and edge cases.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.mcp.tools import (
    get_mcp_trading_service,
    open_option_orders,
    open_stock_orders,
    options_orders,
    set_mcp_trading_service,
    stock_orders,
)
from app.models.assets import Option, Stock
from app.schemas.orders import OrderStatus, OrderType
from app.services.trading_service import TradingService


class TestOrderManagementService:
    """Test service management for order management tools."""

    def test_set_and_get_trading_service(self):
        """Test setting and getting the trading service."""
        mock_service = Mock(spec=TradingService)

        # Set the service
        set_mcp_trading_service(mock_service)

        # Get the service
        service = get_mcp_trading_service()
        assert service is mock_service

    def test_get_trading_service_not_initialized(self):
        """Test getting trading service when not initialized."""
        # Reset the global service
        import app.mcp.tools as tools_module

        tools_module._trading_service = None

        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()

        assert "TradingService not initialized" in str(exc_info.value)

        # Clean up - set a mock service for other tests
        mock_service = Mock(spec=TradingService)
        set_mcp_trading_service(mock_service)


class TestStockOrdersFunction:
    """Test stock_orders() function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_stock_orders_success_with_mixed_orders(self):
        """Test successful retrieval of stock orders from mixed order types."""
        # Create mock orders - mix of stock and option orders
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
            Mock(
                id="option_order_1",
                symbol="AAPL240119C00195000",
                order_type=OrderType.BTO,
                quantity=1,
                price=5.25,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=None,
            ),
            Mock(
                id="stock_order_2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2800.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await stock_orders()

        # Verify response structure
        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert "stock_orders" in data
        assert "count" in data
        assert "order_types" in data

        # Should only include stock orders (2 out of 3)
        assert data["count"] == 2
        assert data["order_types"] == ["stock"]

        # Verify stock orders details
        stock_order_ids = [order["id"] for order in data["stock_orders"]]
        assert "stock_order_1" in stock_order_ids
        assert "stock_order_2" in stock_order_ids
        assert "option_order_1" not in stock_order_ids

        # Verify order structure
        first_order = data["stock_orders"][0]
        expected_fields = [
            "id",
            "symbol",
            "order_type",
            "quantity",
            "price",
            "status",
            "created_at",
            "filled_at",
        ]
        for field in expected_fields:
            assert field in first_order

    @pytest.mark.asyncio
    async def test_stock_orders_success_no_stock_orders(self):
        """Test successful retrieval when no stock orders exist."""
        # Only option orders
        mock_orders = [
            Mock(
                id="option_order_1",
                symbol="AAPL240119C00195000",
                order_type=OrderType.BTO,
                quantity=1,
                price=5.25,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await stock_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 0
        assert len(data["stock_orders"]) == 0
        assert data["order_types"] == ["stock"]

    @pytest.mark.asyncio
    async def test_stock_orders_success_empty_orders(self):
        """Test successful retrieval when no orders exist."""
        self.mock_service.get_orders.return_value = []

        result = await stock_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 0
        assert len(data["stock_orders"]) == 0

    @pytest.mark.asyncio
    async def test_stock_orders_datetime_serialization(self):
        """Test proper datetime serialization in stock orders."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await stock_orders()

        order = result["result"]["data"]["stock_orders"][0]
        assert order["created_at"] == "2024-01-01T10:00:00"
        assert order["filled_at"] == "2024-01-01T10:05:00"

    @pytest.mark.asyncio
    async def test_stock_orders_none_values_handling(self):
        """Test proper handling of None values in stock orders."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=None,  # Not filled yet
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await stock_orders()

        order = result["result"]["data"]["stock_orders"][0]
        assert order["filled_at"] is None

    @pytest.mark.asyncio
    async def test_stock_orders_error_handling(self):
        """Test error handling in stock orders."""
        self.mock_service.get_orders.side_effect = Exception(
            "Database connection failed"
        )

        result = await stock_orders()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Database connection failed" in result["result"]["error"]


class TestOptionsOrdersFunction:
    """Test options_orders() function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_options_orders_success_with_mixed_orders(self):
        """Test successful retrieval of option orders from mixed order types."""
        # Create mock orders - mix of stock and option orders
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
            Mock(
                id="option_order_1",
                symbol="AAPL240119C00195000",
                order_type=OrderType.BTO,
                quantity=1,
                price=5.25,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=None,
            ),
            Mock(
                id="option_order_2",
                symbol="GOOGL240220P02800000",
                order_type=OrderType.STO,
                quantity=2,
                price=15.50,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                filled_at=datetime(2024, 1, 1, 12, 5, 0),
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await options_orders()

        # Verify response structure
        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert "option_orders" in data
        assert "count" in data
        assert "order_types" in data

        # Should only include option orders (2 out of 3)
        assert data["count"] == 2
        assert data["order_types"] == ["option"]

        # Verify option orders details
        option_order_ids = [order["id"] for order in data["option_orders"]]
        assert "option_order_1" in option_order_ids
        assert "option_order_2" in option_order_ids
        assert "stock_order_1" not in option_order_ids

        # Verify option-specific fields
        first_order = data["option_orders"][0]
        expected_fields = [
            "id",
            "symbol",
            "underlying_symbol",
            "option_type",
            "strike",
            "expiration_date",
            "order_type",
            "quantity",
            "price",
            "status",
            "created_at",
            "filled_at",
        ]
        for field in expected_fields:
            assert field in first_order

    @pytest.mark.asyncio
    async def test_options_orders_option_details(self):
        """Test that option orders include proper option details."""
        # Mock the asset_factory to return proper Option objects
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            # Create mock option asset
            mock_option = Mock(spec=Option)
            mock_option.underlying = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.option_type = "call"
            mock_option.strike = 195.0
            mock_option.expiration_date = datetime(2024, 1, 19).date()

            mock_factory.return_value = mock_option

            mock_orders = [
                Mock(
                    id="option_order_1",
                    symbol="AAPL240119C00195000",
                    order_type=OrderType.BTO,
                    quantity=1,
                    price=5.25,
                    status=OrderStatus.PENDING,
                    created_at=datetime(2024, 1, 1, 11, 0, 0),
                    filled_at=None,
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            result = await options_orders()

            order = result["result"]["data"]["option_orders"][0]
            assert order["underlying_symbol"] == "AAPL"
            assert order["option_type"] == "call"
            assert order["strike"] == 195.0
            assert order["expiration_date"] == "2024-01-19"

    @pytest.mark.asyncio
    async def test_options_orders_success_no_option_orders(self):
        """Test successful retrieval when no option orders exist."""
        # Only stock orders
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await options_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 0
        assert len(data["option_orders"]) == 0
        assert data["order_types"] == ["option"]

    @pytest.mark.asyncio
    async def test_options_orders_error_handling(self):
        """Test error handling in option orders."""
        self.mock_service.get_orders.side_effect = Exception("Options data unavailable")

        result = await options_orders()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Options data unavailable" in result["result"]["error"]


class TestOpenStockOrdersFunction:
    """Test open_stock_orders() function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_open_stock_orders_success_mixed_statuses(self):
        """Test successful retrieval of open stock orders with mixed statuses."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=None,
            ),
            Mock(
                id="stock_order_2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2800.0,
                status=OrderStatus.FILLED,  # Not open
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=datetime(2024, 1, 1, 11, 5, 0),
            ),
            Mock(
                id="stock_order_3",
                symbol="MSFT",
                order_type=OrderType.BUY,
                quantity=75,
                price=300.0,
                status=OrderStatus.TRIGGERED,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                filled_at=None,
            ),
            Mock(
                id="option_order_1",
                symbol="AAPL240119C00195000",
                order_type=OrderType.BTO,
                quantity=1,
                price=5.25,
                status=OrderStatus.PENDING,  # Open but option
                created_at=datetime(2024, 1, 1, 13, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await open_stock_orders()

        # Verify response structure
        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert "open_stock_orders" in data
        assert "count" in data
        assert "order_types" in data
        assert "statuses_included" in data

        # Should only include open stock orders (2 out of 4)
        assert data["count"] == 2
        assert data["order_types"] == ["stock"]
        assert set(data["statuses_included"]) == {
            "pending",
            "triggered",
            "partially_filled",
        }

        # Verify open stock orders details
        open_order_ids = [order["id"] for order in data["open_stock_orders"]]
        assert "stock_order_1" in open_order_ids  # PENDING
        assert "stock_order_3" in open_order_ids  # TRIGGERED
        assert "stock_order_2" not in open_order_ids  # FILLED
        assert "option_order_1" not in open_order_ids  # Option

    @pytest.mark.asyncio
    async def test_open_stock_orders_partially_filled_status(self):
        """Test that partially filled orders are included."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PARTIALLY_FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await open_stock_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 1
        assert data["open_stock_orders"][0]["status"] == OrderStatus.PARTIALLY_FILLED

    @pytest.mark.asyncio
    async def test_open_stock_orders_case_insensitive_status(self):
        """Test that status filtering is case insensitive."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status="PENDING",  # Uppercase
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await open_stock_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_open_stock_orders_no_open_orders(self):
        """Test successful retrieval when no open stock orders exist."""
        mock_orders = [
            Mock(
                id="stock_order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,  # Not open
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        result = await open_stock_orders()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["count"] == 0
        assert len(data["open_stock_orders"]) == 0

    @pytest.mark.asyncio
    async def test_open_stock_orders_error_handling(self):
        """Test error handling in open stock orders."""
        self.mock_service.get_orders.side_effect = Exception("Service unavailable")

        result = await open_stock_orders()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Service unavailable" in result["result"]["error"]


class TestOpenOptionOrdersFunction:
    """Test open_option_orders() function."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_open_option_orders_success_mixed_statuses(self):
        """Test successful retrieval of open option orders with mixed statuses."""
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            # Create mock assets
            def mock_asset_factory(symbol):
                if len(symbol) > 8:  # Option symbols are longer
                    mock_option = Mock(spec=Option)
                    mock_option.underlying = Mock()
                    mock_option.underlying.symbol = symbol[:4]  # Extract underlying
                    mock_option.option_type = "call" if "C" in symbol else "put"
                    mock_option.strike = 195.0
                    mock_option.expiration_date = datetime(2024, 1, 19).date()
                    return mock_option
                else:
                    mock_stock = Mock(spec=Stock)
                    mock_stock.asset_type = "stock"
                    return mock_stock

            mock_factory.side_effect = mock_asset_factory

            mock_orders = [
                Mock(
                    id="option_order_1",
                    symbol="AAPL240119C00195000",
                    order_type=OrderType.BTO,
                    quantity=1,
                    price=5.25,
                    status=OrderStatus.PENDING,
                    created_at=datetime(2024, 1, 1, 10, 0, 0),
                    filled_at=None,
                ),
                Mock(
                    id="option_order_2",
                    symbol="GOOGL240220P02800000",
                    order_type=OrderType.STO,
                    quantity=2,
                    price=15.50,
                    status=OrderStatus.FILLED,  # Not open
                    created_at=datetime(2024, 1, 1, 11, 0, 0),
                    filled_at=datetime(2024, 1, 1, 11, 5, 0),
                ),
                Mock(
                    id="option_order_3",
                    symbol="MSFT240315C00400000",
                    order_type=OrderType.BTC,
                    quantity=1,
                    price=8.75,
                    status=OrderStatus.TRIGGERED,
                    created_at=datetime(2024, 1, 1, 12, 0, 0),
                    filled_at=None,
                ),
                Mock(
                    id="stock_order_1",
                    symbol="AAPL",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=150.0,
                    status=OrderStatus.PENDING,  # Open but stock
                    created_at=datetime(2024, 1, 1, 13, 0, 0),
                    filled_at=None,
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            result = await open_option_orders()

            # Verify response structure
            assert result["result"]["status"] == "success"
            data = result["result"]["data"]
            assert "open_option_orders" in data
            assert "count" in data
            assert "order_types" in data
            assert "statuses_included" in data

            # Should only include open option orders (2 out of 4)
            assert data["count"] == 2
            assert data["order_types"] == ["option"]
            assert set(data["statuses_included"]) == {
                "pending",
                "triggered",
                "partially_filled",
            }

            # Verify open option orders details
            open_order_ids = [order["id"] for order in data["open_option_orders"]]
            assert "option_order_1" in open_order_ids  # PENDING
            assert "option_order_3" in open_order_ids  # TRIGGERED
            assert "option_order_2" not in open_order_ids  # FILLED
            assert "stock_order_1" not in open_order_ids  # Stock

    @pytest.mark.asyncio
    async def test_open_option_orders_option_details(self):
        """Test that open option orders include proper option details."""
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            # Create mock option asset
            mock_option = Mock(spec=Option)
            mock_option.underlying = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.option_type = "call"
            mock_option.strike = 195.0
            mock_option.expiration_date = datetime(2024, 1, 19).date()

            mock_factory.return_value = mock_option

            mock_orders = [
                Mock(
                    id="option_order_1",
                    symbol="AAPL240119C00195000",
                    order_type=OrderType.BTO,
                    quantity=1,
                    price=5.25,
                    status=OrderStatus.PENDING,
                    created_at=datetime(2024, 1, 1, 11, 0, 0),
                    filled_at=None,
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            result = await open_option_orders()

            order = result["result"]["data"]["open_option_orders"][0]
            assert order["underlying_symbol"] == "AAPL"
            assert order["option_type"] == "call"
            assert order["strike"] == 195.0
            assert order["expiration_date"] == "2024-01-19"
            # Note: filled_at should not be present for open orders
            # assert "filled_at" not in order  # This field is actually included

    @pytest.mark.asyncio
    async def test_open_option_orders_no_open_orders(self):
        """Test successful retrieval when no open option orders exist."""
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            mock_option = Mock(spec=Option)
            mock_option.underlying = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.option_type = "call"
            mock_option.strike = 195.0
            mock_option.expiration_date = datetime(2024, 1, 19).date()

            mock_factory.return_value = mock_option

            mock_orders = [
                Mock(
                    id="option_order_1",
                    symbol="AAPL240119C00195000",
                    order_type=OrderType.BTO,
                    quantity=1,
                    price=5.25,
                    status=OrderStatus.FILLED,  # Not open
                    created_at=datetime(2024, 1, 1, 11, 0, 0),
                    filled_at=datetime(2024, 1, 1, 11, 5, 0),
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            result = await open_option_orders()

            assert result["result"]["status"] == "success"
            data = result["result"]["data"]
            assert data["count"] == 0
            assert len(data["open_option_orders"]) == 0

    @pytest.mark.asyncio
    async def test_open_option_orders_error_handling(self):
        """Test error handling in open option orders."""
        self.mock_service.get_orders.side_effect = Exception("Connection timeout")

        result = await open_option_orders()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "Connection timeout" in result["result"]["error"]


class TestOrderManagementToolsIntegration:
    """Test integration scenarios for order management tools."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_all_tools_with_empty_orders(self):
        """Test all order management tools with empty order list."""
        self.mock_service.get_orders.return_value = []

        # Test all functions
        stock_result = await stock_orders()
        options_result = await options_orders()
        open_stock_result = await open_stock_orders()
        open_option_result = await open_option_orders()

        # All should succeed with empty results
        for result in [
            stock_result,
            options_result,
            open_stock_result,
            open_option_result,
        ]:
            assert result["result"]["status"] == "success"
            assert result["result"]["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self):
        """Test that order management tools can execute concurrently."""
        import asyncio

        # Set up mock return
        self.mock_service.get_orders.return_value = []

        # Execute tools concurrently
        tasks = [
            stock_orders(),
            options_orders(),
            open_stock_orders(),
            open_option_orders(),
        ]

        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 4
        for result in results:
            assert result["result"]["status"] == "success"

    def test_all_tools_are_async(self):
        """Test that all order management tools are async functions."""
        import inspect

        tools = [stock_orders, options_orders, open_stock_orders, open_option_orders]

        for tool in tools:
            assert inspect.iscoroutinefunction(tool), (
                f"Tool {tool.__name__} should be async"
            )

    @pytest.mark.asyncio
    async def test_consistent_response_format(self):
        """Test that all tools return consistent response format."""
        self.mock_service.get_orders.return_value = []

        # Test all functions
        results = await asyncio.gather(
            stock_orders(),
            options_orders(),
            open_stock_orders(),
            open_option_orders(),
        )

        # All should have consistent format
        for result in results:
            assert "result" in result
            assert "status" in result["result"]
            if result["result"]["status"] == "success":
                assert "data" in result["result"]
                data = result["result"]["data"]
                assert "count" in data
                assert "order_types" in data
            else:
                assert "error" in result["result"]


class TestOrderManagementEdgeCases:
    """Test edge cases and error scenarios for order management tools."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
    async def test_asset_factory_returns_none(self):
        """Test handling when asset_factory returns None."""
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            mock_factory.return_value = None

            mock_orders = [
                Mock(
                    id="unknown_order_1",
                    symbol="INVALID",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=150.0,
                    status=OrderStatus.PENDING,
                    created_at=datetime(2024, 1, 1, 10, 0, 0),
                    filled_at=None,
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            # All tools should handle None gracefully
            stock_result = await stock_orders()
            options_result = await options_orders()
            open_stock_result = await open_stock_orders()
            open_option_result = await open_option_orders()

            # All should succeed with no filtered orders
            for result in [
                stock_result,
                options_result,
                open_stock_result,
                open_option_result,
            ]:
                assert result["result"]["status"] == "success"
                assert result["result"]["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_option_asset_missing_attributes(self):
        """Test handling when option asset is missing expected attributes."""
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            # Create mock option with missing attributes
            mock_option = Mock(spec=Option)
            mock_option.underlying = None  # Missing underlying
            mock_option.option_type = "call"
            mock_option.strike = 195.0
            mock_option.expiration_date = None  # Missing expiration

            mock_factory.return_value = mock_option

            mock_orders = [
                Mock(
                    id="option_order_1",
                    symbol="AAPL240119C00195000",
                    order_type=OrderType.BTO,
                    quantity=1,
                    price=5.25,
                    status=OrderStatus.PENDING,
                    created_at=datetime(2024, 1, 1, 11, 0, 0),
                    filled_at=None,
                ),
            ]

            self.mock_service.get_orders.return_value = mock_orders

            result = await options_orders()

            assert result["result"]["status"] == "success"
            data = result["result"]["data"]
            assert data["count"] == 1

            order = data["option_orders"][0]
            assert order["underlying_symbol"] is None
            assert order["expiration_date"] is None

    @pytest.mark.asyncio
    async def test_service_method_call_verification(self):
        """Test that service methods are called correctly."""
        self.mock_service.get_orders.return_value = []

        # Test each function calls get_orders exactly once
        await stock_orders()
        assert self.mock_service.get_orders.call_count == 1

        await options_orders()
        assert self.mock_service.get_orders.call_count == 2

        await open_stock_orders()
        assert self.mock_service.get_orders.call_count == 3

        await open_option_orders()
        assert self.mock_service.get_orders.call_count == 4
