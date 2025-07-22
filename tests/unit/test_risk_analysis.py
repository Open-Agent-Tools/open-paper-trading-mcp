"""
Unit tests for the risk analysis service.

This module tests the risk analysis functionality, including risk checks,
portfolio impact calculations, and decision-making logic.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.assets import Option, Stock
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
    get_risk_analyzer,
)


@pytest.fixture
def mock_quote():
    """Create a mock quote for testing."""
    return Quote(
        asset="AAPL",
        price=150.0,
        bid=149.5,
        ask=150.5,
        volume=1000000,
        quote_date=datetime.now(),
    )


@pytest.fixture
def mock_option_quote():
    """Create a mock option quote for testing."""
    return Quote(
        asset="AAPL240119C00150000",
        price=5.0,
        bid=4.8,
        ask=5.2,
        volume=1000,
        quote_date=datetime.now(),
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
        ],
        daily_pnl=500.0,
        total_pnl=2000.0,
    )


@pytest.fixture
def risk_analyzer():
    """Create a risk analyzer with default limits for testing."""
    return RiskAnalyzer()


@pytest.fixture
def custom_risk_limits():
    """Create custom risk limits for testing."""
    return RiskLimits(
        max_position_concentration=0.10,  # 10% of portfolio
        max_sector_exposure=0.30,  # 30% of portfolio
        max_leverage=1.5,  # 1.5x leverage
        min_buying_power=2000.0,  # Minimum $2000
        max_day_trades=2,  # Stricter PDT rule
        max_volatility_exposure=0.20,  # 20% in high volatility
        options_trading_level=1,  # Lower options level
        margin_maintenance_buffer=1.5,  # 50% buffer
    )


class TestRiskAnalyzerInitialization:
    """Test risk analyzer initialization and configuration."""

    def test_default_initialization(self):
        """Test initialization with default risk limits."""
        analyzer = RiskAnalyzer()
        assert analyzer is not None
        assert analyzer.risk_limits is not None
        assert analyzer.risk_limits.max_position_concentration == 0.20
        assert analyzer.risk_limits.max_sector_exposure == 0.40
        assert analyzer.risk_limits.max_leverage == 2.0

    def test_custom_initialization(self, custom_risk_limits):
        """Test initialization with custom risk limits."""
        analyzer = RiskAnalyzer(custom_risk_limits)
        assert analyzer is not None
        assert analyzer.risk_limits is not None
        assert analyzer.risk_limits.max_position_concentration == 0.10
        assert analyzer.risk_limits.max_sector_exposure == 0.30
        assert analyzer.risk_limits.max_leverage == 1.5

    def test_sector_mappings_loaded(self, risk_analyzer):
        """Test sector mappings are loaded."""
        assert risk_analyzer.sector_mappings is not None
        assert len(risk_analyzer.sector_mappings) > 0
        assert "AAPL" in risk_analyzer.sector_mappings
        assert risk_analyzer.sector_mappings["AAPL"] == "Technology"

    def test_volatility_rankings_loaded(self, risk_analyzer):
        """Test volatility rankings are loaded."""
        assert risk_analyzer.volatility_rankings is not None
        assert len(risk_analyzer.volatility_rankings) > 0
        assert "AAPL" in risk_analyzer.volatility_rankings
        assert risk_analyzer.volatility_rankings["AAPL"] == "normal"
        assert "TSLA" in risk_analyzer.volatility_rankings
        assert risk_analyzer.volatility_rankings["TSLA"] == "high"

    def test_global_risk_analyzer(self):
        """Test global risk analyzer instance."""
        analyzer = get_risk_analyzer()
        assert analyzer is not None
        assert isinstance(analyzer, RiskAnalyzer)


class TestPortfolioImpactCalculation:
    """Test portfolio impact calculation."""

    def test_calculate_portfolio_impact_buy(
        self, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test portfolio impact calculation for buy order."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=50,
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Act
        impact = risk_analyzer._calculate_portfolio_impact(
            order, mock_portfolio, mock_quote
        )

        # Assert
        assert isinstance(impact, PortfolioImpact)
        assert impact.total_value_before == 25000.0
        assert impact.cash_before == 10000.0
        assert impact.cash_after < 10000.0  # Cash should decrease
        assert impact.buying_power_before == 10000.0
        assert impact.buying_power_after < 10000.0  # Buying power should decrease
        assert len(impact.positions_affected) > 0  # Should affect AAPL position

    def test_calculate_portfolio_impact_sell(
        self, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test portfolio impact calculation for sell order."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=-50,  # Negative for sell
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Act
        impact = risk_analyzer._calculate_portfolio_impact(
            order, mock_portfolio, mock_quote
        )

        # Assert
        assert isinstance(impact, PortfolioImpact)
        assert impact.total_value_before == 25000.0
        assert impact.cash_before == 10000.0
        assert impact.cash_after > 10000.0  # Cash should increase
        assert impact.buying_power_before == 10000.0
        assert impact.buying_power_after > 10000.0  # Buying power should increase
        assert len(impact.positions_affected) > 0  # Should affect AAPL position

    def test_calculate_portfolio_impact_new_position(
        self, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test portfolio impact calculation for new position."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="GOOGL",  # New position
            order_type=OrderType.BUY,
            quantity=10,
            price=2800.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Mock quote for GOOGL
        googl_quote = Quote(
            asset="GOOGL",
            price=2800.0,
            bid=2795.0,
            ask=2805.0,
            volume=500000,
            quote_date=datetime.now(),
        )

        # Act
        impact = risk_analyzer._calculate_portfolio_impact(
            order, mock_portfolio, googl_quote
        )

        # Assert
        assert isinstance(impact, PortfolioImpact)
        assert impact.total_value_before == 25000.0
        assert impact.cash_before == 10000.0
        assert impact.cash_after < 10000.0  # Cash should decrease
        assert "GOOGL" in impact.new_positions  # Should be a new position
        assert len(impact.positions_affected) == 0  # No existing positions affected


class TestPositionImpactCalculation:
    """Test position impact calculation."""

    def test_calculate_position_impacts_existing(
        self, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test position impact calculation for existing position."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=50,
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Act
        impacts = risk_analyzer._calculate_position_impacts(
            order, mock_portfolio, mock_quote
        )

        # Assert
        assert len(impacts) == 1  # Should affect one position
        impact = impacts[0]
        assert isinstance(impact, PositionImpact)
        assert impact.symbol == "AAPL"
        assert impact.current_quantity == 100
        assert impact.new_quantity == 150  # 100 + 50
        assert impact.current_avg_price == 140.0
        assert impact.new_avg_price > 140.0  # Average price should increase
        assert impact.current_value == 15000.0  # 100 * 150.0
        assert impact.new_value == 22500.0  # 150 * 150.0

    def test_calculate_single_position_impact(
        self, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test single position impact calculation."""
        # Arrange
        position = mock_portfolio.positions[0]  # AAPL position
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=50,
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Act
        impact = risk_analyzer._calculate_single_position_impact(
            position, order, mock_quote, mock_portfolio
        )

        # Assert
        assert isinstance(impact, PositionImpact)
        assert impact.symbol == "AAPL"
        assert impact.current_quantity == 100
        assert impact.new_quantity == 150  # 100 + 50
        assert impact.current_avg_price == 140.0
        assert impact.new_avg_price > 140.0  # Average price should increase
        assert impact.current_value == 15000.0  # 100 * 150.0
        assert impact.new_value == 22500.0  # 150 * 150.0
        assert impact.pnl_impact == 0.0  # No realized P&L for buy


@patch("app.services.risk_analysis.asset_factory")
class TestRiskChecks:
    """Test risk check functionality."""

    def test_check_position_concentration(
        self, mock_asset_factory, risk_analyzer, mock_portfolio
    ):
        """Test position concentration check."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=500,  # Large quantity to trigger violation
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Create a portfolio impact with high concentration
        position_impact = PositionImpact(
            symbol="AAPL",
            current_quantity=100,
            new_quantity=600,
            current_avg_price=140.0,
            new_avg_price=145.0,
            current_value=15000.0,
            new_value=90000.0,  # High value
            pnl_impact=0.0,
            concentration_before=0.15,
            concentration_after=0.30,  # > 20% limit
        )

        portfolio_impact = PortfolioImpact(
            total_value_before=25000.0,
            total_value_after=100000.0,
            cash_before=10000.0,
            cash_after=10000.0,
            buying_power_before=10000.0,
            buying_power_after=10000.0,
            leverage_before=1.5,
            leverage_after=1.5,
            positions_affected=[position_impact],
            new_positions=[],
            closed_positions=[],
        )

        # Act
        violations = risk_analyzer._check_position_concentration(
            order, mock_portfolio, portfolio_impact
        )

        # Assert
        assert len(violations) == 1
        violation = violations[0]
        assert isinstance(violation, RiskViolation)
        assert violation.check_type == RiskCheckType.POSITION_CONCENTRATION
        assert violation.severity == RiskLevel.HIGH
        assert "concentration limit" in violation.message
        assert violation.current_value == 0.30
        assert violation.limit_value == 0.20

    def test_check_buying_power(self, mock_asset_factory, risk_analyzer):
        """Test buying power check."""
        # Arrange
        portfolio_impact = PortfolioImpact(
            total_value_before=25000.0,
            total_value_after=25000.0,
            cash_before=10000.0,
            cash_after=500.0,  # Low cash after order
            buying_power_before=10000.0,
            buying_power_after=500.0,  # < 1000 limit
            leverage_before=1.5,
            leverage_after=1.5,
            positions_affected=[],
            new_positions=[],
            closed_positions=[],
        )

        # Act
        violations = risk_analyzer._check_buying_power(portfolio_impact)

        # Assert
        assert len(violations) == 1
        violation = violations[0]
        assert isinstance(violation, RiskViolation)
        assert violation.check_type == RiskCheckType.BUYING_POWER
        assert violation.severity == RiskLevel.EXTREME
        assert "Insufficient buying power" in violation.message
        assert violation.current_value == 500.0
        assert violation.limit_value == 1000.0

    def test_check_leverage(self, mock_asset_factory, risk_analyzer):
        """Test leverage check."""
        # Arrange
        portfolio_impact = PortfolioImpact(
            total_value_before=25000.0,
            total_value_after=25000.0,
            cash_before=10000.0,
            cash_after=10000.0,
            buying_power_before=10000.0,
            buying_power_after=10000.0,
            leverage_before=1.5,
            leverage_after=2.5,  # > 2.0 limit
            positions_affected=[],
            new_positions=[],
            closed_positions=[],
        )

        # Act
        violations = risk_analyzer._check_leverage(portfolio_impact)

        # Assert
        assert len(violations) == 1
        violation = violations[0]
        assert isinstance(violation, RiskViolation)
        assert violation.check_type == RiskCheckType.PORTFOLIO_LEVERAGE
        assert violation.severity == RiskLevel.HIGH
        assert "leverage would exceed limit" in violation.message
        assert violation.current_value == 2.5
        assert violation.limit_value == 2.0

    def test_check_options_level(self, mock_asset_factory, risk_analyzer):
        """Test options level check."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL240119C00150000",
            order_type=OrderType.STO,  # Sell to open (requires higher level)
            quantity=-1,
            price=5.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Mock option asset
        mock_option = MagicMock(spec=Option)
        mock_option.option_type = "call"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_asset_factory.return_value = mock_option

        # Act
        violations = risk_analyzer._check_options_level(order, mock_option)

        # Assert
        assert len(violations) == 1
        violation = violations[0]
        assert isinstance(violation, RiskViolation)
        assert violation.check_type == RiskCheckType.OPTIONS_LEVEL
        assert violation.severity == RiskLevel.EXTREME
        assert "Options trading level" in violation.message
        assert violation.current_value == 2  # Default level
        assert violation.limit_value == 4  # Required for uncovered options


@patch("app.services.risk_analysis.asset_factory")
class TestRiskAnalysis:
    """Test complete risk analysis functionality."""

    def test_analyze_order_low_risk(
        self, mock_asset_factory, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test risk analysis for low-risk order."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,  # Small quantity
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Mock stock asset
        mock_stock = MagicMock(spec=Stock)
        mock_stock.symbol = "AAPL"
        mock_asset_factory.return_value = mock_stock

        # Act
        result = risk_analyzer.analyze_order(order, mock_portfolio, mock_quote)

        # Assert
        assert isinstance(result, RiskAnalysisResult)
        assert result.risk_level == RiskLevel.LOW
        assert len(result.violations) == 0
        assert result.can_execute is True
        assert result.estimated_cost > 0
        assert result.margin_requirement > 0

    def test_analyze_order_high_risk(
        self, mock_asset_factory, risk_analyzer, mock_portfolio, mock_quote
    ):
        """Test risk analysis for high-risk order."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=500,  # Large quantity to trigger violation
            price=150.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Mock stock asset
        mock_stock = MagicMock(spec=Stock)
        mock_stock.symbol = "AAPL"
        mock_asset_factory.return_value = mock_stock

        # Act
        result = risk_analyzer.analyze_order(order, mock_portfolio, mock_quote)

        # Assert
        assert isinstance(result, RiskAnalysisResult)
        assert result.risk_level in [
            RiskLevel.HIGH,
            RiskLevel.EXTREME,
        ]  # Depending on violations
        assert len(result.violations) > 0
        assert any(
            v.check_type == RiskCheckType.POSITION_CONCENTRATION
            for v in result.violations
        )
        assert result.estimated_cost > 0
        assert result.margin_requirement > 0

    @patch("app.services.risk_analysis.calculate_option_greeks")
    def test_analyze_order_options(
        self,
        mock_calculate_greeks,
        mock_asset_factory,
        risk_analyzer,
        mock_portfolio,
        mock_option_quote,
    ):
        """Test risk analysis for options order."""
        # Arrange
        order = Order(
            id="test-order",
            symbol="AAPL240119C00150000",
            order_type=OrderType.BTO,  # Buy to open
            quantity=1,
            price=5.0,
            status="pending",
            created_at=datetime.now(),
        )

        # Mock option asset
        mock_option = MagicMock(spec=Option)
        mock_option.symbol = "AAPL240119C00150000"
        mock_option.option_type = "call"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.underlying = MagicMock()
        mock_option.underlying.symbol = "AAPL"
        mock_option.get_days_to_expiration.return_value = 30
        mock_asset_factory.return_value = mock_option

        # Mock Greeks calculation
        mock_calculate_greeks.return_value = {
            "delta": 0.6,
            "gamma": 0.05,
            "theta": -0.1,
            "vega": 0.2,
            "rho": 0.05,
        }

        # Act
        result = risk_analyzer.analyze_order(order, mock_portfolio, mock_option_quote)

        # Assert
        assert isinstance(result, RiskAnalysisResult)
        assert result.Greeks_impact is not None
        assert "delta_change" in result.Greeks_impact
        assert "gamma_change" in result.Greeks_impact
        assert "theta_change" in result.Greeks_impact
        assert "vega_change" in result.Greeks_impact
        assert "rho_change" in result.Greeks_impact
        assert result.estimated_cost > 0
        assert result.margin_requirement > 0


class TestRiskUtilityFunctions:
    """Test risk utility functions."""

    def test_determine_risk_level_no_violations(self, risk_analyzer):
        """Test risk level determination with no violations."""
        # Act
        risk_level = risk_analyzer._determine_risk_level([])

        # Assert
        assert risk_level == RiskLevel.LOW

    def test_determine_risk_level_with_violations(self, risk_analyzer):
        """Test risk level determination with violations."""
        # Arrange
        violations = [
            RiskViolation(
                check_type=RiskCheckType.POSITION_CONCENTRATION,
                severity=RiskLevel.MODERATE,
                message="Test violation",
                current_value=0.25,
                limit_value=0.20,
            ),
            RiskViolation(
                check_type=RiskCheckType.BUYING_POWER,
                severity=RiskLevel.HIGH,
                message="Test violation",
                current_value=500.0,
                limit_value=1000.0,
            ),
        ]

        # Act
        risk_level = risk_analyzer._determine_risk_level(violations)

        # Assert
        assert risk_level == RiskLevel.HIGH  # Highest severity

    def test_can_execute_order_no_violations(self, risk_analyzer):
        """Test order execution decision with no violations."""
        # Arrange
        portfolio_impact = MagicMock()
        portfolio_impact.cash_after = 5000.0

        # Act
        can_execute = risk_analyzer._can_execute_order([], portfolio_impact)

        # Assert
        assert can_execute is True

    def test_can_execute_order_extreme_violations(self, risk_analyzer):
        """Test order execution decision with extreme violations."""
        # Arrange
        violations = [
            RiskViolation(
                check_type=RiskCheckType.BUYING_POWER,
                severity=RiskLevel.EXTREME,
                message="Insufficient buying power",
                current_value=500.0,
                limit_value=1000.0,
            )
        ]
        portfolio_impact = MagicMock()
        portfolio_impact.cash_after = 500.0

        # Act
        can_execute = risk_analyzer._can_execute_order(violations, portfolio_impact)

        # Assert
        assert can_execute is False

    def test_can_execute_order_insufficient_funds(self, risk_analyzer):
        """Test order execution decision with insufficient funds."""
        # Arrange
        violations = [
            RiskViolation(
                check_type=RiskCheckType.POSITION_CONCENTRATION,
                severity=RiskLevel.MODERATE,
                message="Position concentration high",
                current_value=0.25,
                limit_value=0.20,
            )
        ]
        portfolio_impact = MagicMock()
        portfolio_impact.cash_after = -100.0  # Negative cash

        # Act
        can_execute = risk_analyzer._can_execute_order(violations, portfolio_impact)

        # Assert
        assert can_execute is False

    def test_generate_warnings(self, risk_analyzer, mock_portfolio):
        """Test warning generation."""
        # Arrange
        order = MagicMock()
        order.symbol = "AAPL"

        portfolio_impact = MagicMock()
        portfolio_impact.cash_after = 4000.0  # Below 5000 warning threshold
        portfolio_impact.positions_affected = [
            MagicMock(
                symbol="AAPL", concentration_after=0.16
            )  # Above 15% warning threshold
        ]

        violations = []

        # Act
        warnings = risk_analyzer._generate_warnings(
            order, mock_portfolio, portfolio_impact, violations
        )

        # Assert
        assert len(warnings) > 0
        assert any(
            "cash balance will be low" in warning.lower() for warning in warnings
        )
        assert any("represent 16.0% of portfolio" in warning for warning in warnings)
