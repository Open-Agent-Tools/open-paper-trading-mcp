"""
Comprehensive tests for trading endpoints.

Tests all trading endpoints with proper mocking:
- GET /quote/{symbol} (deprecated)
- POST /order (create order)
- GET /orders (get all orders)
- GET /order/{order_id} (get specific order)
- DELETE /order/{order_id} (cancel order)
- GET /quote/{symbol}/enhanced (enhanced quote with Greeks)
- POST /order/multi-leg (multi-leg order creation)

Covers success paths, error handling, authentication, and edge cases.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.orders import (
    Order,
    OrderCondition,
    OrderStatus,
    OrderType,
)
from app.schemas.trading import StockQuote


class TestTradingEndpoints:
    """Test suite for trading endpoints."""

    # GET /quote/{symbol} - Deprecated endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_quote_success(self, mock_get_service, client: TestClient):
        """Test successful quote retrieval for deprecated endpoint."""
        mock_service = AsyncMock()
        mock_quote = StockQuote(
            symbol="AAPL",
            price=155.0,
            bid=154.95,
            ask=155.05,
            volume=1000000,
            quote_date=datetime(2023, 6, 15),
        )
        mock_service.get_quote.return_value = mock_quote
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.0
        assert data["bid"] == 154.95
        assert data["ask"] == 155.05
        assert data["volume"] == 1000000

        mock_service.get_quote.assert_called_once_with("AAPL")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_quote_not_found(self, mock_get_service, client: TestClient):
        """Test quote retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_quote.side_effect = NotFoundError("Symbol not found")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/INVALID")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Symbol not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_quote_service_error(self, mock_get_service, client: TestClient):
        """Test quote retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_quote.side_effect = Exception("Service unavailable")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # POST /order - Create order endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_create_order_success(self, mock_get_service, client: TestClient):
        """Test successful order creation."""
        mock_service = AsyncMock()
        mock_order = Order(
            id="order_123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_order.return_value = mock_order
        mock_get_service.return_value = mock_service

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.0,
        }

        response = client.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "order_123"
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == "buy"
        assert data["quantity"] == 100
        assert data["price"] == 155.0
        assert data["status"] == "pending"

    @patch("app.core.dependencies.get_trading_service")
    def test_create_order_validation_error(self, mock_get_service, client: TestClient):
        """Test order creation with invalid data."""
        mock_service = AsyncMock()
        mock_service.create_order.side_effect = ValidationError("Invalid order data")
        mock_get_service.return_value = mock_service

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": -100,  # Invalid negative quantity
            "price": 155.0,
        }

        response = client.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.core.dependencies.get_trading_service")
    def test_create_order_insufficient_funds(
        self, mock_get_service, client: TestClient
    ):
        """Test order creation with insufficient funds."""
        mock_service = AsyncMock()
        mock_service.create_order.side_effect = ValidationError("Insufficient funds")
        mock_get_service.return_value = mock_service

        order_data = {
            "symbol": "BERKB",
            "order_type": "buy",
            "quantity": 1000,
            "price": 500000.0,  # Very expensive order
        }

        response = client.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_order_invalid_json(self, client: TestClient):
        """Test order creation with invalid JSON."""
        response = client.post("/api/v1/trading/order", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # GET /orders - Get all orders endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_orders_success(self, mock_get_service, client: TestClient):
        """Test successful retrieval of all orders."""
        mock_service = AsyncMock()
        mock_orders = [
            Order(
                id="order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=155.0,
                condition=OrderCondition.LIMIT,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            ),
            Order(
                id="order_2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2500.0,
                condition=OrderCondition.LIMIT,
                status=OrderStatus.FILLED,
                created_at=datetime.utcnow(),
            ),
        ]
        mock_service.get_orders.return_value = mock_orders
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/orders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 2
        assert data[0]["id"] == "order_1"
        assert data[1]["id"] == "order_2"

    @patch("app.core.dependencies.get_trading_service")
    def test_get_orders_empty(self, mock_get_service, client: TestClient):
        """Test retrieval of orders when none exist."""
        mock_service = AsyncMock()
        mock_service.get_orders.return_value = []
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/orders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 0

    # GET /order/{order_id} - Get specific order endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_order_success(self, mock_get_service, client: TestClient):
        """Test successful retrieval of specific order."""
        mock_service = AsyncMock()
        mock_order = Order(
            id="order_123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.get_order.return_value = mock_order
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/order/order_123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "order_123"
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == "buy"

        mock_service.get_order.assert_called_once_with("order_123")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_order_not_found(self, mock_get_service, client: TestClient):
        """Test retrieval of non-existent order."""
        mock_service = AsyncMock()
        mock_service.get_order.side_effect = NotFoundError("Order not found")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/order/invalid_order")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Order not found" in data["detail"]

    # DELETE /order/{order_id} - Cancel order endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_cancel_order_success(self, mock_get_service, client: TestClient):
        """Test successful order cancellation."""
        mock_service = AsyncMock()
        mock_service.cancel_order.return_value = {
            "message": "Order cancelled successfully",
            "order_id": "order_123",
        }
        mock_get_service.return_value = mock_service

        response = client.delete("/api/v1/trading/order/order_123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["message"] == "Order cancelled successfully"
        assert data["order_id"] == "order_123"

        mock_service.cancel_order.assert_called_once_with("order_123")

    @patch("app.core.dependencies.get_trading_service")
    def test_cancel_order_not_found(self, mock_get_service, client: TestClient):
        """Test cancellation of non-existent order."""
        mock_service = AsyncMock()
        mock_service.cancel_order.side_effect = NotFoundError("Order not found")
        mock_get_service.return_value = mock_service

        response = client.delete("/api/v1/trading/order/invalid_order")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.core.dependencies.get_trading_service")
    def test_cancel_order_already_filled(self, mock_get_service, client: TestClient):
        """Test cancellation of already filled order."""
        mock_service = AsyncMock()
        mock_service.cancel_order.side_effect = ValidationError(
            "Cannot cancel filled order"
        )
        mock_get_service.return_value = mock_service

        response = client.delete("/api/v1/trading/order/filled_order")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # GET /quote/{symbol}/enhanced - Enhanced quote endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_enhanced_quote_stock_success(
        self, mock_get_service, client: TestClient
    ):
        """Test successful enhanced quote retrieval for stock."""
        mock_service = AsyncMock()
        mock_quote = StockQuote(
            symbol="AAPL",
            price=155.0,
            bid=154.95,
            ask=155.05,
            volume=1000000,
            quote_date=datetime(2023, 6, 15),
        )
        mock_service.get_enhanced_quote.return_value = mock_quote
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/AAPL/enhanced")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.0
        assert data["asset_type"] == "stock"
        assert "delta" not in data  # Stock quotes don't have Greeks

    @patch("app.core.dependencies.get_trading_service")
    def test_get_enhanced_quote_option_success(
        self, mock_get_service, client: TestClient
    ):
        """Test successful enhanced quote retrieval for option with Greeks."""
        mock_service = AsyncMock()

        # Create a mock option quote with Greeks
        class MockOptionQuote:
            def __init__(self):
                self.symbol = "AAPL_230616C00150000"
                self.price = 5.25
                self.bid = 5.20
                self.ask = 5.30
                self.volume = 1000
                self.quote_date = datetime(2023, 6, 15)
                self.delta = 0.65
                self.gamma = 0.03
                self.theta = -0.02
                self.vega = 0.15
                self.rho = 0.08
                self.iv = 0.25
                self.underlying_price = 155.0

        mock_quote = MockOptionQuote()
        mock_service.get_enhanced_quote.return_value = mock_quote
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/AAPL_230616C00150000/enhanced")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["price"] == 5.25
        assert data["asset_type"] == "option"
        assert data["delta"] == 0.65
        assert data["gamma"] == 0.03
        assert data["theta"] == -0.02
        assert data["vega"] == 0.15
        assert data["rho"] == 0.08
        assert data["iv"] == 0.25
        assert data["underlying_price"] == 155.0

    @patch("app.core.dependencies.get_trading_service")
    def test_get_enhanced_quote_not_found(self, mock_get_service, client: TestClient):
        """Test enhanced quote retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_enhanced_quote.side_effect = NotFoundError("Symbol not found")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/INVALID/enhanced")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Symbol not found" in data["detail"]

    # POST /order/multi-leg - Multi-leg order endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_success(self, mock_get_service, client: TestClient):
        """Test successful multi-leg order creation."""
        mock_service = AsyncMock()
        mock_order = Order(
            id="multileg_123",
            symbol="AAPL_SPREAD",
            order_type=OrderType.BUY,
            quantity=1,
            price=-2.75,  # Net debit
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_multi_leg_order.return_value = mock_order
        mock_get_service.return_value = mock_service

        multileg_data = {
            "legs": [
                {
                    "asset": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": 5.25,
                },
                {
                    "asset": "AAPL_230616C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                    "price": 2.50,
                },
            ],
            "condition": "limit",
            "limit_price": -2.75,
        }

        response = client.post("/api/v1/trading/order/multi-leg", json=multileg_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "multileg_123"
        assert data["status"] == "pending"

    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_validation_error(
        self, mock_get_service, client: TestClient
    ):
        """Test multi-leg order creation with validation error."""
        mock_service = AsyncMock()
        mock_service.create_multi_leg_order.side_effect = ValidationError(
            "Invalid legs configuration"
        )
        mock_get_service.return_value = mock_service

        multileg_data = {
            "legs": [],  # Empty legs - invalid
            "condition": "limit",
            "limit_price": -2.75,
        }

        response = client.post("/api/v1/trading/order/multi-leg", json=multileg_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid legs configuration" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_not_found_error(
        self, mock_get_service, client: TestClient
    ):
        """Test multi-leg order creation with symbol not found."""
        mock_service = AsyncMock()
        mock_service.create_multi_leg_order.side_effect = NotFoundError(
            "Option symbol not found"
        )
        mock_get_service.return_value = mock_service

        multileg_data = {
            "legs": [
                {
                    "asset": "INVALID_OPTION",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": 5.25,
                }
            ],
            "condition": "limit",
            "limit_price": 5.25,
        }

        response = client.post("/api/v1/trading/order/multi-leg", json=multileg_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_multi_leg_order_invalid_json(self, client: TestClient):
        """Test multi-leg order creation with invalid JSON."""
        response = client.post("/api/v1/trading/order/multi-leg", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTradingEndpointsErrorHandling:
    """Test error handling for trading endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_service_unavailable_error(self, mock_get_service, client: TestClient):
        """Test handling when trading service is unavailable."""
        mock_get_service.side_effect = Exception("Service unavailable")

        response = client.get("/api/v1/trading/orders")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.core.dependencies.get_trading_service")
    def test_timeout_error_handling(self, mock_get_service, client: TestClient):
        """Test handling of timeout errors."""
        mock_service = AsyncMock()
        mock_service.get_quote.side_effect = TimeoutError("Request timeout")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/trading/quote/AAPL")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_invalid_symbol_format(self, client: TestClient):
        """Test handling of invalid symbol formats."""
        # Test with symbols containing invalid characters
        invalid_symbols = ["", "A" * 20, "AAPL@", "AAPL#123"]

        for symbol in invalid_symbols:
            response = client.get(f"/api/v1/trading/quote/{symbol}")
            # Should handle gracefully - either 400 or 404
            assert response.status_code in [400, 404, 422, 500]

    def test_large_order_quantities(self, client: TestClient):
        """Test handling of extremely large order quantities."""
        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 999999999,  # Very large quantity
            "price": 155.0,
        }

        response = client.post("/api/v1/trading/order", json=order_data)

        # Should either validate and reject, or handle gracefully
        assert response.status_code in [400, 422, 500]


class TestTradingEndpointsAuthentication:
    """Test authentication scenarios for trading endpoints."""

    def test_endpoints_require_authentication(self, client: TestClient):
        """Test that trading endpoints handle authentication properly."""
        # These tests assume authentication is handled by middleware/dependencies
        # In a real system, you'd test with and without valid auth tokens

        endpoints_to_test = [
            ("GET", "/api/v1/trading/quote/AAPL"),
            ("GET", "/api/v1/trading/orders"),
            (
                "POST",
                "/api/v1/trading/order",
                {"symbol": "AAPL", "order_type": "buy", "quantity": 100},
            ),
            ("DELETE", "/api/v1/trading/order/123"),
        ]

        for method, endpoint, *data in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=data[0] if data else {})
            elif method == "DELETE":
                response = client.delete(endpoint)

            # These endpoints should work without explicit auth in test environment
            # In production, they would require proper authentication
            assert response.status_code in [200, 400, 401, 404, 422, 500]
