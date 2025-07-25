"""
Tests for portfolio analytics MCP tools.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.mcp.portfolio_analytics_tools import (
    calculate_portfolio_beta,
    calculate_sharpe_ratio,
    calculate_var,
    get_portfolio_correlation,
    analyze_sector_allocation,
    get_risk_metrics,
)
from app.schemas.positions import Portfolio, Position


class TestPortfolioAnalyticsTools:
    """Test portfolio analytics MCP tools."""

    @pytest_asyncio.fixture
    async def mock_portfolio(self):
        """Create a mock portfolio for testing."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=10,
                avg_price=180.00,
                current_price=185.00,
                total_value=1850.00,
                unrealized_pnl=50.00,
                unrealized_pnl_percent=2.78
            ),
            Position(
                symbol="GOOGL",
                quantity=5,
                avg_price=2800.00,
                current_price=2850.00,
                total_value=14250.00,
                unrealized_pnl=250.00,
                unrealized_pnl_percent=1.79
            ),
            Position(
                symbol="MSFT",
                quantity=8,
                avg_price=380.00,
                current_price=385.00,
                total_value=3080.00,
                unrealized_pnl=40.00,
                unrealized_pnl_percent=1.32
            )
        ]
        
        return Portfolio(
            total_value=19180.00,
            cash_balance=5000.00,
            day_change=340.00,
            day_change_percent=1.81,
            positions=positions
        )

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_portfolio_beta(self, mock_get_service, mock_portfolio):
        """Test portfolio beta calculation."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_portfolio_beta()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "portfolio_beta" in data
        assert "benchmark" in data
        assert "interpretation" in data
        assert "position_betas" in data
        assert "total_portfolio_value" in data
        
        # Check that beta is a reasonable number
        assert isinstance(data["portfolio_beta"], (int, float))
        assert data["benchmark"] == "S&P 500"
        assert len(data["position_betas"]) == len(mock_portfolio.positions)

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_sharpe_ratio(self, mock_get_service, mock_portfolio):
        """Test Sharpe ratio calculation."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_sharpe_ratio()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "sharpe_ratio" in data
        assert "annual_return" in data
        assert "annual_volatility" in data
        assert "risk_free_rate" in data
        assert "interpretation" in data
        assert "additional_metrics" in data
        
        # Check that Sharpe ratio is calculated correctly
        expected_sharpe = (data["annual_return"] - data["risk_free_rate"]) / data["annual_volatility"]
        assert abs(data["sharpe_ratio"] - expected_sharpe) < 0.01

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_sharpe_ratio_custom_period(self, mock_get_service, mock_portfolio):
        """Test Sharpe ratio calculation with custom period."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_sharpe_ratio(period_days=126)  # Half year
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert data["period_days"] == 126

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_var(self, mock_get_service, mock_portfolio):
        """Test Value at Risk calculation."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_var()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "var_amount" in data
        assert "var_percentage" in data
        assert "confidence_level" in data
        assert "portfolio_value" in data
        assert "interpretation" in data
        assert "expected_shortfall" in data
        
        # Check that VaR is positive (represents potential loss)
        assert data["var_amount"] > 0
        assert data["var_percentage"] > 0
        assert data["confidence_level"] == 0.95  # Default

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_var_custom_confidence(self, mock_get_service, mock_portfolio):
        """Test VaR calculation with custom confidence level."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_var(confidence_level=0.99, period_days=5)
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert data["confidence_level"] == 0.99
        assert data["period_days"] == 5

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_get_portfolio_correlation(self, mock_get_service, mock_portfolio):
        """Test portfolio correlation matrix calculation."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await get_portfolio_correlation()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "correlation_matrix" in data
        assert "average_correlation" in data
        assert "interpretation" in data
        assert "highest_correlation" in data
        assert "lowest_correlation" in data
        
        # Check correlation matrix structure
        matrix = data["correlation_matrix"]
        assert len(matrix) == len(mock_portfolio.positions)
        
        for row in matrix:
            assert "symbol" in row
            assert "correlations" in row
            assert len(row["correlations"]) == len(mock_portfolio.positions)

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_analyze_sector_allocation(self, mock_get_service, mock_portfolio):
        """Test sector allocation analysis."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await analyze_sector_allocation()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "sector_allocations" in data
        assert "total_portfolio_value" in data
        assert "largest_sector" in data
        assert "concentration_risk" in data
        assert "benchmark_comparison" in data
        assert "diversification_score" in data
        
        # Check sector allocation structure
        allocations = data["sector_allocations"]
        assert len(allocations) > 0
        
        total_percentage = sum(sector["percentage"] for sector in allocations)
        assert abs(total_percentage - 100.0) < 0.1  # Should sum to ~100%

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_get_risk_metrics(self, mock_get_service, mock_portfolio):
        """Test comprehensive risk metrics calculation."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        mock_get_service.return_value = mock_service
        
        result = await get_risk_metrics()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert "portfolio_value" in data
        assert "risk_metrics" in data
        assert "overall_risk_assessment" in data
        assert "recommendations" in data
        
        # Check risk metrics structure
        risk_metrics = data["risk_metrics"]
        assert "volatility" in risk_metrics
        assert "downside_metrics" in risk_metrics
        assert "risk_ratios" in risk_metrics
        assert "tail_risk" in risk_metrics
        assert "concentration_risk" in risk_metrics
        
        # Check overall assessment
        assessment = data["overall_risk_assessment"]
        assert "risk_score" in assessment
        assert "risk_level" in assessment
        assert "description" in assessment


class TestPortfolioAnalyticsToolsErrorHandling:
    """Test error handling in portfolio analytics tools."""

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_portfolio_beta_service_error(self, mock_get_service):
        """Test portfolio beta calculation handles service errors."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        result = await calculate_portfolio_beta()
        
        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_sharpe_ratio_portfolio_error(self, mock_get_service):
        """Test Sharpe ratio calculation handles portfolio errors."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = Exception("Portfolio error")
        mock_get_service.return_value = mock_service
        
        result = await calculate_sharpe_ratio()
        
        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_calculate_var_empty_portfolio(self, mock_get_service):
        """Test VaR calculation with empty portfolio."""
        mock_service = AsyncMock()
        empty_portfolio = Portfolio(
            total_value=0.0,
            cash_balance=10000.00,
            day_change=0.0,
            day_change_percent=0.0,
            positions=[]
        )
        mock_service.get_portfolio.return_value = empty_portfolio
        mock_get_service.return_value = mock_service
        
        result = await calculate_var()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert data["portfolio_value"] == 0.0
        assert data["var_amount"] == 0.0

    @patch('app.mcp.portfolio_analytics_tools.math')
    @pytest.mark.asyncio
    async def test_calculate_var_math_error(self, mock_math):
        """Test VaR calculation handles math errors."""
        mock_math.sqrt.side_effect = Exception("Math error")
        
        result = await calculate_var()
        
        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]


class TestPortfolioAnalyticsEdgeCases:
    """Test edge cases for portfolio analytics tools."""

    @patch('app.mcp.portfolio_analytics_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_single_position_portfolio(self, mock_get_service):
        """Test analytics with single position portfolio."""
        single_position_portfolio = Portfolio(
            total_value=10000.00,
            cash_balance=0.00,
            day_change=100.00,
            day_change_percent=1.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=50,
                    avg_price=190.00,
                    current_price=200.00,
                    total_value=10000.00,
                    unrealized_pnl=500.00,
                    unrealized_pnl_percent=5.26
                )
            ]
        )
        
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = single_position_portfolio
        mock_get_service.return_value = mock_service
        
        result = await analyze_sector_allocation()
        
        assert "result" in result
        assert result["result"]["status"] == "success"
        
        data = result["result"]["data"]
        assert len(data["sector_allocations"]) >= 1
        assert data["concentration_risk"]["top_sector_percentage"] == 100.0