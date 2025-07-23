"""
Test cases for pre-trade risk analysis and position impact simulation.

Tests risk analysis, position impact calculations, exposure limits,
and comprehensive risk checking functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from decimal import Decimal

from app.services.risk_analysis import (
    RiskAnalyzer,
    RiskLevel,
    RiskCheckType,
    RiskViolation,
    PositionImpact,
    PortfolioImpact,
    RiskAnalysisResult,
    RiskLimits,
    ExposureLimits,
    get_risk_analyzer,
    configure_risk_limits,
    risk_analyzer,
    PositionImpactResult,
    RiskMetrics,
)
from app.schemas.orders import Order, OrderType
from app.schemas.positions import Portfolio, Position
from app.models.quotes import Quote
from app.models.assets import Stock, Option, Call, Put


class TestRiskAnalyzer:
    """Test comprehensive risk analyzer functionality."""

    def test_analyzer_initialization(self):
        """Test risk analyzer initialization."""
        analyzer = RiskAnalyzer()
        
        assert analyzer is not None
        assert isinstance(analyzer.risk_limits, RiskLimits)
        assert isinstance(analyzer.sector_mappings, dict)
        assert isinstance(analyzer.volatility_rankings, dict)

    def test_analyzer_with_custom_limits(self):
        """Test analyzer initialization with custom risk limits."""
        custom_limits = RiskLimits(
            max_position_concentration=0.15,
            max_sector_exposure=0.30,
            max_leverage=1.5
        )
        
        analyzer = RiskAnalyzer(custom_limits)
        
        assert analyzer.risk_limits.max_position_concentration == 0.15
        assert analyzer.risk_limits.max_sector_exposure == 0.30
        assert analyzer.risk_limits.max_leverage == 1.5

    def test_global_analyzer_access(self):
        """Test global analyzer access functions."""
        global_analyzer = get_risk_analyzer()
        
        assert global_analyzer is not None
        assert isinstance(global_analyzer, RiskAnalyzer)
        assert global_analyzer is risk_analyzer

    def test_configure_risk_limits(self):
        """Test risk limits configuration."""
        new_limits = RiskLimits(max_position_concentration=0.10)
        
        configure_risk_limits(new_limits)
        
        updated_analyzer = get_risk_analyzer()
        assert updated_analyzer.risk_limits.max_position_concentration == 0.10

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
    def sample_order(self):
        """Create sample order for testing."""
        return Order(
            symbol="AAPL",
            quantity=50,
            order_type=OrderType.BUY,
            price=155.0
        )

    @pytest.fixture
    def sample_quote(self):
        """Create sample quote for testing."""
        return Quote(
            symbol="AAPL",
            price=155.0,
            bid=154.95,
            ask=155.05,
            midpoint=155.0,
            timestamp=datetime.now()
        )

    def test_analyze_order_basic(self, sample_order, sample_portfolio, sample_quote):
        """Test basic order risk analysis."""
        analyzer = RiskAnalyzer()
        
        result = analyzer.analyze_order(
            sample_order,
            sample_portfolio,
            sample_quote
        )
        
        assert isinstance(result, RiskAnalysisResult)
        assert result.order == sample_order
        assert isinstance(result.risk_level, RiskLevel)
        assert isinstance(result.violations, list)
        assert isinstance(result.portfolio_impact, PortfolioImpact)
        assert isinstance(result.position_impacts, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.can_execute, bool)
        assert isinstance(result.estimated_cost, (int, float))
        assert isinstance(result.margin_requirement, (int, float))

    def test_portfolio_impact_calculation(self, sample_order, sample_portfolio, sample_quote):
        """Test portfolio impact calculation."""
        analyzer = RiskAnalyzer()
        
        impact = analyzer._calculate_portfolio_impact(
            sample_order, sample_portfolio, sample_quote
        )
        
        assert isinstance(impact, PortfolioImpact)
        assert impact.total_value_before == sample_portfolio.total_value
        assert impact.cash_before == sample_portfolio.cash_balance
        assert impact.cash_after < impact.cash_before  # Buy order reduces cash
        assert isinstance(impact.positions_affected, list)
        assert isinstance(impact.new_positions, list)
        assert isinstance(impact.closed_positions, list)

    def test_position_impacts_calculation(self, sample_order, sample_portfolio, sample_quote):
        """Test position impacts calculation."""
        analyzer = RiskAnalyzer()
        
        impacts = analyzer._calculate_position_impacts(
            sample_order, sample_portfolio, sample_quote
        )
        
        assert isinstance(impacts, list)
        
        if impacts:  # If order affects existing positions
            for impact in impacts:
                assert isinstance(impact, PositionImpact)
                assert impact.symbol
                assert isinstance(impact.current_quantity, int)
                assert isinstance(impact.new_quantity, int)
                assert isinstance(impact.concentration_before, float)
                assert isinstance(impact.concentration_after, float)

    def test_single_position_impact_calculation(self, sample_portfolio, sample_quote):
        """Test single position impact calculation."""
        analyzer = RiskAnalyzer()
        
        # Order that affects existing AAPL position
        order = Order(
            symbol="AAPL",
            quantity=25,
            order_type=OrderType.BUY,
            price=155.0
        )
        
        existing_position = sample_portfolio.positions[0]  # AAPL position
        
        impact = analyzer._calculate_single_position_impact(
            existing_position, order, sample_quote, sample_portfolio
        )
        
        assert isinstance(impact, PositionImpact)
        assert impact.symbol == "AAPL"
        assert impact.current_quantity == 100
        assert impact.new_quantity == 125  # 100 + 25
        assert impact.concentration_after > impact.concentration_before

    def test_risk_checks_execution(self, sample_order, sample_portfolio, sample_quote):
        """Test comprehensive risk checks execution."""
        analyzer = RiskAnalyzer()
        
        portfolio_impact = analyzer._calculate_portfolio_impact(
            sample_order, sample_portfolio, sample_quote
        )
        
        violations = analyzer._perform_risk_checks(
            sample_order, sample_portfolio, portfolio_impact, "cash"
        )
        
        assert isinstance(violations, list)
        
        for violation in violations:
            assert isinstance(violation, RiskViolation)
            assert isinstance(violation.check_type, RiskCheckType)
            assert isinstance(violation.severity, RiskLevel)
            assert violation.message
            assert isinstance(violation.current_value, (int, float))
            assert isinstance(violation.limit_value, (int, float))

    def test_position_concentration_check(self, sample_portfolio):
        """Test position concentration limit checking."""
        analyzer = RiskAnalyzer()
        
        # Create order that would create high concentration
        large_order = Order(
            symbol="AAPL",
            quantity=500,  # Large position
            order_type=OrderType.BUY,
            price=155.0
        )
        
        quote = Quote(symbol="AAPL", price=155.0, bid=154.95, ask=155.05, midpoint=155.0, timestamp=datetime.now())
        
        portfolio_impact = analyzer._calculate_portfolio_impact(
            large_order, sample_portfolio, quote
        )
        
        violations = analyzer._check_position_concentration(
            large_order, sample_portfolio, portfolio_impact
        )
        
        # Should detect high concentration
        concentration_violations = [
            v for v in violations 
            if v.check_type == RiskCheckType.POSITION_CONCENTRATION
        ]
        
        if concentration_violations:
            assert concentration_violations[0].severity in [RiskLevel.HIGH, RiskLevel.MODERATE]

    def test_sector_exposure_check(self, sample_portfolio):
        """Test sector exposure limit checking."""
        analyzer = RiskAnalyzer()
        
        # Large tech order that increases sector exposure
        tech_order = Order(
            symbol="GOOGL",  # Another tech stock
            quantity=200,
            order_type=OrderType.BUY,
            price=2800.0
        )
        
        quote = Quote(symbol="GOOGL", price=2800.0, bid=2795.0, ask=2805.0, midpoint=2800.0, timestamp=datetime.now())
        
        portfolio_impact = analyzer._calculate_portfolio_impact(
            tech_order, sample_portfolio, quote
        )
        
        violations = analyzer._check_sector_exposure(
            tech_order, sample_portfolio, portfolio_impact
        )
        
        # May have sector exposure violations
        assert isinstance(violations, list)

    def test_leverage_check_margin_account(self, sample_portfolio):
        """Test leverage checking for margin accounts."""
        analyzer = RiskAnalyzer()
        
        # Create portfolio impact with high leverage
        portfolio_impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=150000.0,
            cash_before=50000.0,
            cash_after=10000.0,  # Low cash
            buying_power_before=50000.0,
            buying_power_after=10000.0,
            leverage_before=1.0,
            leverage_after=5.0,  # High leverage
            positions_affected=[],
            new_positions=[],
            closed_positions=[]
        )
        
        violations = analyzer._check_leverage(portfolio_impact)
        
        leverage_violations = [
            v for v in violations 
            if v.check_type == RiskCheckType.PORTFOLIO_LEVERAGE
        ]
        
        assert len(leverage_violations) > 0
        assert leverage_violations[0].severity == RiskLevel.HIGH

    def test_buying_power_check(self, sample_portfolio):
        """Test buying power checking."""
        analyzer = RiskAnalyzer()
        
        # Portfolio impact with insufficient buying power
        portfolio_impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=100000.0,
            cash_before=50000.0,
            cash_after=500.0,  # Very low cash remaining
            buying_power_before=50000.0,
            buying_power_after=500.0,  # Below minimum
            leverage_before=1.0,
            leverage_after=1.0,
            positions_affected=[],
            new_positions=[],
            closed_positions=[]
        )
        
        violations = analyzer._check_buying_power(portfolio_impact)
        
        buying_power_violations = [
            v for v in violations 
            if v.check_type == RiskCheckType.BUYING_POWER
        ]
        
        assert len(buying_power_violations) > 0
        assert buying_power_violations[0].severity == RiskLevel.EXTREME

    def test_options_level_check(self):
        """Test options trading level checking."""
        analyzer = RiskAnalyzer()
        
        # Create options order
        call_option = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        options_order = Order(
            symbol="AAPL240315C00155000",
            quantity=-1,  # Selling option
            order_type=OrderType.STO,
            price=5.0
        )
        
        violations = analyzer._check_options_level(options_order, call_option)
        
        # Should require level 4 for uncovered options
        assert len(violations) > 0
        level_violations = [
            v for v in violations 
            if v.check_type == RiskCheckType.OPTIONS_LEVEL
        ]
        
        if level_violations:
            assert level_violations[0].severity == RiskLevel.EXTREME

    def test_volatility_exposure_check(self, sample_portfolio):
        """Test volatility exposure checking."""
        analyzer = RiskAnalyzer()
        
        # Order in high volatility stock
        volatile_order = Order(
            symbol="TSLA",  # High volatility stock
            quantity=100,
            order_type=OrderType.BUY,
            price=200.0
        )
        
        quote = Quote(symbol="TSLA", price=200.0, bid=199.5, ask=200.5, midpoint=200.0, timestamp=datetime.now())
        
        portfolio_impact = analyzer._calculate_portfolio_impact(
            volatile_order, sample_portfolio, quote
        )
        
        violations = analyzer._check_volatility_exposure(
            volatile_order, sample_portfolio, portfolio_impact
        )
        
        # May have volatility exposure warnings
        assert isinstance(violations, list)

    def test_order_cost_calculation(self, sample_order, sample_quote):
        """Test order cost calculation."""
        analyzer = RiskAnalyzer()
        
        cost = analyzer._calculate_order_cost(sample_order, sample_quote)
        
        # Should include base cost + commission
        expected_base_cost = 50 * 155.0  # quantity * price
        assert cost > expected_base_cost  # Should include commission
        assert cost < expected_base_cost + 100  # Commission should be reasonable

    def test_margin_requirement_calculation_cash(self, sample_order, sample_quote):
        """Test margin requirement for cash account."""
        analyzer = RiskAnalyzer()
        
        margin = analyzer._calculate_margin_requirement(
            sample_order, sample_quote, "cash"
        )
        
        # Cash account requires full cost
        expected_cost = analyzer._calculate_order_cost(sample_order, sample_quote)
        assert margin == expected_cost

    def test_margin_requirement_calculation_margin(self, sample_quote):
        """Test margin requirement for margin account."""
        analyzer = RiskAnalyzer()
        
        stock_order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            price=155.0
        )
        
        margin = analyzer._calculate_margin_requirement(
            stock_order, sample_quote, "margin"
        )
        
        # Margin account - should be about 50% of order cost
        full_cost = analyzer._calculate_order_cost(stock_order, sample_quote)
        assert margin < full_cost  # Should be less than full cost
        assert margin > full_cost * 0.4  # Should be reasonable margin

    def test_greeks_impact_calculation_options(self):
        """Test Greeks impact calculation for options orders."""
        analyzer = RiskAnalyzer()
        
        call_option = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        options_order = Order(
            symbol="AAPL240315C00155000",
            quantity=2,
            order_type=OrderType.BTO,
            price=5.0
        )
        
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        quote = Quote(symbol="AAPL240315C00155000", price=5.0, bid=4.95, ask=5.05, midpoint=5.0, timestamp=datetime.now())
        
        with patch('app.services.greeks.calculate_option_greeks') as mock_greeks:
            mock_greeks.return_value = {
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.2,
                "rho": 0.1
            }
            
            greeks_impact = analyzer._calculate_greeks_impact(
                options_order, portfolio, quote
            )
            
            assert isinstance(greeks_impact, dict)
            assert "delta_change" in greeks_impact
            assert "gamma_change" in greeks_impact
            assert "theta_change" in greeks_impact
            assert "vega_change" in greeks_impact
            assert "rho_change" in greeks_impact

    def test_risk_level_determination(self):
        """Test overall risk level determination."""
        analyzer = RiskAnalyzer()
        
        # No violations - low risk
        no_violations = []
        risk_level = analyzer._determine_risk_level(no_violations)
        assert risk_level == RiskLevel.LOW
        
        # High severity violations
        high_violations = [
            RiskViolation(
                check_type=RiskCheckType.PORTFOLIO_LEVERAGE,
                severity=RiskLevel.HIGH,
                message="High leverage",
                current_value=3.0,
                limit_value=2.0
            )
        ]
        risk_level = analyzer._determine_risk_level(high_violations)
        assert risk_level == RiskLevel.HIGH
        
        # Extreme violations
        extreme_violations = [
            RiskViolation(
                check_type=RiskCheckType.BUYING_POWER,
                severity=RiskLevel.EXTREME,
                message="Insufficient funds",
                current_value=500.0,
                limit_value=1000.0
            )
        ]
        risk_level = analyzer._determine_risk_level(extreme_violations)
        assert risk_level == RiskLevel.EXTREME

    def test_warning_generation(self, sample_order, sample_portfolio, sample_quote):
        """Test warning message generation."""
        analyzer = RiskAnalyzer()
        
        portfolio_impact = analyzer._calculate_portfolio_impact(
            sample_order, sample_portfolio, sample_quote
        )
        
        violations = []  # No violations for this test
        
        warnings = analyzer._generate_warnings(
            sample_order, sample_portfolio, portfolio_impact, violations
        )
        
        assert isinstance(warnings, list)
        # Should generate warnings for various conditions

    def test_order_execution_determination(self, sample_portfolio):
        """Test order execution capability determination."""
        analyzer = RiskAnalyzer()
        
        # No extreme violations - should allow execution
        minor_violations = [
            RiskViolation(
                check_type=RiskCheckType.POSITION_CONCENTRATION,
                severity=RiskLevel.MODERATE,
                message="Moderate concentration",
                current_value=0.15,
                limit_value=0.10
            )
        ]
        
        portfolio_impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=110000.0,
            cash_before=50000.0,
            cash_after=40000.0,  # Positive cash
            buying_power_before=50000.0,
            buying_power_after=40000.0,
            leverage_before=1.0,
            leverage_after=1.1,
            positions_affected=[],
            new_positions=[],
            closed_positions=[]
        )
        
        can_execute = analyzer._can_execute_order(minor_violations, portfolio_impact)
        assert can_execute is True
        
        # Extreme violations - should block execution
        extreme_violations = [
            RiskViolation(
                check_type=RiskCheckType.BUYING_POWER,
                severity=RiskLevel.EXTREME,
                message="Insufficient funds",
                current_value=500.0,
                limit_value=1000.0
            )
        ]
        
        can_execute = analyzer._can_execute_order(extreme_violations, portfolio_impact)
        assert can_execute is False

    def test_required_options_level_mapping(self):
        """Test required options level mapping for different strategies."""
        analyzer = RiskAnalyzer()
        
        call_option = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        # Buying options
        buy_order = Order(
            symbol="AAPL240315C00155000",
            quantity=1,
            order_type=OrderType.BTO,
            price=5.0
        )
        
        level = analyzer._get_required_options_level(buy_order, call_option)
        assert level == 2  # Level 2 for buying options
        
        # Selling options
        sell_order = Order(
            symbol="AAPL240315C00155000",
            quantity=-1,
            order_type=OrderType.STO,
            price=5.0
        )
        
        level = analyzer._get_required_options_level(sell_order, call_option)
        assert level == 4  # Level 4 for uncovered selling

    def test_day_trade_detection(self, sample_order, sample_portfolio):
        """Test day trade detection logic."""
        analyzer = RiskAnalyzer()
        
        # Simplified test - actual implementation would need transaction history
        is_day_trade = analyzer._is_day_trade(sample_order, sample_portfolio)
        
        # Currently returns False (simplified implementation)
        assert isinstance(is_day_trade, bool)

    def test_safe_price_helpers(self, sample_quote):
        """Test safe price helper methods."""
        analyzer = RiskAnalyzer()
        
        # Test with valid price
        price = analyzer._get_safe_price(sample_quote)
        assert price == sample_quote.price
        
        # Test with None price (should use midpoint)
        quote_no_price = Quote(
            symbol="AAPL",
            price=None,
            bid=154.95,
            ask=155.05,
            midpoint=155.0,
            timestamp=datetime.now()
        )
        
        price = analyzer._get_safe_price(quote_no_price)
        assert price == quote_no_price.midpoint

    def test_safe_position_price_helpers(self):
        """Test safe position price helper methods."""
        analyzer = RiskAnalyzer()
        
        # Position with current price
        position_with_price = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            asset=Stock("AAPL")
        )
        
        price = analyzer._get_safe_position_price(position_with_price)
        assert price == 155.0
        
        # Position without current price (should use avg_price)
        position_no_current_price = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None,
            asset=Stock("AAPL")
        )
        
        price = analyzer._get_safe_position_price(position_no_current_price)
        assert price == 150.0


class TestDataClasses:
    """Test data classes used in risk analysis."""

    def test_exposure_limits(self):
        """Test ExposureLimits data class."""
        limits = ExposureLimits()
        
        assert limits.max_gross_exposure == 1000000.0
        assert limits.max_net_exposure == 500000.0
        assert limits.max_concentration_per_asset == 0.25
        
        # Test custom limits
        custom_limits = ExposureLimits(
            max_gross_exposure=2000000.0,
            max_net_exposure=1000000.0,
            max_concentration_per_asset=0.15
        )
        
        assert custom_limits.max_gross_exposure == 2000000.0
        assert custom_limits.max_concentration_per_asset == 0.15

    def test_risk_limits(self):
        """Test RiskLimits data class."""
        limits = RiskLimits()
        
        assert limits.max_position_concentration == 0.20
        assert limits.max_sector_exposure == 0.40
        assert limits.max_leverage == 2.0
        assert limits.min_buying_power == 1000.0
        assert limits.max_day_trades == 3
        assert limits.max_volatility_exposure == 0.30
        assert limits.options_trading_level == 2
        assert limits.margin_maintenance_buffer == 1.25

    def test_risk_violation(self):
        """Test RiskViolation data class."""
        violation = RiskViolation(
            check_type=RiskCheckType.POSITION_CONCENTRATION,
            severity=RiskLevel.HIGH,
            message="High concentration in AAPL",
            current_value=0.30,
            limit_value=0.20,
            recommendation="Reduce position size"
        )
        
        assert violation.check_type == RiskCheckType.POSITION_CONCENTRATION
        assert violation.severity == RiskLevel.HIGH
        assert violation.message == "High concentration in AAPL"
        assert violation.current_value == 0.30
        assert violation.limit_value == 0.20
        assert violation.recommendation == "Reduce position size"

    def test_position_impact(self):
        """Test PositionImpact data class."""
        impact = PositionImpact(
            symbol="AAPL",
            current_quantity=100,
            new_quantity=150,
            current_avg_price=150.0,
            new_avg_price=152.0,
            current_value=15500.0,
            new_value=23250.0,
            pnl_impact=500.0,
            concentration_before=0.15,
            concentration_after=0.23
        )
        
        assert impact.symbol == "AAPL"
        assert impact.current_quantity == 100
        assert impact.new_quantity == 150
        assert impact.concentration_after > impact.concentration_before

    def test_portfolio_impact(self):
        """Test PortfolioImpact data class."""
        impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=110000.0,
            cash_before=50000.0,
            cash_after=40000.0,
            buying_power_before=50000.0,
            buying_power_after=40000.0,
            leverage_before=1.0,
            leverage_after=1.1,
            positions_affected=[],
            new_positions=["AAPL"],
            closed_positions=[]
        )
        
        assert impact.total_value_before == 100000.0
        assert impact.total_value_after == 110000.0
        assert impact.cash_after < impact.cash_before
        assert len(impact.new_positions) == 1
        assert "AAPL" in impact.new_positions

    def test_risk_analysis_result(self):
        """Test RiskAnalysisResult data class."""
        order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            price=155.0
        )
        
        portfolio_impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=110000.0,
            cash_before=50000.0,
            cash_after=40000.0,
            buying_power_before=50000.0,
            buying_power_after=40000.0,
            leverage_before=1.0,
            leverage_after=1.1,
            positions_affected=[],
            new_positions=[],
            closed_positions=[]
        )
        
        result = RiskAnalysisResult(
            order=order,
            risk_level=RiskLevel.LOW,
            violations=[],
            portfolio_impact=portfolio_impact,
            position_impacts=[],
            warnings=[],
            can_execute=True,
            estimated_cost=15500.0,
            margin_requirement=15500.0
        )
        
        assert result.order == order
        assert result.risk_level == RiskLevel.LOW
        assert result.can_execute is True
        assert result.estimated_cost == 15500.0


class TestStubClasses:
    """Test stub classes that will be implemented later."""

    def test_position_impact_result_stub(self):
        """Test PositionImpactResult stub class."""
        result = PositionImpactResult()
        assert result is not None
        assert isinstance(result, PositionImpactResult)

    def test_risk_metrics_stub(self):
        """Test RiskMetrics stub class."""
        metrics = RiskMetrics()
        assert metrics is not None
        assert isinstance(metrics, RiskMetrics)


class TestComplexScenarios:
    """Test complex risk analysis scenarios."""

    @pytest.fixture
    def complex_portfolio(self):
        """Create complex portfolio with multiple asset types."""
        positions = [
            # Stocks
            Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0, asset=Stock("AAPL")),
            Position(symbol="MSFT", quantity=50, avg_price=300.0, current_price=310.0, asset=Stock("MSFT")),
            Position(symbol="TSLA", quantity=25, avg_price=200.0, current_price=220.0, asset=Stock("TSLA")),
            
            # Short position
            Position(symbol="META", quantity=-30, avg_price=280.0, current_price=275.0, asset=Stock("META")),
        ]
        
        return Portfolio(
            cash_balance=25000.0,
            positions=positions,
            total_value=150000.0,
            daily_pnl=2000.0,
            total_pnl=10000.0
        )

    def test_complex_portfolio_analysis(self, complex_portfolio):
        """Test risk analysis with complex portfolio."""
        analyzer = RiskAnalyzer()
        
        # Large order that would increase concentration
        large_order = Order(
            symbol="AAPL",
            quantity=200,
            order_type=OrderType.BUY,
            price=155.0
        )
        
        quote = Quote(symbol="AAPL", price=155.0, bid=154.95, ask=155.05, midpoint=155.0, timestamp=datetime.now())
        
        result = analyzer.analyze_order(large_order, complex_portfolio, quote)
        
        # Should detect various risk factors
        assert isinstance(result, RiskAnalysisResult)
        assert len(result.position_impacts) > 0  # Should affect existing AAPL position
        
        # Check for concentration warnings
        concentration_violations = [
            v for v in result.violations 
            if v.check_type == RiskCheckType.POSITION_CONCENTRATION
        ]
        
        # Large order might trigger concentration warnings
        if concentration_violations:
            assert concentration_violations[0].current_value > concentration_violations[0].limit_value

    def test_options_order_analysis(self, complex_portfolio):
        """Test risk analysis for options orders."""
        analyzer = RiskAnalyzer()
        
        # Options order
        options_order = Order(
            symbol="AAPL240315C00155000",
            quantity=5,
            order_type=OrderType.BTO,
            price=5.0
        )
        
        quote = Quote(symbol="AAPL240315C00155000", price=5.0, bid=4.95, ask=5.05, midpoint=5.0, timestamp=datetime.now())
        
        with patch('app.services.greeks.calculate_option_greeks') as mock_greeks:
            mock_greeks.return_value = {
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.2,
                "rho": 0.1
            }
            
            result = analyzer.analyze_order(options_order, complex_portfolio, quote)
            
            assert isinstance(result, RiskAnalysisResult)
            assert result.Greeks_impact is not None  # Should calculate Greeks
            assert "delta_change" in result.Greeks_impact

    def test_margin_account_high_leverage(self, complex_portfolio):
        """Test risk analysis for margin account with high leverage potential."""
        analyzer = RiskAnalyzer()
        
        # Large order that would create high leverage
        leveraged_order = Order(
            symbol="NVDA",
            quantity=500,
            order_type=OrderType.BUY,
            price=800.0  # $400k order
        )
        
        quote = Quote(symbol="NVDA", price=800.0, bid=799.5, ask=800.5, midpoint=800.0, timestamp=datetime.now())
        
        result = analyzer.analyze_order(
            leveraged_order, complex_portfolio, quote, account_type="margin"
        )
        
        # Should detect leverage violations
        leverage_violations = [
            v for v in result.violations 
            if v.check_type == RiskCheckType.PORTFOLIO_LEVERAGE
        ]
        
        # Large order should trigger leverage warnings
        assert len(leverage_violations) > 0

    def test_short_selling_risk_analysis(self, complex_portfolio):
        """Test risk analysis for short selling orders."""
        analyzer = RiskAnalyzer()
        
        # Short selling order
        short_order = Order(
            symbol="AMZN",
            quantity=-50,
            order_type=OrderType.SELL,
            price=3000.0
        )
        
        quote = Quote(symbol="AMZN", price=3000.0, bid=2999.5, ask=3000.5, midpoint=3000.0, timestamp=datetime.now())
        
        result = analyzer.analyze_order(
            short_order, complex_portfolio, quote, account_type="margin"
        )
        
        # Should handle short selling analysis
        assert isinstance(result, RiskAnalysisResult)
        assert result.can_execute in [True, False]  # Should make execution decision
        
        # Check portfolio impact for short position
        assert result.portfolio_impact.cash_after > result.portfolio_impact.cash_before  # Short selling adds cash

    @patch('app.services.risk_analysis.datetime')
    def test_expiration_day_options_restriction(self, mock_datetime, complex_portfolio):
        """Test restriction on selling options on expiration day."""
        # Mock today as expiration day
        mock_datetime.now.return_value.date.return_value = date(2024, 3, 15)
        
        analyzer = RiskAnalyzer()
        
        # Try to sell option on expiration day
        expiring_option_order = Order(
            symbol="AAPL240315C00155000",
            quantity=-1,
            order_type=OrderType.STO,
            price=0.5
        )
        
        # Mock the asset creation for this test
        with patch('app.models.assets.asset_factory') as mock_factory:
            mock_option = Mock()
            mock_option.expiration_date = date(2024, 3, 15)  # Today
            mock_factory.return_value = mock_option
            
            quote = Quote(symbol="AAPL240315C00155000", price=0.5, bid=0.45, ask=0.55, midpoint=0.5, timestamp=datetime.now())
            
            result = analyzer.analyze_order(expiring_option_order, complex_portfolio, quote)
            
            # Should have regulatory violation for expiration day short
            regulatory_violations = [
                v for v in result.violations 
                if "expiration day" in v.message.lower()
            ]
            
            if regulatory_violations:
                assert regulatory_violations[0].severity == RiskLevel.EXTREME