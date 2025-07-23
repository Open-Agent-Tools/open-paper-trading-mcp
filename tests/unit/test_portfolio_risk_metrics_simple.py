"""
Unit tests for the portfolio risk metrics service.

This module tests the portfolio risk metrics functionality, including VaR calculation,
exposure metrics, risk budget allocation, and stress testing.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.models.assets import Option, Stock
from app.schemas.positions import Portfolio, Position
from app.services.portfolio_risk_metrics import (
    ExposureMetrics,
    PortfolioRiskCalculator,
    PortfolioRiskSummary,
    RiskBudgetAllocation,
    StressTestResult,
    VaRResult,
    get_portfolio_risk_calculator,
)


@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio for testing."""
    return Portfolio(
        cash_balance=10000.0,
        total_value=25000.0,
        positions=[
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=140.0,
                current_price=150.0,
                unrealized_pnl=1000.0,
                realized_pnl=0.0,
            ),
            Position(
                symbol="MSFT",
                quantity=50,
                avg_price=280.0,
                current_price=300.0,
                unrealized_pnl=1000.0,
                realized_pnl=0.0,
            ),
            Position(
                symbol="JPM",
                quantity=75,
                avg_price=130.0,
                current_price=140.0,
                unrealized_pnl=750.0,
                realized_pnl=0.0,
            ),
        ],
        daily_pnl=500.0,
        total_pnl=2750.0,
    )


@pytest.fixture
def mock_historical_data():
    """Create mock historical price data for testing."""
    return {
        "AAPL": [145.0, 147.0, 148.0, 146.0, 150.0],  # 5 days of prices
        "MSFT": [290.0, 295.0, 292.0, 298.0, 300.0],
        "JPM": [135.0, 138.0, 137.0, 139.0, 140.0],
    }


@pytest.fixture
def risk_calculator():
    """Create a portfolio risk calculator for testing."""
    return PortfolioRiskCalculator()


class TestPortfolioRiskCalculatorInitialization:
    """Test portfolio risk calculator initialization."""

    def test_initialization(self):
        """Test initialization of portfolio risk calculator."""
        calculator = PortfolioRiskCalculator()
        assert calculator is not None
        assert hasattr(calculator, "price_history")
        assert hasattr(calculator, "return_history")
        assert hasattr(calculator, "sector_mappings")
        assert hasattr(calculator, "correlation_cache")

    def test_sector_mappings_loaded(self, risk_calculator):
        """Test sector mappings are loaded."""
        assert risk_calculator.sector_mappings is not None
        assert len(risk_calculator.sector_mappings) > 0
        assert "AAPL" in risk_calculator.sector_mappings
        assert risk_calculator.sector_mappings["AAPL"] == "Technology"
        assert "JPM" in risk_calculator.sector_mappings
        assert risk_calculator.sector_mappings["JPM"] == "Financials"

    def test_global_risk_calculator(self):
        """Test global risk calculator instance."""
        calculator = get_portfolio_risk_calculator()
        assert calculator is not None
        assert isinstance(calculator, PortfolioRiskCalculator)


class TestVaRCalculation:
    """Test Value at Risk calculation."""

    def test_calculate_parametric_var(self, risk_calculator, mock_portfolio):
        """Test parametric VaR calculation."""
        # Act
        var_result = risk_calculator._calculate_parametric_var(
            mock_portfolio, confidence_level=0.95, time_horizon=1
        )

        # Assert
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.time_horizon == 1
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0
        assert var_result.expected_shortfall > 0
        assert var_result.method == "parametric"

    @patch("scipy.stats.norm.ppf")
    @patch("scipy.stats.norm.pdf")
    def test_calculate_parametric_var_with_mocks(
        self, mock_pdf, mock_ppf, risk_calculator, mock_portfolio
    ):
        """Test parametric VaR calculation with mocked scipy functions."""
        # Arrange
        mock_ppf.return_value = 1.645  # z-score for 95% confidence
        mock_pdf.return_value = 0.103  # pdf value at z-score

        # Act
        var_result = risk_calculator._calculate_parametric_var(
            mock_portfolio, confidence_level=0.95, time_horizon=1
        )

        # Assert
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.var_amount > 0
        assert var_result.expected_shortfall > 0
        mock_ppf.assert_called_once_with(1 - 0.95)
        mock_pdf.assert_called_once()

    def test_calculate_var_with_historical_data(
        self, risk_calculator, mock_portfolio, mock_historical_data
    ):
        """Test VaR calculation with historical data."""
        # Act
        var_result = risk_calculator._calculate_var(
            mock_portfolio, confidence_level=0.95, historical_data=mock_historical_data
        )

        # Assert
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0
        assert var_result.expected_shortfall > 0
        assert var_result.method == "historical"

    def test_calculate_var_without_historical_data(
        self, risk_calculator, mock_portfolio
    ):
        """Test VaR calculation without historical data (falls back to parametric)."""
        # Act
        var_result = risk_calculator._calculate_var(
            mock_portfolio, confidence_level=0.95, historical_data=None
        )

        # Assert
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0
        assert var_result.expected_shortfall > 0
        assert var_result.method == "parametric"

    def test_calculate_portfolio_returns(
        self, risk_calculator, mock_portfolio, mock_historical_data
    ):
        """Test portfolio returns calculation from historical data."""
        # Act
        returns = risk_calculator._calculate_portfolio_returns(
            mock_portfolio, mock_historical_data
        )

        # Assert
        assert isinstance(returns, list)
        assert len(returns) > 0
        assert all(isinstance(r, float) for r in returns)

    def test_calculate_position_var(self, risk_calculator):
        """Test VaR calculation for a single position."""
        # Arrange
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=140.0,
            current_price=150.0,
            unrealized_pnl=1000.0,
            realized_pnl=0.0,
        )

        # Act
        var_result = risk_calculator.calculate_position_var(
            position, confidence_level=0.95, time_horizon=1
        )

        # Assert
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.time_horizon == 1
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0
        assert var_result.expected_shortfall > 0
        assert var_result.method == "parametric"


class TestExposureMetrics:
    """Test exposure metrics calculation."""

    def test_calculate_exposure_metrics(self, risk_calculator, mock_portfolio):
        """Test exposure metrics calculation."""
        # Act
        metrics = risk_calculator._calculate_exposure_metrics(mock_portfolio)

        # Assert
        assert isinstance(metrics, ExposureMetrics)
        assert metrics.gross_exposure > 0
        assert metrics.long_exposure > 0
        assert metrics.short_exposure >= 0
        assert metrics.leverage_ratio > 0
        assert metrics.beta_weighted_exposure > 0
        assert len(metrics.sector_exposures) > 0
        assert len(metrics.concentration_metrics) > 0

    def test_calculate_concentration_metrics(self, risk_calculator, mock_portfolio):
        """Test concentration metrics calculation."""
        # Act
        metrics = risk_calculator._calculate_concentration_metrics(mock_portfolio)

        # Assert
        assert isinstance(metrics, dict)
        assert "herfindahl_index" in metrics
        assert "effective_positions" in metrics
        assert "max_concentration" in metrics
        assert "top3_concentration" in metrics
        assert metrics["herfindahl_index"] > 0
        assert metrics["effective_positions"] > 0
        assert metrics["max_concentration"] > 0
        assert metrics["top3_concentration"] > 0


class TestRiskBudget:
    """Test risk budget allocation."""

    def test_calculate_risk_budget(self, risk_calculator, mock_portfolio):
        """Test risk budget calculation."""
        # Act
        budget = risk_calculator._calculate_risk_budget(mock_portfolio)

        # Assert
        assert isinstance(budget, RiskBudgetAllocation)
        assert len(budget.position_risk_contributions) == len(mock_portfolio.positions)
        assert len(budget.marginal_risk_contributions) == len(mock_portfolio.positions)
        assert len(budget.component_var) == len(mock_portfolio.positions)
        assert budget.diversification_ratio > 0

        # Check that all positions are included
        for position in mock_portfolio.positions:
            assert position.symbol in budget.position_risk_contributions
            assert position.symbol in budget.marginal_risk_contributions
            assert position.symbol in budget.component_var


class TestStressTests:
    """Test stress test scenarios."""

    @patch("app.services.portfolio_risk_metrics.asset_factory")
    def test_run_stress_tests(
        self, mock_asset_factory, risk_calculator, mock_portfolio
    ):
        """Test running stress test scenarios."""
        # Arrange
        # Mock asset_factory to return Stock objects
        mock_asset_factory.return_value = MagicMock(spec=Stock)

        # Act
        stress_tests = risk_calculator._run_stress_tests(mock_portfolio)

        # Assert
        assert isinstance(stress_tests, list)
        assert len(stress_tests) > 0
        assert all(isinstance(test, StressTestResult) for test in stress_tests)

        # Check specific scenarios
        scenario_names = [test.scenario_name for test in stress_tests]
        assert "Market Crash" in scenario_names
        assert "Sector Rotation" in scenario_names
        assert "Interest Rate Shock" in scenario_names
        assert "Volatility Spike" in scenario_names

    @patch("app.services.portfolio_risk_metrics.asset_factory")
    def test_stress_test_scenario(
        self, mock_asset_factory, risk_calculator, mock_portfolio
    ):
        """Test applying a specific stress test scenario."""
        # Arrange
        # Mock asset_factory to return Stock objects
        mock_asset_factory.return_value = MagicMock(spec=Stock)

        # Act
        result = risk_calculator._stress_test_scenario(
            mock_portfolio, "Test Scenario", {"all": -0.10}
        )

        # Assert
        assert isinstance(result, StressTestResult)
        assert result.scenario_name == "Test Scenario"
        assert result.portfolio_return < 0  # Negative return for -10% shock
        assert len(result.position_impacts) == len(mock_portfolio.positions)
        assert len(result.sector_impacts) > 0
        assert len(result.largest_losses) > 0

    @patch("app.services.portfolio_risk_metrics.asset_factory")
    def test_stress_test_with_options(self, mock_asset_factory, risk_calculator):
        """Test stress test with options positions."""
        # Arrange
        # Create a portfolio with an option position
        portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=15000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=140.0,
                    current_price=150.0,
                    unrealized_pnl=1000.0,
                    realized_pnl=0.0,
                ),
                Position(
                    symbol="AAPL240119C00150000",
                    quantity=5,
                    avg_price=5.0,
                    current_price=7.0,
                    unrealized_pnl=100.0,
                    realized_pnl=0.0,
                ),
            ],
            daily_pnl=200.0,
            total_pnl=1100.0,
        )

        # Mock asset_factory to return Option for option symbol and Stock for stock symbol
        def mock_asset_side_effect(symbol):
            if "C00" in symbol or "P00" in symbol:
                option = MagicMock(spec=Option)
                option.symbol = symbol
                return option
            else:
                stock = MagicMock(spec=Stock)
                stock.symbol = symbol
                return stock

        mock_asset_factory.side_effect = mock_asset_side_effect

        # Act
        result = risk_calculator._stress_test_scenario(
            portfolio, "Volatility Spike", {"options": 0.30, "stocks": -0.10}
        )

        # Assert
        assert isinstance(result, StressTestResult)
        assert result.scenario_name == "Volatility Spike"
        assert "AAPL" in result.position_impacts
        assert "AAPL240119C00150000" in result.position_impacts
        assert result.position_impacts["AAPL"] < 0  # Stock should lose value
        assert (
            result.position_impacts["AAPL240119C00150000"] > 0
        )  # Option should gain value


class TestRiskAlerts:
    """Test risk alert generation."""

    def test_generate_risk_alerts(self, risk_calculator, mock_portfolio):
        """Test risk alert generation."""
        # Arrange
        exposure_metrics = ExposureMetrics(
            gross_exposure=20000.0,
            net_exposure=20000.0,
            long_exposure=20000.0,
            short_exposure=0.0,
            sector_exposures={"Technology": 15000.0, "Financials": 5000.0},
            concentration_metrics={
                "herfindahl_index": 0.3,
                "effective_positions": 3.3,
                "max_concentration": 0.25,  # High concentration
                "top3_concentration": 1.0,
            },
            leverage_ratio=2.5,  # High leverage
            beta_weighted_exposure=20000.0,
        )

        var_results = {
            0.95: VaRResult(
                confidence_level=0.95,
                time_horizon=1,
                var_amount=2000.0,  # High VaR
                var_percent=0.08,
                expected_shortfall=2500.0,
                method="parametric",
            )
        }

        # Act
        alerts = risk_calculator._generate_risk_alerts(
            mock_portfolio, exposure_metrics, var_results
        )

        # Assert
        assert isinstance(alerts, list)
        assert len(alerts) > 0
        assert any("concentration" in alert.lower() for alert in alerts)
        assert any("leverage" in alert.lower() for alert in alerts)
        assert any("var" in alert.lower() for alert in alerts)


class TestCorrelationMatrix:
    """Test correlation matrix calculation."""

    def test_calculate_correlation_matrix(self, risk_calculator, mock_historical_data):
        """Test correlation matrix calculation."""
        # Arrange
        symbols = ["AAPL", "MSFT", "JPM"]

        # Act
        corr_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, mock_historical_data
        )

        # Assert
        assert isinstance(corr_matrix, np.ndarray)
        assert corr_matrix.shape == (3, 3)  # 3x3 matrix for 3 symbols
        assert np.all(np.diag(corr_matrix) == 1.0)  # Diagonal should be 1.0
        assert np.all(corr_matrix <= 1.0)  # Correlations should be <= 1.0
        assert np.all(corr_matrix >= -1.0)  # Correlations should be >= -1.0

    def test_calculate_correlation_matrix_missing_data(self, risk_calculator):
        """Test correlation matrix calculation with missing data."""
        # Arrange
        symbols = ["AAPL", "MSFT", "UNKNOWN"]
        historical_data = {
            "AAPL": [100.0, 102.0, 101.0, 103.0],
            "MSFT": [200.0, 202.0, 201.0, 203.0],
            # UNKNOWN symbol has no data
        }

        # Act
        corr_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, historical_data
        )

        # Assert
        assert isinstance(corr_matrix, np.ndarray)
        assert corr_matrix.shape == (3, 3)  # 3x3 matrix for 3 symbols
        assert np.all(np.diag(corr_matrix) == 1.0)  # Diagonal should be 1.0

    def test_calculate_correlation_matrix_no_data(self, risk_calculator):
        """Test correlation matrix calculation with no data."""
        # Arrange
        symbols = ["AAPL", "MSFT", "JPM"]
        historical_data = {}  # No data

        # Act
        corr_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, historical_data
        )

        # Assert
        assert isinstance(corr_matrix, np.ndarray)
        assert corr_matrix.shape == (3, 3)  # 3x3 matrix for 3 symbols
        assert np.all(np.diag(corr_matrix) == 1.0)  # Diagonal should be 1.0
        assert np.all(corr_matrix == np.eye(3))  # Should be identity matrix


class TestComprehensiveRiskCalculation:
    """Test comprehensive portfolio risk calculation."""

    @patch("app.services.portfolio_risk_metrics.PortfolioRiskCalculator._calculate_var")
    @patch(
        "app.services.portfolio_risk_metrics.PortfolioRiskCalculator._calculate_exposure_metrics"
    )
    @patch(
        "app.services.portfolio_risk_metrics.PortfolioRiskCalculator._calculate_risk_budget"
    )
    @patch(
        "app.services.portfolio_risk_metrics.PortfolioRiskCalculator._run_stress_tests"
    )
    @patch(
        "app.services.portfolio_risk_metrics.PortfolioRiskCalculator._generate_risk_alerts"
    )
    def test_calculate_portfolio_risk(
        self,
        mock_generate_alerts,
        mock_run_stress_tests,
        mock_calculate_risk_budget,
        mock_calculate_exposure_metrics,
        mock_calculate_var,
        risk_calculator,
        mock_portfolio,
        mock_historical_data,
    ):
        """Test comprehensive portfolio risk calculation with mocks."""
        # Arrange
        mock_var_result = VaRResult(
            confidence_level=0.95,
            time_horizon=1,
            var_amount=1000.0,
            var_percent=0.04,
            expected_shortfall=1200.0,
            method="historical",
        )
        mock_calculate_var.return_value = mock_var_result

        mock_exposure_metrics = MagicMock(spec=ExposureMetrics)
        mock_calculate_exposure_metrics.return_value = mock_exposure_metrics

        mock_risk_budget = MagicMock(spec=RiskBudgetAllocation)
        mock_calculate_risk_budget.return_value = mock_risk_budget

        mock_stress_tests = [MagicMock(spec=StressTestResult)]
        mock_run_stress_tests.return_value = mock_stress_tests

        mock_alerts = ["Test alert"]
        mock_generate_alerts.return_value = mock_alerts

        # Act
        result = risk_calculator.calculate_portfolio_risk(
            mock_portfolio, mock_historical_data, [0.95, 0.99]
        )

        # Assert
        assert isinstance(result, PortfolioRiskSummary)
        assert 0.95 in result.var_results
        assert 0.99 in result.var_results
        assert result.exposure_metrics == mock_exposure_metrics
        assert result.risk_budget == mock_risk_budget
        assert result.stress_tests == mock_stress_tests
        assert result.risk_alerts == mock_alerts

        # Verify method calls
        mock_calculate_var.assert_called()
        mock_calculate_exposure_metrics.assert_called_once_with(mock_portfolio)
        mock_calculate_risk_budget.assert_called_once_with(
            mock_portfolio, mock_historical_data
        )
        mock_run_stress_tests.assert_called_once_with(mock_portfolio)
        mock_generate_alerts.assert_called_once()

    def test_calculate_portfolio_risk_integration(
        self, risk_calculator, mock_portfolio, mock_historical_data
    ):
        """Test comprehensive portfolio risk calculation (integration test)."""
        # Act
        result = risk_calculator.calculate_portfolio_risk(
            mock_portfolio, mock_historical_data, [0.95]
        )

        # Assert
        assert isinstance(result, PortfolioRiskSummary)
        assert 0.95 in result.var_results
        assert isinstance(result.exposure_metrics, ExposureMetrics)
        assert isinstance(result.risk_budget, RiskBudgetAllocation)
        assert isinstance(result.stress_tests, list)
        assert all(isinstance(test, StressTestResult) for test in result.stress_tests)
        assert isinstance(result.risk_alerts, list)
        assert isinstance(result.calculation_timestamp, datetime)

    def test_calculate_portfolio_risk_no_historical_data(
        self, risk_calculator, mock_portfolio
    ):
        """Test portfolio risk calculation without historical data."""
        # Act
        result = risk_calculator.calculate_portfolio_risk(mock_portfolio, None, [0.95])

        # Assert
        assert isinstance(result, PortfolioRiskSummary)
        assert 0.95 in result.var_results
        assert (
            result.var_results[0.95].method == "parametric"
        )  # Should use parametric method
        assert isinstance(result.exposure_metrics, ExposureMetrics)
        assert isinstance(result.risk_budget, RiskBudgetAllocation)
        assert isinstance(result.stress_tests, list)
        assert isinstance(result.risk_alerts, list)

    def test_calculate_portfolio_risk_error_handling(
        self, risk_calculator, mock_portfolio
    ):
        """Test error handling in portfolio risk calculation."""
        # Arrange
        # Create a portfolio with invalid data to trigger errors
        invalid_portfolio = Portfolio(
            cash_balance=-1000.0,  # Negative cash balance
            total_value=0.0,  # Zero total value
            positions=[],  # No positions
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Act
        result = risk_calculator.calculate_portfolio_risk(
            invalid_portfolio, None, [0.95]
        )

        # Assert
        assert isinstance(result, PortfolioRiskSummary)
        assert 0.95 in result.var_results
        assert isinstance(result.exposure_metrics, ExposureMetrics)
        assert isinstance(result.risk_budget, RiskBudgetAllocation)
        assert isinstance(result.stress_tests, list)
        assert isinstance(result.risk_alerts, list)
