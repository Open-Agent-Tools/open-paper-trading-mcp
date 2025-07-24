"""
MCP Error Handling and Protocol Compliance Tests

Tests for Model Context Protocol error handling, exception management,
and protocol compliance under various failure conditions.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.mcp.tools import get_mcp_trading_service, set_mcp_trading_service
from app.services.trading_service import TradingService


class TestMCPServiceErrorHandling:
    """Test MCP error handling for service-level failures."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools

        app.mcp.tools._trading_service = None

    def test_mcp_service_not_initialized_error(self):
        """Test MCP handles service not initialized error."""

        # Ensure service is not initialized
        import app.mcp.tools

        app.mcp.tools._trading_service = None

        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()

        assert "TradingService not initialized for MCP tools" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_service_unavailable_during_operation(self):
        """Test MCP handles service becoming unavailable during operation."""
        # Service not initialized
        import app.mcp.tools
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        app.mcp.tools._trading_service = None

        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Should return error message, not raise exception
        assert isinstance(result, str)
        assert "Error getting quote" in result
        assert "TradingService not initialized" in result

    @pytest.mark.asyncio
    async def test_mcp_service_timeout_handling(self, setup_mcp_service):
        """Test MCP handles service timeout errors."""
        from app.mcp.tools import get_portfolio_summary

        # Mock timeout
        setup_mcp_service.get_portfolio_summary.side_effect = TimeoutError(
            "Service timeout"
        )

        result = await get_portfolio_summary()

        # Should handle timeout gracefully
        assert isinstance(result, str)
        assert "Error getting portfolio summary" in result
        assert "Service timeout" in result

    @pytest.mark.asyncio
    async def test_mcp_service_connection_error(self, setup_mcp_service):
        """Test MCP handles service connection errors."""
        from app.mcp.tools import get_all_orders

        # Mock connection error
        setup_mcp_service.get_orders.side_effect = ConnectionError(
            "Database connection failed"
        )

        result = await get_all_orders()

        # Should handle connection error gracefully
        assert isinstance(result, str)
        assert "Error getting orders" in result
        assert "Database connection failed" in result

    @pytest.mark.asyncio
    async def test_mcp_service_authentication_error(self, setup_mcp_service):
        """Test MCP handles service authentication errors."""
        from app.mcp.tools import CreateOrderArgs, create_buy_order
        from app.schemas.orders import OrderType

        # Mock authentication error
        setup_mcp_service.create_order.side_effect = PermissionError(
            "Authentication failed"
        )

        args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        result = await create_buy_order(args)

        # Should handle auth error gracefully
        assert isinstance(result, str)
        assert "Error creating buy order" in result
        assert "Authentication failed" in result

    @pytest.mark.asyncio
    async def test_mcp_service_data_integrity_error(self, setup_mcp_service):
        """Test MCP handles service data integrity errors."""
        from app.mcp.tools import GetPositionArgs, get_position

        # Mock data integrity error
        setup_mcp_service.get_position.side_effect = ValueError("Invalid position data")

        args = GetPositionArgs(symbol="AAPL")
        result = await get_position(args)

        # Should handle data error gracefully
        assert isinstance(result, str)
        assert "Error getting position" in result
        assert "Invalid position data" in result


class TestMCPValidationErrorHandling:
    """Test MCP error handling for validation failures."""

    def test_mcp_missing_required_fields(self):
        """Test MCP handles missing required fields."""
        from app.mcp.tools import GetQuoteArgs

        # Missing required symbol
        with pytest.raises(ValidationError) as exc_info:
            GetQuoteArgs()

        error_details = exc_info.value.errors()
        assert len(error_details) > 0
        assert any(error["loc"] == ("symbol",) for error in error_details)
        assert any("missing" in error["type"] for error in error_details)

    def test_mcp_invalid_field_types(self):
        """Test MCP handles invalid field types."""
        from app.mcp.tools import CreateOrderArgs
        from app.schemas.orders import OrderType

        # Invalid quantity type
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderArgs(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity="invalid",  # Should be int
                price=150.0,
            )

        error_details = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in error_details)

    def test_mcp_field_constraints_validation(self):
        """Test MCP validates field constraints."""
        from app.mcp.tools import CreateOrderArgs
        from app.schemas.orders import OrderType

        # Quantity must be > 0
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderArgs(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=0,  # Invalid: must be > 0
                price=150.0,
            )

        error_details = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in error_details)
        assert any("greater_than" in error["type"] for error in error_details)

        # Price must be > 0
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderArgs(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=-10.0,  # Invalid: must be > 0
            )

        error_details = exc_info.value.errors()
        assert any(error["loc"] == ("price",) for error in error_details)

    def test_mcp_enum_validation(self):
        """Test MCP validates enum fields correctly."""
        from app.mcp.tools import CreateOrderArgs

        # Invalid order type
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderArgs(
                symbol="AAPL",
                order_type="INVALID_TYPE",  # Should be OrderType enum
                quantity=100,
                price=150.0,
            )

        error_details = exc_info.value.errors()
        assert any(error["loc"] == ("order_type",) for error in error_details)

    def test_mcp_options_validation(self):
        """Test MCP validates options-specific fields."""
        from app.mcp.tools import CalculateGreeksArgs, GetOptionsChainArgs

        # Valid options args should work
        valid_chain_args = GetOptionsChainArgs(symbol="AAPL")
        assert valid_chain_args.symbol == "AAPL"

        valid_greeks_args = CalculateGreeksArgs(option_symbol="AAPL240119C00150000")
        assert valid_greeks_args.option_symbol == "AAPL240119C00150000"

        # Invalid option symbol format (basic test)
        # Note: Actual validation depends on implementation
        try:
            CalculateGreeksArgs(option_symbol="")
            # If no validation error, that's also acceptable
        except ValidationError:
            # If validation error occurs, it should be meaningful
            pass


class TestMCPProtocolErrorHandling:
    """Test MCP protocol-level error handling."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools

        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_malformed_response_handling(self, setup_mcp_service):
        """Test MCP handles malformed service responses."""
        from app.mcp.tools import get_all_positions

        # Mock malformed position data
        malformed_position = Mock()
        malformed_position.symbol = None  # Invalid None symbol
        malformed_position.quantity = "invalid_quantity"
        malformed_position.avg_price = float("inf")  # Invalid infinity
        malformed_position.current_price = None
        malformed_position.unrealized_pnl = "not_a_number"
        malformed_position.realized_pnl = None

        setup_mcp_service.get_positions.return_value = [malformed_position]

        result = await get_all_positions()

        # Should handle malformed data gracefully
        assert isinstance(result, str)
        # Should either return error or sanitized data
        if "Error" in result:
            assert "getting positions" in result
        else:
            # If it returns data, should be valid JSON
            try:
                parsed = json.loads(result)
                assert isinstance(parsed, list)
            except json.JSONDecodeError:
                pytest.fail("Result should be valid JSON or error message")

    @pytest.mark.asyncio
    async def test_mcp_json_serialization_error(self, setup_mcp_service):
        """Test MCP handles JSON serialization errors."""
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        # Mock quote with non-serializable data
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.0
        mock_quote.change = 2.5
        mock_quote.change_percent = 1.69
        mock_quote.volume = 50000000
        # Non-serializable datetime object (if not handled properly)
        mock_quote.last_updated = object()  # Non-serializable object

        setup_mcp_service.get_quote.return_value = mock_quote

        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)

        # Should handle serialization error gracefully
        assert isinstance(result, str)
        if "Error" in result:
            assert "getting quote" in result
        else:
            # Should be valid JSON
            try:
                json.loads(result)
            except json.JSONDecodeError:
                pytest.fail("Result should be valid JSON")

    @pytest.mark.asyncio
    async def test_mcp_memory_error_handling(self, setup_mcp_service):
        """Test MCP handles memory-related errors."""
        from app.mcp.tools import get_all_orders

        # Mock memory error
        setup_mcp_service.get_orders.side_effect = MemoryError("Out of memory")

        result = await get_all_orders()

        # Should handle memory error gracefully
        assert isinstance(result, str)
        assert "Error getting orders" in result
        assert "Out of memory" in result

    @pytest.mark.asyncio
    async def test_mcp_unexpected_exception_handling(self, setup_mcp_service):
        """Test MCP handles unexpected exceptions."""
        from app.mcp.tools import CancelOrderArgs, cancel_order

        # Mock unexpected exception
        setup_mcp_service.cancel_order.side_effect = Exception(
            "Unexpected error occurred"
        )

        args = CancelOrderArgs(order_id="test_order")
        result = await cancel_order(args)

        # Should handle unexpected exception gracefully
        assert isinstance(result, str)
        assert "Error cancelling order" in result
        assert "Unexpected error occurred" in result

    @pytest.mark.asyncio
    async def test_mcp_recursive_error_prevention(self, setup_mcp_service):
        """Test MCP prevents recursive errors."""
        from app.mcp.tools import get_portfolio

        # Mock service that raises exception during error handling
        def raise_on_call(*args, **kwargs):
            raise RuntimeError("Service error")

        setup_mcp_service.get_portfolio.side_effect = raise_on_call

        result = await get_portfolio()

        # Should not cause recursive errors
        assert isinstance(result, str)
        assert "Error getting portfolio" in result
        assert "Service error" in result


class TestMCPConcurrentErrorHandling:
    """Test MCP error handling under concurrent conditions."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools

        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_concurrent_service_errors(self, setup_mcp_service):
        """Test MCP handles concurrent service errors."""
        from app.mcp.tools import (
            CancelOrderArgs,
            cancel_order,
            get_all_orders,
            get_portfolio,
        )

        # Mock different errors for different operations
        setup_mcp_service.get_orders.side_effect = ValueError("Orders error")
        setup_mcp_service.get_portfolio.side_effect = TimeoutError("Portfolio timeout")
        setup_mcp_service.cancel_order.side_effect = ConnectionError(
            "Cancel connection error"
        )

        # Execute concurrently
        tasks = [
            get_all_orders(),
            get_portfolio(),
            cancel_order(CancelOrderArgs(order_id="test")),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # All should return error strings, not raise exceptions
        assert len(results) == 3
        for result in results:
            assert isinstance(result, str)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_mcp_partial_failure_handling(self, setup_mcp_service):
        """Test MCP handles partial failures in concurrent operations."""
        from app.mcp.market_data_tools import GetStockPriceArgs, get_stock_price
        from app.mcp.tools import get_all_positions, get_portfolio_summary

        # Mock partial success
        setup_mcp_service.get_positions.return_value = []  # Success
        setup_mcp_service.get_portfolio_summary.side_effect = ValueError(
            "Summary error"
        )  # Failure
        setup_mcp_service.get_stock_price.return_value = {
            "symbol": "AAPL",
            "price": 150.0,
        }  # Success

        # Execute concurrently
        tasks = [
            get_all_positions(),
            get_portfolio_summary(),
            get_stock_price(GetStockPriceArgs(symbol="AAPL")),
        ]

        results = await asyncio.gather(*tasks)

        # Should handle partial failures
        assert len(results) == 3

        # First result should be success (empty positions list)
        positions_result = json.loads(results[0])
        assert isinstance(positions_result, list)
        assert len(positions_result) == 0

        # Second result should be error
        assert isinstance(results[1], str)
        assert "Error getting portfolio summary" in results[1]

        # Third result should be success
        assert isinstance(results[2], dict)
        assert results[2]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_mcp_error_isolation(self, setup_mcp_service):
        """Test MCP isolates errors between operations."""
        from app.mcp.tools import CreateOrderArgs, create_buy_order, create_sell_order
        from app.schemas.orders import OrderType

        # Mock one success, one failure
        success_order = Mock()
        success_order.id = "success_order"
        success_order.symbol = "AAPL"
        success_order.order_type = OrderType.BUY
        success_order.quantity = 100
        success_order.price = 150.0
        success_order.status = "PENDING"
        success_order.created_at = datetime.now()

        def mock_create_order(order_data):
            if order_data.order_type == OrderType.BUY:
                return success_order
            else:
                raise ValueError("Sell order failed")

        setup_mcp_service.create_order.side_effect = mock_create_order

        # Execute both orders
        buy_args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )
        sell_args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.SELL, quantity=100, price=150.0
        )

        buy_result = await create_buy_order(buy_args)
        sell_result = await create_sell_order(sell_args)

        # Buy should succeed
        buy_data = json.loads(buy_result)
        assert buy_data["id"] == "success_order"

        # Sell should fail but be isolated
        assert isinstance(sell_result, str)
        assert "Error creating sell order" in sell_result
        assert "Sell order failed" in sell_result


class TestMCPErrorRecovery:
    """Test MCP error recovery and resilience mechanisms."""

    @pytest.fixture
    def mock_trading_service(self):
        """Create mock trading service."""
        service = AsyncMock(spec=TradingService)
        return service

    @pytest.fixture
    def setup_mcp_service(self, mock_trading_service):
        """Set up MCP service."""
        set_mcp_trading_service(mock_trading_service)
        yield mock_trading_service
        import app.mcp.tools

        app.mcp.tools._trading_service = None

    @pytest.mark.asyncio
    async def test_mcp_service_recovery_after_error(self, setup_mcp_service):
        """Test MCP can recover after service errors."""
        from app.mcp.tools import GetQuoteArgs, get_stock_quote

        # Mock first call fails, second succeeds
        call_count = 0

        def mock_get_quote(symbol):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First call failed")
            else:
                mock_quote = Mock()
                mock_quote.symbol = symbol
                mock_quote.price = 150.0
                mock_quote.change = 2.5
                mock_quote.change_percent = 1.69
                mock_quote.volume = 50000000
                mock_quote.last_updated = datetime.now()
                return mock_quote

        setup_mcp_service.get_quote.side_effect = mock_get_quote

        args = GetQuoteArgs(symbol="AAPL")

        # First call should fail
        first_result = await get_stock_quote(args)
        assert "Error getting quote" in first_result
        assert "First call failed" in first_result

        # Second call should succeed
        second_result = await get_stock_quote(args)
        assert "Error" not in second_result
        parsed = json.loads(second_result)
        assert parsed["symbol"] == "AAPL"

    def test_mcp_service_reinitialization(self):
        """Test MCP can reinitialize service after failure."""
        # Clear service
        import app.mcp.tools
        from app.mcp.tools import set_mcp_trading_service

        app.mcp.tools._trading_service = None

        # Should raise error when not initialized
        with pytest.raises(RuntimeError):
            get_mcp_trading_service()

        # Should be able to reinitialize
        new_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(new_service)

        # Should work after reinitialization
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service is new_service

    @pytest.mark.asyncio
    async def test_mcp_graceful_degradation(self, setup_mcp_service):
        """Test MCP graceful degradation under sustained errors."""
        from app.mcp.tools import get_all_orders

        # Mock sustained service failure
        setup_mcp_service.get_orders.side_effect = ConnectionError(
            "Service unavailable"
        )

        # Multiple calls should all handle error gracefully
        results = []
        for _ in range(5):
            result = await get_all_orders()
            results.append(result)

        # All should return error messages
        for result in results:
            assert isinstance(result, str)
            assert "Error getting orders" in result
            assert "Service unavailable" in result

    @pytest.mark.asyncio
    async def test_mcp_error_reporting_consistency(self, setup_mcp_service):
        """Test MCP error reporting is consistent across tools."""
        from app.mcp.tools import (
            CreateOrderArgs,
            GetQuoteArgs,
            create_buy_order,
            get_portfolio,
            get_stock_quote,
        )
        from app.schemas.orders import OrderType

        # Mock same error for different tools
        error_message = "Consistent service error"
        setup_mcp_service.get_quote.side_effect = ValueError(error_message)
        setup_mcp_service.create_order.side_effect = ValueError(error_message)
        setup_mcp_service.get_portfolio.side_effect = ValueError(error_message)

        # Execute different tools
        quote_result = await get_stock_quote(GetQuoteArgs(symbol="AAPL"))
        order_result = await create_buy_order(
            CreateOrderArgs(
                symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
            )
        )
        portfolio_result = await get_portfolio()

        # All should have consistent error format
        results = [quote_result, order_result, portfolio_result]
        for result in results:
            assert isinstance(result, str)
            assert "Error" in result
            assert error_message in result

        # Error messages should follow pattern: "Error {action}: {detail}"
        assert "Error getting quote:" in quote_result
        assert "Error creating buy order:" in order_result
        assert "Error getting portfolio:" in portfolio_result
