"""
Advanced test coverage for PortfolioRiskMetrics service.

This module provides comprehensive testing of the portfolio risk metrics service,
focusing on Value at Risk calculations, exposure measurements, correlation analysis,
risk limit monitoring, and advanced portfolio analytics.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio

from app.schemas.positions import Portfolio, Position
from app.services.portfolio_risk_metrics import (
    CorrelationMatrix,
    DrawdownAnalysis,
    ExposureMetrics,
    PerformanceAttribution,
    PortfolioRiskAnalyzer,
    RiskDecomposition,
    StressTestResult,
    VaRResult,
)


@pytest.fixture
def diversified_portfolio():
    """Create diversified portfolio for testing."""
    positions = [
        # Technology sector
        Position(
            symbol="AAPL",
            quantity=100,
            average_cost=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            unrealized_pnl_percent=3.33,
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            quantity=10,
            average_cost=2500.0,
            current_price=2600.0,
            market_value=26000.0,
            unrealized_pnl=1000.0,
            unrealized_pnl_percent=4.0,
            sector="Technology",
        ),
        # Financial sector
        Position(
            symbol="JPM",
            quantity=50,
            average_cost=140.0,
            current_price=145.0,
            market_value=7250.0,
            unrealized_pnl=250.0,
            unrealized_pnl_percent=3.57,
            sector="Financial",
        ),
        # Healthcare sector
        Position(
            symbol="JNJ",
            quantity=75,
            average_cost=160.0,
            current_price=165.0,
            market_value=12375.0,
            unrealized_pnl=375.0,
            unrealized_pnl_percent=3.13,
            sector="Healthcare",
        ),
        # Energy sector
        Position(
            symbol="XOM",
            quantity=200,
            average_cost=95.0,
            current_price=100.0,
            market_value=20000.0,
            unrealized_pnl=1000.0,
            unrealized_pnl_percent=5.26,
            sector="Energy",
        ),
    ]

    return Portfolio(
        cash_balance=50000.0,
        total_value=131125.0,  # 50k cash + 81.125k positions
        positions=positions,
        unrealized_pnl=3125.0,
        unrealized_pnl_percent=2.44,
    )


@pytest.fixture
def concentrated_portfolio():
    """Create concentrated portfolio for testing."""
    positions = [
        Position(
            symbol="TSLA",
            quantity=500,
            average_cost=800.0,
            current_price=750.0,
            market_value=375000.0,  # 75% of portfolio
            unrealized_pnl=-25000.0,
            unrealized_pnl_percent=-6.25,
            sector="Automotive",
        ),
        Position(
            symbol="AAPL",
            quantity=200,
            average_cost=150.0,
            current_price=155.0,
            market_value=31000.0,  # 6.2% of portfolio
            unrealized_pnl=1000.0,
            unrealized_pnl_percent=3.33,
            sector="Technology",
        ),
    ]

    return Portfolio(
        cash_balance=94000.0,  # 18.8% cash
        total_value=500000.0,
        positions=positions,
        unrealized_pnl=-24000.0,
        unrealized_pnl_percent=-4.8,
    )


@pytest.fixture
def risk_analyzer():
    """Create PortfolioRiskAnalyzer instance for testing."""
    return PortfolioRiskAnalyzer()


@pytest.fixture
def mock_market_data():
    """Mock market data for risk calculations."""
    return {
        "AAPL": {
            "returns": np.random.normal(0.001, 0.02, 252),  # Daily returns for 1 year
            "volatility": 0.25,
            "beta": 1.2,
            "correlation_spy": 0.85,
        },
        "GOOGL": {
            "returns": np.random.normal(0.0012, 0.022, 252),
            "volatility": 0.28,
            "beta": 1.1,
            "correlation_spy": 0.80,
        },
        "JPM": {
            "returns": np.random.normal(0.0008, 0.025, 252),
            "volatility": 0.32,
            "beta": 1.4,
            "correlation_spy": 0.75,
        },
        "JNJ": {
            "returns": np.random.normal(0.0005, 0.015, 252),
            "volatility": 0.18,
            "beta": 0.7,
            "correlation_spy": 0.60,
        },
        "XOM": {
            "returns": np.random.normal(0.0003, 0.035, 252),
            "volatility": 0.45,
            "beta": 1.8,
            "correlation_spy": 0.65,
        },
        "TSLA": {
            "returns": np.random.normal(0.0015, 0.045, 252),
            "volatility": 0.55,
            "beta": 2.1,
            "correlation_spy": 0.70,
        },
    }


class TestPortfolioRiskAnalyzer:
    """Test PortfolioRiskAnalyzer functionality."""

    def test_analyzer_initialization(self, risk_analyzer):
        """Test risk analyzer initialization."""
        assert risk_analyzer.confidence_levels == [0.90, 0.95, 0.99]
        assert risk_analyzer.time_horizons == [1, 5, 10, 21]  # days
        assert risk_analyzer.simulation_iterations == 10000

    def test_custom_analyzer_configuration(self):
        """Test custom analyzer configuration."""
        custom_analyzer = PortfolioRiskAnalyzer(
            confidence_levels=[0.95, 0.99],
            time_horizons=[1, 10],
            simulation_iterations=5000,
        )

        assert custom_analyzer.confidence_levels == [0.95, 0.99]
        assert custom_analyzer.time_horizons == [1, 10]
        assert custom_analyzer.simulation_iterations == 5000


class TestValueAtRiskCalculation:
    """Test Value at Risk calculation methods."""

    @pytest.mark.asyncio
    async def test_historical_var_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test historical VaR calculation."""
        with patch.object(risk_analyzer, "_get_historical_returns") as mock_returns:
            mock_returns.return_value = mock_market_data

            var_result = await risk_analyzer.calculate_historical_var(
                diversified_portfolio, confidence_level=0.95, time_horizon=1
            )

            assert isinstance(var_result, VaRResult)
            assert var_result.confidence_level == 0.95
            assert var_result.time_horizon == 1
            assert var_result.method == "historical"
            assert var_result.var_amount > 0
            assert var_result.var_percent > 0
            assert var_result.expected_shortfall >= var_result.var_amount

    @pytest.mark.asyncio
    async def test_parametric_var_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test parametric VaR calculation."""
        with patch.object(risk_analyzer, "_get_portfolio_statistics") as mock_stats:
            mock_stats.return_value = {
                "expected_return": 0.001,
                "volatility": 0.025,
                "skewness": -0.1,
                "kurtosis": 3.2,
            }

            var_result = await risk_analyzer.calculate_parametric_var(
                diversified_portfolio, confidence_level=0.99, time_horizon=10
            )

            assert var_result.confidence_level == 0.99
            assert var_result.time_horizon == 10
            assert var_result.method == "parametric"
            assert var_result.var_amount > 0

            # 99% VaR should be higher than 95% VaR
            var_95 = await risk_analyzer.calculate_parametric_var(
                diversified_portfolio, 0.95, 10
            )
            assert var_result.var_amount > var_95.var_amount

    @pytest.mark.asyncio
    async def test_monte_carlo_var_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test Monte Carlo VaR calculation."""
        with patch.object(risk_analyzer, "_get_correlation_matrix") as mock_corr:
            # Mock correlation matrix
            symbols = ["AAPL", "GOOGL", "JPM", "JNJ", "XOM"]
            corr_matrix = np.eye(len(symbols))  # Start with identity
            # Add some correlations
            for i in range(len(symbols)):
                for j in range(len(symbols)):
                    if i != j:
                        corr_matrix[i][j] = 0.3  # Moderate correlation
            mock_corr.return_value = corr_matrix

            with patch.object(
                risk_analyzer, "_get_portfolio_volatilities"
            ) as mock_vols:
                mock_vols.return_value = [0.25, 0.28, 0.32, 0.18, 0.45]

                var_result = await risk_analyzer.calculate_monte_carlo_var(
                    diversified_portfolio,
                    confidence_level=0.95,
                    time_horizon=5,
                    iterations=1000,  # Reduced for testing
                )

                assert var_result.method == "monte_carlo"
                assert var_result.confidence_level == 0.95
                assert var_result.time_horizon == 5
                assert var_result.var_amount > 0
                assert "monte_carlo_details" in var_result.metadata

    @pytest.mark.asyncio
    async def test_conditional_var_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test Conditional VaR (Expected Shortfall) calculation."""
        with patch.object(risk_analyzer, "_get_historical_returns") as mock_returns:
            mock_returns.return_value = mock_market_data

            var_result = await risk_analyzer.calculate_historical_var(
                diversified_portfolio, confidence_level=0.95, time_horizon=1
            )

            # Conditional VaR should be higher than VaR
            assert var_result.expected_shortfall > var_result.var_amount

            # CVaR represents average loss beyond VaR threshold
            cvar_ratio = var_result.expected_shortfall / var_result.var_amount
            assert 1.0 < cvar_ratio < 2.0  # Reasonable range


class TestExposureMetricsCalculation:
    """Test portfolio exposure metrics calculation."""

    def test_basic_exposure_calculation(self, risk_analyzer, diversified_portfolio):
        """Test basic exposure metrics calculation."""
        exposure = risk_analyzer.calculate_exposure_metrics(diversified_portfolio)

        assert isinstance(exposure, ExposureMetrics)

        # Gross exposure = sum of absolute position values
        expected_gross = sum(
            abs(pos.market_value) for pos in diversified_portfolio.positions
        )
        assert abs(exposure.gross_exposure - expected_gross) < 0.01

        # Net exposure = sum of signed position values
        expected_net = sum(pos.market_value for pos in diversified_portfolio.positions)
        assert abs(exposure.net_exposure - expected_net) < 0.01

        # Long exposure (all positions are long in this case)
        assert exposure.long_exposure == expected_gross
        assert exposure.short_exposure == 0.0

        # Leverage ratio
        portfolio_value = diversified_portfolio.total_value
        expected_leverage = expected_gross / portfolio_value
        assert abs(exposure.leverage_ratio - expected_leverage) < 0.01

    def test_sector_exposure_calculation(self, risk_analyzer, diversified_portfolio):
        """Test sector exposure breakdown."""
        exposure = risk_analyzer.calculate_exposure_metrics(diversified_portfolio)

        # Verify sector exposures
        tech_exposure = (
            15500 + 26000
        ) / diversified_portfolio.total_value  # AAPL + GOOGL
        financial_exposure = 7250 / diversified_portfolio.total_value  # JPM
        healthcare_exposure = 12375 / diversified_portfolio.total_value  # JNJ
        energy_exposure = 20000 / diversified_portfolio.total_value  # XOM

        assert abs(exposure.sector_exposures["Technology"] - tech_exposure) < 0.01
        assert abs(exposure.sector_exposures["Financial"] - financial_exposure) < 0.01
        assert abs(exposure.sector_exposures["Healthcare"] - healthcare_exposure) < 0.01
        assert abs(exposure.sector_exposures["Energy"] - energy_exposure) < 0.01

    def test_concentration_metrics(self, risk_analyzer, concentrated_portfolio):
        """Test concentration risk metrics."""
        exposure = risk_analyzer.calculate_exposure_metrics(concentrated_portfolio)

        # TSLA dominates the portfolio (75%)
        tsla_concentration = 375000 / 500000  # 0.75
        max_position_concentration = max(exposure.concentration_metrics.values())

        assert abs(max_position_concentration - tsla_concentration) < 0.01
        assert max_position_concentration > 0.5  # Highly concentrated

        # Herfindahl index should be high for concentrated portfolio
        hhi = exposure.concentration_metrics.get("herfindahl_index", 0)
        assert hhi > 0.5  # High concentration


class TestCorrelationAnalysis:
    """Test correlation analysis and matrix calculations."""

    @pytest.mark.asyncio
    async def test_correlation_matrix_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test correlation matrix calculation."""
        with patch.object(risk_analyzer, "_get_returns_data") as mock_returns:
            returns_data = {}
            for symbol, data in mock_market_data.items():
                if symbol in ["AAPL", "GOOGL", "JPM", "JNJ", "XOM"]:
                    returns_data[symbol] = data["returns"]
            mock_returns.return_value = returns_data

            corr_matrix = await risk_analyzer.calculate_correlation_matrix(
                diversified_portfolio
            )

            assert isinstance(corr_matrix, CorrelationMatrix)
            assert len(corr_matrix.symbols) == 5
            assert corr_matrix.matrix.shape == (5, 5)

            # Diagonal should be 1.0 (perfect self-correlation)
            np.testing.assert_array_almost_equal(
                np.diag(corr_matrix.matrix), np.ones(5)
            )

            # Matrix should be symmetric
            assert np.allclose(corr_matrix.matrix, corr_matrix.matrix.T)

            # Correlations should be between -1 and 1
            assert np.all(corr_matrix.matrix >= -1.0)
            assert np.all(corr_matrix.matrix <= 1.0)

    @pytest.mark.asyncio
    async def test_portfolio_diversification_ratio(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test portfolio diversification ratio calculation."""
        with patch.object(risk_analyzer, "_get_individual_volatilities") as mock_vols:
            mock_vols.return_value = {
                "AAPL": 0.25,
                "GOOGL": 0.28,
                "JPM": 0.32,
                "JNJ": 0.18,
                "XOM": 0.45,
            }

            with patch.object(
                risk_analyzer, "_calculate_portfolio_volatility"
            ) as mock_port_vol:
                mock_port_vol.return_value = (
                    0.22  # Portfolio vol less than weighted average
                )

                div_ratio = await risk_analyzer.calculate_diversification_ratio(
                    diversified_portfolio
                )

                # Diversification ratio > 1 indicates diversification benefit
                assert div_ratio > 1.0
                assert div_ratio < 2.0  # Reasonable upper bound

    @pytest.mark.asyncio
    async def test_effective_number_of_bets(self, risk_analyzer, diversified_portfolio):
        """Test effective number of independent bets calculation."""
        with patch.object(
            risk_analyzer, "_get_risk_contributions"
        ) as mock_contributions:
            # Mock equal risk contributions for diversified portfolio
            mock_contributions.return_value = {
                "AAPL": 0.20,
                "GOOGL": 0.20,
                "JPM": 0.20,
                "JNJ": 0.20,
                "XOM": 0.20,
            }

            effective_bets = risk_analyzer.calculate_effective_number_of_bets(
                mock_contributions.return_value
            )

            # For equal contributions, should be close to number of positions
            assert 4.5 <= effective_bets <= 5.0

        # Test concentrated portfolio
        with patch.object(
            risk_analyzer, "_get_risk_contributions"
        ) as mock_concentrated:
            mock_concentrated.return_value = {
                "TSLA": 0.80,
                "AAPL": 0.20,  # Concentrated risk
            }

            concentrated_bets = risk_analyzer.calculate_effective_number_of_bets(
                mock_concentrated.return_value
            )

            # Concentrated portfolio should have fewer effective bets
            assert concentrated_bets < 2.0
            assert concentrated_bets > 1.0


class TestRiskDecomposition:
    """Test risk decomposition and attribution analysis."""

    @pytest.mark.asyncio
    async def test_component_var_calculation(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test Component VaR calculation."""
        with patch.object(risk_analyzer, "_calculate_marginal_var") as mock_marginal:
            mock_marginal.return_value = {
                "AAPL": 850.0,
                "GOOGL": 1200.0,
                "JPM": 950.0,
                "JNJ": 450.0,
                "XOM": 1350.0,
            }

            component_var = await risk_analyzer.calculate_component_var(
                diversified_portfolio
            )

            assert isinstance(component_var, RiskDecomposition)
            assert len(component_var.components) == 5

            # Sum of component VaRs should equal total portfolio VaR
            total_component_var = sum(component_var.components.values())
            assert total_component_var > 0

            # Each component should have positive contribution
            for _symbol, contribution in component_var.components.items():
                assert contribution > 0

    @pytest.mark.asyncio
    async def test_marginal_var_calculation(self, risk_analyzer, diversified_portfolio):
        """Test Marginal VaR calculation."""
        with patch.object(risk_analyzer, "calculate_parametric_var") as mock_var:
            # Mock portfolio VaR before and after position changes
            mock_var.side_effect = [
                VaRResult(0.95, 1, 5000.0, 0.05, 6500.0, "parametric"),  # Original
                VaRResult(
                    0.95, 1, 4800.0, 0.048, 6200.0, "parametric"
                ),  # After reducing AAPL
            ]

            marginal_var = await risk_analyzer.calculate_marginal_var(
                diversified_portfolio, "AAPL", position_change=-10
            )

            # Marginal VaR should represent change in portfolio VaR
            expected_marginal = (5000.0 - 4800.0) / 10  # Per unit change
            assert abs(marginal_var - expected_marginal) < 1.0

    @pytest.mark.asyncio
    async def test_incremental_var_calculation(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test Incremental VaR calculation."""
        new_position = Position(
            symbol="MSFT",
            quantity=100,
            average_cost=300.0,
            current_price=310.0,
            market_value=31000.0,
            sector="Technology",
        )

        with patch.object(risk_analyzer, "calculate_parametric_var") as mock_var:
            mock_var.side_effect = [
                VaRResult(0.95, 1, 5000.0, 0.05, 6500.0, "parametric"),  # Original
                VaRResult(
                    0.95, 1, 5800.0, 0.052, 7200.0, "parametric"
                ),  # With new position
            ]

            incremental_var = await risk_analyzer.calculate_incremental_var(
                diversified_portfolio, new_position
            )

            # Incremental VaR should be positive for adding risky position
            assert incremental_var > 0
            assert incremental_var == 800.0  # 5800 - 5000


class TestStressTesting:
    """Test portfolio stress testing scenarios."""

    @pytest.mark.asyncio
    async def test_market_shock_stress_test(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test market shock stress testing."""
        shock_scenarios = [
            {"market_drop": -0.20},  # 20% market decline
            {"market_drop": -0.10},  # 10% market decline
            {"volatility_spike": 2.0},  # Volatility doubles
        ]

        with patch.object(risk_analyzer, "_apply_market_shock") as mock_shock:
            mock_shock.side_effect = [
                {
                    "portfolio_pnl": -16000.0,
                    "position_impacts": {"AAPL": -3100.0, "GOOGL": -5200.0},
                },
                {
                    "portfolio_pnl": -8000.0,
                    "position_impacts": {"AAPL": -1550.0, "GOOGL": -2600.0},
                },
                {
                    "portfolio_pnl": -12000.0,
                    "position_impacts": {"AAPL": -2400.0, "GOOGL": -3800.0},
                },
            ]

            stress_results = await risk_analyzer.run_stress_tests(
                diversified_portfolio, shock_scenarios
            )

            assert len(stress_results) == 3

            for i, result in enumerate(stress_results):
                assert isinstance(result, StressTestResult)
                assert result.scenario_name == f"scenario_{i + 1}"
                assert result.portfolio_pnl < 0  # All scenarios show losses
                assert len(result.position_impacts) > 0

    @pytest.mark.asyncio
    async def test_sector_rotation_stress_test(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test sector rotation stress testing."""
        sector_shocks = {
            "Technology": -0.15,  # Tech sector down 15%
            "Financial": 0.10,  # Financial sector up 10%
            "Healthcare": 0.05,  # Healthcare up 5%
            "Energy": -0.08,  # Energy down 8%
        }

        with patch.object(risk_analyzer, "_apply_sector_shocks") as mock_sector:
            mock_sector.return_value = {
                "portfolio_pnl": -2500.0,
                "sector_impacts": {
                    "Technology": -6225.0,  # (15500 + 26000) * -0.15
                    "Financial": 725.0,  # 7250 * 0.10
                    "Healthcare": 618.75,  # 12375 * 0.05
                    "Energy": -1600.0,  # 20000 * -0.08
                },
            }

            result = await risk_analyzer.run_sector_rotation_test(
                diversified_portfolio, sector_shocks
            )

            assert result.portfolio_pnl == -2500.0
            assert "Technology" in result.sector_impacts
            assert result.sector_impacts["Technology"] < 0  # Tech hurt by rotation
            assert result.sector_impacts["Financial"] > 0  # Financial benefits

    @pytest.mark.asyncio
    async def test_tail_risk_scenarios(self, risk_analyzer, diversified_portfolio):
        """Test tail risk scenario analysis."""
        tail_scenarios = [
            {"name": "Black Monday", "market_drop": -0.22, "volatility_spike": 3.0},
            {
                "name": "Flash Crash",
                "market_drop": -0.09,
                "volatility_spike": 5.0,
                "liquidity_shock": 0.5,
            },
            {
                "name": "Credit Crisis",
                "market_drop": -0.35,
                "credit_spread_widening": 0.03,
            },
        ]

        with patch.object(risk_analyzer, "_simulate_tail_event") as mock_tail:
            mock_tail.side_effect = [
                {"portfolio_pnl": -25000.0, "max_drawdown": -0.19},
                {"portfolio_pnl": -18000.0, "max_drawdown": -0.14},
                {"portfolio_pnl": -45000.0, "max_drawdown": -0.34},
            ]

            tail_results = await risk_analyzer.analyze_tail_risks(
                diversified_portfolio, tail_scenarios
            )

            assert len(tail_results) == 3

            # Credit crisis should be worst scenario
            credit_result = tail_results[2]
            assert credit_result.portfolio_pnl == -45000.0
            assert credit_result.max_drawdown < -0.30


class TestPerformanceAttribution:
    """Test performance attribution analysis."""

    @pytest.mark.asyncio
    async def test_sector_performance_attribution(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test sector-based performance attribution."""
        benchmark_returns = {
            "Technology": 0.08,  # Tech sector benchmark return
            "Financial": 0.05,  # Financial sector benchmark
            "Healthcare": 0.06,  # Healthcare sector benchmark
            "Energy": 0.03,  # Energy sector benchmark
        }

        with patch.object(risk_analyzer, "_calculate_sector_returns") as mock_returns:
            mock_returns.return_value = {
                "Technology": 0.095,  # Outperformed by 1.5%
                "Financial": 0.045,  # Underperformed by 0.5%
                "Healthcare": 0.070,  # Outperformed by 1.0%
                "Energy": 0.025,  # Underperformed by 0.5%
            }

            attribution = await risk_analyzer.calculate_performance_attribution(
                diversified_portfolio, benchmark_returns, period_days=90
            )

            assert isinstance(attribution, PerformanceAttribution)
            assert len(attribution.sector_contributions) == 4

            # Technology should have positive contribution (outperformed + large weight)
            tech_contribution = attribution.sector_contributions["Technology"]
            assert tech_contribution > 0

            # Total attribution should sum to portfolio excess return
            total_attribution = sum(attribution.sector_contributions.values())
            assert abs(total_attribution - attribution.total_excess_return) < 0.001

    @pytest.mark.asyncio
    async def test_stock_specific_attribution(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test stock-specific performance attribution."""
        with patch.object(risk_analyzer, "_calculate_stock_alpha") as mock_alpha:
            mock_alpha.return_value = {
                "AAPL": 0.02,  # 2% alpha
                "GOOGL": -0.01,  # -1% alpha
                "JPM": 0.005,  # 0.5% alpha
                "JNJ": 0.015,  # 1.5% alpha
                "XOM": -0.008,  # -0.8% alpha
            }

            stock_attribution = await risk_analyzer.calculate_stock_attribution(
                diversified_portfolio, period_days=30
            )

            assert len(stock_attribution) == 5

            # AAPL should contribute positively (positive alpha + significant weight)
            aapl_weight = 15500 / 131125  # Position value / total portfolio
            expected_aapl_contribution = 0.02 * aapl_weight

            assert abs(stock_attribution["AAPL"] - expected_aapl_contribution) < 0.001

    @pytest.mark.asyncio
    async def test_factor_based_attribution(self, risk_analyzer, diversified_portfolio):
        """Test factor-based performance attribution."""
        factor_exposures = {
            "market": 1.15,  # Portfolio beta
            "size": -0.25,  # Large cap tilt
            "value": 0.10,  # Slight value tilt
            "momentum": 0.35,  # Momentum exposure
            "quality": 0.20,  # Quality exposure
        }

        factor_returns = {
            "market": 0.08,
            "size": -0.02,
            "value": 0.03,
            "momentum": 0.12,
            "quality": 0.06,
        }

        with patch.object(
            risk_analyzer, "_calculate_factor_exposures"
        ) as mock_exposures:
            mock_exposures.return_value = factor_exposures

            factor_attribution = risk_analyzer.calculate_factor_attribution(
                factor_exposures, factor_returns
            )

            assert len(factor_attribution) == 5

            # Factor contributions should equal exposure * factor return
            assert abs(factor_attribution["market"] - (1.15 * 0.08)) < 0.001
            assert abs(factor_attribution["momentum"] - (0.35 * 0.12)) < 0.001


class TestDrawdownAnalysis:
    """Test drawdown analysis and risk monitoring."""

    def test_maximum_drawdown_calculation(self, risk_analyzer):
        """Test maximum drawdown calculation."""
        # Mock portfolio values over time
        portfolio_values = [
            100000,
            105000,
            102000,
            108000,
            95000,  # Max drawdown here: 108000 -> 95000
            98000,
            103000,
            101000,
            110000,
            115000,
        ]

        drawdown_analysis = risk_analyzer.calculate_drawdown_analysis(portfolio_values)

        assert isinstance(drawdown_analysis, DrawdownAnalysis)

        # Maximum drawdown should be (108000 - 95000) / 108000 = 12.04%
        expected_max_drawdown = (108000 - 95000) / 108000
        assert abs(drawdown_analysis.max_drawdown - expected_max_drawdown) < 0.001

        # Peak value should be 115000 (final value)
        assert drawdown_analysis.peak_value == 115000

        # Current drawdown should be 0 (at peak)
        assert drawdown_analysis.current_drawdown == 0.0

    def test_underwater_period_analysis(self, risk_analyzer):
        """Test underwater period analysis."""
        # Portfolio that experiences prolonged drawdown
        portfolio_values = [
            100000,
            95000,
            90000,
            88000,
            92000,
            89000,
            94000,
            98000,
            101000,  # Recovery
        ]

        drawdown_analysis = risk_analyzer.calculate_drawdown_analysis(portfolio_values)

        # Should identify underwater period from index 1 to 7 (7 periods)
        assert drawdown_analysis.longest_underwater_period >= 7

        # Recovery factor should be > 1 (recovered from drawdown)
        assert drawdown_analysis.recovery_factor > 1.0

    @pytest.mark.asyncio
    async def test_rolling_drawdown_monitoring(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test rolling drawdown monitoring."""
        # Mock historical portfolio values
        with patch.object(
            risk_analyzer, "_get_historical_portfolio_values"
        ) as mock_values:
            dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
            values = [
                130000 + i * 1000 + (i % 5) * 500 for i in range(30)
            ]  # Trending up with volatility
            mock_values.return_value = list(zip(dates, values, strict=False))

            rolling_drawdowns = await risk_analyzer.calculate_rolling_drawdowns(
                diversified_portfolio, window_days=10
            )

            assert len(rolling_drawdowns) >= 20  # At least 20 rolling windows

            # Each entry should have date and drawdown
            for date, drawdown in rolling_drawdowns:
                assert isinstance(date, datetime)
                assert drawdown >= 0.0  # Drawdowns are non-negative

    def test_drawdown_risk_metrics(self, risk_analyzer):
        """Test drawdown-based risk metrics."""
        portfolio_values = [100000, 95000, 92000, 89000, 94000, 97000, 99000, 102000]

        risk_metrics = risk_analyzer.calculate_drawdown_risk_metrics(portfolio_values)

        # Should include Calmar ratio, Sterling ratio, etc.
        assert "calmar_ratio" in risk_metrics
        assert "sterling_ratio" in risk_metrics
        assert "pain_index" in risk_metrics

        # Calmar ratio = Annual return / Max drawdown
        assert risk_metrics["calmar_ratio"] > 0

        # Pain index should be positive (measures sustained underperformance)
        assert risk_metrics["pain_index"] >= 0


class TestRiskBudgeting:
    """Test risk budgeting and allocation optimization."""

    @pytest.mark.asyncio
    async def test_equal_risk_contribution_portfolio(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test Equal Risk Contribution (ERC) portfolio construction."""
        with patch.object(
            risk_analyzer, "_calculate_risk_contributions"
        ) as mock_contributions:
            # Start with unequal contributions
            mock_contributions.return_value = {
                "AAPL": 0.15,
                "GOOGL": 0.30,
                "JPM": 0.25,
                "JNJ": 0.10,
                "XOM": 0.20,
            }

            # Mock optimization to equal contributions
            dict.fromkeys(["AAPL", "GOOGL", "JPM", "JNJ", "XOM"], 0.2)

            erc_weights = await risk_analyzer.calculate_erc_weights(
                diversified_portfolio
            )

            assert len(erc_weights) == 5
            assert all(0 < weight < 1 for weight in erc_weights.values())

            # Weights should sum to 1
            total_weight = sum(erc_weights.values())
            assert abs(total_weight - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_risk_parity_optimization(self, risk_analyzer, diversified_portfolio):
        """Test risk parity optimization."""
        target_risk_budget = {
            "AAPL": 0.25,  # 25% of risk budget
            "GOOGL": 0.25,  # 25% of risk budget
            "JPM": 0.20,  # 20% of risk budget
            "JNJ": 0.15,  # 15% of risk budget
            "XOM": 0.15,  # 15% of risk budget
        }

        with patch.object(risk_analyzer, "_optimize_risk_parity") as mock_optimize:
            mock_optimize.return_value = {
                "AAPL": 0.18,
                "GOOGL": 0.15,
                "JPM": 0.22,
                "JNJ": 0.28,
                "XOM": 0.17,
            }

            optimized_weights = await risk_analyzer.optimize_risk_parity_weights(
                diversified_portfolio, target_risk_budget
            )

            assert len(optimized_weights) == 5
            assert abs(sum(optimized_weights.values()) - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_risk_budgeting_monitoring(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test ongoing risk budget monitoring."""
        target_budget = {
            "AAPL": 0.20,
            "GOOGL": 0.20,
            "JPM": 0.20,
            "JNJ": 0.20,
            "XOM": 0.20,
        }

        with patch.object(
            risk_analyzer, "_calculate_current_risk_contributions"
        ) as mock_current:
            mock_current.return_value = {
                "AAPL": 0.18,
                "GOOGL": 0.25,
                "JPM": 0.19,
                "JNJ": 0.15,
                "XOM": 0.23,
            }

            budget_analysis = await risk_analyzer.analyze_risk_budget_deviations(
                diversified_portfolio, target_budget
            )

            assert "deviations" in budget_analysis
            assert "max_deviation" in budget_analysis
            assert "total_tracking_error" in budget_analysis

            # GOOGL should have largest deviation (0.25 vs 0.20 target)
            assert budget_analysis["deviations"]["GOOGL"] == 0.05
            assert budget_analysis["max_deviation"] == 0.05


class TestAdvancedRiskMetrics:
    """Test advanced risk metrics and analytics."""

    @pytest.mark.asyncio
    async def test_tail_dependency_analysis(
        self, risk_analyzer, diversified_portfolio, mock_market_data
    ):
        """Test tail dependency analysis between positions."""
        with patch.object(
            risk_analyzer, "_calculate_tail_dependencies"
        ) as mock_tail_dep:
            # Mock copula-based tail dependencies
            mock_tail_dep.return_value = {
                ("AAPL", "GOOGL"): 0.45,  # Moderate tail dependence
                ("AAPL", "JPM"): 0.65,  # Higher tail dependence
                ("JPM", "XOM"): 0.35,  # Lower tail dependence
                ("JNJ", "XOM"): 0.20,  # Low tail dependence
            }

            tail_deps = await risk_analyzer.analyze_tail_dependencies(
                diversified_portfolio
            )

            assert len(tail_deps) >= 4

            # All dependencies should be between 0 and 1
            for pair, dependency in tail_deps.items():
                assert 0 <= dependency <= 1
                assert len(pair) == 2  # Pair of symbols

    @pytest.mark.asyncio
    async def test_regime_dependent_risk_analysis(
        self, risk_analyzer, diversified_portfolio
    ):
        """Test regime-dependent risk analysis."""
        market_regimes = ["bull", "bear", "sideways"]

        with patch.object(risk_analyzer, "_identify_market_regime") as mock_regime:
            mock_regime.return_value = "bull"

            with patch.object(
                risk_analyzer, "_calculate_regime_risk_metrics"
            ) as mock_metrics:
                mock_metrics.return_value = {
                    "bull": {"var_95": 3500.0, "correlation_avg": 0.65},
                    "bear": {"var_95": 8500.0, "correlation_avg": 0.85},
                    "sideways": {"var_95": 2200.0, "correlation_avg": 0.45},
                }

                regime_analysis = await risk_analyzer.analyze_regime_dependent_risk(
                    diversified_portfolio, regimes=market_regimes
                )

                assert len(regime_analysis) == 3

                # Bear market should have highest VaR
                assert (
                    regime_analysis["bear"]["var_95"]
                    > regime_analysis["bull"]["var_95"]
                )
                assert (
                    regime_analysis["bear"]["var_95"]
                    > regime_analysis["sideways"]["var_95"]
                )

                # Bear market should have highest correlations
                assert (
                    regime_analysis["bear"]["correlation_avg"]
                    > regime_analysis["bull"]["correlation_avg"]
                )

    @pytest.mark.asyncio
    async def test_liquidity_adjusted_var(self, risk_analyzer, diversified_portfolio):
        """Test liquidity-adjusted Value at Risk calculation."""
        liquidity_metrics = {
            "AAPL": {"bid_ask_spread": 0.01, "avg_daily_volume": 50000000},
            "GOOGL": {"bid_ask_spread": 0.50, "avg_daily_volume": 1500000},
            "JPM": {"bid_ask_spread": 0.05, "avg_daily_volume": 15000000},
            "JNJ": {"bid_ask_spread": 0.03, "avg_daily_volume": 8000000},
            "XOM": {"bid_ask_spread": 0.02, "avg_daily_volume": 25000000},
        }

        with patch.object(risk_analyzer, "_get_liquidity_data") as mock_liquidity:
            mock_liquidity.return_value = liquidity_metrics

            lvar_result = await risk_analyzer.calculate_liquidity_adjusted_var(
                diversified_portfolio, confidence_level=0.95, time_horizon=1
            )

            assert isinstance(lvar_result, VaRResult)
            assert lvar_result.method == "liquidity_adjusted"

            # LVaR should be higher than regular VaR due to liquidity costs
            regular_var = await risk_analyzer.calculate_parametric_var(
                diversified_portfolio, 0.95, 1
            )
            assert lvar_result.var_amount >= regular_var.var_amount
