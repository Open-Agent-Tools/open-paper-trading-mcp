"""
Test cases for advanced order validation of complex multi-leg orders.

Tests strategy recognition, validation rules, margin calculations,
risk metrics, and regulatory compliance checking.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from decimal import Decimal

from app.services.order_validation_advanced import (
    ComplexOrderValidator,
    StrategyType,
    ValidationIssue,
    StrategyValidation,
    ComplexOrderValidationResult,
    get_complex_order_validator,
    complex_order_validator,
)
from app.schemas.orders import MultiLegOrder, OrderLeg, OrderType
from app.schemas.positions import Portfolio, Position
from app.models.assets import Stock, Option, Call, Put


class TestComplexOrderValidator:
    """Test complex order validator functionality."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = ComplexOrderValidator()
        
        assert validator is not None
        assert isinstance(validator.strategy_rules, dict)
        assert len(validator.strategy_rules) > 0
        
        # Check that common strategies are defined
        assert StrategyType.VERTICAL_SPREAD in validator.strategy_rules
        assert StrategyType.CALENDAR_SPREAD in validator.strategy_rules
        assert StrategyType.STRADDLE in validator.strategy_rules
        assert StrategyType.COVERED_CALL in validator.strategy_rules

    def test_global_validator_access(self):
        """Test global validator access."""
        global_validator = get_complex_order_validator()
        
        assert global_validator is not None
        assert isinstance(global_validator, ComplexOrderValidator)
        assert global_validator is complex_order_validator

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
    def vertical_spread_order(self):
        """Create vertical spread order for testing."""
        # Buy 155 call, sell 160 call (bull call spread)
        buy_call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        sell_call = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=buy_call,
                quantity=1,
                order_type=OrderType.BTO,
                price=5.0
            ),
            OrderLeg(
                asset=sell_call,
                quantity=-1,
                order_type=OrderType.STO,
                price=2.0
            )
        ]
        
        return MultiLegOrder(legs=legs)

    @pytest.fixture
    def straddle_order(self):
        """Create straddle order for testing."""
        # Buy call and put at same strike
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        put = Put(
            symbol="AAPL240315P00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=1,
                order_type=OrderType.BTO,
                price=5.0
            ),
            OrderLeg(
                asset=put,
                quantity=1,
                order_type=OrderType.BTO,
                price=3.0
            )
        ]
        
        return MultiLegOrder(legs=legs)

    @pytest.fixture
    def covered_call_order(self):
        """Create covered call order for testing."""
        stock = Stock("AAPL")
        
        call = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=stock,
                quantity=100,
                order_type=OrderType.BUY,
                price=155.0
            ),
            OrderLeg(
                asset=call,
                quantity=-1,
                order_type=OrderType.STO,
                price=3.0
            )
        ]
        
        return MultiLegOrder(legs=legs)

    def test_validate_order_basic(self, vertical_spread_order, sample_portfolio):
        """Test basic order validation."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        assert isinstance(result, ComplexOrderValidationResult)
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.detected_strategy, StrategyType)
        assert isinstance(result.issues, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.info, list)
        assert isinstance(result.margin_requirement, (int, float))

    def test_vertical_spread_detection(self, vertical_spread_order, sample_portfolio):
        """Test vertical spread strategy detection."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        assert result.detected_strategy == StrategyType.VERTICAL_SPREAD
        
        # Should have strategy description
        assert result.strategy_description is not None
        assert "spread" in result.strategy_description.lower()

    def test_straddle_detection(self, straddle_order, sample_portfolio):
        """Test straddle strategy detection."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(straddle_order, sample_portfolio)
        
        assert result.detected_strategy == StrategyType.STRADDLE

    def test_covered_call_detection(self, covered_call_order, sample_portfolio):
        """Test covered call strategy detection."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(covered_call_order, sample_portfolio)
        
        assert result.detected_strategy == StrategyType.COVERED_CALL

    def test_basic_requirements_validation(self):
        """Test basic order requirements validation."""
        validator = ComplexOrderValidator()
        
        # Empty order
        empty_order = MultiLegOrder(legs=[])
        
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        result = validator.validate_order(empty_order, portfolio)
        
        # Should have validation issues
        empty_order_issues = [
            issue for issue in result.issues
            if issue.code == "EMPTY_ORDER"
        ]
        
        assert len(empty_order_issues) > 0
        assert empty_order_issues[0].severity == "error"

    def test_zero_quantity_validation(self, sample_portfolio):
        """Test validation of zero quantity legs."""
        validator = ComplexOrderValidator()
        
        # Create order with zero quantity leg
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=0,  # Invalid zero quantity
                order_type=OrderType.BTO,
                price=5.0
            )
        ]
        
        order = MultiLegOrder(legs=legs)
        result = validator.validate_order(order, sample_portfolio)
        
        # Should have zero quantity issues
        zero_qty_issues = [
            issue for issue in result.issues
            if issue.code == "ZERO_QUANTITY"
        ]
        
        assert len(zero_qty_issues) > 0

    def test_duplicate_symbols_validation(self, sample_portfolio):
        """Test validation of duplicate symbols."""
        validator = ComplexOrderValidator()
        
        # Create order with duplicate symbols
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(asset=call, quantity=1, order_type=OrderType.BTO, price=5.0),
            OrderLeg(asset=call, quantity=-1, order_type=OrderType.STC, price=5.0)  # Same asset
        ]
        
        order = MultiLegOrder(legs=legs)
        result = validator.validate_order(order, sample_portfolio)
        
        # Should detect duplicate symbols
        duplicate_issues = [
            issue for issue in result.issues
            if issue.code == "DUPLICATE_SYMBOLS"
        ]
        
        assert len(duplicate_issues) > 0

    def test_strategy_specific_validation(self, vertical_spread_order, sample_portfolio):
        """Test strategy-specific validation rules."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        # Vertical spread should pass strategy validation
        strategy_issues = [
            issue for issue in result.issues
            if issue.code in ["INVALID_LEG_COUNT", "MISSING_ASSET_TYPE", "DIFFERENT_UNDERLYINGS"]
        ]
        
        # Should have no strategy validation issues for valid spread
        assert len(strategy_issues) == 0

    def test_options_level_validation_insufficient(self, vertical_spread_order, sample_portfolio):
        """Test options level validation with insufficient level."""
        validator = ComplexOrderValidator()
        
        # Test with options level 1 (insufficient for spreads)
        result = validator.validate_order(
            vertical_spread_order, sample_portfolio, options_level=1
        )
        
        # Should have options level violation
        level_issues = [
            issue for issue in result.issues
            if issue.code == "INSUFFICIENT_OPTIONS_LEVEL"
        ]
        
        assert len(level_issues) > 0
        assert level_issues[0].severity == "error"

    def test_options_level_validation_sufficient(self, vertical_spread_order, sample_portfolio):
        """Test options level validation with sufficient level."""
        validator = ComplexOrderValidator()
        
        # Test with options level 3 (sufficient for spreads)
        result = validator.validate_order(
            vertical_spread_order, sample_portfolio, options_level=3
        )
        
        # Should have no options level violations
        level_issues = [
            issue for issue in result.issues
            if issue.code == "INSUFFICIENT_OPTIONS_LEVEL"
        ]
        
        assert len(level_issues) == 0

    def test_naked_options_detection(self, sample_portfolio):
        """Test naked options detection."""
        validator = ComplexOrderValidator()
        
        # Create naked call order
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=-1,  # Short call (naked)
                order_type=OrderType.STO,
                price=5.0
            )
        ]
        
        naked_order = MultiLegOrder(legs=legs)
        
        # Test with insufficient options level
        result = validator.validate_order(naked_order, sample_portfolio, options_level=2)
        
        # Should detect naked options violation
        naked_issues = [
            issue for issue in result.issues
            if issue.code == "NAKED_OPTIONS_NOT_ALLOWED"
        ]
        
        assert len(naked_issues) > 0

    def test_risk_parameter_validation(self, sample_portfolio):
        """Test risk parameter validation."""
        validator = ComplexOrderValidator()
        
        # Create large order (high concentration)
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=100,  # Large quantity
                order_type=OrderType.BTO,
                price=50.0  # High price - creates large position
            )
        ]
        
        large_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(large_order, sample_portfolio)
        
        # Should generate concentration warnings
        concentration_warnings = [
            warning for warning in result.warnings
            if warning.code == "HIGH_CONCENTRATION"
        ]
        
        if concentration_warnings:
            assert concentration_warnings[0].severity == "warning"

    def test_near_expiration_warning(self, sample_portfolio):
        """Test near expiration warning generation."""
        validator = ComplexOrderValidator()
        
        # Create order with near-expiration option
        near_expiry_date = date.today()  # Expiring today
        
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=near_expiry_date,
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=1,
                order_type=OrderType.BTO,
                price=0.5
            )
        ]
        
        near_expiry_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(near_expiry_order, sample_portfolio)
        
        # Should generate near expiration warnings
        expiry_warnings = [
            warning for warning in result.warnings
            if warning.code == "NEAR_EXPIRATION"
        ]
        
        if expiry_warnings:
            assert expiry_warnings[0].severity == "warning"

    @patch('app.services.order_validation_advanced.date')
    def test_expiration_day_restriction(self, mock_date, sample_portfolio):
        """Test expiration day selling restriction."""
        # Mock today as expiration day
        expiry_date = date(2024, 3, 15)
        mock_date.today.return_value = expiry_date
        
        validator = ComplexOrderValidator()
        
        # Try to sell option on expiration day
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=expiry_date,
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=call,
                quantity=-1,  # Selling on expiration day
                order_type=OrderType.STO,
                price=0.1
            )
        ]
        
        expiry_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(expiry_order, sample_portfolio)
        
        # Should have regulatory violation
        expiry_issues = [
            issue for issue in result.issues
            if issue.code == "EXPIRATION_DAY_SHORT"
        ]
        
        assert len(expiry_issues) > 0
        assert expiry_issues[0].severity == "error"

    def test_margin_requirement_calculation_stock(self, covered_call_order, sample_portfolio):
        """Test margin requirement calculation for stock positions."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(covered_call_order, sample_portfolio)
        
        # Should calculate margin requirement
        assert result.margin_requirement > 0
        
        # For covered call: stock margin + option premium
        expected_stock_margin = 100 * 155.0 * 0.5  # 50% margin on stock
        expected_option_premium = 1 * 3.0 * 100  # Option premium received
        
        # Margin should be reasonable
        assert result.margin_requirement > expected_stock_margin - expected_option_premium

    def test_margin_requirement_calculation_options(self, vertical_spread_order, sample_portfolio):
        """Test margin requirement calculation for options."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        # Should calculate margin requirement
        assert result.margin_requirement > 0
        
        # For options, should include premium and potential margin
        assert result.margin_requirement > 0

    def test_max_profit_loss_vertical_spread(self, vertical_spread_order, sample_portfolio):
        """Test max profit/loss calculation for vertical spread."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        # Should calculate max profit and loss
        if result.max_profit is not None:
            assert result.max_profit > 0  # Bull call spread can be profitable
        
        if result.max_loss is not None:
            assert result.max_loss > 0  # Limited loss

    def test_breakeven_calculation_vertical_spread(self, vertical_spread_order, sample_portfolio):
        """Test breakeven calculation for vertical spread."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        # Vertical spread should have breakeven points
        if result.breakeven_points:
            assert len(result.breakeven_points) >= 1
            assert all(isinstance(bp, float) for bp in result.breakeven_points)

    def test_iron_condor_pnl_calculation(self, sample_portfolio):
        """Test P&L calculation for iron condor."""
        validator = ComplexOrderValidator()
        
        # Create iron condor (4-leg strategy)
        # Sell put spread (lower strikes) + sell call spread (higher strikes)
        put1 = Put(
            symbol="AAPL240315P00145000",
            underlying=Stock("AAPL"),
            strike=145.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        put2 = Put(
            symbol="AAPL240315P00150000",
            underlying=Stock("AAPL"),
            strike=150.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        call1 = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call2 = Call(
            symbol="AAPL240315C00165000",
            underlying=Stock("AAPL"),
            strike=165.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(asset=put1, quantity=1, order_type=OrderType.BTO, price=1.0),    # Buy put (lower)
            OrderLeg(asset=put2, quantity=-1, order_type=OrderType.STO, price=2.0),   # Sell put (higher)
            OrderLeg(asset=call1, quantity=-1, order_type=OrderType.STO, price=3.0),  # Sell call (lower)
            OrderLeg(asset=call2, quantity=1, order_type=OrderType.BTO, price=1.0),   # Buy call (higher)
        ]
        
        iron_condor = MultiLegOrder(legs=legs)
        result = validator.validate_order(iron_condor, sample_portfolio)
        
        # Should detect iron condor
        assert result.detected_strategy == StrategyType.IRON_CONDOR
        
        # Should calculate P&L metrics
        if result.max_profit is not None and result.max_loss is not None:
            assert result.max_profit > 0  # Net credit strategy
            assert result.max_loss > 0    # Limited loss

    def test_strategy_description_generation(self, vertical_spread_order, sample_portfolio):
        """Test strategy description generation."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        assert result.strategy_description is not None
        assert isinstance(result.strategy_description, str)
        assert len(result.strategy_description) > 0
        
        # Should contain relevant terms
        description_lower = result.strategy_description.lower()
        assert "spread" in description_lower

    def test_straddle_breakeven_calculation(self, straddle_order, sample_portfolio):
        """Test breakeven calculation for straddle."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(straddle_order, sample_portfolio)
        
        # Straddle should have two breakeven points
        if result.breakeven_points:
            assert len(result.breakeven_points) == 2
            
            # Breakevens should be on either side of strike
            strike = 155.0
            breakevens = sorted(result.breakeven_points)
            assert breakevens[0] < strike < breakevens[1]

    def test_custom_strategy_detection(self, sample_portfolio):
        """Test detection of custom/unrecognized strategies."""
        validator = ComplexOrderValidator()
        
        # Create unusual strategy that doesn't fit standard patterns
        call1 = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call2 = Call(
            symbol="MSFT240315C00300000",  # Different underlying
            underlying=Stock("MSFT"),
            strike=300.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(asset=call1, quantity=1, order_type=OrderType.BTO, price=5.0),
            OrderLeg(asset=call2, quantity=1, order_type=OrderType.BTO, price=10.0)
        ]
        
        custom_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(custom_order, sample_portfolio)
        
        # Should detect as custom strategy
        assert result.detected_strategy == StrategyType.CUSTOM

    def test_required_options_level_mapping(self):
        """Test required options level mapping for strategies."""
        validator = ComplexOrderValidator()
        
        # Test various strategy level requirements
        assert validator._get_required_options_level(StrategyType.COVERED_CALL) == 1
        assert validator._get_required_options_level(StrategyType.SINGLE_LEG) == 2
        assert validator._get_required_options_level(StrategyType.VERTICAL_SPREAD) == 3
        assert validator._get_required_options_level(StrategyType.IRON_CONDOR) == 3
        assert validator._get_required_options_level(StrategyType.CUSTOM) == 4

    def test_validation_result_completeness(self, vertical_spread_order, sample_portfolio):
        """Test that validation result contains all required fields."""
        validator = ComplexOrderValidator()
        
        result = validator.validate_order(vertical_spread_order, sample_portfolio)
        
        # Check all required fields are present
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'detected_strategy')
        assert hasattr(result, 'issues')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'info')
        assert hasattr(result, 'margin_requirement')
        assert hasattr(result, 'max_profit')
        assert hasattr(result, 'max_loss')
        assert hasattr(result, 'breakeven_points')
        assert hasattr(result, 'strategy_description')

    def test_complex_three_leg_strategy(self, sample_portfolio):
        """Test detection of three-leg strategies (butterfly)."""
        validator = ComplexOrderValidator()
        
        # Create butterfly spread (buy-sell-buy pattern)
        call1 = Call(
            symbol="AAPL240315C00150000",
            underlying=Stock("AAPL"),
            strike=150.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call2 = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call3 = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(asset=call1, quantity=1, order_type=OrderType.BTO, price=7.0),   # Buy low strike
            OrderLeg(asset=call2, quantity=-2, order_type=OrderType.STO, price=4.0),  # Sell 2x middle
            OrderLeg(asset=call3, quantity=1, order_type=OrderType.BTO, price=2.0),   # Buy high strike
        ]
        
        butterfly_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(butterfly_order, sample_portfolio)
        
        # Should detect butterfly pattern
        assert result.detected_strategy == StrategyType.BUTTERFLY

    def test_error_handling_invalid_asset(self, sample_portfolio):
        """Test error handling for invalid assets."""
        validator = ComplexOrderValidator()
        
        # Create order with None asset (should not happen in practice)
        legs = [
            OrderLeg(
                asset=None,  # Invalid asset
                quantity=1,
                order_type=OrderType.BTO,
                price=5.0
            )
        ]
        
        invalid_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(invalid_order, sample_portfolio)
        
        # Should handle gracefully and mark as invalid
        assert result.is_valid is False
        
        # Should have validation issues
        invalid_asset_issues = [
            issue for issue in result.issues
            if issue.code == "INVALID_ASSET"
        ]
        
        assert len(invalid_asset_issues) > 0


class TestDataClasses:
    """Test data classes used in order validation."""

    def test_validation_issue(self):
        """Test ValidationIssue data class."""
        issue = ValidationIssue(
            severity="error",
            code="TEST_ERROR",
            message="Test error message",
            field="test_field",
            leg_index=0
        )
        
        assert issue.severity == "error"
        assert issue.code == "TEST_ERROR"
        assert issue.message == "Test error message"
        assert issue.field == "test_field"
        assert issue.leg_index == 0

    def test_strategy_validation(self):
        """Test StrategyValidation data class."""
        validation = StrategyValidation(
            strategy_type=StrategyType.VERTICAL_SPREAD,
            min_legs=2,
            max_legs=2,
            required_asset_types=["option"],
            same_underlying=True,
            same_expiration=True,
            strike_relationship="different"
        )
        
        assert validation.strategy_type == StrategyType.VERTICAL_SPREAD
        assert validation.min_legs == 2
        assert validation.max_legs == 2
        assert "option" in validation.required_asset_types
        assert validation.same_underlying is True
        assert validation.same_expiration is True
        assert validation.strike_relationship == "different"

    def test_complex_order_validation_result(self):
        """Test ComplexOrderValidationResult data class."""
        result = ComplexOrderValidationResult(
            is_valid=True,
            detected_strategy=StrategyType.STRADDLE,
            issues=[],
            warnings=[],
            info=[],
            margin_requirement=5000.0,
            max_profit=2000.0,
            max_loss=3000.0,
            breakeven_points=[152.0, 158.0],
            strategy_description="Long straddle at 155 strike"
        )
        
        assert result.is_valid is True
        assert result.detected_strategy == StrategyType.STRADDLE
        assert result.margin_requirement == 5000.0
        assert result.max_profit == 2000.0
        assert result.max_loss == 3000.0
        assert len(result.breakeven_points) == 2
        assert result.strategy_description == "Long straddle at 155 strike"


class TestStrategyDetection:
    """Test strategy detection logic in detail."""

    def test_two_leg_strategy_detection(self):
        """Test detection of various two-leg strategies."""
        validator = ComplexOrderValidator()
        
        # Test covered call detection
        stock = Stock("AAPL")
        call = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        covered_call_legs = [
            OrderLeg(asset=stock, quantity=100, order_type=OrderType.BUY, price=155.0),
            OrderLeg(asset=call, quantity=-1, order_type=OrderType.STO, price=3.0)
        ]
        
        covered_call_order = MultiLegOrder(legs=covered_call_legs)
        strategy = validator._detect_strategy(covered_call_order)
        
        assert strategy == StrategyType.COVERED_CALL

    def test_protective_put_detection(self):
        """Test detection of protective put strategy."""
        validator = ComplexOrderValidator()
        
        stock = Stock("AAPL")
        put = Put(
            symbol="AAPL240315P00150000",
            underlying=Stock("AAPL"),
            strike=150.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        protective_put_legs = [
            OrderLeg(asset=stock, quantity=100, order_type=OrderType.BUY, price=155.0),
            OrderLeg(asset=put, quantity=1, order_type=OrderType.BTO, price=2.0)
        ]
        
        protective_put_order = MultiLegOrder(legs=protective_put_legs)
        strategy = validator._detect_strategy(protective_put_order)
        
        assert strategy == StrategyType.PROTECTIVE_PUT

    def test_strangle_detection(self):
        """Test detection of strangle strategy."""
        validator = ComplexOrderValidator()
        
        # Different strikes, same expiration, different option types
        call = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        put = Put(
            symbol="AAPL240315P00150000",
            underlying=Stock("AAPL"),
            strike=150.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        strangle_legs = [
            OrderLeg(asset=call, quantity=1, order_type=OrderType.BTO, price=3.0),
            OrderLeg(asset=put, quantity=1, order_type=OrderType.BTO, price=2.0)
        ]
        
        strangle_order = MultiLegOrder(legs=strangle_legs)
        strategy = validator._detect_strategy(strangle_order)
        
        assert strategy == StrategyType.STRANGLE

    def test_calendar_spread_detection(self):
        """Test detection of calendar spread strategy."""
        validator = ComplexOrderValidator()
        
        # Same strike, different expirations
        call_near = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call_far = Call(
            symbol="AAPL240415C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 4, 15),
            option_type="call"
        )
        
        calendar_legs = [
            OrderLeg(asset=call_near, quantity=-1, order_type=OrderType.STO, price=3.0),
            OrderLeg(asset=call_far, quantity=1, order_type=OrderType.BTO, price=5.0)
        ]
        
        calendar_order = MultiLegOrder(legs=calendar_legs)
        strategy = validator._detect_strategy(calendar_order)
        
        assert strategy == StrategyType.CALENDAR_SPREAD

    def test_four_leg_iron_butterfly_detection(self):
        """Test detection of iron butterfly strategy."""
        validator = ComplexOrderValidator()
        
        # Iron butterfly: short straddle + long strangle
        put_low = Put(
            symbol="AAPL240315P00150000",
            underlying=Stock("AAPL"),
            strike=150.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        put_mid = Put(
            symbol="AAPL240315P00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="put"
        )
        
        call_mid = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        call_high = Call(
            symbol="AAPL240315C00160000",
            underlying=Stock("AAPL"),
            strike=160.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        iron_butterfly_legs = [
            OrderLeg(asset=put_low, quantity=1, order_type=OrderType.BTO, price=1.0),
            OrderLeg(asset=put_mid, quantity=-1, order_type=OrderType.STO, price=3.0),
            OrderLeg(asset=call_mid, quantity=-1, order_type=OrderType.STO, price=3.0),
            OrderLeg(asset=call_high, quantity=1, order_type=OrderType.BTO, price=1.0),
        ]
        
        iron_butterfly_order = MultiLegOrder(legs=iron_butterfly_legs)
        strategy = validator._detect_strategy(iron_butterfly_order)
        
        assert strategy == StrategyType.IRON_BUTTERFLY


class TestRealWorldScenarios:
    """Test real-world validation scenarios."""

    def test_large_portfolio_complex_order(self):
        """Test validation with large portfolio and complex order."""
        validator = ComplexOrderValidator()
        
        # Large diversified portfolio
        positions = []
        for i, symbol in enumerate(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]):
            positions.append(
                Position(
                    symbol=symbol,
                    quantity=100 * (i + 1),
                    avg_price=100.0 + i * 50,
                    current_price=110.0 + i * 55,
                    asset=Stock(symbol)
                )
            )
        
        large_portfolio = Portfolio(
            cash_balance=500000.0,
            positions=positions,
            total_value=1000000.0,
            daily_pnl=10000.0,
            total_pnl=100000.0
        )
        
        # Complex iron condor order
        legs = [
            OrderLeg(
                asset=Put(
                    symbol="AAPL240315P00145000",
                    underlying=Stock("AAPL"),
                    strike=145.0,
                    expiration_date=date(2024, 3, 15),
                    option_type="put"
                ),
                quantity=1,
                order_type=OrderType.BTO,
                price=1.0
            ),
            OrderLeg(
                asset=Put(
                    symbol="AAPL240315P00150000",
                    underlying=Stock("AAPL"),
                    strike=150.0,
                    expiration_date=date(2024, 3, 15),
                    option_type="put"
                ),
                quantity=-1,
                order_type=OrderType.STO,
                price=2.0
            ),
            OrderLeg(
                asset=Call(
                    symbol="AAPL240315C00160000",
                    underlying=Stock("AAPL"),
                    strike=160.0,
                    expiration_date=date(2024, 3, 15),
                    option_type="call"
                ),
                quantity=-1,
                order_type=OrderType.STO,
                price=3.0
            ),
            OrderLeg(
                asset=Call(
                    symbol="AAPL240315C00165000",
                    underlying=Stock("AAPL"),
                    strike=165.0,
                    expiration_date=date(2024, 3, 15),
                    option_type="call"
                ),
                quantity=1,
                order_type=OrderType.BTO,
                price=1.0
            ),
        ]
        
        iron_condor_order = MultiLegOrder(legs=legs)
        
        result = validator.validate_order(
            iron_condor_order, large_portfolio, options_level=4
        )
        
        # Should be valid with sufficient options level and capital
        assert result.is_valid is True
        assert result.detected_strategy == StrategyType.IRON_CONDOR
        assert result.margin_requirement > 0

    def test_insufficient_capital_scenario(self):
        """Test validation with insufficient capital."""
        validator = ComplexOrderValidator()
        
        # Small portfolio
        small_portfolio = Portfolio(
            cash_balance=1000.0,  # Very limited cash
            positions=[],
            total_value=1000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        # Expensive order
        expensive_call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(
                asset=expensive_call,
                quantity=10,  # Large quantity
                order_type=OrderType.BTO,
                price=50.0  # Expensive option
            )
        ]
        
        expensive_order = MultiLegOrder(legs=legs)
        result = validator.validate_order(expensive_order, small_portfolio)
        
        # Should generate concentration warnings
        concentration_warnings = [
            w for w in result.warnings
            if w.code == "HIGH_CONCENTRATION"
        ]
        
        # Order value (10 * 50 * 100 = $50,000) is much larger than portfolio
        assert len(concentration_warnings) > 0

    def test_beginner_options_level_restriction(self):
        """Test validation for beginner options trading level."""
        validator = ComplexOrderValidator()
        
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        # Advanced strategy (iron condor) with beginner level
        call = Call(
            symbol="AAPL240315C00155000",
            underlying=Stock("AAPL"),
            strike=155.0,
            expiration_date=date(2024, 3, 15),
            option_type="call"
        )
        
        legs = [
            OrderLeg(asset=call, quantity=1, order_type=OrderType.BTO, price=5.0)
        ]
        
        simple_order = MultiLegOrder(legs=legs)
        
        # Test with options level 0 (no options allowed)
        result = validator.validate_order(simple_order, portfolio, options_level=0)
        
        # Should be blocked
        level_issues = [
            issue for issue in result.issues
            if issue.code == "INSUFFICIENT_OPTIONS_LEVEL"
        ]
        
        assert len(level_issues) > 0
        assert result.is_valid is False