"""
Test cases for portfolio risk metrics calculations.

Tests VaR calculations, exposure metrics, risk analysis, and stress testing.
Mocks mathematical operations and data sources for consistent testing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
import numpy as np

from app.services.portfolio_risk_metrics import (
    PortfolioRiskCalculator,
    CorrelationMatrix,
    VaRResult,
    ExposureMetrics,
    RiskBudgetAllocation,
    StressTestResult,
    PortfolioRiskSummary,
    get_portfolio_risk_calculator,
    portfolio_risk_calculator,
    DrawdownAnalysis,
    PerformanceAttribution,
    PortfolioRiskAnalyzer,
    RiskDecomposition,
)
from app.schemas.positions import Portfolio, Position
from app.models.assets import Stock, Option


class TestPortfolioRiskCalculator:
    """Test portfolio risk calculator functionality."""

    def test_calculator_initialization(self):
        """Test risk calculator initialization."""
        calculator = PortfolioRiskCalculator()
        
        assert calculator is not None
        assert isinstance(calculator.price_history, dict)
        assert isinstance(calculator.return_history, dict)
        assert isinstance(calculator.sector_mappings, dict)
        assert isinstance(calculator.correlation_cache, dict)

    def test_sector_mappings_loaded(self):
        """Test that sector mappings are properly loaded."""
        calculator = PortfolioRiskCalculator()
        
        # Check that common symbols are mapped
        assert "AAPL" in calculator.sector_mappings
        assert "MSFT" in calculator.sector_mappings
        assert "JPM" in calculator.sector_mappings
        
        assert calculator.sector_mappings["AAPL"] == "Technology"
        assert calculator.sector_mappings["JPM"] == "Financials"

    def test_global_calculator_access(self):
        """Test global calculator access functions."""
        global_calc = get_portfolio_risk_calculator()
        
        assert global_calc is not None
        assert isinstance(global_calc, PortfolioRiskCalculator)
        assert global_calc is portfolio_risk_calculator

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio for testing."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0,
                asset=Stock("AAPL")
            ),
            Position(
                symbol="MSFT",
                quantity=50,
                avg_price=300.0,
                current_price=310.0,
                asset=Stock("MSFT")
            ),
            Position(
                symbol="JPM",
                quantity=75,
                avg_price=120.0,
                current_price=125.0,
                asset=Stock("JPM")
            )
        ]
        
        return Portfolio(
            cash_balance=50000.0,
            positions=positions,
            total_value=100000.0,
            daily_pnl=1000.0,
            total_pnl=5000.0
        )

    @pytest.fixture
    def sample_historical_data(self):
        """Create sample historical price data."""
        # 30 days of price data for each symbol
        np.random.seed(42)  # For reproducible results
        
        base_prices = {"AAPL": 150.0, "MSFT": 300.0, "JPM": 120.0}
        historical_data = {}
        
        for symbol, base_price in base_prices.items():
            # Generate random walk price series
            returns = np.random.normal(0, 0.02, 30)  # 2% daily volatility
            prices = [base_price]
            
            for return_val in returns:
                new_price = prices[-1] * (1 + return_val)
                prices.append(new_price)
            
            historical_data[symbol] = prices
        
        return historical_data

    def test_calculate_portfolio_risk_basic(self, sample_portfolio):
        """Test basic portfolio risk calculation."""
        calculator = PortfolioRiskCalculator()
        
        result = calculator.calculate_portfolio_risk(sample_portfolio)
        
        assert isinstance(result, PortfolioRiskSummary)
        assert isinstance(result.var_results, dict)
        assert isinstance(result.exposure_metrics, ExposureMetrics)
        assert isinstance(result.risk_budget, RiskBudgetAllocation)
        assert isinstance(result.stress_tests, list)
        assert isinstance(result.risk_alerts, list)

    def test_calculate_portfolio_risk_with_data(self, sample_portfolio, sample_historical_data):
        """Test portfolio risk calculation with historical data."""
        calculator = PortfolioRiskCalculator()
        
        result = calculator.calculate_portfolio_risk(
            sample_portfolio,
            historical_data=sample_historical_data,
            confidence_levels=[0.95, 0.99]
        )
        
        assert len(result.var_results) == 2
        assert 0.95 in result.var_results
        assert 0.99 in result.var_results
        
        var_95 = result.var_results[0.95]
        var_99 = result.var_results[0.99]
        
        assert isinstance(var_95, VaRResult)
        assert isinstance(var_99, VaRResult)
        assert var_95.confidence_level == 0.95
        assert var_99.confidence_level == 0.99
        assert var_99.var_amount >= var_95.var_amount  # 99% VaR should be higher

    def test_parametric_var_calculation(self, sample_portfolio):
        """Test parametric VaR calculation when no historical data."""
        calculator = PortfolioRiskCalculator()
        
        var_result = calculator._calculate_parametric_var(sample_portfolio, 0.95)
        
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.method == "parametric"
        assert var_result.var_amount > 0
        assert var_result.expected_shortfall > 0

    def test_historical_var_calculation(self, sample_portfolio, sample_historical_data):
        """Test historical VaR calculation."""
        calculator = PortfolioRiskCalculator()
        
        var_result = calculator._calculate_var(
            sample_portfolio, 0.95, sample_historical_data
        )
        
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.method == "historical"
        assert var_result.var_amount > 0
        assert var_result.expected_shortfall > 0

    def test_portfolio_returns_calculation(self, sample_portfolio, sample_historical_data):
        """Test portfolio returns calculation."""
        calculator = PortfolioRiskCalculator()
        
        returns = calculator._calculate_portfolio_returns(
            sample_portfolio, sample_historical_data
        )
        
        assert isinstance(returns, list)
        assert len(returns) > 0
        assert all(isinstance(r, float) for r in returns)

    def test_exposure_metrics_calculation(self, sample_portfolio):
        """Test exposure metrics calculation."""
        calculator = PortfolioRiskCalculator()
        
        exposure = calculator._calculate_exposure_metrics(sample_portfolio)
        
        assert isinstance(exposure, ExposureMetrics)
        assert exposure.gross_exposure > 0
        assert exposure.long_exposure > 0
        assert exposure.short_exposure >= 0
        assert exposure.net_exposure > 0
        assert isinstance(exposure.sector_exposures, dict)
        assert isinstance(exposure.concentration_metrics, dict)
        assert exposure.leverage_ratio > 0

    def test_concentration_metrics(self, sample_portfolio):
        """Test position concentration metrics."""
        calculator = PortfolioRiskCalculator()
        
        concentration = calculator._calculate_concentration_metrics(sample_portfolio)
        
        assert isinstance(concentration, dict)
        assert "herfindahl_index" in concentration
        assert "effective_positions" in concentration
        assert "max_concentration" in concentration
        assert "top3_concentration" in concentration
        
        assert 0 <= concentration["herfindahl_index"] <= 1
        assert concentration["effective_positions"] > 0
        assert 0 <= concentration["max_concentration"] <= 1

    def test_risk_budget_allocation(self, sample_portfolio):
        """Test risk budget allocation calculation."""
        calculator = PortfolioRiskCalculator()
        
        risk_budget = calculator._calculate_risk_budget(sample_portfolio)
        
        assert isinstance(risk_budget, RiskBudgetAllocation)
        assert isinstance(risk_budget.position_risk_contributions, dict)
        assert isinstance(risk_budget.marginal_risk_contributions, dict)
        assert isinstance(risk_budget.component_var, dict)
        assert risk_budget.diversification_ratio >= 0

    def test_stress_testing(self, sample_portfolio):
        """Test stress testing scenarios."""
        calculator = PortfolioRiskCalculator()
        
        stress_tests = calculator._run_stress_tests(sample_portfolio)
        
        assert isinstance(stress_tests, list)
        assert len(stress_tests) > 0
        
        for stress_test in stress_tests:
            assert isinstance(stress_test, StressTestResult)
            assert stress_test.scenario_name
            assert isinstance(stress_test.portfolio_return, (int, float))
            assert isinstance(stress_test.position_impacts, dict)
            assert isinstance(stress_test.sector_impacts, dict)
            assert isinstance(stress_test.largest_losses, list)

    def test_stress_test_scenario(self, sample_portfolio):
        """Test individual stress test scenario."""
        calculator = PortfolioRiskCalculator()
        
        scenario = calculator._stress_test_scenario(
            sample_portfolio,
            "Test Scenario",
            {"all": -0.10}  # 10% decline
        )
        
        assert isinstance(scenario, StressTestResult)
        assert scenario.scenario_name == "Test Scenario"
        assert scenario.portfolio_return < 0  # Should be negative for decline

    def test_risk_alerts_generation(self, sample_portfolio):
        """Test risk alerts generation."""
        calculator = PortfolioRiskCalculator()
        
        # Create mock exposure and VaR results
        exposure = ExposureMetrics(
            gross_exposure=100000.0,
            net_exposure=100000.0,
            long_exposure=100000.0,
            short_exposure=0.0,
            sector_exposures={"Technology": 60000.0},  # 60% in tech
            concentration_metrics={"max_concentration": 0.25},  # 25% in one position
            leverage_ratio=3.0,  # High leverage
            beta_weighted_exposure=100000.0
        )
        
        var_results = {
            0.95: VaRResult(
                confidence_level=0.95,
                time_horizon=1,
                var_amount=10000.0,  # High VaR
                var_percent=0.10,
                expected_shortfall=12000.0,
                method="historical"
            )
        }
        
        alerts = calculator._generate_risk_alerts(
            sample_portfolio, exposure, var_results
        )
        
        assert isinstance(alerts, list)
        # Should have alerts for high concentration, leverage, and VaR
        assert len(alerts) >= 3

    def test_position_var_calculation(self):
        """Test VaR calculation for individual position."""
        calculator = PortfolioRiskCalculator()
        
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            asset=Stock("AAPL")
        )
        
        # Test with historical prices
        historical_prices = [150.0, 152.0, 149.0, 153.0, 151.0]
        
        var_result = calculator.calculate_position_var(
            position, 0.95, 1, historical_prices
        )
        
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.method == "historical"
        assert var_result.var_amount > 0

    def test_position_var_without_historical_data(self):
        """Test VaR calculation without historical data (parametric)."""
        calculator = PortfolioRiskCalculator()
        
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            asset=Stock("AAPL")
        )
        
        var_result = calculator.calculate_position_var(position, 0.95)
        
        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.method == "parametric"
        assert var_result.var_amount > 0

    def test_correlation_matrix_calculation(self):
        """Test correlation matrix calculation."""
        calculator = PortfolioRiskCalculator()
        
        symbols = ["AAPL", "MSFT", "JPM"]
        historical_data = {
            "AAPL": [150.0, 152.0, 149.0, 153.0, 151.0],
            "MSFT": [300.0, 305.0, 298.0, 310.0, 303.0],
            "JPM": [120.0, 122.0, 119.0, 125.0, 121.0]
        }
        
        correlation_matrix = calculator.calculate_correlation_matrix(
            symbols, historical_data
        )
        
        assert isinstance(correlation_matrix, np.ndarray)
        assert correlation_matrix.shape == (3, 3)
        
        # Diagonal should be close to 1 (self-correlation)
        np.testing.assert_array_almost_equal(
            np.diag(correlation_matrix), [1.0, 1.0, 1.0], decimal=5
        )

    def test_correlation_matrix_with_missing_data(self):
        """Test correlation matrix with missing symbol data."""
        calculator = PortfolioRiskCalculator()
        
        symbols = ["AAPL", "UNKNOWN", "MSFT"]
        historical_data = {
            "AAPL": [150.0, 152.0, 149.0],
            "MSFT": [300.0, 305.0, 298.0]
            # "UNKNOWN" missing
        }
        
        correlation_matrix = calculator.calculate_correlation_matrix(
            symbols, historical_data
        )
        
        assert isinstance(correlation_matrix, np.ndarray)
        assert correlation_matrix.shape == (3, 3)

    def test_return_history_update(self):
        """Test internal return history caching."""
        calculator = PortfolioRiskCalculator()
        
        historical_data = {
            "AAPL": [150.0, 152.0, 149.0, 153.0],
            "MSFT": [300.0, 305.0, 298.0, 310.0]
        }
        
        calculator._update_return_history(historical_data)
        
        assert "AAPL" in calculator.return_history
        assert "MSFT" in calculator.return_history
        
        # Check that returns were calculated correctly
        aapl_returns = calculator.return_history["AAPL"]
        assert len(aapl_returns) == 3  # n-1 returns from n prices
        
        # First return should be (152-150)/150
        expected_first_return = (152.0 - 150.0) / 150.0
        assert abs(aapl_returns[0] - expected_first_return) < 1e-10


class TestDataClasses:
    """Test data classes used in portfolio risk metrics."""

    def test_correlation_matrix(self):
        """Test CorrelationMatrix data class."""
        symbols = ["AAPL", "MSFT"]
        matrix = np.array([[1.0, 0.5], [0.5, 1.0]])
        
        corr_matrix = CorrelationMatrix(symbols=symbols, matrix=matrix)
        
        assert corr_matrix.symbols == symbols
        np.testing.assert_array_equal(corr_matrix.matrix, matrix)

    def test_var_result(self):
        """Test VaRResult data class."""
        var_result = VaRResult(
            confidence_level=0.95,
            time_horizon=1,
            var_amount=5000.0,
            var_percent=0.05,
            expected_shortfall=6000.0,
            method="historical"
        )
        
        assert var_result.confidence_level == 0.95
        assert var_result.time_horizon == 1
        assert var_result.var_amount == 5000.0
        assert var_result.var_percent == 0.05
        assert var_result.expected_shortfall == 6000.0
        assert var_result.method == "historical"
        assert isinstance(var_result.calculation_date, datetime)

    def test_exposure_metrics(self):
        """Test ExposureMetrics data class."""
        exposure = ExposureMetrics(
            gross_exposure=100000.0,
            net_exposure=90000.0,
            long_exposure=95000.0,
            short_exposure=5000.0,
            sector_exposures={"Technology": 50000.0},
            concentration_metrics={"max_concentration": 0.20},
            leverage_ratio=1.5,
            beta_weighted_exposure=88000.0
        )
        
        assert exposure.gross_exposure == 100000.0
        assert exposure.net_exposure == 90000.0
        assert exposure.long_exposure == 95000.0
        assert exposure.short_exposure == 5000.0
        assert "Technology" in exposure.sector_exposures
        assert "max_concentration" in exposure.concentration_metrics

    def test_risk_budget_allocation(self):
        """Test RiskBudgetAllocation data class."""
        risk_budget = RiskBudgetAllocation(
            position_risk_contributions={"AAPL": 1000.0, "MSFT": 800.0},
            marginal_risk_contributions={"AAPL": 0.02, "MSFT": 0.015},
            component_var={"AAPL": 1000.0, "MSFT": 800.0},
            diversification_ratio=0.85
        )
        
        assert risk_budget.position_risk_contributions["AAPL"] == 1000.0
        assert risk_budget.marginal_risk_contributions["MSFT"] == 0.015
        assert risk_budget.component_var["AAPL"] == 1000.0
        assert risk_budget.diversification_ratio == 0.85

    def test_stress_test_result(self):
        """Test StressTestResult data class."""
        stress_test = StressTestResult(
            scenario_name="Market Crash",
            portfolio_return=-15000.0,
            position_impacts={"AAPL": -5000.0, "MSFT": -7000.0},
            sector_impacts={"Technology": -12000.0},
            largest_losses=[("MSFT", -7000.0), ("AAPL", -5000.0)]
        )
        
        assert stress_test.scenario_name == "Market Crash"
        assert stress_test.portfolio_return == -15000.0
        assert stress_test.position_impacts["AAPL"] == -5000.0
        assert len(stress_test.largest_losses) == 2

    def test_portfolio_risk_summary(self):
        """Test PortfolioRiskSummary data class."""
        var_results = {
            0.95: VaRResult(0.95, 1, 5000.0, 0.05, 6000.0, "historical")
        }
        
        exposure = ExposureMetrics(
            gross_exposure=100000.0,
            net_exposure=100000.0,
            long_exposure=100000.0,
            short_exposure=0.0,
            sector_exposures={},
            concentration_metrics={},
            leverage_ratio=1.0,
            beta_weighted_exposure=100000.0
        )
        
        risk_budget = RiskBudgetAllocation(
            position_risk_contributions={},
            marginal_risk_contributions={},
            component_var={},
            diversification_ratio=1.0
        )
        
        summary = PortfolioRiskSummary(
            var_results=var_results,
            exposure_metrics=exposure,
            risk_budget=risk_budget,
            stress_tests=[],
            risk_alerts=["High concentration warning"]
        )
        
        assert len(summary.var_results) == 1
        assert isinstance(summary.exposure_metrics, ExposureMetrics)
        assert isinstance(summary.risk_budget, RiskBudgetAllocation)
        assert isinstance(summary.stress_tests, list)
        assert len(summary.risk_alerts) == 1
        assert isinstance(summary.calculation_timestamp, datetime)


class TestStubClasses:
    """Test stub classes that will be implemented later."""

    def test_drawdown_analysis_stub(self):
        """Test DrawdownAnalysis stub class."""
        analysis = DrawdownAnalysis()
        assert analysis is not None
        assert isinstance(analysis, DrawdownAnalysis)

    def test_performance_attribution_stub(self):
        """Test PerformanceAttribution stub class."""
        attribution = PerformanceAttribution()
        assert attribution is not None
        assert isinstance(attribution, PerformanceAttribution)

    def test_portfolio_risk_analyzer_stub(self):
        """Test PortfolioRiskAnalyzer stub class."""
        analyzer = PortfolioRiskAnalyzer()
        assert analyzer is not None
        assert isinstance(analyzer, PortfolioRiskAnalyzer)

    def test_risk_decomposition_stub(self):
        """Test RiskDecomposition stub class."""
        decomposition = RiskDecomposition()
        assert decomposition is not None
        assert isinstance(decomposition, RiskDecomposition)


class TestErrorHandling:
    """Test error handling in portfolio risk calculations."""

    def test_var_calculation_with_insufficient_data(self):
        """Test VaR calculation with insufficient historical data."""
        calculator = PortfolioRiskCalculator()
        
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        # Only 2 data points - insufficient for reliable VaR
        historical_data = {"AAPL": [150.0, 152.0]}
        
        # Should fall back to parametric VaR
        result = calculator.calculate_portfolio_risk(
            portfolio, historical_data
        )
        
        assert isinstance(result, PortfolioRiskSummary)
        # Should still provide some results even with limited data

    def test_empty_portfolio_risk_calculation(self):
        """Test risk calculation with empty portfolio."""
        calculator = PortfolioRiskCalculator()
        
        empty_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        result = calculator.calculate_portfolio_risk(empty_portfolio)
        
        assert isinstance(result, PortfolioRiskSummary)
        assert result.exposure_metrics.gross_exposure == 0.0
        assert result.exposure_metrics.long_exposure == 0.0

    def test_position_var_with_invalid_price(self):
        """Test position VaR calculation with invalid current price."""
        calculator = PortfolioRiskCalculator()
        
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None,  # Invalid price
            asset=Stock("AAPL")
        )
        
        with pytest.raises(ValueError, match="Position must have a current price"):
            calculator.calculate_position_var(position)


# Integration tests with mocked data
class TestIntegrationScenarios:
    """Test realistic portfolio risk analysis scenarios."""

    @pytest.fixture
    def diversified_portfolio(self):
        """Create a diversified portfolio for testing."""
        positions = [
            # Technology stocks
            Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0, asset=Stock("AAPL")),
            Position(symbol="MSFT", quantity=50, avg_price=300.0, current_price=310.0, asset=Stock("MSFT")),
            Position(symbol="GOOGL", quantity=25, avg_price=2800.0, current_price=2900.0, asset=Stock("GOOGL")),
            
            # Financial stocks
            Position(symbol="JPM", quantity=75, avg_price=120.0, current_price=125.0, asset=Stock("JPM")),
            Position(symbol="BAC", quantity=200, avg_price=35.0, current_price=37.0, asset=Stock("BAC")),
            
            # Consumer stocks
            Position(symbol="PG", quantity=60, avg_price=140.0, current_price=145.0, asset=Stock("PG")),
        ]
        
        return Portfolio(
            cash_balance=25000.0,
            positions=positions,
            total_value=200000.0,
            daily_pnl=2000.0,
            total_pnl=15000.0
        )

    def test_diversified_portfolio_analysis(self, diversified_portfolio):
        """Test risk analysis of a diversified portfolio."""
        calculator = PortfolioRiskCalculator()
        
        result = calculator.calculate_portfolio_risk(diversified_portfolio)
        
        # Should have exposure across multiple sectors
        sector_exposures = result.exposure_metrics.sector_exposures
        assert len(sector_exposures) >= 3  # At least 3 sectors
        assert "Technology" in sector_exposures
        assert "Financials" in sector_exposures
        assert "Consumer Staples" in sector_exposures
        
        # Concentration should be reasonable for diversified portfolio
        concentration = result.exposure_metrics.concentration_metrics
        assert concentration["max_concentration"] < 0.30  # No single position > 30%
        assert concentration["effective_positions"] > 3  # Good diversification

    def test_concentrated_portfolio_alerts(self):
        """Test alerts for concentrated portfolio."""
        calculator = PortfolioRiskCalculator()
        
        # Very concentrated portfolio - 80% in one position
        concentrated_positions = [
            Position(symbol="AAPL", quantity=800, avg_price=150.0, current_price=155.0, asset=Stock("AAPL")),
            Position(symbol="MSFT", quantity=20, avg_price=300.0, current_price=310.0, asset=Stock("MSFT")),
        ]
        
        concentrated_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=concentrated_positions,
            total_value=140000.0,
            daily_pnl=1000.0,
            total_pnl=5000.0
        )
        
        result = calculator.calculate_portfolio_risk(concentrated_portfolio)
        
        # Should generate concentration alerts
        alerts = result.risk_alerts
        concentration_alerts = [a for a in alerts if "concentration" in a.lower()]
        assert len(concentration_alerts) > 0

    @patch('numpy.random.normal')
    def test_monte_carlo_simulation_scenario(self, mock_random, diversified_portfolio):
        """Test scenario with mocked Monte Carlo simulation."""
        # Mock consistent random returns for testing
        mock_random.return_value = np.array([-0.02, -0.01, 0.01, 0.02, -0.015])
        
        calculator = PortfolioRiskCalculator()
        
        # Generate mock historical data
        historical_data = {}
        for position in diversified_portfolio.positions:
            symbol = position.symbol
            base_price = position.current_price or position.avg_price
            
            # Generate 30 days of price data
            prices = [base_price]
            for _ in range(30):
                change = mock_random.return_value[0]  # Use first mocked value
                new_price = prices[-1] * (1 + change)
                prices.append(new_price)
            
            historical_data[symbol] = prices
        
        result = calculator.calculate_portfolio_risk(
            diversified_portfolio,
            historical_data=historical_data
        )
        
        # Should have VaR results
        assert len(result.var_results) > 0
        var_95 = result.var_results.get(0.95)
        assert var_95 is not None
        assert var_95.method == "historical"