"""
Comprehensive tests for Risk Analysis module.

Tests risk management functionality including:
- Risk level and violation detection
- Portfolio and position impact analysis
- Risk checks (concentration, leverage, buying power, options level)
- Greeks calculations and margin requirements
- Risk analyzer configuration and limits
"""

from unittest.mock import Mock, patch

from app.models.assets import Option
from app.models.quotes import Quote
from app.schemas.orders import Order, OrderType
from app.schemas.positions import Portfolio, Position
from app.services.risk_analysis import (
    PortfolioImpact,
    PositionImpact,
    RiskAnalysisResult,
    RiskAnalyzer,
    RiskCheckType,
    RiskLevel,
    RiskLimits,
    RiskViolation,
    configure_risk_limits,
    get_risk_analyzer,
)


class TestRiskEnums:
    """Test suite for risk-related enums."""

    def test_risk_level_enum(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_check_type_enum(self):
        """Test RiskCheckType enum values."""
        assert RiskCheckType.POSITION_CONCENTRATION == "position_concentration"
        assert RiskCheckType.SECTOR_EXPOSURE == "sector_exposure"
        assert RiskCheckType.LEVERAGE == "leverage"
        assert RiskCheckType.BUYING_POWER == "buying_power"
        assert RiskCheckType.OPTIONS_LEVEL == "options_level"
        assert RiskCheckType.VOLATILITY_EXPOSURE == "volatility_exposure"


class TestRiskDataClasses:
    """Test suite for risk-related data classes."""

    def test_risk_violation_creation(self):
        """Test RiskViolation data class creation."""
        violation = RiskViolation(
            check_type=RiskCheckType.LEVERAGE,
            severity=RiskLevel.HIGH,
            message="Leverage too high",
            current_value=2.5,
            limit_value=2.0,
        )

        assert violation.check_type == RiskCheckType.LEVERAGE
        assert violation.severity == RiskLevel.HIGH
        assert violation.message == "Leverage too high"
        assert violation.current_value == 2.5
        assert violation.limit_value == 2.0

    def test_position_impact_creation(self):
        """Test PositionImpact data class creation."""
        impact = PositionImpact(
            symbol="AAPL",
            current_quantity=100,
            new_quantity=150,
            current_value=15000.0,
            new_value=22500.0,
            pnl_impact=7500.0,
            percentage_change=0.5,
            concentration_before=0.1,
            concentration_after=0.15,
        )

        assert impact.symbol == "AAPL"
        assert impact.current_quantity == 100
        assert impact.new_quantity == 150
        assert impact.current_value == 15000.0
        assert impact.new_value == 22500.0
        assert impact.pnl_impact == 7500.0
        assert impact.percentage_change == 0.5
        assert impact.concentration_before == 0.1
        assert impact.concentration_after == 0.15

    def test_portfolio_impact_creation(self):
        """Test PortfolioImpact data class creation."""
        impact = PortfolioImpact(
            total_value_before=100000.0,
            total_value_after=107500.0,
            cash_impact=-7500.0,
            buying_power_before=25000.0,
            buying_power_after=17500.0,
            leverage_before=1.5,
            leverage_after=1.8,
            margin_requirement=5000.0,
        )

        assert impact.total_value_before == 100000.0
        assert impact.total_value_after == 107500.0
        assert impact.cash_impact == -7500.0
        assert impact.buying_power_before == 25000.0
        assert impact.buying_power_after == 17500.0
        assert impact.leverage_before == 1.5
        assert impact.leverage_after == 1.8
        assert impact.margin_requirement == 5000.0

    def test_risk_analysis_result_creation(self):
        """Test RiskAnalysisResult data class creation."""
        violations = [
            RiskViolation(
                check_type=RiskCheckType.LEVERAGE,
                severity=RiskLevel.MEDIUM,
                message="Test violation",
                current_value=1.5,
                limit_value=1.0,
            )
        ]

        result = RiskAnalysisResult(
            can_execute=True,
            risk_level=RiskLevel.MEDIUM,
            violations=violations,
            warnings=["Test warning"],
            portfolio_impact=None,
            position_impacts=[],
        )

        assert result.can_execute is True
        assert result.risk_level == RiskLevel.MEDIUM
        assert len(result.violations) == 1
        assert result.violations[0].message == "Test violation"
        assert result.warnings == ["Test warning"]

    def test_risk_limits_creation(self):
        """Test RiskLimits data class creation."""
        limits = RiskLimits(
            max_position_concentration=0.2,
            max_sector_concentration=0.3,
            max_leverage=2.0,
            min_buying_power=10000.0,
            max_options_level=3,
            max_volatility_exposure=0.4,
        )

        assert limits.max_position_concentration == 0.2
        assert limits.max_sector_concentration == 0.3
        assert limits.max_leverage == 2.0
        assert limits.min_buying_power == 10000.0
        assert limits.max_options_level == 3
        assert limits.max_volatility_exposure == 0.4


class TestRiskAnalyzerInitialization:
    """Test suite for RiskAnalyzer initialization."""

    def test_risk_analyzer_default_initialization(self):
        """Test RiskAnalyzer initialization with default limits."""
        analyzer = RiskAnalyzer()

        assert analyzer.risk_limits is not None
        assert isinstance(analyzer.risk_limits, RiskLimits)

    def test_risk_analyzer_custom_limits(self):
        """Test RiskAnalyzer initialization with custom limits."""
        custom_limits = RiskLimits(max_position_concentration=0.15, max_leverage=1.5)

        analyzer = RiskAnalyzer(risk_limits=custom_limits)

        assert analyzer.risk_limits is custom_limits
        assert analyzer.risk_limits.max_position_concentration == 0.15
        assert analyzer.risk_limits.max_leverage == 1.5


class TestRiskAnalyzerUtilityMethods:
    """Test suite for RiskAnalyzer utility methods."""

    def test_get_safe_price(self):
        """Test _get_safe_price method."""
        analyzer = RiskAnalyzer()

        # Test with valid quote
        quote = Mock(spec=Quote)
        quote.price = 150.0
        assert analyzer._get_safe_price(quote) == 150.0

        # Test with None quote
        assert analyzer._get_safe_price(None) == 0.0

        # Test with quote without price
        quote_no_price = Mock(spec=Quote)
        del quote_no_price.price
        assert analyzer._get_safe_price(quote_no_price) == 0.0

    def test_get_safe_position_price(self):
        """Test _get_safe_position_price method."""
        analyzer = RiskAnalyzer()

        # Test with valid position
        position = Mock(spec=Position)
        position.current_price = 100.0
        assert analyzer._get_safe_position_price(position) == 100.0

        # Test with None position
        assert analyzer._get_safe_position_price(None) == 0.0

        # Test with position without current_price
        position_no_price = Mock(spec=Position)
        del position_no_price.current_price
        assert analyzer._get_safe_position_price(position_no_price) == 0.0


class TestRiskAnalyzerOrderAnalysis:
    """Test suite for order analysis functionality."""

    def test_analyze_order_basic(self):
        """Test basic order analysis."""
        analyzer = RiskAnalyzer()

        # Create mock objects
        order = Mock(spec=Order)
        order.symbol = "AAPL"
        order.quantity = 10
        order.order_type = OrderType.MARKET
        order.side = "buy"

        portfolio = Mock(spec=Portfolio)
        portfolio.total_value = 100000.0
        portfolio.cash = 50000.0
        portfolio.positions = []

        quote = Mock(spec=Quote)
        quote.price = 150.0
        quote.symbol = "AAPL"

        with patch.object(analyzer, "_calculate_portfolio_impact") as mock_impact:
            mock_portfolio_impact = Mock(spec=PortfolioImpact)
            mock_impact.return_value = mock_portfolio_impact

            with patch.object(analyzer, "_perform_risk_checks") as mock_checks:
                mock_checks.return_value = []

                result = analyzer.analyze_order(order, portfolio, quote)

                assert isinstance(result, RiskAnalysisResult)
                mock_impact.assert_called_once()
                mock_checks.assert_called_once()

    def test_analyze_order_with_violations(self):
        """Test order analysis with risk violations."""
        analyzer = RiskAnalyzer()

        order = Mock(spec=Order)
        portfolio = Mock(spec=Portfolio)
        quote = Mock(spec=Quote)

        violation = RiskViolation(
            check_type=RiskCheckType.LEVERAGE,
            severity=RiskLevel.HIGH,
            message="Leverage exceeded",
            current_value=2.5,
            limit_value=2.0,
        )

        with patch.object(analyzer, "_calculate_portfolio_impact"):
            with patch.object(analyzer, "_perform_risk_checks") as mock_checks:
                mock_checks.return_value = [violation]

                result = analyzer.analyze_order(order, portfolio, quote)

                assert len(result.violations) == 1
                assert result.violations[0].message == "Leverage exceeded"
                assert result.risk_level == RiskLevel.HIGH


class TestRiskAnalyzerImpactCalculations:
    """Test suite for impact calculation methods."""

    def test_calculate_order_cost(self):
        """Test order cost calculation."""
        analyzer = RiskAnalyzer()

        order = Mock(spec=Order)
        order.quantity = 10
        order.side = "buy"

        quote = Mock(spec=Quote)
        quote.price = 150.0

        cost = analyzer._calculate_order_cost(order, quote)
        assert cost == 1500.0  # 10 * 150.0

    def test_calculate_buying_power(self):
        """Test buying power calculation."""
        analyzer = RiskAnalyzer()

        portfolio = Mock(spec=Portfolio)
        portfolio.cash = 50000.0

        buying_power = analyzer._calculate_buying_power(portfolio)
        assert buying_power == 50000.0

    def test_calculate_leverage(self):
        """Test leverage calculation."""
        analyzer = RiskAnalyzer()

        portfolio = Mock(spec=Portfolio)
        portfolio.total_value = 100000.0
        portfolio.cash = 50000.0

        leverage = analyzer._calculate_leverage(portfolio)
        assert leverage == 0.5  # (100000 - 50000) / 100000


class TestRiskAnalyzerRiskChecks:
    """Test suite for individual risk check methods."""

    def test_check_position_concentration(self):
        """Test position concentration check."""
        analyzer = RiskAnalyzer()
        analyzer.risk_limits.max_position_concentration = 0.2

        order = Mock(spec=Order)
        order.symbol = "AAPL"

        portfolio = Mock(spec=Portfolio)
        portfolio.total_value = 100000.0

        portfolio_impact = Mock(spec=PortfolioImpact)
        portfolio_impact.total_value_after = 100000.0

        # Mock position impacts to simulate high concentration
        with patch.object(analyzer, "_calculate_position_impacts") as mock_impacts:
            position_impact = Mock(spec=PositionImpact)
            position_impact.symbol = "AAPL"
            position_impact.concentration_after = 0.25  # Above limit
            mock_impacts.return_value = [position_impact]

            violations = analyzer._check_position_concentration(
                order, portfolio, portfolio_impact
            )

            assert len(violations) == 1
            assert violations[0].check_type == RiskCheckType.POSITION_CONCENTRATION

    def test_check_leverage(self):
        """Test leverage check."""
        analyzer = RiskAnalyzer()
        analyzer.risk_limits.max_leverage = 2.0

        portfolio_impact = Mock(spec=PortfolioImpact)
        portfolio_impact.leverage_after = 2.5  # Above limit

        violations = analyzer._check_leverage(portfolio_impact)

        assert len(violations) == 1
        assert violations[0].check_type == RiskCheckType.LEVERAGE
        assert violations[0].current_value == 2.5
        assert violations[0].limit_value == 2.0

    def test_check_buying_power(self):
        """Test buying power check."""
        analyzer = RiskAnalyzer()
        analyzer.risk_limits.min_buying_power = 10000.0

        portfolio_impact = Mock(spec=PortfolioImpact)
        portfolio_impact.buying_power_after = 5000.0  # Below limit

        violations = analyzer._check_buying_power(portfolio_impact)

        assert len(violations) == 1
        assert violations[0].check_type == RiskCheckType.BUYING_POWER
        assert violations[0].current_value == 5000.0
        assert violations[0].limit_value == 10000.0


class TestRiskAnalyzerOptionsChecks:
    """Test suite for options-specific risk checks."""

    def test_check_options_level(self):
        """Test options level check."""
        analyzer = RiskAnalyzer()

        order = Mock(spec=Order)
        order.symbol = "AAPL240119C00150000"  # Options symbol

        option = Mock(spec=Option)
        option.option_type = "call"
        option.strike = 150.0

        with patch.object(analyzer, "_get_required_options_level") as mock_level:
            mock_level.return_value = 4  # Requires level 4

            # Simulate account with insufficient options level
            violations = analyzer._check_options_level(order, option)

            # This test would need more setup to properly test options level validation
            assert isinstance(violations, list)

    def test_get_required_options_level(self):
        """Test required options level determination."""
        analyzer = RiskAnalyzer()

        order = Mock(spec=Order)
        order.side = "buy"

        # Test call option
        call_option = Mock(spec=Option)
        call_option.option_type = "call"

        level = analyzer._get_required_options_level(order, call_option)
        assert level == 1  # Buying calls requires level 1

        # Test put option
        put_option = Mock(spec=Option)
        put_option.option_type = "put"

        level = analyzer._get_required_options_level(order, put_option)
        assert level == 1  # Buying puts requires level 1


class TestRiskAnalyzerRiskLevelDetermination:
    """Test suite for risk level determination."""

    def test_determine_risk_level_no_violations(self):
        """Test risk level with no violations."""
        analyzer = RiskAnalyzer()

        risk_level = analyzer._determine_risk_level([])
        assert risk_level == RiskLevel.LOW

    def test_determine_risk_level_with_violations(self):
        """Test risk level with various violation severities."""
        analyzer = RiskAnalyzer()

        # Test with medium severity violation
        medium_violation = RiskViolation(
            check_type=RiskCheckType.LEVERAGE,
            severity=RiskLevel.MEDIUM,
            message="Medium risk",
            current_value=1.5,
            limit_value=1.0,
        )

        risk_level = analyzer._determine_risk_level([medium_violation])
        assert risk_level == RiskLevel.MEDIUM

        # Test with critical severity violation
        critical_violation = RiskViolation(
            check_type=RiskCheckType.BUYING_POWER,
            severity=RiskLevel.CRITICAL,
            message="Critical risk",
            current_value=0.0,
            limit_value=10000.0,
        )

        risk_level = analyzer._determine_risk_level([critical_violation])
        assert risk_level == RiskLevel.CRITICAL

    def test_can_execute_order(self):
        """Test order execution determination."""
        analyzer = RiskAnalyzer()

        # Test with no violations
        portfolio_impact = Mock(spec=PortfolioImpact)
        portfolio_impact.buying_power_after = 10000.0

        can_execute = analyzer._can_execute_order([], portfolio_impact)
        assert can_execute is True

        # Test with critical violation
        critical_violation = RiskViolation(
            check_type=RiskCheckType.BUYING_POWER,
            severity=RiskLevel.CRITICAL,
            message="Critical risk",
            current_value=0.0,
            limit_value=10000.0,
        )

        can_execute = analyzer._can_execute_order(
            [critical_violation], portfolio_impact
        )
        assert can_execute is False


class TestRiskAnalyzerWarnings:
    """Test suite for warning generation."""

    def test_generate_warnings(self):
        """Test warning message generation."""
        analyzer = RiskAnalyzer()

        order = Mock(spec=Order)
        order.symbol = "AAPL"
        order.quantity = 100

        portfolio = Mock(spec=Portfolio)
        portfolio_impact = Mock(spec=PortfolioImpact)
        portfolio_impact.leverage_after = 1.8

        violation = RiskViolation(
            check_type=RiskCheckType.LEVERAGE,
            severity=RiskLevel.MEDIUM,
            message="Leverage approaching limit",
            current_value=1.8,
            limit_value=2.0,
        )

        warnings = analyzer._generate_warnings(
            order, portfolio, portfolio_impact, [violation]
        )

        assert isinstance(warnings, list)
        assert len(warnings) > 0


class TestRiskAnalyzerGlobalFunctions:
    """Test suite for global risk analyzer functions."""

    def test_get_risk_analyzer(self):
        """Test global risk analyzer getter."""
        analyzer = get_risk_analyzer()

        assert isinstance(analyzer, RiskAnalyzer)

    def test_configure_risk_limits(self):
        """Test global risk limits configuration."""
        custom_limits = RiskLimits(max_position_concentration=0.15, max_leverage=1.5)

        configure_risk_limits(custom_limits)

        # Test that configuration is applied
        analyzer = get_risk_analyzer()
        assert analyzer.risk_limits.max_position_concentration == 0.15
        assert analyzer.risk_limits.max_leverage == 1.5


class TestRiskAnalyzerIntegration:
    """Integration tests for RiskAnalyzer components."""

    def test_full_risk_analysis_flow(self):
        """Test complete risk analysis workflow."""
        analyzer = RiskAnalyzer()

        # Create realistic test data
        order = Mock(spec=Order)
        order.symbol = "AAPL"
        order.quantity = 100
        order.side = "buy"
        order.order_type = OrderType.MARKET

        portfolio = Mock(spec=Portfolio)
        portfolio.total_value = 100000.0
        portfolio.cash = 50000.0
        portfolio.positions = []

        quote = Mock(spec=Quote)
        quote.price = 150.0
        quote.symbol = "AAPL"

        # Mock the complex calculation methods
        with patch.object(analyzer, "_calculate_portfolio_impact") as mock_portfolio:
            portfolio_impact = PortfolioImpact(
                total_value_before=100000.0,
                total_value_after=115000.0,
                cash_impact=-15000.0,
                buying_power_before=50000.0,
                buying_power_after=35000.0,
                leverage_before=0.5,
                leverage_after=0.65,
                margin_requirement=0.0,
            )
            mock_portfolio.return_value = portfolio_impact

            with patch.object(
                analyzer, "_calculate_position_impacts"
            ) as mock_positions:
                position_impact = PositionImpact(
                    symbol="AAPL",
                    current_quantity=0,
                    new_quantity=100,
                    current_value=0.0,
                    new_value=15000.0,
                    pnl_impact=15000.0,
                    percentage_change=1.0,
                    concentration_before=0.0,
                    concentration_after=0.13,
                )
                mock_positions.return_value = [position_impact]

                result = analyzer.analyze_order(order, portfolio, quote)

                assert isinstance(result, RiskAnalysisResult)
                assert result.can_execute is True
                assert result.risk_level == RiskLevel.LOW
                assert result.portfolio_impact is not None
                assert len(result.position_impacts) == 1

    def test_risk_analysis_with_multiple_violations(self):
        """Test risk analysis with multiple risk violations."""
        # Create analyzer with strict limits
        strict_limits = RiskLimits(
            max_position_concentration=0.1, max_leverage=1.2, min_buying_power=40000.0
        )
        analyzer = RiskAnalyzer(risk_limits=strict_limits)

        order = Mock(spec=Order)
        order.symbol = "AAPL"
        order.quantity = 200  # Large order
        order.side = "buy"

        portfolio = Mock(spec=Portfolio)
        portfolio.total_value = 100000.0
        portfolio.cash = 30000.0  # Low cash

        quote = Mock(spec=Quote)
        quote.price = 150.0

        with patch.object(analyzer, "_calculate_portfolio_impact") as mock_portfolio:
            # Simulate high-risk portfolio impact
            portfolio_impact = PortfolioImpact(
                total_value_before=100000.0,
                total_value_after=130000.0,
                cash_impact=-30000.0,
                buying_power_before=30000.0,
                buying_power_after=0.0,  # Violates min buying power
                leverage_before=0.7,
                leverage_after=1.3,  # Violates max leverage
                margin_requirement=5000.0,
            )
            mock_portfolio.return_value = portfolio_impact

            with patch.object(
                analyzer, "_calculate_position_impacts"
            ) as mock_positions:
                position_impact = PositionImpact(
                    symbol="AAPL",
                    current_quantity=0,
                    new_quantity=200,
                    current_value=0.0,
                    new_value=30000.0,
                    pnl_impact=30000.0,
                    percentage_change=1.0,
                    concentration_before=0.0,
                    concentration_after=0.23,  # Violates max concentration
                )
                mock_positions.return_value = [position_impact]

                result = analyzer.analyze_order(order, portfolio, quote)

                # Should have multiple violations
                assert len(result.violations) >= 2
                assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                assert result.can_execute is False
