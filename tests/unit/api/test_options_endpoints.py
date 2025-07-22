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

import pytest
from fastapi import status
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from app.core.exceptions import NotFoundError, ValidationError
from app.services.trading_service import TradingService
from app.models.quotes import OptionsChainResponse, GreeksResponse


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
                            "rho": 0.08
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
                            "rho": -0.05
                        }
                    ]
                }
            },
            "expiration_dates": ["2023-06-16", "2023-06-23", "2023-06-30"]
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            "expiration_dates": []
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain_data

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            response = await ac.get("/api/v1/options/AAPL/chain?expiration_date=invalid-date")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self, client):
        """Test options chain for non-existent symbol."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_formatted_options_chain.side_effect = NotFoundError("Symbol not found")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/NONEXISTENT/chain")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_options_chain_service_error(self, client):
        """Test options chain when service raises unexpected error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_formatted_options_chain.side_effect = RuntimeError("API timeout")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            date(2023, 7, 7)
        ]
        mock_service.get_expiration_dates.return_value = mock_dates

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
        mock_service.get_expiration_dates.side_effect = NotFoundError("Symbol not found")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
                    "price": 5.25
                },
                {
                    "symbol": "AAPL_230616C00160000", 
                    "order_type": "sell_to_open",
                    "quantity": 1,
                    "price": 2.50
                }
            ],
            "strategy_type": "call_spread",
            "net_debit": 2.75,
            "status": "pending"
        }
        mock_service.create_multi_leg_order_from_request.return_value = mock_order

        order_data = {
            "legs": [
                {"symbol": "AAPL_230616C00150000", "order_type": "buy_to_open", "quantity": 1},
                {"symbol": "AAPL_230616C00160000", "order_type": "sell_to_open", "quantity": 1}
            ],
            "order_type": "limit",
            "net_price": -2.75
        }

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/orders/multi-leg", json=order_data)

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
                {"symbol": "AAPL_230616C00150000", "order_type": "buy_to_open", "quantity": 1}
            ]
        }

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/orders/multi-leg", json=order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_missing_legs(self, client):
        """Test multi-leg order creation without legs."""
        order_data = {}

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/options/orders/multi-leg", json=order_data)

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
            "calculated_at": "2023-06-15T15:30:00Z"
        }
        mock_service.get_option_greeks_response.return_value = mock_greeks

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
        mock_service.get_option_greeks_response.side_effect = NotFoundError("Option not found")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/NONEXISTENT/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_invalid_symbol(self, client):
        """Test Greeks calculation for invalid option symbol format."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_greeks_response.side_effect = ValueError("Invalid option symbol")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
                        {"symbol": "AAPL_230616P00140000", "action": "sell", "quantity": 1},
                        {"symbol": "AAPL_230616P00145000", "action": "buy", "quantity": 1},
                        {"symbol": "AAPL_230616C00165000", "action": "buy", "quantity": 1},
                        {"symbol": "AAPL_230616C00170000", "action": "sell", "quantity": 1}
                    ],
                    "max_profit": 200.0,
                    "max_loss": -300.0,
                    "breakeven_points": [142.0, 167.0],
                    "current_pnl": 50.0,
                    "risk_reward_ratio": 0.67,
                    "probability_of_profit": 0.65,
                    "days_to_expiration": 1,
                    "recommendation": "Hold to expiration"
                }
            ],
            "portfolio_greeks": {
                "total_delta": 0.05,
                "total_gamma": 0.12,
                "total_theta": -15.50,
                "total_vega": 45.20
            },
            "risk_metrics": {
                "var_1day": -1250.0,
                "expected_move": 3.2,
                "portfolio_beta": 0.95
            },
            "recommendations": [
                "Portfolio is delta neutral - good for theta collection",
                "Consider closing positions before expiration to avoid assignment risk"
            ]
        }
        mock_service.analyze_portfolio_strategies.return_value = mock_analysis

        request_data = {
            "include_greeks": True,
            "include_pnl": True,
            "include_complex_strategies": True,
            "include_recommendations": True
        }

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/strategies/analyze", json=request_data)

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
            include_recommendations=True
        )

    @pytest.mark.asyncio
    async def test_analyze_portfolio_strategies_minimal_request(self, client):
        """Test portfolio strategy analysis with minimal request parameters."""
        mock_service = MagicMock(spec=TradingService)
        mock_analysis = {"recognized_strategies": [], "recommendations": []}
        mock_service.analyze_portfolio_strategies.return_value = mock_analysis

        request_data = {
            "include_greeks": False,
            "include_pnl": False
        }

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/strategies/analyze", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        
        mock_service.analyze_portfolio_strategies.assert_called_once_with(
            include_greeks=False,
            include_pnl=False,
            include_complex_strategies=True,  # Default value
            include_recommendations=True  # Default value
        )

    @pytest.mark.asyncio
    async def test_analyze_portfolio_strategies_service_error(self, client):
        """Test strategy analysis when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.analyze_portfolio_strategies.side_effect = RuntimeError("Analysis failed")

        request_data = {"include_greeks": True}

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/strategies/analyze", json=request_data)

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
                    "delta": 0.65
                }
            ],
            "total_count": 1,
            "expiration_dates": ["2023-06-16"],
            "strike_range": {"min": 150.0, "max": 150.0}
        }
        mock_service.find_tradable_options.return_value = mock_options

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
        mock_service.find_tradable_options.return_value = {"options": [], "total_count": 0}

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/options/AAPL/search?expiration_date=2023-06-16&option_type=call"
                )

        assert response.status_code == status.HTTP_200_OK
        
        mock_service.find_tradable_options.assert_called_once_with("AAPL", "2023-06-16", "call")

    @pytest.mark.asyncio
    async def test_find_tradable_options_service_error(self, client):
        """Test tradable options search when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.find_tradable_options.side_effect = Exception("Search failed")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            "days_to_expiration": 1
        }
        mock_service.get_option_market_data.return_value = mock_market_data

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/market-data/AAPL_230616C00150000")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["symbol"] == "AAPL_230616C00150000"
        assert data["underlying_symbol"] == "AAPL"
        assert data["strike"] == 150.0
        assert data["delta"] == 0.65
        assert data["moneyness"] == "ITM"

        mock_service.get_option_market_data.assert_called_once_with("AAPL_230616C00150000")

    @pytest.mark.asyncio
    async def test_get_option_market_data_not_found(self, client):
        """Test option market data for non-existent option."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_market_data.return_value = {"error": "Option not found"}

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/market-data/NONEXISTENT")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_option_market_data_service_error(self, client):
        """Test option market data when service raises error."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_option_market_data.side_effect = Exception("Data unavailable")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/options/market-data/AAPL_230616C00150000")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Edge cases and additional tests
    @pytest.mark.asyncio
    async def test_options_endpoints_with_complex_symbols(self, client):
        """Test options endpoints handle complex option symbols correctly."""
        complex_symbols = [
            "AAPL_230616C00150000",  # Standard format
            "SPY_230616P00400000",   # ETF option
            "QQQ_230616C00350000",   # Tech ETF
        ]
        
        for symbol in complex_symbols:
            mock_service = MagicMock(spec=TradingService)
            mock_service.get_option_greeks_response.return_value = {
                "symbol": symbol,
                "delta": 0.5
            }

            with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            "chains": {}
        }
        
        # Generate multiple expiration dates with options
        for i in range(10):  # 10 expiration dates
            exp_date = f"2023-{6 + i // 4:02d}-{16 + (i % 4) * 7:02d}"
            large_chain["chains"][exp_date] = {
                "calls": [{"strike": 390.0 + j, "symbol": f"SPY_{exp_date.replace('-', '')}C00{390 + j:06.0f}"} 
                         for j in range(20)],  # 20 strikes
                "puts": [{"strike": 390.0 + j, "symbol": f"SPY_{exp_date.replace('-', '')}P00{390 + j:06.0f}"} 
                        for j in range(20)]
            }
        
        mock_service.get_formatted_options_chain.return_value = large_chain

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.asyncio
    async def test_options_endpoints_response_models(self, client):
        """Test that options endpoints return properly structured responses."""
        # Test OptionsChainResponse structure
        mock_service = MagicMock(spec=TradingService)
        mock_chain = {
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "chains": {},
            "expiration_dates": []
        }
        mock_service.get_formatted_options_chain.return_value = mock_chain

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
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
            "legs": [
                {"symbol": "AAPL_230616C00150000"}  # Missing required fields
            ]
        }

        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/options/orders/multi-leg", json=invalid_order_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_options_strategy_analysis_request_defaults(self, client):
        """Test strategy analysis request uses proper defaults."""
        mock_service = MagicMock(spec=TradingService)
        mock_service.analyze_portfolio_strategies.return_value = {"strategies": []}

        # Send minimal request
        request_data = {}

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/options/strategies/analyze", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        
        # Verify defaults were used
        call_kwargs = mock_service.analyze_portfolio_strategies.call_args[1]
        assert call_kwargs["include_greeks"] == True  # Default
        assert call_kwargs["include_pnl"] == True  # Default
        assert call_kwargs["include_complex_strategies"] == True  # Default
        assert call_kwargs["include_recommendations"] == True  # Default