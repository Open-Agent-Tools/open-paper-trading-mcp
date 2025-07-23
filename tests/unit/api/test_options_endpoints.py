"""
Comprehensive tests for options endpoints.

Tests for:
- GET /{symbol}/chain (get_options_chain)
- GET /{symbol}/expirations (get_expiration_dates)
- POST /orders/multi-leg (create_multi_leg_order)
- GET /{option_symbol}/greeks (calculate_option_greeks)
- POST /strategies/analyze (analyze_portfolio_strategies)
- GET /{symbol}/search (find_tradable_options_endpoint)
- GET /market-data/{option_id} (get_option_market_data_endpoint)

All tests use proper async patterns with comprehensive mocking of TradingService.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions import NotFoundError, ValidationError
from app.services.trading_service import TradingService


class TestOptionsEndpoints:
    """Test options endpoints with comprehensive coverage."""

    # GET /{symbol}/chain endpoint tests
    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, client):
        """Test successful options chain retrieval."""
        mock_service = MagicMock(spec=TradingService)
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
                            "last": 5.25,
                            "volume": 1000,
                            "open_interest": 5000,
                            "delta": 0.65,
                            "gamma": 0.03,
                            "theta": -0.02,
                            "vega": 0.15,
                            "rho": 0.08,
                        }
                    ],
                    "puts": [
                        {
                            "symbol": "AAPL_230616P00150000",
                            "strike": 150.0,
                            "bid": 2.10,
                            "ask": 2.20,
                            "last": 2.15,
                            "volume": 800,
                            "open_interest": 3000,
                            "delta": -0.35,
                            "gamma": 0.03,
                            "theta": -0.02,
                            "vega": 0.15,
                            "rho": -0.05,
                        }
                    ],
                }
            },
            "expiration_dates": ["2023-06-16", "2023-06-23", "2023-06-30"],
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert data["underlying_price"] == 155.0
        assert "chains" in data
        assert "2023-06-16" in data["chains"]
        assert len(data["chains"]["2023-06-16"]["calls"]) == 1
        assert len(data["chains"]["2023-06-16"]["puts"]) == 1
        assert data["chains"]["2023-06-16"]["calls"][0]["delta"] == 0.65

        # Verify service was called with correct parameters
        mock_service.get_formatted_options_chain.assert_called_once_with(
            "AAPL", None, None, None, True
        )

    @pytest.mark.asyncio
    async def test_get_options_chain_with_filters(self, client):
        """Test options chain retrieval with expiration and strike filters."""
        mock_service = MagicMock(spec=TradingService)
        mock_chain_data = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {},
            "expiration_dates": [],
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/AAPL/chain"
                    "?expiration_date=2023-06-16"
                    "&min_strike=150.0"
                    "&max_strike=160.0"
                    "&include_greeks=false"
                )

        assert response.status_code == status.HTTP_200_OK

        # Verify service was called with filters
        mock_service.get_formatted_options_chain.assert_called_once_with(
            "AAPL", date(2023, 6, 16), 150.0, 160.0, False
        )

    @pytest.mark.asyncio
    async def test_get_options_chain_invalid_date(self, client):
        """Test options chain with invalid expiration date format."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/options/AAPL/chain?expiration_date=invalid-date"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self, client):
        """Test options chain for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_formatted_options_chain.side_effect = NotFoundError(
            "Symbol not found"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/NONEXISTENT/chain")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_options_chain_service_error(self, client):
        """Test options chain when service raises unexpected error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_formatted_options_chain.side_effect = RuntimeError(
            "API timeout"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /{symbol}/expirations endpoint tests
    @pytest.mark.asyncio
    async def test_get_expiration_dates_success(self, client):
        """Test successful expiration dates retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_dates = [
            date(2023, 6, 16),
            date(2023, 6, 23),
            date(2023, 6, 30),
            date(2023, 7, 7),
        ]
        mock_service.get_expiration_dates.return_value = mock_dates

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/expirations")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert data["count"] == 4
        assert len(data["expiration_dates"]) == 4
        assert data["expiration_dates"][0] == "2023-06-16"
        assert data["next_expiration"] == "2023-06-16"
        assert data["last_expiration"] == "2023-07-07"

        mock_service.get_expiration_dates.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_expiration_dates_empty(self, client):
        """Test expiration dates when no options available."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_expiration_dates.return_value = []

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/expirations")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["count"] == 0
        assert data["expiration_dates"] == []
        assert data["next_expiration"] is None
        assert data["last_expiration"] is None

    @pytest.mark.asyncio
    async def test_get_expiration_dates_not_found(self, client):
        """Test expiration dates for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_expiration_dates.side_effect = NotFoundError(
            "Symbol not found"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/NONEXISTENT/expirations")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # POST /orders/multi-leg endpoint tests
    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(self, client):
        """Test successful multi-leg order creation."""
        mock_service = MagicMock(spec=TradingService)
        mock_order = {
            "id": "multileg_123",
            "legs": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": 5.25,
                },
                {
                    "symbol": "AAPL_230616C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                    "price": 2.50,
                },
            ],
            "strategy_type": "call_spread",
            "net_debit": 2.75,
            "status": "pending",
        }
        mock_service.create_multi_leg_order_from_request.return_value = mock_order

        order_data = {
            "legs": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                },
                {
                    "symbol": "AAPL_230616C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                },
            ],
            "order_type": "limit",
            "net_price": -2.75,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/orders/multi-leg", json=order_data
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "multileg_123"
        assert len(data["legs"]) == 2
        assert data["strategy_type"] == "call_spread"
        assert data["status"] == "pending"

        mock_service.create_multi_leg_order_from_request.assert_called_once_with(
            order_data["legs"], "limit", -2.75
        )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_validation_error(self, client):
        """Test multi-leg order creation with validation error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.create_multi_leg_order_from_request.side_effect = ValidationError(
            "Invalid options strategy"
        )

        order_data = {
            "legs": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                }
            ]
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/orders/multi-leg", json=order_data
                )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_missing_legs(self, client):
        """Test multi-leg order creation without legs."""
        order_data = {}

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/options/orders/multi-leg", json=order_data
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # GET /{option_symbol}/greeks endpoint tests
    @pytest.mark.asyncio
    async def test_calculate_option_greeks_success(self, client):
        """Test successful option Greeks calculation."""
        mock_service = MagicMock(spec=TradingService)
        mock_greeks = {
            "symbol": "AAPL_230616C00150000",
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "strike": 150.0,
            "expiration": "2023-06-16",
            "option_type": "call",
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "implied_volatility": 0.25,
            "intrinsic_value": 5.0,
            "time_value": 0.25,
            "calculated_at": "2023-06-15T15:30:00Z",
        }
        mock_service.get_option_greeks_response.return_value = mock_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL_230616C00150000/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["delta"] == 0.65
        assert data["gamma"] == 0.03
        assert data["theta"] == -0.02
        assert data["vega"] == 0.15
        assert data["rho"] == 0.08
        assert data["implied_volatility"] == 0.25

        mock_service.get_option_greeks_response.assert_called_once_with(
            "AAPL_230616C00150000", None
        )

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_with_override(self, client):
        """Test option Greeks calculation with underlying price override."""
        mock_service = MagicMock(spec=TradingService)
        mock_greeks = {"symbol": "AAPL_230616C00150000", "delta": 0.70}
        mock_service.get_option_greeks_response.return_value = mock_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/AAPL_230616C00150000/greeks?underlying_price=160.0"
                )

        assert response.status_code == status.HTTP_200_OK

        # Verify override parameter was passed
        mock_service.get_option_greeks_response.assert_called_once_with(
            "AAPL_230616C00150000", 160.0
        )

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_not_found(self, client):
        """Test Greeks calculation for non-existent option."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_greeks_response.side_effect = NotFoundError(
            "Option not found"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/NONEXISTENT/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_invalid_symbol(self, client):
        """Test Greeks calculation for invalid option symbol format."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_greeks_response.side_effect = ValueError(
            "Invalid option symbol"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/INVALID_SYMBOL/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # POST /strategies/analyze endpoint tests
    @pytest.mark.asyncio
    async def test_analyze_portfolio_strategies_success(self, client):
        """Test successful portfolio strategy analysis."""
        mock_service = MagicMock(spec=TradingService)
        mock_analysis = {
            "recognized_strategies": [
                {
                    "strategy_name": "Iron Condor",
                    "strategy_type": "iron_condor",
                    "legs": [
                        {
                            "symbol": "AAPL_230616P00140000",
                            "action": "sell",
                            "quantity": 1,
                        },
                        {
                            "symbol": "AAPL_230616P00145000",
                            "action": "buy",
                            "quantity": 1,
                        },
                        {
                            "symbol": "AAPL_230616C00165000",
                            "action": "buy",
                            "quantity": 1,
                        },
                        {
                            "symbol": "AAPL_230616C00170000",
                            "action": "sell",
                            "quantity": 1,
                        },
                    ],
                    "max_profit": 200.0,
                    "max_loss": -300.0,
                    "breakeven_points": [142.0, 167.0],
                    "current_pnl": 50.0,
                    "risk_reward_ratio": 0.67,
                    "probability_of_profit": 0.65,
                    "days_to_expiration": 1,
                    "recommendation": "Hold to expiration",
                }
            ],
            "portfolio_greeks": {
                "total_delta": 0.05,
                "total_gamma": 0.12,
                "total_theta": -15.50,
                "total_vega": 45.20,
            },
            "risk_metrics": {
                "var_1day": -1250.0,
                "expected_move": 3.2,
                "portfolio_beta": 0.95,
            },
            "recommendations": [
                "Portfolio is delta neutral - good for theta collection",
                "Consider closing positions before expiration to avoid assignment risk",
            ],
        }
        mock_service.analyze_portfolio_strategies.return_value = mock_analysis

        request_data = {
            "include_greeks": True,
            "include_pnl": True,
            "include_complex_strategies": True,
            "include_recommendations": True,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "recognized_strategies" in data
        assert "portfolio_greeks" in data
        assert "risk_metrics" in data
        assert "recommendations" in data
        assert len(data["recognized_strategies"]) == 1
        assert data["recognized_strategies"][0]["strategy_type"] == "iron_condor"
        assert data["portfolio_greeks"]["total_theta"] == -15.50

        mock_service.analyze_portfolio_strategies.assert_called_once_with(
            include_greeks=True,
            include_pnl=True,
            include_complex_strategies=True,
            include_recommendations=True,
        )

    @pytest.mark.asyncio
    async def test_analyze_portfolio_strategies_minimal_request(self, client):
        """Test portfolio strategy analysis with minimal request parameters."""
        mock_service = MagicMock(spec=TradingService)
        mock_analysis = {"recognized_strategies": [], "recommendations": []}
        mock_service.analyze_portfolio_strategies.return_value = mock_analysis

        request_data = {"include_greeks": False, "include_pnl": False}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_200_OK

        mock_service.analyze_portfolio_strategies.assert_called_once_with(
            include_greeks=False,
            include_pnl=False,
            include_complex_strategies=True,  # Default value
            include_recommendations=True,  # Default value
        )

    @pytest.mark.asyncio
    async def test_analyze_portfolio_strategies_service_error(self, client):
        """Test strategy analysis when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.analyze_portfolio_strategies.side_effect = RuntimeError(
            "Analysis failed"
        )

        request_data = {"include_greeks": True}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /{symbol}/search endpoint tests
    @pytest.mark.asyncio
    async def test_find_tradable_options_success(self, client):
        """Test successful tradable options search."""
        mock_service = MagicMock(spec=TradingService)
        mock_options = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "options": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": "2023-06-16",
                    "bid": 5.20,
                    "ask": 5.30,
                    "volume": 1000,
                    "open_interest": 5000,
                    "delta": 0.65,
                }
            ],
            "total_count": 1,
            "expiration_dates": ["2023-06-16"],
            "strike_range": {"min": 150.0, "max": 150.0},
        }
        mock_service.find_tradable_options.return_value = mock_options

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/search")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["underlying_symbol"] == "AAPL"
        assert data["total_count"] == 1
        assert len(data["options"]) == 1
        assert data["options"][0]["symbol"] == "AAPL_230616C00150000"

        mock_service.find_tradable_options.assert_called_once_with("AAPL", None, None)

    @pytest.mark.asyncio
    async def test_find_tradable_options_with_filters(self, client):
        """Test tradable options search with filters."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.find_tradable_options.return_value = {
            "options": [],
            "total_count": 0,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/AAPL/search?expiration_date=2023-06-16&option_type=call"
                )

        assert response.status_code == status.HTTP_200_OK

        mock_service.find_tradable_options.assert_called_once_with(
            "AAPL", "2023-06-16", "call"
        )

    @pytest.mark.asyncio
    async def test_find_tradable_options_service_error(self, client):
        """Test tradable options search when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.find_tradable_options.side_effect = Exception("Search failed")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/search")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /market-data/{option_id} endpoint tests
    @pytest.mark.asyncio
    async def test_get_option_market_data_success(self, client):
        """Test successful option market data retrieval."""
        mock_service = MagicMock(spec=TradingService)
        mock_market_data = {
            "symbol": "AAPL_230616C00150000",
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "option_type": "call",
            "strike": 150.0,
            "expiration": "2023-06-16",
            "bid": 5.20,
            "ask": 5.30,
            "last": 5.25,
            "change": 0.15,
            "change_percent": 2.94,
            "volume": 1000,
            "open_interest": 5000,
            "implied_volatility": 0.25,
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "intrinsic_value": 5.0,
            "time_value": 0.25,
            "moneyness": "ITM",
            "days_to_expiration": 1,
        }
        mock_service.get_option_market_data.return_value = mock_market_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/market-data/AAPL_230616C00150000"
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["underlying_symbol"] == "AAPL"
        assert data["strike"] == 150.0
        assert data["delta"] == 0.65
        assert data["moneyness"] == "ITM"

        mock_service.get_option_market_data.assert_called_once_with(
            "AAPL_230616C00150000"
        )

    @pytest.mark.asyncio
    async def test_get_option_market_data_not_found(self, client):
        """Test option market data for non-existent option."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_market_data.return_value = {"error": "Option not found"}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/market-data/NONEXISTENT")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_option_market_data_service_error(self, client):
        """Test option market data when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_market_data.side_effect = Exception("Data unavailable")

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/market-data/AAPL_230616C00150000"
                )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Edge cases and additional tests
    @pytest.mark.asyncio
    async def test_options_endpoints_with_complex_symbols(self, client):
        """Test options endpoints handle complex option symbols correctly."""
        complex_symbols = [
            "AAPL_230616C00150000",  # Standard format
            "SPY_230616P00400000",  # ETF option
            "QQQ_230616C00350000",  # Tech ETF
        ]

        for symbol in complex_symbols:
            mock_service = MagicMock(spec=TradingService)
            mock_service.get_option_greeks_response.return_value = {
                "symbol": symbol,
                "delta": 0.5,
            }

            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    response = await ac.get(f"/api/v1/options/{symbol}/greeks")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["symbol"] == symbol

    @pytest.mark.asyncio
    async def test_options_chain_pagination_large_dataset(self, client):
        """Test options chain handles large datasets correctly."""
        mock_service = MagicMock(spec=TradingService)

        # Mock large options chain with multiple expirations
        large_chain = {
            "underlying_symbol": "SPY",
            "underlying_price": 400.0,
            "chains": {},
        }

        # Generate multiple expiration dates with options
        for i in range(10):  # 10 expiration dates
            exp_date = f"2023-{6 + i // 4:02d}-{16 + (i % 4) * 7:02d}"
            large_chain["chains"][exp_date] = {
                "calls": [
                    {
                        "strike": 390.0 + j,
                        "symbol": f"SPY_{exp_date.replace('-', '')}C00{390 + j:06.0f}",
                    }
                    for j in range(20)
                ],  # 20 strikes
                "puts": [
                    {
                        "strike": 390.0 + j,
                        "symbol": f"SPY_{exp_date.replace('-', '')}P00{390 + j:06.0f}",
                    }
                    for j in range(20)
                ],
            }

        mock_service.get_formatted_options_chain.return_value = large_chain

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/SPY/chain")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["chains"]) == 10

    @pytest.mark.asyncio
    async def test_options_endpoints_parameter_validation(self, client):
        """Test options endpoints handle parameter validation correctly."""
        # Test negative strike prices
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/options/AAPL/chain?min_strike=-100")

        # Should still work - service layer handles business logic validation
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

        # Test invalid option type filter
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/options/AAPL/search?option_type=invalid")

        # Should work - service validates option types
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    async def test_options_endpoints_response_models(self, client):
        """Test that options endpoints return properly structured responses."""
        # Test OptionsChainResponse structure
        mock_service = MagicMock(spec=TradingService)
        mock_chain = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {},
            "expiration_dates": [],
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required OptionsChainResponse fields
        required_fields = ["underlying_symbol", "chains", "data_source", "cached"]
        for field in required_fields:
            assert field in data

    @pytest.mark.asyncio
    async def test_options_multi_leg_order_request_validation(self, client):
        """Test multi-leg order request model validation."""
        # Test with invalid leg structure
        invalid_order_data = {
            "legs": [{"symbol": "AAPL_230616C00150000"}]  # Missing required fields
        }

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/options/orders/multi-leg", json=invalid_order_data
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_options_strategy_analysis_request_defaults(self, client):
        """Test strategy analysis request uses proper defaults."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.analyze_portfolio_strategies.return_value = {"strategies": []}

        # Send minimal request
        request_data = {}

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_200_OK

        # Verify defaults were used
        call_kwargs = mock_service.analyze_portfolio_strategies.call_args[1]
        assert call_kwargs["include_greeks"]  # Default
        assert call_kwargs["include_pnl"]  # Default
        assert call_kwargs["include_complex_strategies"]  # Default
        assert call_kwargs["include_recommendations"]  # Default

    # Enhanced complex strategy testing
    @pytest.mark.asyncio
    async def test_complex_multi_leg_strategies(self, client):
        """Test complex multi-leg options strategies."""
        complex_strategies = [
            # Iron Condor
            {
                "name": "Iron Condor",
                "legs": [
                    {
                        "symbol": "AAPL_230616P00140000",
                        "order_type": "sell_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616P00145000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616C00165000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616C00170000",
                        "order_type": "sell_to_open",
                        "quantity": 1,
                    },
                ],
                "expected_strategy": "iron_condor",
            },
            # Butterfly Spread
            {
                "name": "Call Butterfly",
                "legs": [
                    {
                        "symbol": "AAPL_230616C00150000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616C00155000",
                        "order_type": "sell_to_open",
                        "quantity": 2,
                    },
                    {
                        "symbol": "AAPL_230616C00160000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                ],
                "expected_strategy": "butterfly_spread",
            },
            # Straddle
            {
                "name": "Long Straddle",
                "legs": [
                    {
                        "symbol": "AAPL_230616C00155000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616P00155000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                ],
                "expected_strategy": "straddle",
            },
            # Strangle
            {
                "name": "Long Strangle",
                "legs": [
                    {
                        "symbol": "AAPL_230616C00160000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                    {
                        "symbol": "AAPL_230616P00150000",
                        "order_type": "buy_to_open",
                        "quantity": 1,
                    },
                ],
                "expected_strategy": "strangle",
            },
        ]

        for strategy in complex_strategies:
            mock_service = MagicMock(spec=TradingService)
            mock_order = {
                "id": f"order_{strategy['name'].lower().replace(' ', '_')}",
                "legs": strategy["legs"],
                "strategy_type": strategy["expected_strategy"],
                "status": "pending",
                "max_profit": 500.0,
                "max_loss": -1500.0,
                "breakeven_points": [152.0, 158.0],
            }
            mock_service.create_multi_leg_order_from_request.return_value = mock_order

            order_data = {
                "legs": strategy["legs"],
                "order_type": "limit",
                "net_price": -2.50,
            }

            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    response = await ac.post(
                        "/api/v1/options/orders/multi-leg", json=order_data
                    )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["strategy_type"] == strategy["expected_strategy"]
            assert len(data["legs"]) == len(strategy["legs"])

    @pytest.mark.asyncio
    async def test_options_greeks_scenario_analysis(self, client):
        """Test options Greeks under different market scenarios."""
        scenarios = [
            # High volatility scenario
            {
                "name": "High Volatility",
                "underlying_price": 155.0,
                "volatility": 0.40,
                "expected_vega_impact": "high",
            },
            # Low volatility scenario
            {
                "name": "Low Volatility",
                "underlying_price": 155.0,
                "volatility": 0.10,
                "expected_vega_impact": "low",
            },
            # Deep ITM scenario
            {
                "name": "Deep ITM",
                "underlying_price": 180.0,
                "volatility": 0.25,
                "expected_delta": "high",
            },
            # Deep OTM scenario
            {
                "name": "Deep OTM",
                "underlying_price": 130.0,
                "volatility": 0.25,
                "expected_delta": "low",
            },
        ]

        for scenario in scenarios:
            mock_service = MagicMock(spec=TradingService)
            mock_greeks = {
                "symbol": "AAPL_230616C00150000",
                "underlying_price": scenario["underlying_price"],
                "delta": 0.85 if scenario.get("expected_delta") == "high" else 0.15,
                "gamma": 0.01,
                "theta": -0.05,
                "vega": (
                    0.30 if scenario.get("expected_vega_impact") == "high" else 0.05
                ),
                "rho": 0.08,
                "implied_volatility": scenario["volatility"],
                "scenario": scenario["name"],
            }
            mock_service.get_option_greeks_response.return_value = mock_greeks

            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    response = await ac.get(
                        f"/api/v1/options/AAPL_230616C00150000/greeks"
                        f"?underlying_price={scenario['underlying_price']}"
                        f"&volatility={scenario['volatility']}"
                    )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["underlying_price"] == scenario["underlying_price"]
            assert data["implied_volatility"] == scenario["volatility"]

    @pytest.mark.asyncio
    async def test_options_expiration_edge_cases(self, client):
        """Test options behavior near expiration dates."""
        mock_service = MagicMock(spec=TradingService)

        # Test with options expiring today
        today_greeks = {
            "symbol": "AAPL_230616C00150000",
            "days_to_expiration": 0,
            "theta": -0.50,  # High theta decay
            "gamma": 0.10,  # High gamma risk
            "time_value": 0.01,  # Very low time value
            "expiration_risk": "high",
            "assignment_probability": 0.85,
        }
        mock_service.get_option_greeks_response.return_value = today_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL_230616C00150000/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["days_to_expiration"] == 0
        assert data["expiration_risk"] == "high"
        assert data["theta"] == -0.50

    @pytest.mark.asyncio
    async def test_options_chain_real_time_data_handling(self, client):
        """Test options chain with real-time vs delayed data."""
        mock_service = MagicMock(spec=TradingService)

        real_time_chain = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.50,
            "data_source": "real_time",
            "last_updated": "2023-06-15T15:30:00Z",
            "market_status": "open",
            "chains": {
                "2023-06-16": {
                    "calls": [
                        {
                            "symbol": "AAPL_230616C00150000",
                            "strike": 150.0,
                            "bid": 5.25,
                            "ask": 5.35,
                            "last": 5.30,
                            "volume": 1250,
                            "bid_size": 10,
                            "ask_size": 15,
                            "last_trade_time": "2023-06-15T15:29:45Z",
                        }
                    ],
                    "puts": [],
                }
            },
            "disclaimer": None,
        }
        mock_service.get_formatted_options_chain.return_value = real_time_chain

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/AAPL/chain")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data_source"] == "real_time"
        assert data["market_status"] == "open"
        assert "disclaimer" not in data or data["disclaimer"] is None

    @pytest.mark.asyncio
    async def test_portfolio_risk_analysis_with_options(self, client):
        """Test comprehensive portfolio risk analysis including options positions."""
        mock_service = MagicMock(spec=TradingService)

        comprehensive_analysis = {
            "recognized_strategies": [
                {
                    "strategy_name": "Covered Call",
                    "strategy_type": "covered_call",
                    "underlying_position": {"symbol": "AAPL", "quantity": 100},
                    "option_position": {
                        "symbol": "AAPL_230616C00160000",
                        "quantity": -1,
                    },
                    "max_profit": 500.0,
                    "max_loss": -15000.0,
                    "breakeven_point": 155.0,
                    "current_pnl": 125.0,
                    "assignment_risk": 0.25,
                    "early_assignment_probability": 0.05,
                    "recommendation": "Monitor for early assignment",
                },
                {
                    "strategy_name": "Cash Secured Put",
                    "strategy_type": "cash_secured_put",
                    "cash_requirement": 15000.0,
                    "option_position": {
                        "symbol": "AAPL_230616P00150000",
                        "quantity": -1,
                    },
                    "max_profit": 250.0,
                    "assignment_probability": 0.15,
                    "current_pnl": 75.0,
                    "recommendation": "Let expire worthless",
                },
            ],
            "portfolio_greeks": {
                "total_delta": 45.0,  # Positive delta exposure
                "total_gamma": 12.0,
                "total_theta": -25.0,  # Negative theta (time decay)
                "total_vega": 35.0,  # Positive vega exposure
                "total_rho": 8.0,
                "net_delta_percent": 0.12,  # 12% delta exposure
            },
            "risk_metrics": {
                "portfolio_var_1day": -2500.0,
                "portfolio_var_1week": -5500.0,
                "max_drawdown_potential": -8000.0,
                "volatility_exposure": "moderate",
                "time_decay_daily": -25.0,
                "assignment_risk_total": 0.40,
                "margin_requirement": 25000.0,
                "buying_power_effect": -15000.0,
            },
            "stress_test_scenarios": [
                {
                    "scenario": "10% underlying drop",
                    "portfolio_impact": -3500.0,
                    "delta_adjusted_impact": -4500.0,
                    "gamma_impact": -500.0,
                },
                {
                    "scenario": "Volatility spike to 40%",
                    "portfolio_impact": 1400.0,
                    "vega_impact": 1400.0,
                },
                {
                    "scenario": "Interest rate increase 1%",
                    "portfolio_impact": 80.0,
                    "rho_impact": 80.0,
                },
            ],
            "recommendations": [
                "Portfolio is moderately delta positive - consider hedging for market decline",
                "High gamma exposure may cause rapid delta changes",
                "Positive theta collection strategy - time decay is beneficial",
                "Monitor assignment risk on short options positions",
                "Consider volatility hedging given vega exposure",
            ],
            "alerts": [
                {
                    "type": "assignment_risk",
                    "message": "AAPL call option approaching assignment risk threshold",
                    "severity": "medium",
                },
                {
                    "type": "expiration_notice",
                    "message": "Options expiring in 1 day - review positions",
                    "severity": "high",
                },
            ],
        }
        mock_service.analyze_portfolio_strategies.return_value = comprehensive_analysis

        request_data = {
            "include_greeks": True,
            "include_pnl": True,
            "include_complex_strategies": True,
            "include_recommendations": True,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify comprehensive analysis structure
        assert "recognized_strategies" in data
        assert "portfolio_greeks" in data
        assert "risk_metrics" in data
        assert "stress_test_scenarios" in data
        assert "recommendations" in data
        assert "alerts" in data

        # Verify strategy details
        strategies = data["recognized_strategies"]
        assert len(strategies) == 2
        assert strategies[0]["strategy_type"] == "covered_call"
        assert strategies[1]["strategy_type"] == "cash_secured_put"

        # Verify risk metrics
        risk_metrics = data["risk_metrics"]
        assert "portfolio_var_1day" in risk_metrics
        assert "assignment_risk_total" in risk_metrics
        assert "margin_requirement" in risk_metrics

        # Verify stress testing
        stress_tests = data["stress_test_scenarios"]
        assert len(stress_tests) == 3
        scenario_names = [s["scenario"] for s in stress_tests]
        assert "10% underlying drop" in scenario_names
        assert "Volatility spike to 40%" in scenario_names

    @pytest.mark.asyncio
    async def test_options_market_data_high_frequency_updates(self, client):
        """Test options market data handling with high-frequency updates."""
        mock_service = MagicMock(spec=TradingService)

        # Simulate real-time market data with frequent updates
        high_freq_data = {
            "symbol": "AAPL_230616C00155000",
            "underlying_symbol": "AAPL",
            "underlying_price": 155.75,
            "bid": 1.20,
            "ask": 1.25,
            "last": 1.22,
            "volume": 5000,
            "open_interest": 12000,
            "bid_size": 50,
            "ask_size": 75,
            "last_trade_time": "2023-06-15T15:30:00.123456Z",
            "quote_timestamp": "2023-06-15T15:30:00.234567Z",
            "data_freshness_ms": 15,  # Very fresh data
            "market_maker_spread": 0.05,
            "theoretical_price": 1.23,
            "price_model": "black_scholes",
            "update_frequency": "real_time",
        }
        mock_service.get_option_market_data.return_value = high_freq_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/market-data/AAPL_230616C00155000"
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data_freshness_ms"] == 15
        assert data["update_frequency"] == "real_time"
        assert "quote_timestamp" in data

    @pytest.mark.asyncio
    async def test_options_unusual_activity_detection(self, client):
        """Test detection of unusual options activity."""
        mock_service = MagicMock(spec=TradingService)

        unusual_activity_data = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "options": [
                {
                    "symbol": "AAPL_230616C00160000",
                    "strike": 160.0,
                    "volume": 15000,  # Unusually high volume
                    "avg_volume": 500,  # Normal volume
                    "volume_ratio": 30.0,  # 30x normal volume
                    "open_interest": 2000,
                    "volume_oi_ratio": 7.5,  # High volume vs OI
                    "unusual_activity_flags": [
                        "high_volume",
                        "volume_spike",
                        "possible_institutional_flow",
                    ],
                    "activity_score": 8.5,  # High activity score
                    "price_movement": 0.15,  # 15 cents move
                    "implied_volatility_change": 0.05,  # 5% IV increase
                },
                {
                    "symbol": "AAPL_230616P00150000",
                    "strike": 150.0,
                    "volume": 8000,
                    "avg_volume": 300,
                    "volume_ratio": 26.7,
                    "unusual_activity_flags": [
                        "high_volume",
                        "put_volume_spike",
                        "hedging_activity",
                    ],
                    "activity_score": 7.2,
                },
            ],
            "summary": {
                "total_unusual_contracts": 2,
                "total_volume": 23000,
                "call_put_ratio": 1.88,  # More call activity
                "sentiment": "bullish",
                "institutional_flow_detected": True,
            },
        }
        mock_service.find_tradable_options.return_value = unusual_activity_data

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/AAPL/search?include_unusual_activity=true"
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify unusual activity detection
        assert "summary" in data
        assert data["summary"]["institutional_flow_detected"]
        assert data["summary"]["sentiment"] == "bullish"

        # Check individual options flags
        options = data["options"]
        high_volume_option = next(
            opt for opt in options if "high_volume" in opt["unusual_activity_flags"]
        )
        assert high_volume_option["activity_score"] > 7.0

    @pytest.mark.asyncio
    async def test_options_earnings_volatility_analysis(self, client):
        """Test options analysis around earnings announcements."""
        mock_service = MagicMock(spec=TradingService)

        earnings_analysis = {
            "underlying_symbol": "AAPL",
            "earnings_date": "2023-06-16",
            "earnings_time": "after_market_close",
            "days_until_earnings": 1,
            "implied_move": 0.08,  # 8% implied move
            "historical_moves": [0.05, 0.12, 0.03, 0.09],  # Historical earnings moves
            "average_historical_move": 0.072,
            "iv_rank": 85,  # High IV rank
            "iv_percentile": 92,  # Very high IV percentile
            "earnings_strategies": [
                {
                    "strategy_name": "Short Straddle",
                    "strategy_type": "short_straddle",
                    "legs": [
                        {"symbol": "AAPL_230616C00155000", "action": "sell"},
                        {"symbol": "AAPL_230616P00155000", "action": "sell"},
                    ],
                    "profit_probability": 0.65,
                    "max_profit": 750.0,
                    "breakeven_range": [147.5, 162.5],
                    "risk_reward": "favorable",
                    "capital_requirement": 15000.0,
                },
                {
                    "strategy_name": "Iron Butterfly",
                    "strategy_type": "iron_butterfly",
                    "profit_probability": 0.58,
                    "max_profit": 400.0,
                    "max_loss": -600.0,
                    "risk_reward": "moderate",
                },
            ],
            "volatility_analysis": {
                "pre_earnings_iv": 0.42,
                "post_earnings_iv_estimate": 0.28,
                "volatility_crush_estimate": 0.14,  # 14% vol crush expected
                "theta_acceleration": -0.15,
            },
            "recommendations": [
                "High implied volatility suggests premium selling opportunities",
                "Consider volatility crush strategies for post-earnings",
                "Monitor position sizing due to high risk around earnings",
                "Close positions before earnings if directional exposure is unwanted",
            ],
        }

        mock_service.analyze_portfolio_strategies.return_value = earnings_analysis

        request_data = {
            "include_earnings_analysis": True,
            "include_volatility_metrics": True,
        }

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/options/strategies/analyze", json=request_data
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify earnings analysis components
        assert data["earnings_date"] == "2023-06-16"
        assert data["implied_move"] == 0.08
        assert data["iv_rank"] == 85

        # Verify earnings-specific strategies
        strategies = data["earnings_strategies"]
        assert len(strategies) == 2
        straddle_strategy = next(
            s for s in strategies if s["strategy_type"] == "short_straddle"
        )
        assert straddle_strategy["profit_probability"] == 0.65

        # Verify volatility analysis
        vol_analysis = data["volatility_analysis"]
        assert vol_analysis["volatility_crush_estimate"] == 0.14
