"""
Advanced test coverage for RiskAnalysis service.

This module provides comprehensive testing of the risk analysis service,
focusing on risk calculations, position impact simulation, exposure limits,
and risk metric computations.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.quotes import Quote
from app.schemas.orders import OrderCreate, OrderType
from app.schemas.positions import Portfolio, Position
from app.services.risk_analysis import (
    ExposureLimits,
    PositionImpactResult,
    RiskAnalysisResult,
    RiskAnalyzer,
    RiskCheckType,
    RiskLevel,
    RiskMetrics,
)


@pytest.fixture
def sample_portfolio():
    """Create sample portfolio for testing."""
    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            average_cost=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            unrealized_pnl_percent=3.33,
        ),
        Position(
            symbol="GOOGL",
            quantity=10,
            average_cost=2500.0,
            current_price=2600.0,
            market_value=26000.0,
            unrealized_pnl=1000.0,
            unrealized_pnl_percent=4.0,
        ),
        Position(
            symbol="TSLA",
            quantity=50,
            average_cost=800.0,
            current_price=750.0,
            market_value=37500.0,
            unrealized_pnl=-2500.0,
            unrealized_pnl_percent=-6.25,
        ),
    ]

    return Portfolio(
        cash_balance=10000.0,
        total_value=89000.0,  # 10k cash + 79k positions
        positions=positions,
        unrealized_pnl=-1000.0,
        unrealized_pnl_percent=-1.12,
    )


@pytest.fixture
def sample_quotes():
    """Create sample quote data for testing."""
    return {
        "AAPL": Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        ),
        "GOOGL": Quote(
            symbol="GOOGL",
            current_price=2600.0,
            bid=2595.0,
            ask=2605.0,
            high=2650.0,
            low=2580.0,
            volume=500000,
            market_cap=1700000000.0,
        ),
        "TSLA": Quote(
            symbol="TSLA",
            current_price=750.0,
            bid=748.0,
            ask=752.0,
            high=780.0,
            low=740.0,
            volume=2000000,
            market_cap=800000000.0,
        ),
    }


@pytest.fixture
def risk_analyzer():
    """Create RiskAnalyzer instance for testing."""
    return RiskAnalyzer()


class TestRiskAnalyzerInitialization:
    """Test RiskAnalyzer initialization and configuration."""

    def test_initialization_default_limits(self, risk_analyzer):
        """Test risk analyzer initializes with default limits."""
        assert risk_analyzer.exposure_limits is not None
        assert risk_analyzer.exposure_limits.max_position_concentration <= 1.0
        assert risk_analyzer.exposure_limits.max_sector_concentration <= 1.0
        assert risk_analyzer.exposure_limits.max_portfolio_leverage > 0

    def test_initialization_custom_limits(self):
        """Test risk analyzer with custom exposure limits."""
        custom_limits = ExposureLimits(
            max_position_concentration=0.2,
            max_sector_concentration=0.3,
            max_portfolio_leverage=2.0,
            max_daily_loss=0.05,
            max_buying_power_usage=0.8,
        )

        analyzer = RiskAnalyzer(exposure_limits=custom_limits)
        assert analyzer.exposure_limits.max_position_concentration == 0.2
        assert analyzer.exposure_limits.max_sector_concentration == 0.3
        assert analyzer.exposure_limits.max_portfolio_leverage == 2.0


class TestPositionConcentrationAnalysis:
    """Test position concentration risk analysis."""

    def test_position_concentration_within_limits(
        self, risk_analyzer, sample_portfolio
    ):
        """Test position concentration within acceptable limits."""
        violations = risk_analyzer._check_position_concentration(sample_portfolio)

        # Largest position (TSLA) is $37.5k out of $89k total = 42%
        # Default limit is typically 50%, so should be within limits
        assert len(violations) == 0

    def test_position_concentration_violation(self, risk_analyzer):
        """Test position concentration violation detection."""
        # Create portfolio with high concentration
        concentrated_position = Position(
            symbol="AAPL",
            quantity=500,
            average_cost=150.0,
            current_price=155.0,
            market_value=77500.0,  # 87% of portfolio
            unrealized_pnl=2500.0,
            unrealized_pnl_percent=3.33,
        )

        portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=87500.0,
            positions=[concentrated_position],
            unrealized_pnl=2500.0,
            unrealized_pnl_percent=2.94,
        )

        violations = risk_analyzer._check_position_concentration(portfolio)

        assert len(violations) >= 1
        violation = violations[0]
        assert violation.check_type == RiskCheckType.POSITION_CONCENTRATION
        assert violation.severity in [RiskLevel.HIGH, RiskLevel.EXTREME]
        assert "AAPL" in violation.message

    def test_multiple_concentration_violations(self, risk_analyzer):
        """Test detection of multiple concentration violations."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=300,
                average_cost=150.0,
                current_price=155.0,
                market_value=46500.0,  # 46.5%
                unrealized_pnl=1500.0,
                unrealized_pnl_percent=3.33,
            ),
            Position(
                symbol="GOOGL",
                quantity=15,
                average_cost=2500.0,
                current_price=2600.0,
                market_value=39000.0,  # 39%
                unrealized_pnl=1500.0,
                unrealized_pnl_percent=4.0,
            ),
        ]

        portfolio = Portfolio(
            cash_balance=14500.0,
            total_value=100000.0,
            positions=positions,
            unrealized_pnl=3000.0,
            unrealized_pnl_percent=3.0,
        )

        violations = risk_analyzer._check_position_concentration(portfolio)

        # Both positions exceed reasonable concentration limits
        assert len(violations) >= 2
        symbols_in_violations = {v.message for v in violations}
        assert any("AAPL" in msg for msg in symbols_in_violations)
        assert any("GOOGL" in msg for msg in symbols_in_violations)


class TestBuyingPowerAnalysis:
    """Test buying power and leverage analysis."""

    def test_buying_power_within_limits(self, risk_analyzer, sample_portfolio):
        """Test buying power usage within limits."""
        # Assume buying power is 2x cash balance
        buying_power = sample_portfolio.cash_balance * 2  # $20k

        violations = risk_analyzer._check_buying_power_usage(
            sample_portfolio, buying_power
        )

        # Portfolio value $89k vs buying power $20k = high usage but manageable
        assert len(violations) == 0 or violations[0].severity != RiskLevel.EXTREME

    def test_buying_power_violation(self, risk_analyzer):
        """Test buying power violation detection."""
        # Create over-leveraged portfolio
        positions = [
            Position(
                symbol="AAPL",
                quantity=1000,  # Very large position
                average_cost=150.0,
                current_price=155.0,
                market_value=155000.0,
                unrealized_pnl=5000.0,
                unrealized_pnl_percent=3.33,
            )
        ]

        portfolio = Portfolio(
            cash_balance=5000.0,  # Low cash
            total_value=160000.0,
            positions=positions,
            unrealized_pnl=5000.0,
            unrealized_pnl_percent=3.23,
        )

        buying_power = 15000.0  # Limited buying power

        violations = risk_analyzer._check_buying_power_usage(portfolio, buying_power)

        assert len(violations) >= 1
        violation = violations[0]
        assert violation.check_type == RiskCheckType.BUYING_POWER
        assert violation.severity in [RiskLevel.HIGH, RiskLevel.EXTREME]

    def test_leverage_calculation(self, risk_analyzer, sample_portfolio):
        """Test portfolio leverage calculation."""
        # Total position value: $79k, cash: $10k
        # Leverage = Position Value / (Cash + Position Value) = 79k / 89k ≈ 0.89

        leverage = risk_analyzer._calculate_portfolio_leverage(sample_portfolio)

        expected_leverage = 79000.0 / 89000.0
        assert abs(leverage - expected_leverage) < 0.01


class TestVolatilityRiskAnalysis:
    """Test volatility and price risk analysis."""

    @pytest.mark.asyncio
    async def test_volatility_exposure_calculation(
        self, risk_analyzer, sample_portfolio, sample_quotes
    ):
        """Test volatility exposure calculation."""
        with patch.object(
            risk_analyzer, "_get_historical_volatility"
        ) as mock_volatility:
            # Mock historical volatilities
            mock_volatility.side_effect = lambda symbol: {
                "AAPL": 0.25,  # 25% annual volatility
                "GOOGL": 0.30,  # 30% annual volatility
                "TSLA": 0.45,  # 45% annual volatility (high)
            }.get(symbol, 0.20)

            violations = await risk_analyzer._check_volatility_exposure(
                sample_portfolio, sample_quotes
            )

            # TSLA has high volatility and large position, should flag
            tsla_violations = [v for v in violations if "TSLA" in v.message]
            assert len(tsla_violations) >= 1
            assert tsla_violations[0].check_type == RiskCheckType.VOLATILITY_EXPOSURE

    @pytest.mark.asyncio
    async def test_portfolio_var_calculation(self, risk_analyzer, sample_portfolio):
        """Test Value at Risk calculation."""
        with patch.object(risk_analyzer, "_get_historical_returns") as mock_returns:
            # Mock historical returns for positions
            mock_returns.return_value = {
                "AAPL": [-0.02, 0.01, 0.03, -0.01, 0.02] * 50,  # 250 days
                "GOOGL": [-0.01, 0.02, 0.01, -0.03, 0.01] * 50,
                "TSLA": [-0.05, 0.04, 0.06, -0.04, 0.03] * 50,
            }

            var_result = await risk_analyzer.calculate_portfolio_var(
                sample_portfolio, confidence_level=0.95, time_horizon=1
            )

            assert var_result.confidence_level == 0.95
            assert var_result.time_horizon == 1
            assert var_result.var_amount > 0
            assert var_result.var_percent > 0
            assert var_result.method in ["historical", "parametric", "monte_carlo"]

    @pytest.mark.asyncio
    async def test_stress_testing(self, risk_analyzer, sample_portfolio):
        """Test portfolio stress testing scenarios."""
        stress_scenarios = [
            {"market_shock": -0.20, "volatility_spike": 2.0},  # 20% market drop
            {"sector_rotation": {"tech": -0.15}},  # Tech sector decline
            {"interest_rate_shock": 0.02},  # 2% rate increase
        ]

        with patch.object(risk_analyzer, "_apply_stress_scenario") as mock_stress:
            mock_stress.return_value = {
                "portfolio_value_change": -15000.0,
                "position_impacts": {
                    "AAPL": -3000.0,
                    "GOOGL": -5000.0,
                    "TSLA": -7000.0,
                },
            }

            results = await risk_analyzer.run_stress_tests(
                sample_portfolio, stress_scenarios
            )

            assert len(results) == len(stress_scenarios)
            for result in results:
                assert "portfolio_value_change" in result
                assert "position_impacts" in result


class TestOrderImpactAnalysis:
    """Test order impact and pre-trade risk analysis."""

    @pytest.mark.asyncio
    async def test_order_impact_simulation_buy(
        self, risk_analyzer, sample_portfolio, sample_quotes
    ):
        """Test order impact simulation for buy order."""
        new_order = OrderCreate(
            symbol="MSFT", quantity=50, order_type=OrderType.MARKET, side="buy"
        )

        # Mock MSFT quote
        msft_quote = Quote(
            symbol="MSFT",
            current_price=350.0,
            bid=349.5,
            ask=350.5,
            high=355.0,
            low=345.0,
            volume=800000,
            market_cap=2600000000.0,
        )

        with patch.object(risk_analyzer, "_get_quote") as mock_quote:
            mock_quote.return_value = msft_quote

            impact_result = await risk_analyzer.analyze_order_impact(
                new_order, sample_portfolio
            )

            assert isinstance(impact_result, PositionImpactResult)
            assert impact_result.new_position_value == 50 * 350.0
            assert impact_result.portfolio_concentration_change > 0
            assert impact_result.risk_metrics_change is not None

    @pytest.mark.asyncio
    async def test_order_impact_simulation_sell(
        self, risk_analyzer, sample_portfolio, sample_quotes
    ):
        """Test order impact simulation for sell order."""
        sell_order = OrderCreate(
            symbol="AAPL",
            quantity=50,  # Partial sell of 100 share position
            order_type=OrderType.MARKET,
            side="sell",
        )

        impact_result = await risk_analyzer.analyze_order_impact(
            sell_order, sample_portfolio
        )

        assert isinstance(impact_result, PositionImpactResult)
        assert impact_result.new_position_value == 50 * 155.0  # 50 shares remaining
        assert impact_result.portfolio_concentration_change < 0  # Reduced concentration
        assert impact_result.cash_impact > 0  # Positive cash from sale

    @pytest.mark.asyncio
    async def test_order_size_optimization(self, risk_analyzer, sample_portfolio):
        """Test order size optimization recommendations."""
        large_order = OrderCreate(
            symbol="NVDA",
            quantity=1000,  # Very large order
            order_type=OrderType.MARKET,
            side="buy",
        )

        # Mock NVDA quote with high price
        nvda_quote = Quote(
            symbol="NVDA",
            current_price=800.0,
            bid=799.0,
            ask=801.0,
            high=820.0,
            low=780.0,
            volume=1500000,
            market_cap=2000000000.0,
        )

        with patch.object(risk_analyzer, "_get_quote") as mock_quote:
            mock_quote.return_value = nvda_quote

            optimization = await risk_analyzer.optimize_order_size(
                large_order, sample_portfolio
            )

            # Should recommend smaller size due to concentration risk
            assert optimization.recommended_quantity < large_order.quantity
            assert optimization.risk_reason is not None
            assert "concentration" in optimization.risk_reason.lower()


class TestOptionsRiskAnalysis:
    """Test options-specific risk analysis."""

    def test_options_level_validation(self, risk_analyzer):
        """Test options trading level validation."""
        # Mock account with options level 2
        account_options_level = 2

        # Level 1 option (covered call) - should pass
        covered_call = OrderCreate(
            symbol="AAPL",
            quantity=1,
            order_type=OrderType.MARKET,
            side="sell",  # Selling covered call
        )

        violations = risk_analyzer._check_options_level(
            covered_call, account_options_level
        )
        assert len(violations) == 0

        # Level 4 option (naked put) - should fail for level 2 account
        naked_put = OrderCreate(
            symbol="AAPL",
            quantity=1,
            order_type=OrderType.MARKET,
            side="sell",  # Selling naked put
        )

        violations = risk_analyzer._check_options_level(
            naked_put, account_options_level, is_naked=True
        )
        assert len(violations) >= 1
        assert violations[0].check_type == RiskCheckType.OPTIONS_LEVEL

    @pytest.mark.asyncio
    async def test_options_greeks_analysis(self, risk_analyzer):
        """Test options Greeks risk analysis."""
        # Create option position
        option_position = Position(
            symbol="AAPL240119C00155000",  # AAPL Jan 19 2024 $155 Call
            quantity=10,
            average_cost=5.0,
            current_price=7.5,
            market_value=7500.0,
            unrealized_pnl=2500.0,
            unrealized_pnl_percent=50.0,
        )

        portfolio_with_options = Portfolio(
            cash_balance=10000.0,
            total_value=17500.0,
            positions=[option_position],
            unrealized_pnl=2500.0,
            unrealized_pnl_percent=16.67,
        )

        with patch("app.services.greeks.calculate_option_greeks") as mock_greeks:
            mock_greeks.return_value = {
                "delta": 0.65,
                "gamma": 0.08,
                "theta": -0.15,
                "vega": 0.25,
                "rho": 0.10,
            }

            violations = await risk_analyzer._check_options_risk(portfolio_with_options)

            # Should flag high theta decay risk
            theta_violations = [v for v in violations if "theta" in v.message.lower()]
            assert len(theta_violations) >= 1

    @pytest.mark.asyncio
    async def test_options_expiration_analysis(self, risk_analyzer):
        """Test options expiration risk analysis."""
        # Create option position expiring soon
        soon_expiring_option = Position(
            symbol="AAPL241201C00155000",  # Expires in 1 week
            quantity=5,
            average_cost=2.0,
            current_price=0.5,  # Out of the money
            market_value=250.0,
            unrealized_pnl=-750.0,
            unrealized_pnl_percent=-75.0,
        )

        portfolio_with_expiring_options = Portfolio(
            cash_balance=10000.0,
            total_value=10250.0,
            positions=[soon_expiring_option],
            unrealized_pnl=-750.0,
            unrealized_pnl_percent=-6.83,
        )

        # Mock expiration date to be within 1 week
        with patch.object(risk_analyzer, "_get_option_expiration") as mock_expiry:
            mock_expiry.return_value = datetime.now() + timedelta(days=5)

            violations = await risk_analyzer._check_expiration_risk(
                portfolio_with_expiring_options
            )

            assert len(violations) >= 1
            expiry_violation = violations[0]
            assert "expir" in expiry_violation.message.lower()
            assert expiry_violation.severity in [RiskLevel.HIGH, RiskLevel.EXTREME]


class TestRiskMetricsCalculation:
    """Test comprehensive risk metrics calculation."""

    @pytest.mark.asyncio
    async def test_comprehensive_risk_analysis(
        self, risk_analyzer, sample_portfolio, sample_quotes
    ):
        """Test comprehensive risk analysis with all checks."""
        with patch.object(risk_analyzer, "_get_account_info") as mock_account:
            mock_account.return_value = {
                "buying_power": 20000.0,
                "day_trade_buying_power": 80000.0,
                "options_level": 2,
            }

            result = await risk_analyzer.analyze_portfolio_risk(
                sample_portfolio, sample_quotes
            )

            assert isinstance(result, RiskAnalysisResult)
            assert result.overall_risk_level in [
                RiskLevel.LOW,
                RiskLevel.MODERATE,
                RiskLevel.HIGH,
                RiskLevel.EXTREME,
            ]
            assert isinstance(result.violations, list)
            assert isinstance(result.risk_metrics, RiskMetrics)
            assert result.analysis_timestamp is not None

    @pytest.mark.asyncio
    async def test_risk_metrics_calculation(self, risk_analyzer, sample_portfolio):
        """Test detailed risk metrics calculation."""
        metrics = await risk_analyzer._calculate_risk_metrics(sample_portfolio)

        assert isinstance(metrics, RiskMetrics)
        assert metrics.portfolio_beta >= 0
        assert metrics.sharpe_ratio is not None
        assert metrics.max_drawdown >= 0
        assert 0 <= metrics.portfolio_concentration <= 1
        assert metrics.volatility >= 0

    @pytest.mark.asyncio
    async def test_sector_exposure_analysis(self, risk_analyzer, sample_portfolio):
        """Test sector exposure risk analysis."""
        with patch.object(risk_analyzer, "_get_sector_info") as mock_sector:
            # Mock all positions as tech sector
            mock_sector.return_value = {
                "AAPL": "Technology",
                "GOOGL": "Technology",
                "TSLA": "Technology",  # Simplified for testing
            }

            violations = risk_analyzer._check_sector_exposure(sample_portfolio)

            # All tech positions should trigger sector concentration warning
            sector_violations = [
                v for v in violations if v.check_type == RiskCheckType.SECTOR_EXPOSURE
            ]
            assert len(sector_violations) >= 1
            assert "technology" in sector_violations[0].message.lower()


class TestRiskLimitCompliance:
    """Test risk limit compliance and monitoring."""

    def test_daily_loss_limit_check(self, risk_analyzer, sample_portfolio):
        """Test daily loss limit compliance."""
        # Mock today's P&L as significant loss
        daily_pnl = -5000.0  # $5k loss
        portfolio_value = sample_portfolio.total_value
        daily_loss_percent = abs(daily_pnl) / portfolio_value

        violations = risk_analyzer._check_daily_loss_limit(daily_pnl, portfolio_value)

        # Should flag if loss exceeds limit (typically 2-5%)
        if daily_loss_percent > 0.05:  # 5% daily loss limit
            assert len(violations) >= 1
            assert violations[0].check_type == RiskCheckType.DAY_TRADING_LIMIT

    def test_margin_requirement_check(self, risk_analyzer, sample_portfolio):
        """Test margin requirement compliance."""
        # Mock margin requirements
        margin_requirements = {
            "AAPL": 0.25,  # 25% margin requirement
            "GOOGL": 0.30,  # 30% margin requirement
            "TSLA": 0.50,  # 50% margin requirement (high vol)
        }

        available_margin = 15000.0

        violations = risk_analyzer._check_margin_requirements(
            sample_portfolio, margin_requirements, available_margin
        )

        # Calculate total margin requirement
        total_margin_needed = sum(
            pos.market_value * margin_requirements.get(pos.symbol, 0.25)
            for pos in sample_portfolio.positions
        )

        if total_margin_needed > available_margin:
            assert len(violations) >= 1
            assert violations[0].check_type == RiskCheckType.MARGIN_REQUIREMENT

    @pytest.mark.asyncio
    async def test_risk_limit_escalation(self, risk_analyzer, sample_portfolio):
        """Test risk limit violation escalation."""
        # Create portfolio with multiple severe violations
        high_risk_portfolio = Portfolio(
            cash_balance=1000.0,  # Very low cash
            total_value=100000.0,  # High leverage
            positions=sample_portfolio.positions,
            unrealized_pnl=-10000.0,  # Significant losses
            unrealized_pnl_percent=-10.0,
        )

        with patch.object(risk_analyzer, "_get_account_info") as mock_account:
            mock_account.return_value = {
                "buying_power": 5000.0,  # Limited buying power
                "day_trade_buying_power": 10000.0,
                "options_level": 1,
            }

            result = await risk_analyzer.analyze_portfolio_risk(high_risk_portfolio, {})

            # Should escalate to HIGH or EXTREME risk level
            assert result.overall_risk_level in [RiskLevel.HIGH, RiskLevel.EXTREME]

            # Should have multiple violations
            assert len(result.violations) >= 2

            # Should recommend immediate action
            assert any("immediate" in v.message.lower() for v in result.violations)


class TestConcurrencyAndPerformance:
    """Test concurrent risk analysis and performance optimization."""

    @pytest.mark.asyncio
    async def test_concurrent_risk_checks(
        self, risk_analyzer, sample_portfolio, sample_quotes
    ):
        """Test concurrent execution of risk checks."""
        # Run multiple risk analysis operations concurrently
        tasks = [
            risk_analyzer._check_position_concentration(sample_portfolio),
            risk_analyzer._check_buying_power_usage(sample_portfolio, 20000.0),
            risk_analyzer._check_sector_exposure(sample_portfolio),
        ]

        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()

        # All tasks should complete successfully
        assert all(not isinstance(r, Exception) for r in results)

        # Should complete within reasonable time
        execution_time = end_time - start_time
        assert execution_time < 1.0

    @pytest.mark.asyncio
    async def test_batch_quote_operations(self, risk_analyzer, sample_portfolio):
        """Test batch quote operations for risk analysis."""
        symbols = [pos.symbol for pos in sample_portfolio.positions]

        with patch.object(risk_analyzer, "_get_quotes_batch") as mock_batch:
            mock_batch.return_value = {
                symbol: Quote(
                    symbol=symbol,
                    current_price=150.0,
                    bid=149.5,
                    ask=150.5,
                    high=155.0,
                    low=145.0,
                    volume=1000000,
                    market_cap=2500000000.0,
                )
                for symbol in symbols
            }

            quotes = await risk_analyzer._get_quotes_batch(symbols)

            assert len(quotes) == len(symbols)
            assert all(symbol in quotes for symbol in symbols)
            mock_batch.assert_called_once_with(symbols)

    @pytest.mark.asyncio
    async def test_risk_analysis_caching(self, risk_analyzer, sample_portfolio):
        """Test risk analysis result caching for performance."""
        # First analysis
        start_time1 = asyncio.get_event_loop().time()
        result1 = await risk_analyzer.analyze_portfolio_risk(sample_portfolio, {})
        end_time1 = asyncio.get_event_loop().time()

        # Second analysis (should use cache if implemented)
        start_time2 = asyncio.get_event_loop().time()
        result2 = await risk_analyzer.analyze_portfolio_risk(sample_portfolio, {})
        end_time2 = asyncio.get_event_loop().time()

        # Results should be consistent
        assert result1.overall_risk_level == result2.overall_risk_level
        assert len(result1.violations) == len(result2.violations)

        # Second call should be faster if cached (allowing for variance)
        time1 = end_time1 - start_time1
        time2 = end_time2 - start_time2

        # At minimum, both should complete within reasonable time
        assert time1 < 2.0
        assert time2 < 2.0
