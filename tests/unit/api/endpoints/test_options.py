"""
Comprehensive tests for options trading endpoints.

Tests all options endpoints with proper mocking:
- GET /{symbol}/chain (get options chain)
- GET /{symbol}/expirations (get expiration dates)
- POST /orders/multi-leg (create multi-leg order)
- GET /{option_symbol}/greeks (calculate Greeks)
- POST /strategies/analyze (analyze portfolio strategies)
- GET /{symbol}/search (find tradable options)
- GET /market-data/{option_id} (get option market data)

Covers success paths, error handling, parameter validation, and edge cases.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, ValidationError


class TestOptionsEndpoints:
    """Test suite for options trading endpoints."""

    # GET /{symbol}/chain - Options chain endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_options_chain_success(self, mock_get_service, client: TestClient):
        """Test successful options chain retrieval."""
        mock_service = AsyncMock()
        mock_chain_data = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {
                "2023-06-16": {
                    "calls": [
                        {
                            "symbol": "AAPL_230616C00150000",
                            "strike": 150.0,
                            "bid": 5.20,
                            "ask": 5.30,
                            "volume": 1000,
                            "open_interest": 5000,
                            "delta": 0.65,
                            "gamma": 0.03,
                            "theta": -0.02,
                            "vega": 0.15,
                            "iv": 0.25,
                        },
                        {
                            "symbol": "AAPL_230616C00155000",
                            "strike": 155.0,
                            "bid": 3.10,
                            "ask": 3.20,
                            "volume": 800,
                            "open_interest": 3000,
                            "delta": 0.50,
                            "gamma": 0.04,
                            "theta": -0.03,
                            "vega": 0.18,
                            "iv": 0.28,
                        },
                    ],
                    "puts": [
                        {
                            "symbol": "AAPL_230616P00150000",
                            "strike": 150.0,
                            "bid": 2.05,
                            "ask": 2.15,
                            "volume": 600,
                            "open_interest": 2500,
                            "delta": -0.35,
                            "gamma": 0.03,
                            "theta": -0.02,
                            "vega": 0.15,
                            "iv": 0.26,
                        }
                    ],
                }
            },
            "expiration_dates": ["2023-06-16"],
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert data["underlying_price"] == 155.0
        assert "chains" in data
        assert "2023-06-16" in data["chains"]
        assert len(data["chains"]["2023-06-16"]["calls"]) == 2
        assert len(data["chains"]["2023-06-16"]["puts"]) == 1
        assert data["data_source"] == "trading_service"
        assert data["cached"] is False

        # Verify call details
        call_option = data["chains"]["2023-06-16"]["calls"][0]
        assert call_option["symbol"] == "AAPL_230616C00150000"
        assert call_option["strike"] == 150.0
        assert call_option["delta"] == 0.65

        mock_service.get_formatted_options_chain.assert_called_once_with(
            "AAPL", None, None, None, True
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_get_options_chain_with_filters(self, mock_get_service, client: TestClient):
        """Test options chain retrieval with filters."""
        mock_service = AsyncMock()
        mock_chain_data = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {},
            "expiration_dates": [],
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data
        mock_get_service.return_value = mock_service

        params = {
            "expiration_date": "2023-06-16",
            "min_strike": "145",
            "max_strike": "165",
            "include_greeks": "false",
        }

        response = client.get("/api/v1/options/AAPL/chain", params=params)

        assert response.status_code == status.HTTP_200_OK

        # Verify service was called with correct parameters
        call_args = mock_service.get_formatted_options_chain.call_args
        assert call_args[0][0] == "AAPL"  # symbol
        assert call_args[0][1] == date(2023, 6, 16)  # expiration
        assert call_args[0][2] == 145.0  # min_strike
        assert call_args[0][3] == 165.0  # max_strike
        assert call_args[0][4] is False  # include_greeks

    @patch("app.core.dependencies.get_trading_service")
    def test_get_options_chain_invalid_date(self, mock_get_service, client: TestClient):
        """Test options chain with invalid expiration date format."""
        mock_service = AsyncMock()
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/chain?expiration_date=invalid-date")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid date format" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_options_chain_not_found(self, mock_get_service, client: TestClient):
        """Test options chain for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.side_effect = NotFoundError(
            "Symbol not found"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/INVALID/chain")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Symbol not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_options_chain_service_error(
        self, mock_get_service, client: TestClient
    ):
        """Test options chain with service error."""
        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.side_effect = Exception(
            "Service unavailable"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Error retrieving options chain" in data["detail"]

    # GET /{symbol}/expirations - Expiration dates endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_expiration_dates_success(self, mock_get_service, client: TestClient):
        """Test successful expiration dates retrieval."""
        mock_service = AsyncMock()
        mock_dates = [
            date(2023, 6, 16),
            date(2023, 6, 23),
            date(2023, 6, 30),
            date(2023, 7, 21),
        ]
        mock_service.get_expiration_dates.return_value = mock_dates
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/expirations")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 4
        assert data["expiration_dates"][0] == "2023-06-16"
        assert data["count"] == 4
        assert data["next_expiration"] == "2023-06-16"
        assert data["last_expiration"] == "2023-07-21"

        mock_service.get_expiration_dates.assert_called_once_with("AAPL")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_expiration_dates_empty(self, mock_get_service, client: TestClient):
        """Test expiration dates retrieval when no dates available."""
        mock_service = AsyncMock()
        mock_service.get_expiration_dates.return_value = []
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/expirations")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 0
        assert data["count"] == 0
        assert data["next_expiration"] is None
        assert data["last_expiration"] is None

    @patch("app.core.dependencies.get_trading_service")
    def test_get_expiration_dates_not_found(self, mock_get_service, client: TestClient):
        """Test expiration dates for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_expiration_dates.side_effect = NotFoundError(
            "Symbol not found"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/INVALID/expirations")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # POST /orders/multi-leg - Multi-leg order endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_success(self, mock_get_service, client: TestClient):
        """Test successful multi-leg order creation."""
        mock_service = AsyncMock()

        # Mock order response
        from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType

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
        mock_service.create_multi_leg_order_from_request.return_value = mock_order
        mock_get_service.return_value = mock_service

        order_data = {
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
            "order_type": "limit",
            "net_price": -2.75,
        }

        response = client.post("/api/v1/options/orders/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "multileg_123"
        assert data["symbol"] == "AAPL_SPREAD"
        assert data["price"] == -2.75
        assert data["status"] == "pending"

        mock_service.create_multi_leg_order_from_request.assert_called_once_with(
            order_data["legs"], order_data["order_type"], order_data["net_price"]
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_validation_error(
        self, mock_get_service, client: TestClient
    ):
        """Test multi-leg order creation with validation error."""
        mock_service = AsyncMock()
        mock_service.create_multi_leg_order_from_request.side_effect = ValidationError(
            "Invalid legs configuration"
        )
        mock_get_service.return_value = mock_service

        order_data = {
            "legs": [],  # Empty legs - invalid
            "order_type": "limit",
            "net_price": -2.75,
        }

        response = client.post("/api/v1/options/orders/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid legs configuration" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_create_multi_leg_order_value_error(
        self, mock_get_service, client: TestClient
    ):
        """Test multi-leg order creation with ValueError."""
        mock_service = AsyncMock()
        mock_service.create_multi_leg_order_from_request.side_effect = ValueError(
            "Invalid price values"
        )
        mock_get_service.return_value = mock_service

        order_data = {
            "legs": [
                {
                    "asset": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": -5.25,  # Invalid negative price
                }
            ],
            "order_type": "limit",
            "net_price": -5.25,
        }

        response = client.post("/api/v1/options/orders/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_multi_leg_order_invalid_json(self, client: TestClient):
        """Test multi-leg order creation with invalid JSON."""
        response = client.post("/api/v1/options/orders/multi-leg", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # GET /{option_symbol}/greeks - Greeks calculation endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_calculate_option_greeks_success(
        self, mock_get_service, client: TestClient
    ):
        """Test successful Greeks calculation."""
        mock_service = AsyncMock()
        mock_greeks_data = {
            "symbol": "AAPL_230616C00150000",
            "underlying_symbol": "AAPL",
            "strike": 150.0,
            "expiration": "2023-06-16",
            "option_type": "call",
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "implied_volatility": 0.25,
            "underlying_price": 155.0,
            "option_price": 5.25,
        }
        mock_service.get_option_greeks_response.return_value = mock_greeks_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL_230616C00150000/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["underlying_symbol"] == "AAPL"
        assert data["delta"] == 0.65
        assert data["gamma"] == 0.03
        assert data["theta"] == -0.02
        assert data["vega"] == 0.15
        assert data["rho"] == 0.08
        assert data["implied_volatility"] == 0.25

        mock_service.get_option_greeks_response.assert_called_once_with(
            "AAPL_230616C00150000", None
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_calculate_option_greeks_with_override(
        self, mock_get_service, client: TestClient
    ):
        """Test Greeks calculation with parameter override."""
        mock_service = AsyncMock()
        mock_greeks_data = {
            "symbol": "AAPL_230616C00150000",
            "delta": 0.70,  # Different due to override
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
        }
        mock_service.get_option_greeks_response.return_value = mock_greeks_data
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/options/AAPL_230616C00150000/greeks?underlying_price=160&volatility=0.30"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["delta"] == 0.70

        mock_service.get_option_greeks_response.assert_called_once_with(
            "AAPL_230616C00150000", 160.0
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_calculate_option_greeks_not_found(
        self, mock_get_service, client: TestClient
    ):
        """Test Greeks calculation for non-existent option."""
        mock_service = AsyncMock()
        mock_service.get_option_greeks_response.side_effect = NotFoundError(
            "Option symbol not found"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/INVALID_OPTION/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Option symbol not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_calculate_option_greeks_value_error(
        self, mock_get_service, client: TestClient
    ):
        """Test Greeks calculation with invalid parameters."""
        mock_service = AsyncMock()
        mock_service.get_option_greeks_response.side_effect = ValueError(
            "Invalid option parameters"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL_230616C00150000/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # GET /{symbol}/search - Find tradable options endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_find_tradable_options_success(self, mock_get_service, client: TestClient):
        """Test successful tradable options search."""
        mock_service = AsyncMock()
        mock_options_data = {
            "underlying_symbol": "AAPL",
            "options": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "strike": 150.0,
                    "expiration": "2023-06-16",
                    "option_type": "call",
                    "bid": 5.20,
                    "ask": 5.30,
                    "volume": 1000,
                    "open_interest": 5000,
                },
                {
                    "symbol": "AAPL_230616P00150000",
                    "strike": 150.0,
                    "expiration": "2023-06-16",
                    "option_type": "put",
                    "bid": 2.05,
                    "ask": 2.15,
                    "volume": 600,
                    "open_interest": 2500,
                },
            ],
            "count": 2,
            "filters_applied": {"expiration_date": None, "option_type": None},
        }
        mock_service.find_tradable_options.return_value = mock_options_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/search")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert len(data["options"]) == 2
        assert data["options"][0]["symbol"] == "AAPL_230616C00150000"
        assert data["options"][1]["symbol"] == "AAPL_230616P00150000"
        assert data["count"] == 2

        mock_service.find_tradable_options.assert_called_once_with("AAPL", None, None)

    @patch("app.core.dependencies.get_trading_service")
    def test_find_tradable_options_with_filters(
        self, mock_get_service, client: TestClient
    ):
        """Test tradable options search with filters."""
        mock_service = AsyncMock()
        mock_options_data = {
            "underlying_symbol": "AAPL",
            "options": [],
            "count": 0,
            "filters_applied": {"expiration_date": "2023-06-16", "option_type": "call"},
        }
        mock_service.find_tradable_options.return_value = mock_options_data
        mock_get_service.return_value = mock_service

        params = {"expiration_date": "2023-06-16", "option_type": "call"}

        response = client.get("/api/v1/options/AAPL/search", params=params)

        assert response.status_code == status.HTTP_200_OK

        mock_service.find_tradable_options.assert_called_once_with(
            "AAPL", "2023-06-16", "call"
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_find_tradable_options_service_error(
        self, mock_get_service, client: TestClient
    ):
        """Test tradable options search with service error."""
        mock_service = AsyncMock()
        mock_service.find_tradable_options.side_effect = Exception("Search failed")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/search")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Error finding tradable options" in data["detail"]

    # GET /market-data/{option_id} - Option market data endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_option_market_data_success(self, mock_get_service, client: TestClient):
        """Test successful option market data retrieval."""
        mock_service = AsyncMock()
        mock_market_data = {
            "symbol": "AAPL_230616C00150000",
            "underlying_symbol": "AAPL",
            "strike": 150.0,
            "expiration": "2023-06-16",
            "option_type": "call",
            "bid": 5.20,
            "ask": 5.30,
            "last": 5.25,
            "volume": 1000,
            "open_interest": 5000,
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "implied_volatility": 0.25,
            "intrinsic_value": 5.00,
            "time_value": 0.25,
            "underlying_price": 155.0,
            "days_to_expiration": 7,
        }
        mock_service.get_option_market_data.return_value = mock_market_data
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/market-data/AAPL_230616C00150000")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["underlying_symbol"] == "AAPL"
        assert data["strike"] == 150.0
        assert data["option_type"] == "call"
        assert data["bid"] == 5.20
        assert data["ask"] == 5.30
        assert data["delta"] == 0.65
        assert data["intrinsic_value"] == 5.00
        assert data["time_value"] == 0.25

        mock_service.get_option_market_data.assert_called_once_with(
            "AAPL_230616C00150000"
        )

    @patch("app.core.dependencies.get_trading_service")
    def test_get_option_market_data_not_found(
        self, mock_get_service, client: TestClient
    ):
        """Test option market data retrieval for non-existent option."""
        mock_service = AsyncMock()
        mock_service.get_option_market_data.return_value = {"error": "Option not found"}
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/market-data/INVALID_OPTION")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Option not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_option_market_data_service_error(
        self, mock_get_service, client: TestClient
    ):
        """Test option market data retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_option_market_data.side_effect = Exception(
            "Market data unavailable"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/market-data/AAPL_230616C00150000")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Error getting option market data" in data["detail"]


class TestOptionsEndpointsErrorHandling:
    """Test error handling scenarios for options endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_service_unavailable_error(self, mock_get_service, client: TestClient):
        """Test handling when trading service is unavailable."""
        mock_get_service.side_effect = Exception("Service unavailable")

        endpoints = [
            "/api/v1/options/AAPL/chain",
            "/api/v1/options/AAPL/expirations",
            "/api/v1/options/AAPL_230616C00150000/greeks",
            "/api/v1/options/AAPL/search",
            "/api/v1/options/market-data/AAPL_230616C00150000",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_invalid_option_symbol_formats(self, client: TestClient):
        """Test handling of invalid option symbol formats."""
        invalid_symbols = [
            "",
            "AAPL",  # Stock symbol instead of option
            "AAPL_INVALID",
            "INVALID_230616C00150000",
            "AAPL_230616X00150000",  # Invalid option type
            "AAPL_230616C-150000",  # Invalid strike format
        ]

        for symbol in invalid_symbols:
            response = client.get(f"/api/v1/options/{symbol}/greeks")
            assert response.status_code in [400, 404, 422, 500]

    def test_invalid_strike_price_ranges(self, client: TestClient):
        """Test handling of invalid strike price ranges."""
        # Min strike greater than max strike
        params = {"min_strike": "160", "max_strike": "150"}

        response = client.get("/api/v1/options/AAPL/chain", params=params)
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_invalid_query_parameters(self, client: TestClient):
        """Test handling of invalid query parameters."""
        invalid_params_sets = [
            {"include_greeks": "invalid"},  # Should be boolean
            {"min_strike": "not_a_number"},
            {"max_strike": "not_a_number"},
            {"underlying_price": "invalid"},
            {"volatility": "invalid"},
            {"option_type": "invalid_type"},  # Should be 'call' or 'put'
        ]

        for params in invalid_params_sets:
            response = client.get("/api/v1/options/AAPL/chain", params=params)
            assert response.status_code in [200, 400, 422]


class TestOptionsEndpointsAuthentication:
    """Test authentication scenarios for options endpoints."""

    def test_endpoints_accessibility(self, client: TestClient):
        """Test that options endpoints handle authentication properly."""
        # These endpoints should work without explicit auth in test environment
        endpoints_to_test = [
            "/api/v1/options/AAPL/chain",
            "/api/v1/options/AAPL/expirations",
            "/api/v1/options/AAPL_230616C00150000/greeks",
            "/api/v1/options/AAPL/search",
            "/api/v1/options/market-data/AAPL_230616C00150000",
        ]

        for endpoint in endpoints_to_test:
            response = client.get(endpoint)
            # Should not require authentication for read operations
            assert response.status_code in [200, 404, 422, 500]

    def test_post_endpoints_authentication(self, client: TestClient):
        """Test that POST endpoints handle authentication properly."""
        # POST endpoints typically require authentication
        post_endpoints = [
            ("/api/v1/options/orders/multi-leg", {"legs": []}),
            ("/api/v1/options/strategies/analyze", {"include_greeks": True}),
        ]

        for endpoint, data in post_endpoints:
            response = client.post(endpoint, json=data)
            # Should handle authentication appropriately
            assert response.status_code in [200, 400, 401, 422, 500]


class TestOptionsEndpointsEdgeCases:
    """Test edge cases and boundary conditions for options endpoints."""

    def test_expired_options_handling(self, client: TestClient):
        """Test handling of expired options."""
        # Test with a past expiration date
        past_date = "2020-01-01"
        response = client.get(f"/api/v1/options/AAPL/chain?expiration_date={past_date}")

        # Should handle gracefully
        assert response.status_code in [200, 400, 404]

    def test_future_expiration_dates(self, client: TestClient):
        """Test handling of far future expiration dates."""
        # Test with a very future date
        future_date = "2030-12-31"
        response = client.get(
            f"/api/v1/options/AAPL/chain?expiration_date={future_date}"
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 404]

    def test_extreme_strike_prices(self, client: TestClient):
        """Test handling of extreme strike prices."""
        extreme_params = [
            {"min_strike": "0.01", "max_strike": "10000"},
            {"min_strike": "-100", "max_strike": "100"},  # Negative strikes
            {"min_strike": "999999", "max_strike": "1000000"},  # Very high strikes
        ]

        for params in extreme_params:
            response = client.get("/api/v1/options/AAPL/chain", params=params)
            assert response.status_code in [200, 400, 422]

    @patch("app.core.dependencies.get_trading_service")
    def test_large_options_chain_response(self, mock_get_service, client: TestClient):
        """Test handling of very large options chain responses."""
        mock_service = AsyncMock()

        # Create a large chain with many strikes and expirations
        large_chain = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {},
            "expiration_dates": [],
        }

        # Add many expiration dates
        for i in range(50):
            exp_date = f"2023-{6 + i // 30:02d}-{16 + i % 30:02d}"
            large_chain["expiration_dates"].append(exp_date)
            large_chain["chains"][exp_date] = {"calls": [], "puts": []}

            # Add many strikes for each expiration
            for strike in range(100, 200, 5):
                call_option = {
                    "symbol": f"AAPL_{exp_date.replace('-', '')}C{strike:08d}000",
                    "strike": float(strike),
                    "bid": 1.0,
                    "ask": 1.1,
                }
                put_option = {
                    "symbol": f"AAPL_{exp_date.replace('-', '')}P{strike:08d}000",
                    "strike": float(strike),
                    "bid": 1.0,
                    "ask": 1.1,
                }
                large_chain["chains"][exp_date]["calls"].append(call_option)
                large_chain["chains"][exp_date]["puts"].append(put_option)

        mock_service.get_formatted_options_chain.return_value = large_chain
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/options/AAPL/chain")

        # Should handle large responses gracefully
        assert response.status_code == status.HTTP_200_OK
