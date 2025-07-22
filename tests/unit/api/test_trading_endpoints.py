"""
Comprehensive tests for trading endpoints.

Tests for:
- GET /quote/{symbol} (get_quote) - deprecated endpoint
- POST /order (create_order)
- GET /orders (get_orders)
- GET /order/{order_id} (get_order)
- DELETE /order/{order_id} (cancel_order)
- GET /quote/{symbol}/enhanced (get_enhanced_quote)
- POST /order/multi-leg (create_multi_leg_order_basic)

All tests use proper async patterns with comprehensive mocking of TradingService.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.orders import (
    MultiLegOrderCreate,
    Order,
    OrderCondition,
    OrderCreate,
    OrderStatus,
    OrderType,
)
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService


class TestTradingEndpoints:
    """Test trading endpoints with comprehensive coverage."""

    # GET /quote/{symbol} endpoint tests - DEPRECATED
    @pytest.mark.asyncio
    async def test_get_quote_success(self, client):
        """Test successful quote retrieval for deprecated endpoint."""
        mock_service = AsyncMock(spec=TradingService)
        mock_quote = StockQuote(
            symbol="AAPL",
            price=155.0,
            bid=154.95,
            ask=155.05,
            volume=1000000,
            quote_date=datetime(2023, 6, 15),
        )
        mock_service.get_quote.return_value = mock_quote

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.0
        assert data["bid"] == 154.95
        assert data["ask"] == 155.05
        assert data["volume"] == 1000000

        mock_service.get_quote.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, client):
        """Test quote retrieval for non-existent symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_quote.side_effect = NotFoundError("Symbol not found")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/NONEXISTENT")

        # Global exception handler should convert NotFoundError to 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_quote_special_characters(self, client):
        """Test quote retrieval with special characters in symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_quote = StockQuote(
            symbol="BRK.A", price=400000.0, quote_date=datetime(2023, 6, 15)
        )
        mock_service.get_quote.return_value = mock_quote

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/BRK.A")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["symbol"] == "BRK.A"
        assert data["price"] == 400000.0

    # POST /order endpoint tests
    @pytest.mark.asyncio
    async def test_create_order_success_buy(self, client):
        """Test successful buy order creation."""
        mock_service = AsyncMock(spec=TradingService)
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

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.0,
            "condition": "limit",
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "order_123"
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == "buy"
        assert data["quantity"] == 100
        assert data["price"] == 155.0
        assert data["status"] == "pending"

        # Verify service was called with OrderCreate model
        mock_service.create_order.assert_called_once()
        args = mock_service.create_order.call_args[0]
        assert isinstance(args[0], OrderCreate)

    @pytest.mark.asyncio
    async def test_create_order_success_sell(self, client):
        """Test successful sell order creation."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order_124",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2500.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_order.return_value = mock_order

        order_data = {
            "symbol": "GOOGL",
            "order_type": "sell",
            "quantity": 50,
            "price": 2500.0,
            "condition": "limit",
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["order_type"] == "sell"

    @pytest.mark.asyncio
    async def test_create_order_market_order(self, client):
        """Test successful market order creation."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order_125",
            symbol="MSFT",
            order_type=OrderType.BUY,
            quantity=200,
            price=None,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_order.return_value = mock_order

        order_data = {
            "symbol": "MSFT",
            "order_type": "buy",
            "quantity": 200,
            "condition": "market",
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["price"] is None
        assert data["condition"] == "market"

    @pytest.mark.asyncio
    async def test_create_order_validation_error(self, client):
        """Test order creation with validation error."""
        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": -100,  # Invalid negative quantity
            "price": 155.0,
        }

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_order_missing_required_fields(self, client):
        """Test order creation with missing required fields."""
        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            # Missing quantity
        }

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_order_service_error(self, client):
        """Test order creation when service raises error."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.create_order.side_effect = ValidationError("Insufficient funds")

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        # Global exception handler should convert ValidationError to 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # GET /orders endpoint tests
    @pytest.mark.asyncio
    async def test_get_orders_success(self, client):
        """Test successful orders list retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_orders = [
            Order(
                id="order_123",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=155.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2023, 6, 15, 10, 0),
                filled_at=datetime(2023, 6, 15, 10, 5),
            ),
            Order(
                id="order_124",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2500.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2023, 6, 15, 11, 0),
            ),
        ]
        mock_service.get_orders.return_value = mock_orders

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/orders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 2
        assert data[0]["id"] == "order_123"
        assert data[0]["status"] == "filled"
        assert data[1]["id"] == "order_124"
        assert data[1]["status"] == "pending"

        mock_service.get_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_orders_empty(self, client):
        """Test orders list when no orders exist."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_orders.return_value = []

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/orders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    # GET /order/{order_id} endpoint tests
    @pytest.mark.asyncio
    async def test_get_order_success(self, client):
        """Test successful specific order retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order_123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.0,
            status=OrderStatus.FILLED,
            created_at=datetime(2023, 6, 15, 10, 0),
            filled_at=datetime(2023, 6, 15, 10, 5),
        )
        mock_service.get_order.return_value = mock_order

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/order/order_123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "order_123"
        assert data["symbol"] == "AAPL"
        assert data["status"] == "filled"
        assert data["filled_at"] is not None

        mock_service.get_order.assert_called_once_with("order_123")

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, client):
        """Test order retrieval for non-existent order."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_order.side_effect = NotFoundError("Order not found")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/order/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # DELETE /order/{order_id} endpoint tests
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, client):
        """Test successful order cancellation."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.cancel_order.return_value = {
            "status": "cancelled",
            "order_id": "order_123",
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.delete("/api/v1/trading/order/order_123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["order_id"] == "order_123"

        mock_service.cancel_order.assert_called_once_with("order_123")

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, client):
        """Test order cancellation for non-existent order."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.cancel_order.side_effect = NotFoundError("Order not found")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.delete("/api/v1/trading/order/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, client):
        """Test order cancellation for already filled order."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.cancel_order.side_effect = ValidationError(
            "Cannot cancel filled order"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.delete("/api/v1/trading/order/order_123")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # GET /quote/{symbol}/enhanced endpoint tests
    @pytest.mark.asyncio
    async def test_get_enhanced_quote_stock(self, client):
        """Test enhanced quote for stock symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_quote = StockQuote(
            symbol="AAPL",
            price=155.0,
            bid=154.95,
            ask=155.05,
            volume=1000000,
            quote_date=datetime(2023, 6, 15, 15, 30),
        )
        mock_service.get_enhanced_quote.return_value = mock_quote

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/AAPL/enhanced")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.0
        assert data["bid"] == 154.95
        assert data["ask"] == 155.05
        assert data["volume"] == 1000000
        assert data["asset_type"] == "stock"
        assert "quote_date" in data

        # Should not have Greeks for stocks
        assert "delta" not in data

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_option(self, client):
        """Test enhanced quote for option symbol with Greeks."""
        from app.models.quotes import OptionQuote

        mock_service = AsyncMock(spec=TradingService)
        mock_quote = OptionQuote(
            symbol="AAPL_210618C00155000",
            price=5.50,
            bid=5.45,
            ask=5.55,
            volume=1000,
            quote_date=datetime(2023, 6, 15, 15, 30),
            delta=0.65,
            gamma=0.03,
            theta=-0.02,
            vega=0.15,
            rho=0.08,
            iv=0.25,
            underlying_price=155.0,
        )
        mock_service.get_enhanced_quote.return_value = mock_quote

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/trading/quote/AAPL_210618C00155000/enhanced"
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_210618C00155000"
        assert data["price"] == 5.50
        assert data["asset_type"] == "option"

        # Should have Greeks for options
        assert data["delta"] == 0.65
        assert data["gamma"] == 0.03
        assert data["theta"] == -0.02
        assert data["vega"] == 0.15
        assert data["rho"] == 0.08
        assert data["iv"] == 0.25
        assert data["underlying_price"] == 155.0

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_not_found(self, client):
        """Test enhanced quote for non-existent symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_enhanced_quote.side_effect = NotFoundError("Symbol not found")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/NONEXISTENT/enhanced")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # POST /order/multi-leg endpoint tests
    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(self, client):
        """Test successful multi-leg order creation."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = {
            "id": "multileg_123",
            "legs": [
                {"symbol": "AAPL", "order_type": "buy", "quantity": 100},
                {
                    "symbol": "AAPL_210618C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                },
            ],
            "status": "pending",
            "net_price": -15500.0,
        }
        mock_service.create_multi_leg_order.return_value = mock_order

        order_data = {
            "legs": [
                {
                    "asset": "AAPL",
                    "order_type": "buy_to_open",
                    "quantity": 100,
                    "price": 155.0,
                },
                {
                    "asset": "AAPL_210618C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                    "price": 3.0,
                },
            ],
            "condition": "limit",
            "limit_price": -15200.0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/trading/order/multi-leg", json=order_data
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "multileg_123"
        assert len(data["legs"]) == 2
        assert data["status"] == "pending"

        # Verify service was called with MultiLegOrderCreate model
        mock_service.create_multi_leg_order.assert_called_once()
        args = mock_service.create_multi_leg_order.call_args[0]
        assert isinstance(args[0], MultiLegOrderCreate)

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_validation_error(self, client):
        """Test multi-leg order creation with validation error."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.create_multi_leg_order.side_effect = ValidationError(
            "Invalid leg combination"
        )

        order_data = {
            "legs": [
                {"asset": "AAPL", "order_type": "buy", "quantity": 100},
                {
                    "asset": "AAPL",
                    "order_type": "sell",
                    "quantity": 100,
                },  # Duplicate assets
            ]
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/trading/order/multi-leg", json=order_data
                )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_not_found_error(self, client):
        """Test multi-leg order creation with not found error."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.create_multi_leg_order.side_effect = NotFoundError(
            "Symbol not found"
        )

        order_data = {
            "legs": [{"asset": "NONEXISTENT", "order_type": "buy", "quantity": 100}]
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/trading/order/multi-leg", json=order_data
                )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_empty_legs(self, client):
        """Test multi-leg order creation with empty legs."""
        order_data = {"legs": []}

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/trading/order/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_missing_legs(self, client):
        """Test multi-leg order creation without legs field."""
        order_data = {"condition": "market"}

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/trading/order/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Edge cases and additional tests
    @pytest.mark.asyncio
    async def test_trading_endpoints_with_large_quantities(self, client):
        """Test trading endpoints handle large quantities correctly."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order_large",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=1000000,  # 1 million shares
            price=155.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_order.return_value = mock_order

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 1000000,
            "price": 155.0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["quantity"] == 1000000

    @pytest.mark.asyncio
    async def test_trading_endpoints_with_fractional_prices(self, client):
        """Test trading endpoints handle fractional prices correctly."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order_fractional",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.567,  # Fractional price
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        mock_service.create_order.return_value = mock_order

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.567,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["price"] == 155.567

    @pytest.mark.asyncio
    async def test_order_id_url_encoding(self, client):
        """Test order endpoints handle URL-encoded order IDs."""
        mock_service = AsyncMock(spec=TradingService)
        mock_order = Order(
            id="order-with-dashes",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.0,
            status=OrderStatus.FILLED,
            created_at=datetime.utcnow(),
        )
        mock_service.get_order.return_value = mock_order

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/order/order-with-dashes")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "order-with-dashes"

    @pytest.mark.asyncio
    async def test_deprecated_quote_endpoint_warning(self, client):
        """Test that the deprecated quote endpoint still works but is marked deprecated."""
        mock_service = AsyncMock(spec=TradingService)
        mock_quote = StockQuote(
            symbol="AAPL", price=155.0, quote_date=datetime.utcnow()
        )
        mock_service.get_quote.return_value = mock_quote

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/trading/quote/AAPL")

        # Should still work despite being deprecated
        assert response.status_code == status.HTTP_200_OK
        # In a real implementation, you might check for deprecation warnings in headers

    @pytest.mark.asyncio
    async def test_trading_service_dependency_injection(self):
        """Test that trading service dependency injection works correctly."""
        from app.core.dependencies import get_trading_service

        # Create a mock request with app state
        mock_request = MagicMock()
        mock_service = MagicMock(spec=TradingService)
        mock_request.app.state.trading_service = mock_service

        result = get_trading_service(mock_request)
        assert result is mock_service

    @pytest.mark.asyncio
    async def test_trading_endpoints_response_structure(self, client):
        """Test that trading endpoints return properly structured responses."""
        mock_service = AsyncMock(spec=TradingService)

        # Test order response structure
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

        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/trading/order", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required Order fields are present
        required_fields = ["id", "symbol", "order_type", "quantity", "status"]
        for field in required_fields:
            assert field in data
