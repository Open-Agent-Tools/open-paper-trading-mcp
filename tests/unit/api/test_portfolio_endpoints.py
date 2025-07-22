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

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService


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
                    realized_pnl=0.0,
                )
            ],
            market_value=15500.0,
            total_value=25500.0,
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            position_count=3,
        )
        mock_service.get_portfolio_summary.return_value = mock_summary

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            position_count=2,
        )
        mock_service.get_portfolio_summary.return_value = mock_summary

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                realized_pnl=0.0,
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                average_price=2000.0,
                current_price=2050.0,
                market_value=102500.0,
                unrealized_pnl=2500.0,
                realized_pnl=100.0,
            ),
        ]
        mock_service.get_positions.return_value = mock_positions

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            realized_pnl=0.0,
        )
        mock_service.get_position.return_value = mock_position

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            realized_pnl=0.0,
        )
        mock_service.get_position.return_value = mock_position

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            "implied_volatility": 0.25,
        }
        mock_service.get_position_greeks.return_value = mock_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/portfolio/position/AAPL_210618C00130000/greeks"
                )

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
        mock_service.get_position_greeks.side_effect = ValidationError(
            "Greeks not available for stock positions"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/AAPL/greeks")

        # Global exception handler should convert ValidationError to 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_position_greeks_not_found(self, client):
        """Test position Greeks for non-existent position."""
        mock_service = AsyncMock(spec=TradingService)
        mock_service.get_position_greeks.side_effect = NotFoundError(
            "Position not found"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                    "rho": 0.08,
                }
            ],
        }
        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            "positions": [],
        }
        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                    "description": "Covered call on AAPL shares",
                }
            ],
            "unmatched_positions": ["GOOGL"],
            "risk_metrics": {
                "portfolio_beta": 1.2,
                "max_loss": -5000.0,
                "max_gain": 2000.0,
            },
            "recommendations": ["Consider closing AAPL covered call before expiration"],
        }
        mock_service.get_portfolio_strategies.return_value = mock_strategies

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                "max_gain": 5000.0,
            },
            "recommendations": [
                "Consider implementing covered call strategies on large positions"
            ],
        }
        mock_service.get_portfolio_strategies.return_value = mock_strategies

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
        mock_service.get_portfolio_strategies.side_effect = RuntimeError(
            "Analysis error"
        )

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                    realized_pnl=0.0,
                )
            ],
            market_value=405000.0,
            total_value=1000405000.0,
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
                    realized_pnl=0.0,
                )
            ],
            market_value=0.0,
            total_value=0.0,
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
            realized_pnl=0.0,
        )
        mock_service.get_position.return_value = mock_position

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
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
        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ) as mock_dep:
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                await ac.get("/api/v1/portfolio/")

        mock_dep.assert_called_once()

    @pytest.mark.asyncio
    async def test_portfolio_endpoints_response_structure(self, client):
        """Test that portfolio endpoints return properly structured responses."""
        mock_service = AsyncMock(spec=TradingService)

        # Test portfolio response structure
        mock_portfolio = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required fields are present
        required_fields = ["cash_balance", "positions", "market_value", "total_value"]
        for field in required_fields:
            assert field in data

    # Enhanced comprehensive position testing
    @pytest.mark.asyncio
    async def test_portfolio_with_mixed_asset_types(self, client):
        """Test portfolio containing stocks, options, and other asset types."""
        mock_service = AsyncMock(spec=TradingService)

        mixed_portfolio = Portfolio(
            cash_balance=50000.0,
            positions=[
                # Stock positions
                Position(
                    symbol="AAPL",
                    quantity=100,
                    average_price=150.0,
                    current_price=155.0,
                    market_value=15500.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                ),
                Position(
                    symbol="GOOGL",
                    quantity=10,
                    average_price=2500.0,
                    current_price=2600.0,
                    market_value=26000.0,
                    unrealized_pnl=1000.0,
                    realized_pnl=250.0,
                ),
                # Options positions
                Position(
                    symbol="AAPL_230616C00160000",
                    quantity=5,
                    average_price=3.50,
                    current_price=4.25,
                    market_value=2125.0,
                    unrealized_pnl=375.0,
                    realized_pnl=0.0,
                ),
                Position(
                    symbol="SPY_230616P00400000",
                    quantity=-2,  # Short position
                    average_price=2.75,
                    current_price=1.80,
                    market_value=-360.0,
                    unrealized_pnl=190.0,  # Profit on short
                    realized_pnl=50.0,
                ),
                # ETF position
                Position(
                    symbol="QQQ",
                    quantity=50,
                    average_price=300.0,
                    current_price=310.0,
                    market_value=15500.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                ),
            ],
            market_value=58765.0,
            total_value=108765.0,
        )
        mock_service.get_portfolio.return_value = mixed_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["positions"]) == 5
        assert data["market_value"] == 58765.0
        assert data["total_value"] == 108765.0

        # Verify position types
        symbols = [pos["symbol"] for pos in data["positions"]]
        assert "AAPL" in symbols  # Stock
        assert "AAPL_230616C00160000" in symbols  # Call option
        assert "SPY_230616P00400000" in symbols  # Put option
        assert "QQQ" in symbols  # ETF

        # Verify short position handling
        short_position = next(pos for pos in data["positions"] if pos["quantity"] < 0)
        assert short_position["symbol"] == "SPY_230616P00400000"
        assert short_position["quantity"] == -2

    @pytest.mark.asyncio
    async def test_portfolio_performance_metrics(self, client):
        """Test portfolio summary with detailed performance metrics."""
        mock_service = AsyncMock(spec=TradingService)

        comprehensive_summary = PortfolioSummary(
            cash_balance=25000.0,
            market_value=75000.0,
            total_value=100000.0,
            day_change=1250.0,
            day_change_percent=1.27,
            total_gain_loss=8500.0,
            total_gain_loss_percent=9.28,
            position_count=8,
        )
        mock_service.get_portfolio_summary.return_value = comprehensive_summary

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify comprehensive metrics
        assert data["total_gain_loss"] == 8500.0
        assert data["total_gain_loss_percent"] == 9.28
        assert data["day_change"] == 1250.0
        assert data["day_change_percent"] == 1.27
        assert data["position_count"] == 8

    @pytest.mark.asyncio
    async def test_position_risk_analysis(self, client):
        """Test individual position with risk analysis data."""
        mock_service = AsyncMock(spec=TradingService)

        # Create position with extended risk metrics
        risk_position = Position(
            symbol="TSLA",
            quantity=50,
            average_price=800.0,
            current_price=750.0,
            market_value=37500.0,
            unrealized_pnl=-2500.0,
            realized_pnl=1000.0,
        )
        mock_service.get_position.return_value = risk_position

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/TSLA")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "TSLA"
        assert data["quantity"] == 50
        assert data["unrealized_pnl"] == -2500.0  # Negative (loss)
        assert data["realized_pnl"] == 1000.0  # Positive (profit)

    @pytest.mark.asyncio
    async def test_portfolio_greeks_comprehensive_analysis(self, client):
        """Test comprehensive portfolio Greeks analysis with multiple strategies."""
        mock_service = AsyncMock(spec=TradingService)

        comprehensive_greeks = {
            "total_delta": 125.5,
            "total_gamma": 18.7,
            "total_theta": -45.2,
            "total_vega": 78.3,
            "total_rho": 15.9,
            "weighted_iv": 0.32,
            "net_delta_exposure": 0.15,  # 15% of portfolio
            "positions": [
                {
                    "symbol": "AAPL_230616C00150000",
                    "quantity": 10,
                    "delta": 0.65,
                    "gamma": 0.03,
                    "theta": -0.08,
                    "vega": 0.18,
                    "rho": 0.12,
                    "position_delta": 6.5,
                    "position_theta": -0.8,
                    "days_to_expiration": 30,
                    "moneyness": "ITM",
                },
                {
                    "symbol": "SPY_230616P00400000",
                    "quantity": -5,  # Short puts
                    "delta": -0.35,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "rho": -0.08,
                    "position_delta": 1.75,  # Short delta becomes positive
                    "position_theta": 0.25,  # Short theta becomes positive
                    "days_to_expiration": 15,
                    "moneyness": "OTM",
                },
                {
                    "symbol": "QQQ_230616C00350000",
                    "quantity": 20,
                    "delta": 0.45,
                    "gamma": 0.04,
                    "theta": -0.06,
                    "vega": 0.20,
                    "rho": 0.10,
                    "position_delta": 9.0,
                    "position_theta": -1.2,
                    "days_to_expiration": 45,
                    "moneyness": "ATM",
                },
            ],
            "risk_analysis": {
                "delta_neutral": False,
                "gamma_risk": "moderate",
                "theta_decay_daily": -45.2,
                "vega_risk": "high",
                "concentration_risk": [
                    {"underlying": "AAPL", "exposure_percent": 35.0},
                    {"underlying": "SPY", "exposure_percent": 25.0},
                    {"underlying": "QQQ", "exposure_percent": 40.0},
                ],
            },
            "recommendations": [
                "Portfolio has positive delta bias - consider hedging for market decline",
                "High vega exposure - consider IV hedging strategies",
                "Theta collection strategy working well with short puts",
                "Monitor gamma risk as expiration approaches",
            ],
        }
        mock_service.get_portfolio_greeks.return_value = comprehensive_greeks

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify comprehensive Greeks data
        assert data["total_delta"] == 125.5
        assert data["total_theta"] == -45.2
        assert data["net_delta_exposure"] == 0.15
        assert len(data["positions"]) == 3

        # Verify risk analysis
        assert "risk_analysis" in data
        assert data["risk_analysis"]["delta_neutral"] is False
        assert data["risk_analysis"]["gamma_risk"] == "moderate"
        assert len(data["risk_analysis"]["concentration_risk"]) == 3

        # Verify recommendations
        assert "recommendations" in data
        assert len(data["recommendations"]) == 4

    @pytest.mark.asyncio
    async def test_portfolio_strategies_complex_analysis(self, client):
        """Test complex portfolio strategies with advanced analysis."""
        mock_service = AsyncMock(spec=TradingService)

        complex_strategies = {
            "recognized_strategies": [
                {
                    "strategy_id": "strat_001",
                    "strategy_type": "iron_condor",
                    "strategy_name": "SPY Iron Condor",
                    "underlying": "SPY",
                    "positions": [
                        {
                            "symbol": "SPY_230616P00390000",
                            "quantity": -1,
                            "leg": "short_put",
                        },
                        {
                            "symbol": "SPY_230616P00385000",
                            "quantity": 1,
                            "leg": "long_put",
                        },
                        {
                            "symbol": "SPY_230616C00415000",
                            "quantity": 1,
                            "leg": "long_call",
                        },
                        {
                            "symbol": "SPY_230616C00420000",
                            "quantity": -1,
                            "leg": "short_call",
                        },
                    ],
                    "entry_date": "2023-05-15",
                    "expiration_date": "2023-06-16",
                    "days_to_expiration": 32,
                    "max_profit": 200.0,
                    "max_loss": -300.0,
                    "breakeven_points": [388.0, 417.0],
                    "current_pnl": 85.0,
                    "profit_probability": 0.68,
                    "risk_reward_ratio": 0.67,
                    "theta_decay_daily": 2.5,
                    "delta_exposure": 0.05,
                    "maintenance_margin": 500.0,
                    "assignment_risk": 0.15,
                    "early_close_recommendation": "hold",
                },
                {
                    "strategy_id": "strat_002",
                    "strategy_type": "covered_call",
                    "strategy_name": "AAPL Covered Call",
                    "underlying": "AAPL",
                    "positions": [
                        {"symbol": "AAPL", "quantity": 100, "leg": "long_stock"},
                        {
                            "symbol": "AAPL_230616C00160000",
                            "quantity": -1,
                            "leg": "short_call",
                        },
                    ],
                    "entry_date": "2023-04-20",
                    "expiration_date": "2023-06-16",
                    "days_to_expiration": 32,
                    "max_profit": 750.0,
                    "max_loss": -14250.0,  # Stock cost minus premium
                    "breakeven_point": 152.5,
                    "current_pnl": 425.0,
                    "annualized_return": 0.18,  # 18% annualized
                    "delta_exposure": 0.35,  # Reduced delta from short call
                    "assignment_probability": 0.25,
                    "dividend_capture": True,
                    "next_dividend_date": "2023-05-11",
                    "early_close_recommendation": "hold_to_expiration",
                },
                {
                    "strategy_id": "strat_003",
                    "strategy_type": "long_straddle",
                    "strategy_name": "NVDA Earnings Straddle",
                    "underlying": "NVDA",
                    "positions": [
                        {
                            "symbol": "NVDA_230616C00400000",
                            "quantity": 2,
                            "leg": "long_call",
                        },
                        {
                            "symbol": "NVDA_230616P00400000",
                            "quantity": 2,
                            "leg": "long_put",
                        },
                    ],
                    "entry_date": "2023-05-20",
                    "expiration_date": "2023-06-16",
                    "days_to_expiration": 27,
                    "max_profit": "unlimited",
                    "max_loss": -1200.0,
                    "breakeven_points": [394.0, 406.0],
                    "current_pnl": -150.0,
                    "implied_move": 0.08,  # 8% implied move
                    "actual_move_needed": 0.06,  # 6% move needed for profit
                    "earnings_date": "2023-05-24",
                    "volatility_crush_risk": 0.75,
                    "time_decay_risk": "high",
                    "early_close_recommendation": "monitor_closely",
                },
            ],
            "unmatched_positions": [
                {
                    "symbol": "MSFT",
                    "quantity": 75,
                    "market_value": 23250.0,
                    "recommendation": "Consider implementing covered call strategy",
                },
                {
                    "symbol": "GOOGL",
                    "quantity": 15,
                    "market_value": 39000.0,
                    "recommendation": "Position size suitable for options strategies",
                },
            ],
            "portfolio_level_metrics": {
                "total_strategies": 3,
                "total_strategy_value": 89750.0,
                "strategy_allocation_percent": 0.72,
                "net_theta": 8.5,  # Positive theta collection
                "net_delta": 45.0,
                "net_vega": -25.0,  # Short vega
                "correlation_analysis": {
                    "inter_strategy_correlation": 0.15,
                    "sector_concentration": {
                        "technology": 0.65,
                        "etf": 0.35,
                    },
                },
                "margin_utilization": 0.45,
                "buying_power_reduction": 35000.0,
            },
            "risk_metrics": {
                "portfolio_var_1day": -2850.0,
                "portfolio_var_1week": -6200.0,
                "max_portfolio_loss": -45000.0,
                "stress_test_scenarios": [
                    {
                        "scenario": "Market crash -20%",
                        "estimated_loss": -18500.0,
                        "strategy_performance": [
                            {
                                "strategy_id": "strat_001",
                                "impact": 150.0,
                            },  # Benefits from low vol
                            {
                                "strategy_id": "strat_002",
                                "impact": -15000.0,
                            },  # Stock loss
                            {
                                "strategy_id": "strat_003",
                                "impact": 800.0,
                            },  # Volatility expansion
                        ],
                    },
                    {
                        "scenario": "Volatility spike +50%",
                        "estimated_gain": 2200.0,
                        "strategy_performance": [
                            {"strategy_id": "strat_001", "impact": -100.0},
                            {"strategy_id": "strat_002", "impact": 50.0},
                            {"strategy_id": "strat_003", "impact": 2250.0},
                        ],
                    },
                ],
                "liquidity_analysis": {
                    "highly_liquid_percent": 0.85,
                    "moderately_liquid_percent": 0.15,
                    "illiquid_percent": 0.0,
                },
            },
            "recommendations": [
                "Iron Condor performing well - theta collection strategy working",
                "Covered call approaching assignment - monitor for roll opportunity",
                "NVDA straddle experiencing time decay - consider early exit before earnings",
                "Portfolio delta positive - consider market hedging for downside protection",
                "Implement additional theta collection strategies on unmatched positions",
                "Consider reducing technology sector concentration",
            ],
            "alerts": [
                {
                    "type": "assignment_risk",
                    "strategy_id": "strat_002",
                    "message": "AAPL covered call assignment probability increased to 25%",
                    "severity": "medium",
                    "action_required": "Monitor for early assignment",
                },
                {
                    "type": "expiration_notice",
                    "strategy_id": "strat_003",
                    "message": "NVDA straddle expires in 27 days - manage time decay risk",
                    "severity": "high",
                    "action_required": "Consider exit strategy",
                },
                {
                    "type": "earnings_announcement",
                    "strategy_id": "strat_003",
                    "message": "NVDA earnings announcement in 4 days",
                    "severity": "critical",
                    "action_required": "Prepare for volatility crush",
                },
            ],
        }
        mock_service.get_portfolio_strategies.return_value = complex_strategies

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/strategies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify strategy analysis
        assert len(data["recognized_strategies"]) == 3
        assert len(data["unmatched_positions"]) == 2

        # Verify strategy details
        iron_condor = next(
            s
            for s in data["recognized_strategies"]
            if s["strategy_type"] == "iron_condor"
        )
        assert iron_condor["profit_probability"] == 0.68
        assert iron_condor["max_profit"] == 200.0
        assert len(iron_condor["positions"]) == 4

        covered_call = next(
            s
            for s in data["recognized_strategies"]
            if s["strategy_type"] == "covered_call"
        )
        assert covered_call["annualized_return"] == 0.18
        assert covered_call["assignment_probability"] == 0.25

        # Verify portfolio-level metrics
        portfolio_metrics = data["portfolio_level_metrics"]
        assert portfolio_metrics["total_strategies"] == 3
        assert portfolio_metrics["net_theta"] == 8.5
        assert "correlation_analysis" in portfolio_metrics

        # Verify risk analysis
        risk_metrics = data["risk_metrics"]
        assert "stress_test_scenarios" in risk_metrics
        assert len(risk_metrics["stress_test_scenarios"]) == 2
        assert "liquidity_analysis" in risk_metrics

        # Verify alerts
        assert "alerts" in data
        assert len(data["alerts"]) == 3
        critical_alert = next(a for a in data["alerts"] if a["severity"] == "critical")
        assert "earnings" in critical_alert["message"]

    @pytest.mark.asyncio
    async def test_portfolio_concurrent_access(self, client):
        """Test portfolio endpoints under concurrent access."""
        import asyncio

        mock_service = AsyncMock(spec=TradingService)
        mock_portfolio = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio

        async def make_portfolio_request():
            with patch(
                "app.core.dependencies.get_trading_service", return_value=mock_service
            ):
                async with AsyncClient(app=client.app, base_url="http://test") as ac:
                    return await ac.get("/api/v1/portfolio/")

        # Make 10 concurrent requests
        tasks = [make_portfolio_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_value"] == 10000.0

    @pytest.mark.asyncio
    async def test_position_fractional_shares(self, client):
        """Test positions with fractional shares."""
        mock_service = AsyncMock(spec=TradingService)

        fractional_position = Position(
            symbol="AAPL",
            quantity=10.5,  # Fractional shares
            average_price=150.75,
            current_price=155.25,
            market_value=1629.63,
            unrealized_pnl=47.25,
            realized_pnl=0.0,
        )
        mock_service.get_position.return_value = fractional_position

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/position/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["quantity"] == 10.5
        assert data["average_price"] == 150.75
        assert data["market_value"] == 1629.63

    @pytest.mark.asyncio
    async def test_portfolio_currency_handling(self, client):
        """Test portfolio with multiple currencies."""
        mock_service = AsyncMock(spec=TradingService)

        multi_currency_portfolio = Portfolio(
            cash_balance=50000.0,  # USD
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    average_price=150.0,
                    current_price=155.0,
                    market_value=15500.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                ),
                Position(
                    symbol="ASML.AS",  # Amsterdam (EUR)
                    quantity=25,
                    average_price=600.0,
                    current_price=620.0,
                    market_value=15500.0,  # Converted to USD
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                ),
            ],
            market_value=31000.0,
            total_value=81000.0,
        )
        mock_service.get_portfolio.return_value = multi_currency_portfolio

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["positions"]) == 2
        assert data["total_value"] == 81000.0

        # Verify international symbols are handled
        symbols = [pos["symbol"] for pos in data["positions"]]
        assert "ASML.AS" in symbols

    @pytest.mark.asyncio
    async def test_portfolio_data_consistency(self, client):
        """Test portfolio data consistency across different endpoints."""
        mock_service = AsyncMock(spec=TradingService)

        # Setup consistent data across endpoints
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                average_price=150.0,
                current_price=155.0,
                market_value=15500.0,
                unrealized_pnl=500.0,
                realized_pnl=100.0,
            )
        ]

        portfolio = Portfolio(
            cash_balance=25000.0,
            positions=positions,
            market_value=15500.0,
            total_value=40500.0,
        )

        summary = PortfolioSummary(
            cash_balance=25000.0,
            market_value=15500.0,
            total_value=40500.0,
            day_change=250.0,
            day_change_percent=0.62,
            total_gain_loss=600.0,  # 500 unrealized + 100 realized
            total_gain_loss_percent=1.5,
            position_count=1,
        )

        mock_service.get_portfolio.return_value = portfolio
        mock_service.get_portfolio_summary.return_value = summary
        mock_service.get_positions.return_value = positions
        mock_service.get_position.return_value = positions[0]

        with patch(
            "app.core.dependencies.get_trading_service", return_value=mock_service
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                # Test consistency across endpoints
                portfolio_response = await ac.get("/api/v1/portfolio/")
                summary_response = await ac.get("/api/v1/portfolio/summary")
                positions_response = await ac.get("/api/v1/portfolio/positions")
                position_response = await ac.get("/api/v1/portfolio/position/AAPL")

        # Verify all responses are successful
        assert all(
            r.status_code == status.HTTP_200_OK
            for r in [
                portfolio_response,
                summary_response,
                positions_response,
                position_response,
            ]
        )

        # Verify data consistency
        portfolio_data = portfolio_response.json()
        summary_data = summary_response.json()
        positions_data = positions_response.json()
        position_data = position_response.json()

        # Cash balance should be consistent
        assert portfolio_data["cash_balance"] == summary_data["cash_balance"] == 25000.0

        # Market value should be consistent
        assert portfolio_data["market_value"] == summary_data["market_value"] == 15500.0

        # Total value should be consistent
        assert portfolio_data["total_value"] == summary_data["total_value"] == 40500.0

        # Position count should match
        assert (
            len(portfolio_data["positions"])
            == len(positions_data)
            == summary_data["position_count"]
            == 1
        )

        # Individual position data should match
        portfolio_position = portfolio_data["positions"][0]
        positions_position = positions_data[0]

        for field in ["symbol", "quantity", "market_value", "unrealized_pnl"]:
            assert (
                portfolio_position[field]
                == positions_position[field]
                == position_data[field]
            )
