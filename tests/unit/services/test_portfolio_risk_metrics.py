"""
Comprehensive tests for PortfolioRiskCalculator - risk analysis and metrics service.

Tests cover:
- Value at Risk (VaR) calculations using multiple methods
- Expected Shortfall (CVaR) computations
- Exposure metrics and concentration analysis
- Risk budget allocation and marginal contributions
- Stress testing scenarios and portfolio impact
- Correlation analysis and diversification metrics
- Portfolio risk alerts and limit monitoring
- Position-level risk calculations
- Historical and parametric VaR methods
- Edge cases and error handling
"""

from datetime import date, timedelta
from unittest.mock import patch

import numpy as np
import pytest

from app.models.assets import Call, Put, Stock
from app.schemas.positions import Portfolio, Position
from app.services.portfolio_risk_metrics import (
    ExposureMetrics,
    PortfolioRiskCalculator,
    PortfolioRiskSummary,
    RiskBudgetAllocation,
    StressTestResult,
    VaRResult,
)


@pytest.fixture
def risk_calculator():
    """Portfolio risk calculator instance."""
    return PortfolioRiskCalculator()


@pytest.fixture
def sample_portfolio():
    """Sample portfolio for testing."""
    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            avg_price=145.00,
            current_price=150.00,
            market_value=15000.00,
            unrealized_pnl=500.00,
        ),
        Position(
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.00,
            current_price=2850.00,
            market_value=142500.00,
            unrealized_pnl=2500.00,
        ),
        Position(
            symbol="MSFT",
            quantity=75,
            avg_price=280.00,
            current_price=285.00,
            market_value=21375.00,
            unrealized_pnl=375.00,
        ),
    ]
    return Portfolio(
        cash_balance=20000.00,
        total_value=198875.00,
        positions=positions,
        daily_pnl=3375.00,
        total_pnl=3375.00,
    )


@pytest.fixture
def sample_historical_data():
    """Sample historical price data for testing."""
    np.random.seed(42)  # For reproducible tests

    # Generate realistic price series
    days = 252  # One trading year
    initial_prices = {"AAPL": 145.00, "GOOGL": 2800.00, "MSFT": 280.00}

    data = {}
    for symbol, initial_price in initial_prices.items():
        # Generate random walk with drift
        returns = np.random.normal(0.0008, 0.02, days)  # ~20% annual vol
        prices = [initial_price]

        for ret in returns:
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        data[symbol] = prices

    return data


@pytest.fixture
def options_portfolio():
    """Portfolio with options positions for testing."""
    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            avg_price=145.00,
            current_price=150.00,
            market_value=15000.00,
            unrealized_pnl=500.00,
        ),
        Position(
            symbol="AAPL240119C155",  # Call option
            quantity=10,
            avg_price=5.50,
            current_price=6.25,
            market_value=6250.00,
            unrealized_pnl=750.00,
        ),
        Position(
            symbol="AAPL240119P145",  # Put option
            quantity=-5,  # Short position
            avg_price=3.20,
            current_price=2.80,
            market_value=-1400.00,
            unrealized_pnl=200.00,
        ),
    ]
    return Portfolio(
        cash_balance=10000.00,
        total_value=29850.00,
        positions=positions,
        daily_pnl=1450.00,
        total_pnl=1450.00,
    )


class TestVaRCalculations:
    """Test Value at Risk calculation methods."""

    def test_parametric_var_calculation(self, risk_calculator, sample_portfolio):
        """Test parametric VaR calculation using normal distribution."""
        var_result = risk_calculator._calculate_parametric_var(
            sample_portfolio, confidence_level=0.95, time_horizon=1
        )

        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.time_horizon == 1
        assert var_result.method == "parametric"
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0
        assert var_result.expected_shortfall > var_result.var_amount

    def test_historical_var_calculation(
        self, risk_calculator, sample_portfolio, sample_historical_data
    ):
        """Test historical VaR calculation."""
        var_result = risk_calculator._calculate_var(
            sample_portfolio,
            confidence_level=0.95,
            historical_data=sample_historical_data,
            time_horizon=1,
        )

        assert isinstance(var_result, VaRResult)
        assert var_result.confidence_level == 0.95
        assert var_result.method == "historical"
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0

    def test_var_calculation_insufficient_data_fallback(
        self, risk_calculator, sample_portfolio
    ):
        """Test VaR calculation fallback when insufficient historical data."""
        # Provide very limited historical data
        limited_data = {
            "AAPL": [145.00, 146.00],  # Only 2 data points
            "GOOGL": [2800.00, 2810.00],
            "MSFT": [280.00, 282.00],
        }

        var_result = risk_calculator._calculate_var(
            sample_portfolio, confidence_level=0.95, historical_data=limited_data
        )

        # Should fallback to parametric method
        assert var_result.method == "parametric"

    def test_var_multiple_confidence_levels(
        self, risk_calculator, sample_portfolio, sample_historical_data
    ):
        """Test VaR calculation at different confidence levels."""
        confidence_levels = [0.90, 0.95, 0.99]
        var_results = {}

        for confidence in confidence_levels:
            var_results[confidence] = risk_calculator._calculate_var(
                sample_portfolio,
                confidence_level=confidence,
                historical_data=sample_historical_data,
            )

        # Higher confidence should result in higher VaR
        assert var_results[0.99].var_amount > var_results[0.95].var_amount
        assert var_results[0.95].var_amount > var_results[0.90].var_amount

    def test_var_different_time_horizons(self, risk_calculator, sample_portfolio):
        """Test VaR scaling for different time horizons."""
        var_1day = risk_calculator._calculate_parametric_var(
            sample_portfolio, confidence_level=0.95, time_horizon=1
        )

        var_5day = risk_calculator._calculate_parametric_var(
            sample_portfolio, confidence_level=0.95, time_horizon=5
        )

        # 5-day VaR should be higher than 1-day VaR
        assert var_5day.var_amount > var_1day.var_amount
        assert var_5day.time_horizon == 5
        assert var_1day.time_horizon == 1

    def test_portfolio_returns_calculation(
        self, risk_calculator, sample_portfolio, sample_historical_data
    ):
        """Test portfolio returns calculation from historical data."""
        returns = risk_calculator._calculate_portfolio_returns(
            sample_portfolio, sample_historical_data
        )

        assert len(returns) > 0
        assert all(isinstance(ret, float) for ret in returns)
        # Returns should be reasonable (not extremely large)
        assert all(abs(ret) < 1.0 for ret in returns)  # Less than 100% daily return

    def test_portfolio_returns_empty_data(self, risk_calculator, sample_portfolio):
        """Test portfolio returns calculation with empty data."""
        empty_data = {"AAPL": [], "GOOGL": [], "MSFT": []}

        returns = risk_calculator._calculate_portfolio_returns(
            sample_portfolio, empty_data
        )

        assert returns == []

    def test_portfolio_returns_single_data_point(
        self, risk_calculator, sample_portfolio
    ):
        """Test portfolio returns calculation with single data point."""
        single_point_data = {"AAPL": [145.00], "GOOGL": [2800.00], "MSFT": [280.00]}

        returns = risk_calculator._calculate_portfolio_returns(
            sample_portfolio, single_point_data
        )

        assert returns == []


class TestExposureMetrics:
    """Test exposure calculation and analysis."""

    def test_exposure_metrics_calculation(self, risk_calculator, sample_portfolio):
        """Test comprehensive exposure metrics calculation."""
        exposure_metrics = risk_calculator._calculate_exposure_metrics(sample_portfolio)

        assert isinstance(exposure_metrics, ExposureMetrics)
        assert exposure_metrics.gross_exposure > 0
        assert exposure_metrics.net_exposure > 0
        assert exposure_metrics.long_exposure > 0
        assert exposure_metrics.short_exposure >= 0
        assert exposure_metrics.leverage_ratio > 0
        assert isinstance(exposure_metrics.sector_exposures, dict)
        assert isinstance(exposure_metrics.concentration_metrics, dict)

    def test_exposure_metrics_with_short_positions(self, risk_calculator):
        """Test exposure metrics with short positions."""
        positions = [
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
            ),
            Position(
                symbol="TSLA",
                quantity=-50,  # Short position
                current_price=800.00,
                market_value=-40000.00,
            ),
        ]

        portfolio = Portfolio(
            cash_balance=30000.00,
            total_value=5000.00,  # Net value after short
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)

        assert exposure_metrics.long_exposure == 15000.00
        assert exposure_metrics.short_exposure == 40000.00
        assert exposure_metrics.gross_exposure == 55000.00  # 15k + 40k
        assert exposure_metrics.net_exposure == -25000.00  # 15k - 40k

    def test_sector_exposure_mapping(self, risk_calculator, sample_portfolio):
        """Test sector exposure calculation and mapping."""
        exposure_metrics = risk_calculator._calculate_exposure_metrics(sample_portfolio)

        # Should have Technology sector exposure (AAPL, GOOGL, MSFT)
        assert "Technology" in exposure_metrics.sector_exposures
        assert exposure_metrics.sector_exposures["Technology"] > 0

    def test_concentration_metrics_calculation(self, risk_calculator, sample_portfolio):
        """Test position concentration metrics."""
        concentration_metrics = risk_calculator._calculate_concentration_metrics(
            sample_portfolio
        )

        assert "herfindahl_index" in concentration_metrics
        assert "effective_positions" in concentration_metrics
        assert "max_concentration" in concentration_metrics
        assert "top3_concentration" in concentration_metrics

        # HHI should be between 0 and 1
        assert 0 <= concentration_metrics["herfindahl_index"] <= 1
        assert concentration_metrics["effective_positions"] > 0
        assert 0 <= concentration_metrics["max_concentration"] <= 1

    def test_concentration_metrics_single_position(self, risk_calculator):
        """Test concentration metrics with single position (maximum concentration)."""
        positions = [
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
            )
        ]

        portfolio = Portfolio(
            cash_balance=0.00,
            total_value=15000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        concentration_metrics = risk_calculator._calculate_concentration_metrics(
            portfolio
        )

        # Single position should have maximum concentration
        assert concentration_metrics["max_concentration"] == 1.0
        assert concentration_metrics["herfindahl_index"] == 1.0
        assert concentration_metrics["effective_positions"] == 1.0

    def test_leverage_calculation_with_zero_cash(self, risk_calculator):
        """Test leverage calculation when cash balance is zero."""
        positions = [
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
            )
        ]

        portfolio = Portfolio(
            cash_balance=0.00,  # No cash
            total_value=15000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)

        # Should handle zero cash gracefully
        assert exposure_metrics.leverage_ratio == float("inf")


class TestRiskBudgetAllocation:
    """Test risk budget allocation and contribution analysis."""

    def test_risk_budget_calculation(
        self, risk_calculator, sample_portfolio, sample_historical_data
    ):
        """Test risk budget allocation calculation."""
        risk_budget = risk_calculator._calculate_risk_budget(
            sample_portfolio, sample_historical_data
        )

        assert isinstance(risk_budget, RiskBudgetAllocation)
        assert isinstance(risk_budget.position_risk_contributions, dict)
        assert isinstance(risk_budget.marginal_risk_contributions, dict)
        assert isinstance(risk_budget.component_var, dict)
        assert isinstance(risk_budget.diversification_ratio, float)

    def test_risk_contribution_allocation(self, risk_calculator, sample_portfolio):
        """Test that risk contributions are properly allocated."""
        risk_budget = risk_calculator._calculate_risk_budget(sample_portfolio, None)

        # Should have risk contributions for each position
        for position in sample_portfolio.positions:
            assert position.symbol in risk_budget.position_risk_contributions
            assert position.symbol in risk_budget.marginal_risk_contributions
            assert position.symbol in risk_budget.component_var

    def test_risk_contribution_sum(self, risk_calculator, sample_portfolio):
        """Test that risk contributions sum to total portfolio risk."""
        risk_budget = risk_calculator._calculate_risk_budget(sample_portfolio, None)

        total_contribution = sum(risk_budget.position_risk_contributions.values())
        total_component_var = sum(risk_budget.component_var.values())

        # Contributions should be positive
        assert total_contribution > 0
        assert total_component_var > 0

        # Component VaR should equal position contributions (simplified model)
        assert abs(total_contribution - total_component_var) < 0.01

    def test_diversification_ratio_calculation(self, risk_calculator, sample_portfolio):
        """Test diversification ratio calculation."""
        risk_budget = risk_calculator._calculate_risk_budget(sample_portfolio, None)

        # Diversification ratio should be between 0 and 1 for diversified portfolio
        assert 0 <= risk_budget.diversification_ratio <= 1


class TestStressTesting:
    """Test stress testing scenarios and impact analysis."""

    def test_stress_test_scenarios(self, risk_calculator, sample_portfolio):
        """Test various stress test scenarios."""
        stress_tests = risk_calculator._run_stress_tests(sample_portfolio)

        assert len(stress_tests) > 0
        assert all(isinstance(test, StressTestResult) for test in stress_tests)

        # Should include standard scenarios
        scenario_names = [test.scenario_name for test in stress_tests]
        assert "Market Crash" in scenario_names
        assert "Sector Rotation" in scenario_names

    def test_market_crash_scenario(self, risk_calculator, sample_portfolio):
        """Test market crash stress test scenario."""
        market_crash = risk_calculator._stress_test_scenario(
            sample_portfolio, "Market Crash", {"all": -0.20}
        )

        assert isinstance(market_crash, StressTestResult)
        assert market_crash.scenario_name == "Market Crash"
        assert market_crash.portfolio_return < 0  # Should be negative
        assert len(market_crash.position_impacts) == len(sample_portfolio.positions)
        assert len(market_crash.largest_losses) <= 5

    def test_sector_specific_stress_test(self, risk_calculator, sample_portfolio):
        """Test sector-specific stress test."""
        tech_crash = risk_calculator._stress_test_scenario(
            sample_portfolio, "Tech Crash", {"Technology": -0.30}
        )

        # Technology positions should be impacted
        tech_symbols = ["AAPL", "GOOGL", "MSFT"]
        for symbol in tech_symbols:
            assert symbol in tech_crash.position_impacts
            assert tech_crash.position_impacts[symbol] < 0  # Negative impact

    def test_stress_test_with_options(self, risk_calculator, options_portfolio):
        """Test stress testing with options positions."""
        with patch("app.services.portfolio_risk_metrics.asset_factory") as mock_factory:
            # Mock asset factory responses
            def mock_asset_factory(symbol):
                if "C" in symbol:
                    return Call(
                        underlying=Stock(symbol="AAPL"),
                        strike=155.0,
                        expiration_date=date.today() + timedelta(days=30),
                    )
                elif "P" in symbol:
                    return Put(
                        underlying=Stock(symbol="AAPL"),
                        strike=145.0,
                        expiration_date=date.today() + timedelta(days=30),
                    )
                else:
                    return Stock(symbol=symbol)

            mock_factory.side_effect = mock_asset_factory

            vol_spike = risk_calculator._stress_test_scenario(
                options_portfolio,
                "Volatility Spike",
                {"options": 0.30, "stocks": -0.10},
            )

            assert vol_spike.portfolio_return != 0
            assert len(vol_spike.position_impacts) == len(options_portfolio.positions)

    def test_largest_losses_identification(self, risk_calculator, sample_portfolio):
        """Test identification of largest losses in stress tests."""
        market_crash = risk_calculator._stress_test_scenario(
            sample_portfolio, "Market Crash", {"all": -0.20}
        )

        # Should identify largest losses
        assert len(market_crash.largest_losses) > 0

        # Should be sorted by loss magnitude (most negative first)
        if len(market_crash.largest_losses) > 1:
            for i in range(len(market_crash.largest_losses) - 1):
                assert (
                    market_crash.largest_losses[i][1]
                    <= market_crash.largest_losses[i + 1][1]
                )


class TestRiskAlerts:
    """Test risk alert generation and monitoring."""

    def test_risk_alerts_generation(self, risk_calculator, sample_portfolio):
        """Test generation of risk alerts."""
        # Create mock exposure and VaR results
        exposure_metrics = risk_calculator._calculate_exposure_metrics(sample_portfolio)
        var_results = {
            0.95: VaRResult(
                confidence_level=0.95,
                time_horizon=1,
                var_amount=10000.0,  # High VaR
                var_percent=0.05,
                expected_shortfall=12000.0,
                method="historical",
            )
        }

        alerts = risk_calculator._generate_risk_alerts(
            sample_portfolio, exposure_metrics, var_results
        )

        assert isinstance(alerts, list)

    def test_high_concentration_alert(self, risk_calculator):
        """Test high concentration risk alert."""
        # Create portfolio with high concentration
        positions = [
            Position(
                symbol="AAPL",
                quantity=1000,  # Large position
                current_price=150.00,
                market_value=150000.00,
            ),
            Position(
                symbol="GOOGL",
                quantity=10,  # Small position
                current_price=2800.00,
                market_value=28000.00,
            ),
        ]

        portfolio = Portfolio(
            cash_balance=22000.00,
            total_value=200000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)
        var_results = {}

        alerts = risk_calculator._generate_risk_alerts(
            portfolio, exposure_metrics, var_results
        )

        # Should generate concentration alert
        concentration_alerts = [
            alert for alert in alerts if "concentration" in alert.lower()
        ]
        assert len(concentration_alerts) > 0

    def test_high_leverage_alert(self, risk_calculator):
        """Test high leverage risk alert."""
        # Create highly leveraged portfolio
        positions = [
            Position(
                symbol="AAPL",
                quantity=1000,
                current_price=150.00,
                market_value=150000.00,
            )
        ]

        portfolio = Portfolio(
            cash_balance=50000.00,  # Low cash relative to positions
            total_value=200000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)
        var_results = {}

        alerts = risk_calculator._generate_risk_alerts(
            portfolio, exposure_metrics, var_results
        )

        # Should generate leverage alert
        leverage_alerts = [alert for alert in alerts if "leverage" in alert.lower()]
        assert len(leverage_alerts) > 0

    def test_high_var_alert(self, risk_calculator, sample_portfolio):
        """Test high VaR risk alert."""
        exposure_metrics = risk_calculator._calculate_exposure_metrics(sample_portfolio)

        # Create high VaR result
        var_results = {
            0.95: VaRResult(
                confidence_level=0.95,
                time_horizon=1,
                var_amount=15000.0,  # High VaR (>5% of portfolio)
                var_percent=0.075,
                expected_shortfall=18000.0,
                method="historical",
            )
        }

        alerts = risk_calculator._generate_risk_alerts(
            sample_portfolio, exposure_metrics, var_results
        )

        # Should generate VaR alert
        var_alerts = [alert for alert in alerts if "var" in alert.lower()]
        assert len(var_alerts) > 0

    def test_low_diversification_alert(self, risk_calculator):
        """Test low diversification risk alert."""
        # Create poorly diversified portfolio
        positions = [
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
            )
        ]

        portfolio = Portfolio(
            cash_balance=5000.00,
            total_value=20000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)
        var_results = {}

        alerts = risk_calculator._generate_risk_alerts(
            portfolio, exposure_metrics, var_results
        )

        # Should generate diversification alert
        diversification_alerts = [
            alert for alert in alerts if "diversification" in alert.lower()
        ]
        assert len(diversification_alerts) > 0


class TestPositionRisk:
    """Test individual position risk calculations."""

    def test_position_var_calculation_historical(self, risk_calculator):
        """Test position VaR calculation with historical data."""
        position = Position(
            symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
        )

        # Generate sample historical prices
        np.random.seed(42)
        base_price = 150.0
        historical_prices = [base_price]
        for _ in range(100):
            change = np.random.normal(0, 0.02)  # 2% daily volatility
            new_price = historical_prices[-1] * (1 + change)
            historical_prices.append(new_price)

        var_result = risk_calculator.calculate_position_var(
            position, confidence_level=0.95, historical_prices=historical_prices
        )

        assert isinstance(var_result, VaRResult)
        assert var_result.method == "historical"
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0

    def test_position_var_calculation_parametric(self, risk_calculator):
        """Test position VaR calculation using parametric method."""
        position = Position(
            symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
        )

        var_result = risk_calculator.calculate_position_var(
            position, confidence_level=0.95
        )

        assert isinstance(var_result, VaRResult)
        assert var_result.method == "parametric"
        assert var_result.var_amount > 0
        assert var_result.var_percent > 0

    def test_position_var_missing_price_raises_error(self, risk_calculator):
        """Test position VaR calculation with missing current price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            current_price=None,  # Missing price
            market_value=15000.00,
        )

        with pytest.raises(ValueError, match="Position must have a current price"):
            risk_calculator.calculate_position_var(position)

    def test_position_var_different_confidence_levels(self, risk_calculator):
        """Test position VaR at different confidence levels."""
        position = Position(
            symbol="AAPL", quantity=100, current_price=150.00, market_value=15000.00
        )

        var_95 = risk_calculator.calculate_position_var(position, confidence_level=0.95)
        var_99 = risk_calculator.calculate_position_var(position, confidence_level=0.99)

        # 99% VaR should be higher than 95% VaR
        assert var_99.var_amount > var_95.var_amount
        assert var_99.var_percent > var_95.var_percent


class TestCorrelationAnalysis:
    """Test correlation analysis and matrix calculations."""

    def test_correlation_matrix_calculation(self, risk_calculator):
        """Test correlation matrix calculation."""
        symbols = ["AAPL", "GOOGL", "MSFT"]

        # Generate correlated price data
        np.random.seed(42)
        days = 100

        # Generate correlated returns
        mean_returns = np.array([0.001, 0.0008, 0.0012])
        cov_matrix = np.array(
            [
                [0.0004, 0.0002, 0.0001],
                [0.0002, 0.0005, 0.00015],
                [0.0001, 0.00015, 0.0003],
            ]
        )

        returns = np.random.multivariate_normal(mean_returns, cov_matrix, days)

        # Convert returns to prices
        historical_data = {}
        initial_prices = [150.0, 2800.0, 280.0]

        for i, symbol in enumerate(symbols):
            prices = [initial_prices[i]]
            for ret in returns[:, i]:
                new_price = prices[-1] * (1 + ret)
                prices.append(new_price)
            historical_data[symbol] = prices

        correlation_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, historical_data
        )

        assert correlation_matrix.shape == (3, 3)
        # Diagonal should be 1.0 (perfect self-correlation)
        np.testing.assert_array_almost_equal(
            np.diag(correlation_matrix), [1.0, 1.0, 1.0]
        )
        # Matrix should be symmetric
        np.testing.assert_array_almost_equal(correlation_matrix, correlation_matrix.T)

    def test_correlation_matrix_empty_data(self, risk_calculator):
        """Test correlation matrix calculation with empty data."""
        symbols = ["AAPL", "GOOGL"]
        historical_data = {}

        correlation_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, historical_data
        )

        # Should return identity matrix
        expected = np.eye(len(symbols))
        np.testing.assert_array_equal(correlation_matrix, expected)

    def test_correlation_matrix_missing_symbols(self, risk_calculator):
        """Test correlation matrix with some missing symbol data."""
        symbols = ["AAPL", "GOOGL", "MISSING"]
        historical_data = {
            "AAPL": [150.0, 151.0, 149.0],
            "GOOGL": [2800.0, 2810.0, 2790.0],
            # "MISSING" not in data
        }

        correlation_matrix = risk_calculator.calculate_correlation_matrix(
            symbols, historical_data
        )

        assert correlation_matrix.shape == (3, 3)
        # Should handle missing data gracefully


class TestPortfolioRiskSummary:
    """Test comprehensive portfolio risk summary generation."""

    def test_calculate_portfolio_risk_comprehensive(
        self, risk_calculator, sample_portfolio, sample_historical_data
    ):
        """Test comprehensive portfolio risk calculation."""
        confidence_levels = [0.95, 0.99]

        risk_summary = risk_calculator.calculate_portfolio_risk(
            sample_portfolio, sample_historical_data, confidence_levels
        )

        assert isinstance(risk_summary, PortfolioRiskSummary)
        assert len(risk_summary.var_results) == 2
        assert 0.95 in risk_summary.var_results
        assert 0.99 in risk_summary.var_results
        assert isinstance(risk_summary.exposure_metrics, ExposureMetrics)
        assert isinstance(risk_summary.risk_budget, RiskBudgetAllocation)
        assert len(risk_summary.stress_tests) > 0
        assert isinstance(risk_summary.risk_alerts, list)

    def test_calculate_portfolio_risk_no_historical_data(
        self, risk_calculator, sample_portfolio
    ):
        """Test portfolio risk calculation without historical data."""
        risk_summary = risk_calculator.calculate_portfolio_risk(sample_portfolio)

        # Should still work with parametric methods
        assert isinstance(risk_summary, PortfolioRiskSummary)
        assert len(risk_summary.var_results) == 2  # Default confidence levels

    def test_calculate_portfolio_risk_custom_confidence_levels(
        self, risk_calculator, sample_portfolio
    ):
        """Test portfolio risk calculation with custom confidence levels."""
        custom_levels = [0.90, 0.95, 0.975, 0.99]

        risk_summary = risk_calculator.calculate_portfolio_risk(
            sample_portfolio, confidence_levels=custom_levels
        )

        assert len(risk_summary.var_results) == len(custom_levels)
        for level in custom_levels:
            assert level in risk_summary.var_results

    def test_risk_summary_error_handling(self, risk_calculator, sample_portfolio):
        """Test risk summary generation with calculation errors."""
        # Mock calculation methods to raise errors
        with patch.object(risk_calculator, "_calculate_var") as mock_var:
            mock_var.side_effect = Exception("VaR calculation failed")

            risk_summary = risk_calculator.calculate_portfolio_risk(sample_portfolio)

            # Should handle errors gracefully
            assert isinstance(risk_summary, PortfolioRiskSummary)
            assert len(risk_summary.var_results) == 0  # No VaR results due to errors


class TestRiskCalculatorUtilities:
    """Test utility functions and helper methods."""

    def test_update_return_history(self, risk_calculator, sample_historical_data):
        """Test updating return history cache."""
        risk_calculator._update_return_history(sample_historical_data)

        # Should have calculated returns for each symbol
        for symbol in sample_historical_data.keys():
            assert symbol in risk_calculator.return_history
            returns = risk_calculator.return_history[symbol]
            assert len(returns) == len(sample_historical_data[symbol]) - 1

    def test_load_sector_mappings(self, risk_calculator):
        """Test sector mappings loading."""
        sector_mappings = risk_calculator._load_sector_mappings()

        assert isinstance(sector_mappings, dict)
        assert "AAPL" in sector_mappings
        assert "GOOGL" in sector_mappings
        assert "MSFT" in sector_mappings
        assert sector_mappings["AAPL"] == "Technology"

    def test_global_calculator_instance(self):
        """Test global portfolio risk calculator instance."""
        from app.services.portfolio_risk_metrics import get_portfolio_risk_calculator

        calculator = get_portfolio_risk_calculator()
        assert isinstance(calculator, PortfolioRiskCalculator)

        # Should return same instance
        calculator2 = get_portfolio_risk_calculator()
        assert calculator is calculator2


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    def test_empty_portfolio_handling(self, risk_calculator):
        """Test risk calculation with empty portfolio."""
        empty_portfolio = Portfolio(
            cash_balance=10000.00,
            total_value=10000.00,
            positions=[],
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        risk_summary = risk_calculator.calculate_portfolio_risk(empty_portfolio)

        assert isinstance(risk_summary, PortfolioRiskSummary)
        # Should handle empty portfolio gracefully

    def test_portfolio_with_zero_prices(self, risk_calculator):
        """Test risk calculation with zero position prices."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                current_price=0.0,  # Zero price
                market_value=0.0,
            )
        ]

        portfolio = Portfolio(
            cash_balance=10000.00,
            total_value=10000.00,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        # Should handle zero prices gracefully
        exposure_metrics = risk_calculator._calculate_exposure_metrics(portfolio)
        assert isinstance(exposure_metrics, ExposureMetrics)

    def test_nan_values_in_historical_data(self, risk_calculator, sample_portfolio):
        """Test handling of NaN values in historical data."""
        corrupted_data = {
            "AAPL": [150.0, float("nan"), 152.0, 151.0],
            "GOOGL": [2800.0, 2810.0, float("nan"), 2820.0],
            "MSFT": [280.0, 282.0, 281.0, 283.0],
        }

        # Should handle NaN values without crashing
        try:
            risk_summary = risk_calculator.calculate_portfolio_risk(
                sample_portfolio, corrupted_data
            )
            assert isinstance(risk_summary, PortfolioRiskSummary)
        except Exception as e:
            # If it does raise an exception, it should be handled gracefully
            assert "nan" not in str(e).lower() or "invalid" in str(e).lower()

    def test_extreme_portfolio_values(self, risk_calculator):
        """Test risk calculation with extreme portfolio values."""
        positions = [
            Position(
                symbol="EXTREME",
                quantity=1,
                current_price=1e10,  # Extremely high price
                market_value=1e10,
            )
        ]

        extreme_portfolio = Portfolio(
            cash_balance=1e6,
            total_value=1e10 + 1e6,
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        # Should handle extreme values
        risk_summary = risk_calculator.calculate_portfolio_risk(extreme_portfolio)
        assert isinstance(risk_summary, PortfolioRiskSummary)

    def test_negative_portfolio_values(self, risk_calculator):
        """Test risk calculation with negative portfolio values."""
        positions = [
            Position(
                symbol="SHORT",
                quantity=-100,  # Short position
                current_price=150.0,
                market_value=-15000.0,
            )
        ]

        negative_portfolio = Portfolio(
            cash_balance=20000.00,
            total_value=5000.00,  # Net positive despite short
            positions=positions,
            daily_pnl=0.00,
            total_pnl=0.00,
        )

        risk_summary = risk_calculator.calculate_portfolio_risk(negative_portfolio)
        assert isinstance(risk_summary, PortfolioRiskSummary)
