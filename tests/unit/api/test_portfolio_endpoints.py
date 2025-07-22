"""
Comprehensive tests for portfolio endpoints.

Tests for:
- GET / (get_portfolio)
- GET /summary (get_portfolio_summary)
- GET /positions (get_positions)
- GET /position/{symbol} (get_position)
- GET /position/{symbol}/greeks (get_position_greeks)
- GET /greeks (get_portfolio_greeks)
- GET /strategies (get_portfolio_strategies)

All tests use proper async patterns with comprehensive mocking of TradingService.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.core.exceptions import NotFoundError, ValidationError
from app.services.trading_service import TradingService
from app.schemas.positions import Portfolio, PortfolioSummary, Position


class TestPortfolioEndpoints:
    """Test portfolio endpoints with comprehensive coverage."""

    # GET / (get_portfolio) endpoint tests
    @pytest.mark.asyncio
    async def test_get_portfolio_success(self, client):
        """Test successful portfolio retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    average_price=150.0,
                    current_price=155.0,
                    market_value=15500.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0
                )
            ],
            market_value=15500.0,
            total_value=25500.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["cash_balance"] == 10000.0
        assert data["market_value"] == 15500.0
        assert data["total_value"] == 25500.0
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][0]["quantity"] == 100

        mock_service.get_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_empty(self, client):
        """Test portfolio retrieval when portfolio is empty."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            market_value=0.0,
            total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["cash_balance"] == 10000.0
        assert data["positions"] == []
        assert data["market_value"] == 0.0
        assert data["total_value"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_portfolio_service_error(self, client):
        """Test portfolio retrieval when service raises error."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_portfolio.side_effect = RuntimeError("Database error")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /summary (get_portfolio_summary) endpoint tests
    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(self, client):
        """Test successful portfolio summary retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_summary = PortfolioSummary(
            cash_balance=10000.0,
            market_value=15500.0,
            total_value=25500.0,
            day_change=250.0,
            day_change_percent=1.0,
            total_gain_loss=500.0,
            total_gain_loss_percent=2.0,
            position_count=3
        )
        mock_service.get_portfolio_summary.return_value = mock_summary

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["cash_balance"] == 10000.0
        assert data["market_value"] == 15500.0
        assert data["total_value"] == 25500.0
        assert data["day_change"] == 250.0
        assert data["day_change_percent"] == 1.0
        assert data["total_gain_loss"] == 500.0
        assert data["total_gain_loss_percent"] == 2.0
        assert data["position_count"] == 3

        mock_service.get_portfolio_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_negative_values(self, client):
        """Test portfolio summary with negative values."""
        mock_service = AsyncMock(spec=TradingService)
        mock_summary = PortfolioSummary(
            cash_balance=8000.0,
            market_value=9000.0,
            total_value=17000.0,
            day_change=-300.0,
            day_change_percent=-1.7,
            total_gain_loss=-1000.0,
            total_gain_loss_percent=-5.6,
            position_count=2
        )
        mock_service.get_portfolio_summary.return_value = mock_summary

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["day_change"] == -300.0
        assert data["day_change_percent"] == -1.7
        assert data["total_gain_loss"] == -1000.0
        assert data["total_gain_loss_percent"] == -5.6

    # GET /positions (get_positions) endpoint tests
    @pytest.mark.asyncio
    async def test_get_positions_success(self, client):
        """Test successful positions list retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                average_price=150.0,
                current_price=155.0,
                market_value=15500.0,
                unrealized_pnl=500.0,
                realized_pnl=0.0
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                average_price=2000.0,
                current_price=2050.0,
                market_value=102500.0,
                unrealized_pnl=2500.0,
                realized_pnl=100.0
            )
        ]
        mock_service.get_positions.return_value = mock_positions

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[0]["quantity"] == 100
        assert data[1]["symbol"] == "GOOGL"
        assert data[1]["quantity"] == 50

        mock_service.get_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, client):
        """Test positions list when no positions exist."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_positions.return_value = []

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    # GET /position/{symbol} (get_position) endpoint tests
    @pytest.mark.asyncio
    async def test_get_position_success(self, client):
        """Test successful specific position retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            average_price=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0
        )
        mock_service.get_position.return_value = mock_position

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["symbol"] == "AAPL"
        assert data["quantity"] == 100
        assert data["average_price"] == 150.0
        assert data["current_price"] == 155.0
        assert data["market_value"] == 15500.0
        assert data["unrealized_pnl"] == 500.0

        mock_service.get_position.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, client):
        """Test position retrieval for non-existent symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_position.side_effect = NotFoundError("Position not found")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/NONEXISTENT")

        # Global exception handler should convert NotFoundError to 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_position_special_characters(self, client):
        """Test position retrieval with special characters in symbol."""
        mock_service = AsyncMock(spec=TradingService)
        mock_position = Position(
            symbol="BRK.A",
            quantity=1,
            average_price=400000.0,
            current_price=405000.0,
            market_value=405000.0,
            unrealized_pnl=5000.0,
            realized_pnl=0.0
        )
        mock_service.get_position.return_value = mock_position

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/BRK.A")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["symbol"] == "BRK.A"

    # GET /position/{symbol}/greeks (get_position_greeks) endpoint tests
    @pytest.mark.asyncio
    async def test_get_position_greeks_success(self, client):
        """Test successful position Greeks retrieval."""
        mock_service = AsyncMock(spec=TradingService)
        mock_greeks = {
            "symbol": "AAPL_210618C00130000",
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "implied_volatility": 0.25
        }
        mock_service.get_position_greeks.return_value = mock_greeks

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/AAPL_210618C00130000/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["symbol"] == "AAPL_210618C00130000"
        assert data["delta"] == 0.65
        assert data["gamma"] == 0.03
        assert data["theta"] == -0.02
        assert data["vega"] == 0.15
        assert data["rho"] == 0.08
        assert data["implied_volatility"] == 0.25

        mock_service.get_position_greeks.assert_called_once_with("AAPL_210618C00130000")

    @pytest.mark.asyncio
    async def test_get_position_greeks_stock_position(self, client):
        """Test position Greeks for stock position (should handle gracefully)."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_position_greeks.side_effect = ValidationError("Greeks not available for stock positions")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/AAPL/greeks")

        # Global exception handler should convert ValidationError to 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_position_greeks_not_found(self, client):
        """Test position Greeks for non-existent position."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_position_greeks.side_effect = NotFoundError("Position not found")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/NONEXISTENT/greeks")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # GET /greeks (get_portfolio_greeks) endpoint tests
    @pytest.mark.asyncio
    async def test_get_portfolio_greeks_success(self, client):
        """Test successful portfolio Greeks aggregation."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio_greeks = {
            "total_delta": 150.0,
            "total_gamma": 12.5,
            "total_theta": -8.7,
            "total_vega": 45.2,
            "total_rho": 23.8,
            "weighted_iv": 0.28,
            "positions": [
                {
                    "symbol": "AAPL_210618C00130000",
                    "quantity": 10,
                    "delta": 0.65,
                    "gamma": 0.03,
                    "theta": -0.02,
                    "vega": 0.15,
                    "rho": 0.08
                }
            ]
        }
        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["total_delta"] == 150.0
        assert data["total_gamma"] == 12.5
        assert data["total_theta"] == -8.7
        assert data["total_vega"] == 45.2
        assert data["total_rho"] == 23.8
        assert data["weighted_iv"] == 0.28
        assert len(data["positions"]) == 1

        mock_service.get_portfolio_greeks.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_greeks_no_options(self, client):
        """Test portfolio Greeks when no options positions exist."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio_greeks = {
            "total_delta": 0.0,
            "total_gamma": 0.0,
            "total_theta": 0.0,
            "total_vega": 0.0,
            "total_rho": 0.0,
            "weighted_iv": 0.0,
            "positions": []
        }
        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["total_delta"] == 0.0
        assert data["positions"] == []

    # GET /strategies (get_portfolio_strategies) endpoint tests
    @pytest.mark.asyncio
    async def test_get_portfolio_strategies_success(self, client):
        """Test successful portfolio strategies analysis."""
        mock_service = AsyncMock(spec=TradingService)
        mock_strategies = {
            "recognized_strategies": [
                {
                    "strategy_type": "covered_call",
                    "positions": ["AAPL", "AAPL_210618C00160000"],
                    "profit_target": 500.0,
                    "risk_level": "medium",
                    "description": "Covered call on AAPL shares"
                }
            ],
            "unmatched_positions": ["GOOGL"],
            "risk_metrics": {
                "portfolio_beta": 1.2,
                "max_loss": -5000.0,
                "max_gain": 2000.0
            },
            "recommendations": [
                "Consider closing AAPL covered call before expiration"
            ]
        }
        mock_service.get_portfolio_strategies.return_value = mock_strategies

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/strategies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "recognized_strategies" in data
        assert "unmatched_positions" in data
        assert "risk_metrics" in data
        assert "recommendations" in data
        
        assert len(data["recognized_strategies"]) == 1
        assert data["recognized_strategies"][0]["strategy_type"] == "covered_call"
        assert "AAPL" in data["recognized_strategies"][0]["positions"]
        assert data["unmatched_positions"] == ["GOOGL"]

        mock_service.get_portfolio_strategies.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_strategies_no_strategies(self, client):
        """Test portfolio strategies when no strategies are recognized."""
        mock_service = AsyncMock(spec=TradingService)
        mock_strategies = {
            "recognized_strategies": [],
            "unmatched_positions": ["AAPL", "GOOGL", "MSFT"],
            "risk_metrics": {
                "portfolio_beta": 1.0,
                "max_loss": -10000.0,
                "max_gain": 5000.0
            },
            "recommendations": [
                "Consider implementing covered call strategies on large positions"
            ]
        }
        mock_service.get_portfolio_strategies.return_value = mock_strategies

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/strategies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["recognized_strategies"] == []
        assert len(data["unmatched_positions"]) == 3

    @pytest.mark.asyncio
    async def test_get_portfolio_strategies_service_error(self, client):
        """Test portfolio strategies when service raises error."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_portfolio_strategies.side_effect = RuntimeError("Analysis error")

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/strategies")

        # Global exception handler should handle this
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Edge cases and validation tests
    @pytest.mark.asyncio
    async def test_portfolio_endpoints_with_large_numbers(self, client):
        """Test portfolio endpoints handle large numbers correctly."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio = Portfolio(
            cash_balance=1000000000.0,  # 1 billion
            positions=[
                Position(
                    symbol="BRK.A",
                    quantity=1,
                    average_price=400000.0,
                    current_price=405000.0,
                    market_value=405000.0,
                    unrealized_pnl=5000.0,
                    realized_pnl=0.0
                )
            ],
            market_value=405000.0,
            total_value=1000405000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["cash_balance"] == 1000000000.0
        assert data["total_value"] == 1000405000.0

    @pytest.mark.asyncio
    async def test_portfolio_endpoints_with_zero_values(self, client):
        """Test portfolio endpoints handle zero values correctly."""
        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio = Portfolio(
            cash_balance=0.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=0,
                    average_price=0.0,
                    current_price=155.0,
                    market_value=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0
                )
            ],
            market_value=0.0,
            total_value=0.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["cash_balance"] == 0.0
        assert data["total_value"] == 0.0
        assert data["positions"][0]["quantity"] == 0

    @pytest.mark.asyncio
    async def test_position_symbol_url_encoding(self, client):
        """Test position endpoint handles URL-encoded symbols."""
        mock_service = AsyncMock(spec=TradingService)
        mock_position = Position(
            symbol="BRK.B",
            quantity=100,
            average_price=250.0,
            current_price=255.0,
            market_value=25500.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0
        )
        mock_service.get_position.return_value = mock_position

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                # Test with URL-encoded dot (though FastAPI should decode automatically)
                response = await ac.get("/api/v1/portfolio/position/BRK%2EB")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["symbol"] == "BRK.B"

    @pytest.mark.asyncio
    async def test_portfolio_dependency_injection(self, client):
        """Test that dependency injection works correctly for all endpoints."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_portfolio.return_value = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )

        # Test that the dependency is called for each endpoint
        with patch('app.core.dependencies.get_trading_service', return_value=mock_service) as mock_dep:
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                await ac.get("/api/v1/portfolio/")

        mock_dep.assert_called_once()

    @pytest.mark.asyncio
    async def test_portfolio_endpoints_response_structure(self, client):
        """Test that portfolio endpoints return properly structured responses."""
        mock_service = AsyncMock(spec=TradingService)
        
        # Test portfolio response structure
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            market_value=0.0,
            total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify required fields are present
        required_fields = ["cash_balance", "positions", "market_value", "total_value"]
        for field in required_fields:
            assert field in data