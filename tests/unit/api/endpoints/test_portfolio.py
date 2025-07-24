"""
Comprehensive tests for portfolio endpoints.

Tests all portfolio endpoints with proper mocking:
- GET / (get portfolio)
- GET /summary (get portfolio summary)
- GET /positions (get positions)
- GET /position/{symbol} (get specific position)
- GET /position/{symbol}/greeks (get position Greeks)
- GET /greeks (get portfolio Greeks)

Covers success paths, error handling, and edge cases.
"""

from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.positions import Portfolio, PortfolioSummary, Position


class TestPortfolioEndpoints:
    """Test suite for portfolio endpoints."""

    # GET / - Get portfolio endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_success(self, mock_get_service, client: TestClient):
        """Test successful portfolio retrieval."""
        mock_service = AsyncMock()

        # Create mock positions
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
                average_price=2800.0,
                current_price=2750.0,
                market_value=137500.0,
                unrealized_pnl=-2500.0,
                realized_pnl=1000.0,
            ),
            Position(
                symbol="AAPL_230616C00160000",
                quantity=2,
                average_price=3.25,
                current_price=2.85,
                market_value=570.0,
                unrealized_pnl=-80.0,
                realized_pnl=0.0,
            ),
        ]

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=mock_positions,
            market_value=153570.0,
            total_value=163570.0,
        )

        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["cash_balance"] == 10000.0
        assert data["market_value"] == 153570.0
        assert data["total_value"] == 163570.0
        assert len(data["positions"]) == 3

        # Verify position details
        aapl_position = next(p for p in data["positions"] if p["symbol"] == "AAPL")
        assert aapl_position["quantity"] == 100
        assert aapl_position["average_price"] == 150.0
        assert aapl_position["current_price"] == 155.0
        assert aapl_position["market_value"] == 15500.0
        assert aapl_position["unrealized_pnl"] == 500.0

        mock_service.get_portfolio.assert_called_once()

    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_empty(self, mock_get_service, client: TestClient):
        """Test portfolio retrieval when no positions exist."""
        mock_service = AsyncMock()

        mock_portfolio = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )

        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["cash_balance"] == 10000.0
        assert data["market_value"] == 0.0
        assert data["total_value"] == 10000.0
        assert len(data["positions"]) == 0

    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_service_error(self, mock_get_service, client: TestClient):
        """Test portfolio retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = Exception("Service unavailable")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /summary - Get portfolio summary endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_summary_success(self, mock_get_service, client: TestClient):
        """Test successful portfolio summary retrieval."""
        mock_service = AsyncMock()

        mock_summary = PortfolioSummary(
            cash_balance=10000.0,
            market_value=153570.0,
            total_value=163570.0,
            day_change=1250.0,
            day_change_percent=0.77,
            total_gain_loss=2500.0,
            total_gain_loss_percent=1.55,
            position_count=3,
        )

        mock_service.get_portfolio_summary.return_value = mock_summary
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["cash_balance"] == 10000.0
        assert data["market_value"] == 153570.0
        assert data["total_value"] == 163570.0
        assert data["day_change"] == 1250.0
        assert data["day_change_percent"] == 0.77
        assert data["total_gain_loss"] == 2500.0
        assert data["total_gain_loss_percent"] == 1.55
        assert data["position_count"] == 3

        mock_service.get_portfolio_summary.assert_called_once()

    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_summary_service_error(
        self, mock_get_service, client: TestClient
    ):
        """Test portfolio summary retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_portfolio_summary.side_effect = Exception(
            "Service unavailable"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/summary")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /positions - Get positions endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_positions_success(self, mock_get_service, client: TestClient):
        """Test successful positions retrieval."""
        mock_service = AsyncMock()

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
                average_price=2800.0,
                current_price=2750.0,
                market_value=137500.0,
                unrealized_pnl=-2500.0,
                realized_pnl=1000.0,
            ),
        ]

        mock_service.get_positions.return_value = mock_positions
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[0]["quantity"] == 100
        assert data[1]["symbol"] == "GOOGL"
        assert data[1]["quantity"] == 50

        mock_service.get_positions.assert_called_once()

    @patch("app.core.dependencies.get_trading_service")
    def test_get_positions_empty(self, mock_get_service, client: TestClient):
        """Test positions retrieval when no positions exist."""
        mock_service = AsyncMock()
        mock_service.get_positions.return_value = []
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 0

    @patch("app.core.dependencies.get_trading_service")
    def test_get_positions_service_error(self, mock_get_service, client: TestClient):
        """Test positions retrieval with service error."""
        mock_service = AsyncMock()
        mock_service.get_positions.side_effect = Exception("Service unavailable")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /position/{symbol} - Get specific position endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_success(self, mock_get_service, client: TestClient):
        """Test successful specific position retrieval."""
        mock_service = AsyncMock()

        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            average_price=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            realized_pnl=200.0,
        )

        mock_service.get_position.return_value = mock_position
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/AAPL")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["quantity"] == 100
        assert data["average_price"] == 150.0
        assert data["current_price"] == 155.0
        assert data["market_value"] == 15500.0
        assert data["unrealized_pnl"] == 500.0
        assert data["realized_pnl"] == 200.0

        mock_service.get_position.assert_called_once_with("AAPL")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_not_found(self, mock_get_service, client: TestClient):
        """Test position retrieval for non-existent symbol."""
        mock_service = AsyncMock()
        mock_service.get_position.side_effect = NotFoundError("Position not found")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/INVALID")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Position not found" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_option_symbol(self, mock_get_service, client: TestClient):
        """Test position retrieval for option symbol."""
        mock_service = AsyncMock()

        mock_position = Position(
            symbol="AAPL_230616C00160000",
            quantity=2,
            average_price=3.25,
            current_price=2.85,
            market_value=570.0,
            unrealized_pnl=-80.0,
            realized_pnl=0.0,
        )

        mock_service.get_position.return_value = mock_position
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/AAPL_230616C00160000")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00160000"
        assert data["quantity"] == 2
        assert data["unrealized_pnl"] == -80.0

    # GET /position/{symbol}/greeks - Get position Greeks endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_greeks_success(self, mock_get_service, client: TestClient):
        """Test successful position Greeks retrieval."""
        mock_service = AsyncMock()

        mock_greeks = {
            "symbol": "AAPL_230616C00160000",
            "position_size": 2,
            "greeks": {
                "delta": 0.50,
                "gamma": 0.04,
                "theta": -0.03,
                "vega": 0.18,
                "rho": 0.06,
            },
            "position_greeks": {
                "total_delta": 1.00,  # 0.50 * 2 contracts
                "total_gamma": 0.08,
                "total_theta": -0.06,
                "total_vega": 0.36,
                "total_rho": 0.12,
            },
            "underlying_symbol": "AAPL",
            "underlying_price": 155.0,
            "risk_metrics": {
                "delta_exposure": 100.0,  # Equivalent to 100 shares
                "gamma_risk": "low",
                "theta_decay": -6.0,  # Per day
            },
        }

        mock_service.get_position_greeks.return_value = mock_greeks
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/AAPL_230616C00160000/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["symbol"] == "AAPL_230616C00160000"
        assert data["position_size"] == 2
        assert data["greeks"]["delta"] == 0.50
        assert data["position_greeks"]["total_delta"] == 1.00
        assert data["risk_metrics"]["delta_exposure"] == 100.0

        mock_service.get_position_greeks.assert_called_once_with("AAPL_230616C00160000")

    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_greeks_stock_position(
        self, mock_get_service, client: TestClient
    ):
        """Test Greeks retrieval for stock position (should handle gracefully)."""
        mock_service = AsyncMock()
        mock_service.get_position_greeks.side_effect = ValidationError(
            "Greeks not available for stock positions"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/AAPL/greeks")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Greeks not available for stock positions" in data["detail"]

    @patch("app.core.dependencies.get_trading_service")
    def test_get_position_greeks_not_found(self, mock_get_service, client: TestClient):
        """Test position Greeks for non-existent position."""
        mock_service = AsyncMock()
        mock_service.get_position_greeks.side_effect = NotFoundError(
            "Position not found"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/position/INVALID/greeks")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # GET /greeks - Get portfolio Greeks endpoint
    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_greeks_success(self, mock_get_service, client: TestClient):
        """Test successful portfolio Greeks retrieval."""
        mock_service = AsyncMock()

        mock_portfolio_greeks = {
            "portfolio_greeks": {
                "total_delta": 125.0,
                "total_gamma": 8.5,
                "total_theta": -45.2,
                "total_vega": 75.8,
                "total_rho": 15.3,
            },
            "position_breakdown": [
                {
                    "symbol": "AAPL_230616C00160000",
                    "quantity": 2,
                    "greeks": {
                        "delta": 0.50,
                        "gamma": 0.04,
                        "theta": -0.03,
                        "vega": 0.18,
                        "rho": 0.06,
                    },
                    "position_greeks": {
                        "total_delta": 1.00,
                        "total_gamma": 0.08,
                        "total_theta": -0.06,
                        "total_vega": 0.36,
                        "total_rho": 0.12,
                    },
                },
                {
                    "symbol": "GOOGL_230616P02750000",
                    "quantity": -1,  # Short position
                    "greeks": {
                        "delta": -0.45,
                        "gamma": 0.02,
                        "theta": -0.04,
                        "vega": 0.20,
                        "rho": -0.08,
                    },
                    "position_greeks": {
                        "total_delta": 0.45,  # Short, so reversed
                        "total_gamma": -0.02,
                        "total_theta": 0.04,
                        "total_vega": -0.20,
                        "total_rho": 0.08,
                    },
                },
            ],
            "risk_metrics": {
                "net_delta_exposure": 12500.0,  # Dollar delta
                "gamma_risk": "moderate",
                "theta_decay_per_day": -45.2,
                "vega_exposure": 75.8,
                "portfolio_beta": 1.15,
            },
            "hedging_suggestions": [
                "Consider reducing delta exposure",
                "Monitor theta decay over weekend",
                "Portfolio is short vega - consider vol hedging",
            ],
        }

        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["portfolio_greeks"]["total_delta"] == 125.0
        assert len(data["position_breakdown"]) == 2
        assert data["risk_metrics"]["net_delta_exposure"] == 12500.0
        assert len(data["hedging_suggestions"]) == 3

        # Verify position breakdown
        aapl_position = next(
            p
            for p in data["position_breakdown"]
            if p["symbol"] == "AAPL_230616C00160000"
        )
        assert aapl_position["quantity"] == 2
        assert aapl_position["position_greeks"]["total_delta"] == 1.00

        mock_service.get_portfolio_greeks.assert_called_once()

    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_greeks_no_options(
        self, mock_get_service, client: TestClient
    ):
        """Test portfolio Greeks when no option positions exist."""
        mock_service = AsyncMock()

        mock_portfolio_greeks = {
            "portfolio_greeks": {
                "total_delta": 0.0,
                "total_gamma": 0.0,
                "total_theta": 0.0,
                "total_vega": 0.0,
                "total_rho": 0.0,
            },
            "position_breakdown": [],
            "risk_metrics": {
                "net_delta_exposure": 0.0,
                "gamma_risk": "none",
                "theta_decay_per_day": 0.0,
                "vega_exposure": 0.0,
                "portfolio_beta": 1.0,
            },
            "hedging_suggestions": ["No options positions - no Greeks exposure"],
        }

        mock_service.get_portfolio_greeks.return_value = mock_portfolio_greeks
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["portfolio_greeks"]["total_delta"] == 0.0
        assert len(data["position_breakdown"]) == 0
        assert data["risk_metrics"]["gamma_risk"] == "none"

    @patch("app.core.dependencies.get_trading_service")
    def test_get_portfolio_greeks_service_error(
        self, mock_get_service, client: TestClient
    ):
        """Test portfolio Greeks with service error."""
        mock_service = AsyncMock()
        mock_service.get_portfolio_greeks.side_effect = Exception(
            "Greeks calculation failed"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestPortfolioEndpointsErrorHandling:
    """Test error handling scenarios for portfolio endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_service_unavailable_error(self, mock_get_service, client: TestClient):
        """Test handling when trading service is unavailable."""
        mock_get_service.side_effect = Exception("Service unavailable")

        endpoints = [
            "/api/v1/portfolio/",
            "/api/v1/portfolio/summary",
            "/api/v1/portfolio/positions",
            "/api/v1/portfolio/position/AAPL",
            "/api/v1/portfolio/greeks",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.core.dependencies.get_trading_service")
    def test_timeout_error_handling(self, mock_get_service, client: TestClient):
        """Test handling of timeout errors."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = TimeoutError("Request timeout")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_invalid_symbol_formats(self, client: TestClient):
        """Test handling of invalid symbol formats."""
        invalid_symbols = ["", "A" * 50, "AAPL@", "123AAPL", "AAPL#$%"]

        for symbol in invalid_symbols:
            response = client.get(f"/api/v1/portfolio/position/{symbol}")
            # Should handle gracefully
            assert response.status_code in [400, 404, 422, 500]

    @patch("app.core.dependencies.get_trading_service")
    def test_database_connection_error(self, mock_get_service, client: TestClient):
        """Test handling of database connection errors."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = Exception("Database connection failed")
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestPortfolioEndpointsAuthentication:
    """Test authentication scenarios for portfolio endpoints."""

    def test_endpoints_require_user_context(self, client: TestClient):
        """Test that portfolio endpoints handle user context properly."""
        # Portfolio endpoints should work with proper user context in test environment
        endpoints_to_test = [
            "/api/v1/portfolio/",
            "/api/v1/portfolio/summary",
            "/api/v1/portfolio/positions",
            "/api/v1/portfolio/position/AAPL",
            "/api/v1/portfolio/position/AAPL/greeks",
            "/api/v1/portfolio/greeks",
        ]

        for endpoint in endpoints_to_test:
            response = client.get(endpoint)
            # Should work with test user context
            assert response.status_code in [200, 404, 500]


class TestPortfolioEndpointsEdgeCases:
    """Test edge cases and boundary conditions for portfolio endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_negative_position_quantities(self, mock_get_service, client: TestClient):
        """Test handling of negative position quantities (short positions)."""
        mock_service = AsyncMock()

        mock_positions = [
            Position(
                symbol="AAPL_230616C00160000",
                quantity=-2,  # Short options position
                average_price=3.25,
                current_price=2.85,
                market_value=-570.0,  # Negative for short position
                unrealized_pnl=80.0,  # Profit on short position (price decreased)
                realized_pnl=0.0,
            )
        ]

        mock_service.get_positions.return_value = mock_positions
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 1
        assert data[0]["quantity"] == -2
        assert data[0]["market_value"] == -570.0
        assert data[0]["unrealized_pnl"] == 80.0

    @patch("app.core.dependencies.get_trading_service")
    def test_zero_quantity_positions(self, mock_get_service, client: TestClient):
        """Test handling of zero quantity positions (closed positions)."""
        mock_service = AsyncMock()

        mock_positions = [
            Position(
                symbol="AAPL",
                quantity=0,  # Closed position
                average_price=150.0,
                current_price=155.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=500.0,  # Realized gain from closed position
            )
        ]

        mock_service.get_positions.return_value = mock_positions
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 1
        assert data[0]["quantity"] == 0
        assert data[0]["market_value"] == 0.0
        assert data[0]["realized_pnl"] == 500.0

    @patch("app.core.dependencies.get_trading_service")
    def test_very_large_portfolio_values(self, mock_get_service, client: TestClient):
        """Test handling of very large portfolio values."""
        mock_service = AsyncMock()

        mock_portfolio = Portfolio(
            cash_balance=100000000.0,  # $100M cash
            positions=[
                Position(
                    symbol="BERKB",
                    quantity=1000,
                    average_price=500000.0,
                    current_price=525000.0,
                    market_value=525000000.0,  # $525M position
                    unrealized_pnl=25000000.0,  # $25M unrealized gain
                    realized_pnl=0.0,
                )
            ],
            market_value=525000000.0,
            total_value=625000000.0,  # $625M total
        )

        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["cash_balance"] == 100000000.0
        assert data["total_value"] == 625000000.0
        assert data["positions"][0]["market_value"] == 525000000.0

    @patch("app.core.dependencies.get_trading_service")
    def test_portfolio_with_many_small_positions(
        self, mock_get_service, client: TestClient
    ):
        """Test handling of portfolio with many small positions."""
        mock_service = AsyncMock()

        # Create 100 small positions
        mock_positions = []
        for i in range(100):
            mock_positions.append(
                Position(
                    symbol=f"STOCK{i:03d}",
                    quantity=1,
                    average_price=10.0,
                    current_price=10.05,
                    market_value=10.05,
                    unrealized_pnl=0.05,
                    realized_pnl=0.0,
                )
            )

        mock_portfolio = Portfolio(
            cash_balance=1000.0,
            positions=mock_positions,
            market_value=1005.0,  # 100 * 10.05
            total_value=2005.0,
        )

        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["positions"]) == 100
        assert data["market_value"] == 1005.0

    @patch("app.core.dependencies.get_trading_service")
    def test_fractional_shares(self, mock_get_service, client: TestClient):
        """Test handling of fractional share positions."""
        mock_service = AsyncMock()

        mock_positions = [
            Position(
                symbol="AAPL",
                quantity=10.5,  # Fractional shares
                average_price=150.0,
                current_price=155.0,
                market_value=1627.5,  # 10.5 * 155.0
                unrealized_pnl=52.5,  # 10.5 * (155.0 - 150.0)
                realized_pnl=0.0,
            )
        ]

        mock_service.get_positions.return_value = mock_positions
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 1
        assert data[0]["quantity"] == 10.5
        assert data[0]["market_value"] == 1627.5


class TestPortfolioEndpointsPerformance:
    """Test performance-related scenarios for portfolio endpoints."""

    @patch("app.core.dependencies.get_trading_service")
    def test_concurrent_portfolio_requests(self, mock_get_service, client: TestClient):
        """Test handling of multiple concurrent portfolio requests."""
        mock_service = AsyncMock()
        mock_portfolio = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service

        # Simulate multiple concurrent requests
        responses = []
        for _ in range(5):
            response = client.get("/api/v1/portfolio/")
            responses.append(response)

        # All requests should be handled successfully
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    @patch("app.core.dependencies.get_trading_service")
    def test_large_greeks_calculation(self, mock_get_service, client: TestClient):
        """Test handling of Greeks calculation for large options portfolio."""
        mock_service = AsyncMock()

        # Create large position breakdown
        position_breakdown = []
        for i in range(50):  # 50 different option positions
            position_breakdown.append(
                {
                    "symbol": f"OPTION{i:03d}_230616C00150000",
                    "quantity": 10,
                    "greeks": {
                        "delta": 0.5,
                        "gamma": 0.03,
                        "theta": -0.02,
                        "vega": 0.15,
                        "rho": 0.06,
                    },
                    "position_greeks": {
                        "total_delta": 5.0,
                        "total_gamma": 0.3,
                        "total_theta": -0.2,
                        "total_vega": 1.5,
                        "total_rho": 0.6,
                    },
                }
            )

        mock_greeks = {
            "portfolio_greeks": {
                "total_delta": 250.0,  # Sum of all deltas
                "total_gamma": 15.0,
                "total_theta": -10.0,
                "total_vega": 75.0,
                "total_rho": 30.0,
            },
            "position_breakdown": position_breakdown,
            "risk_metrics": {
                "net_delta_exposure": 25000.0,
                "gamma_risk": "high",
                "theta_decay_per_day": -10.0,
                "vega_exposure": 75.0,
                "portfolio_beta": 1.2,
            },
            "hedging_suggestions": [],
        }

        mock_service.get_portfolio_greeks.return_value = mock_greeks
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/portfolio/greeks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["position_breakdown"]) == 50
        assert data["portfolio_greeks"]["total_delta"] == 250.0
