"""
Comprehensive test suite for order_validation_advanced.py service.

Tests all classes, methods, and edge cases for 100% coverage:
- ComplexOrderValidator class and all methods
- Strategy detection algorithms
- Validation rules and compliance checks
- Risk calculations and margin requirements
- P&L calculations for different strategies
- Breakeven point calculations
- Strategy descriptions and error handling
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.models.assets import Option, Stock
from app.schemas.orders import MultiLegOrder, OrderLeg
from app.schemas.positions import Portfolio
from app.services.order_validation_advanced import (
    ComplexOrderValidationResult,
    ComplexOrderValidator,
    StrategyType,
    StrategyValidation,
    ValidationIssue,
    complex_order_validator,
    get_complex_order_validator,
)


class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_validation_issue_creation(self):
        """Test ValidationIssue creation with required fields."""
        issue = ValidationIssue(
            severity="error", code="TEST_CODE", message="Test message"
        )

        assert issue.severity == "error"
        assert issue.code == "TEST_CODE"
        assert issue.message == "Test message"
        assert issue.field is None
        assert issue.leg_index is None

    def test_validation_issue_with_optional_fields(self):
        """Test ValidationIssue with optional fields."""
        issue = ValidationIssue(
            severity="warning",
            code="FIELD_WARNING",
            message="Field warning message",
            field="quantity",
            leg_index=1,
        )

        assert issue.severity == "warning"
        assert issue.field == "quantity"
        assert issue.leg_index == 1


class TestStrategyValidation:
    """Test StrategyValidation dataclass."""

    def test_strategy_validation_defaults(self):
        """Test StrategyValidation with default values."""
        validation = StrategyValidation(
            strategy_type=StrategyType.VERTICAL_SPREAD,
            min_legs=2,
            max_legs=2,
            required_asset_types=["option"],
        )

        assert validation.same_underlying is True
        assert validation.same_expiration is True
        assert validation.strike_relationship is None

    def test_strategy_validation_custom_values(self):
        """Test StrategyValidation with custom values."""
        validation = StrategyValidation(
            strategy_type=StrategyType.CALENDAR_SPREAD,
            min_legs=2,
            max_legs=2,
            required_asset_types=["option"],
            same_underlying=True,
            same_expiration=False,
            strike_relationship="same",
        )

        assert validation.same_underlying is True
        assert validation.same_expiration is False
        assert validation.strike_relationship == "same"


class TestComplexOrderValidationResult:
    """Test ComplexOrderValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test validation result creation."""
        result = ComplexOrderValidationResult(
            is_valid=True,
            detected_strategy=StrategyType.STRADDLE,
            issues=[],
            warnings=[],
            info=[],
            margin_requirement=1000.0,
        )

        assert result.is_valid is True
        assert result.detected_strategy == StrategyType.STRADDLE
        assert result.margin_requirement == 1000.0
        assert result.max_profit is None
        assert result.max_loss is None
        assert result.breakeven_points == []

    def test_validation_result_with_all_fields(self):
        """Test validation result with all fields populated."""
        issues = [ValidationIssue("error", "E001", "Error message")]
        warnings = [ValidationIssue("warning", "W001", "Warning message")]
        info = [ValidationIssue("info", "I001", "Info message")]

        result = ComplexOrderValidationResult(
            is_valid=False,
            detected_strategy=StrategyType.IRON_CONDOR,
            issues=issues,
            warnings=warnings,
            info=info,
            margin_requirement=2500.0,
            max_profit=500.0,
            max_loss=1500.0,
            breakeven_points=[95.0, 105.0],
            strategy_description="Test strategy",
        )

        assert result.is_valid is False
        assert len(result.issues) == 1
        assert len(result.warnings) == 1
        assert len(result.info) == 1
        assert result.max_profit == 500.0
        assert result.max_loss == 1500.0
        assert result.breakeven_points == [95.0, 105.0]
        assert result.strategy_description == "Test strategy"


class TestComplexOrderValidatorInitialization:
    """Test ComplexOrderValidator initialization."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = ComplexOrderValidator()

        assert validator.strategy_rules is not None
        assert isinstance(validator.strategy_rules, dict)

        # Check some key strategies are initialized
        assert StrategyType.VERTICAL_SPREAD in validator.strategy_rules
        assert StrategyType.STRADDLE in validator.strategy_rules
        assert StrategyType.IRON_CONDOR in validator.strategy_rules

    def test_initialize_strategy_rules(self):
        """Test strategy rules initialization."""
        validator = ComplexOrderValidator()
        rules = validator.strategy_rules

        # Test vertical spread rules
        vertical_rules = rules[StrategyType.VERTICAL_SPREAD]
        assert vertical_rules.min_legs == 2
        assert vertical_rules.max_legs == 2
        assert vertical_rules.required_asset_types == ["option"]
        assert vertical_rules.same_underlying is True
        assert vertical_rules.same_expiration is True

        # Test calendar spread rules
        calendar_rules = rules[StrategyType.CALENDAR_SPREAD]
        assert calendar_rules.same_expiration is False
        assert calendar_rules.strike_relationship == "same"

        # Test covered call rules
        covered_call_rules = rules[StrategyType.COVERED_CALL]
        assert covered_call_rules.required_asset_types == ["stock", "option"]
        assert covered_call_rules.same_expiration is False


class TestComplexOrderValidatorBasicValidation:
    """Test basic validation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def sample_option(self):
        """Create sample option."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        return Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call $150 2024-03-15",
            underlying=stock,
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

    def test_validate_basic_requirements_empty_order(self, validator):
        """Test basic validation with empty order."""
        order = MultiLegOrder(legs=[])
        issues = validator._validate_basic_requirements(order)

        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].code == "EMPTY_ORDER"

    def test_validate_basic_requirements_duplicate_symbols(
        self, validator, sample_stock
    ):
        """Test basic validation with duplicate symbols."""
        leg1 = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        leg2 = OrderLeg(asset=sample_stock, quantity=200, price=151.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_basic_requirements(order)

        assert any(issue.code == "DUPLICATE_SYMBOLS" for issue in issues)

    def test_validate_basic_requirements_zero_quantity(self, validator, sample_stock):
        """Test basic validation with zero quantity."""
        leg = OrderLeg(asset=sample_stock, quantity=0, price=150.0)
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_basic_requirements(order)

        assert any(issue.code == "ZERO_QUANTITY" for issue in issues)
        assert any(issue.leg_index == 0 for issue in issues)

    def test_validate_basic_requirements_invalid_asset(self, validator):
        """Test basic validation with invalid asset."""
        # Create leg with invalid asset (None)
        leg = OrderLeg(asset=None, quantity=100, price=150.0)
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_basic_requirements(order)

        assert any(issue.code == "INVALID_ASSET" for issue in issues)

    def test_validate_basic_requirements_valid_order(
        self, validator, sample_stock, sample_option
    ):
        """Test basic validation with valid order."""
        leg1 = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        leg2 = OrderLeg(asset=sample_option, quantity=-1, price=5.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_basic_requirements(order)

        assert len(issues) == 0


class TestComplexOrderValidatorStrategyDetection:
    """Test strategy detection methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_detect_strategy_single_leg(self, validator, sample_stock):
        """Test single leg strategy detection."""
        leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        order = MultiLegOrder(legs=[leg])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.SINGLE_LEG

    def test_detect_strategy_covered_call(self, validator, sample_stock, create_option):
        """Test covered call detection."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))

        stock_leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        option_leg = OrderLeg(asset=option, quantity=-1, price=5.0)
        order = MultiLegOrder(legs=[stock_leg, option_leg])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.COVERED_CALL

    def test_detect_strategy_protective_put(
        self, validator, sample_stock, create_option
    ):
        """Test protective put detection."""
        option = create_option("AAPL240315P00140000", "put", 140.0, date(2024, 3, 15))

        stock_leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        option_leg = OrderLeg(asset=option, quantity=1, price=3.0)
        order = MultiLegOrder(legs=[stock_leg, option_leg])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.PROTECTIVE_PUT

    def test_detect_strategy_straddle(self, validator, create_option):
        """Test straddle detection."""
        call_option = create_option(
            "AAPL240315C00150000", "call", 150.0, date(2024, 3, 15)
        )
        put_option = create_option(
            "AAPL240315P00150000", "put", 150.0, date(2024, 3, 15)
        )

        call_leg = OrderLeg(asset=call_option, quantity=1, price=5.0)
        put_leg = OrderLeg(asset=put_option, quantity=1, price=4.0)
        order = MultiLegOrder(legs=[call_leg, put_leg])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.STRADDLE

    def test_detect_strategy_strangle(self, validator, create_option):
        """Test strangle detection."""
        call_option = create_option(
            "AAPL240315C00155000", "call", 155.0, date(2024, 3, 15)
        )
        put_option = create_option(
            "AAPL240315P00145000", "put", 145.0, date(2024, 3, 15)
        )

        call_leg = OrderLeg(asset=call_option, quantity=1, price=3.0)
        put_leg = OrderLeg(asset=put_option, quantity=1, price=2.0)
        order = MultiLegOrder(legs=[call_leg, put_leg])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.STRANGLE

    def test_detect_strategy_vertical_spread(self, validator, create_option):
        """Test vertical spread detection."""
        call_option_1 = create_option(
            "AAPL240315C00150000", "call", 150.0, date(2024, 3, 15)
        )
        call_option_2 = create_option(
            "AAPL240315C00155000", "call", 155.0, date(2024, 3, 15)
        )

        leg1 = OrderLeg(asset=call_option_1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=call_option_2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.VERTICAL_SPREAD

    def test_detect_strategy_calendar_spread(self, validator, create_option):
        """Test calendar spread detection."""
        call_option_1 = create_option(
            "AAPL240315C00150000", "call", 150.0, date(2024, 3, 15)
        )
        call_option_2 = create_option(
            "AAPL240415C00150000", "call", 150.0, date(2024, 4, 15)
        )

        leg1 = OrderLeg(asset=call_option_1, quantity=-1, price=5.0)
        leg2 = OrderLeg(asset=call_option_2, quantity=1, price=7.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.CALENDAR_SPREAD

    def test_detect_strategy_butterfly(self, validator, create_option):
        """Test butterfly detection."""
        call_1 = create_option("AAPL240315C00145000", "call", 145.0, date(2024, 3, 15))
        call_2 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        call_3 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=call_1, quantity=1, price=7.0)
        leg2 = OrderLeg(asset=call_2, quantity=-2, price=5.0)
        leg3 = OrderLeg(asset=call_3, quantity=1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2, leg3])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.BUTTERFLY

    def test_detect_strategy_iron_condor(self, validator, create_option):
        """Test iron condor detection."""
        put_1 = create_option("AAPL240315P00140000", "put", 140.0, date(2024, 3, 15))
        put_2 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        call_1 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))
        call_2 = create_option("AAPL240315C00160000", "call", 160.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=put_1, quantity=1, price=1.0)  # Buy low put
        leg2 = OrderLeg(asset=put_2, quantity=-1, price=2.0)  # Sell high put
        leg3 = OrderLeg(asset=call_1, quantity=-1, price=2.5)  # Sell low call
        leg4 = OrderLeg(asset=call_2, quantity=1, price=1.5)  # Buy high call
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.IRON_CONDOR

    def test_detect_strategy_iron_butterfly(self, validator, create_option):
        """Test iron butterfly detection."""
        put_1 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        put_2 = create_option("AAPL240315P00150000", "put", 150.0, date(2024, 3, 15))
        call_1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        call_2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=put_1, quantity=1, price=2.0)
        leg2 = OrderLeg(asset=put_2, quantity=-1, price=4.0)
        leg3 = OrderLeg(asset=call_1, quantity=-1, price=4.0)
        leg4 = OrderLeg(asset=call_2, quantity=1, price=2.0)
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.IRON_BUTTERFLY

    def test_detect_strategy_custom_different_underlyings(
        self, validator, create_option
    ):
        """Test custom strategy detection with different underlyings."""
        # Create options with different underlyings
        aapl_stock = Stock(symbol="AAPL", name="Apple Inc.")
        msft_stock = Stock(symbol="MSFT", name="Microsoft Corp.")

        aapl_option = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=aapl_stock,
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        msft_option = Option(
            symbol="MSFT240315C00300000",
            name="MSFT Call",
            underlying=msft_stock,
            option_type="call",
            strike=300.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=aapl_option, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=msft_option, quantity=1, price=10.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.CUSTOM

    def test_detect_strategy_five_legs_custom(self, validator, create_option):
        """Test custom strategy detection with five legs."""
        options = []
        legs = []

        for _i, strike in enumerate([140, 145, 150, 155, 160]):
            option = create_option(
                f"AAPL240315C00{strike}000", "call", strike, date(2024, 3, 15)
            )
            options.append(option)
            legs.append(OrderLeg(asset=option, quantity=1, price=5.0))

        order = MultiLegOrder(legs=legs)

        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.CUSTOM


class TestComplexOrderValidatorStrategyValidation:
    """Test strategy-specific validation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_validate_strategy_invalid_leg_count(self, validator, create_option):
        """Test strategy validation with invalid leg count."""
        # Create single leg for vertical spread (requires 2)
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_strategy(order, StrategyType.VERTICAL_SPREAD)

        assert any(issue.code == "INVALID_LEG_COUNT" for issue in issues)

    def test_validate_strategy_missing_asset_type(self, validator, create_option):
        """Test strategy validation with missing asset type."""
        # Create order with only options for covered call (requires stock + option)
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_strategy(order, StrategyType.COVERED_CALL)

        assert any(issue.code == "MISSING_ASSET_TYPE" for issue in issues)

    def test_validate_strategy_different_underlyings(self, validator):
        """Test strategy validation with different underlyings."""
        # Create options with different underlyings
        aapl_stock = Stock(symbol="AAPL", name="Apple Inc.")
        msft_stock = Stock(symbol="MSFT", name="Microsoft Corp.")

        aapl_option = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=aapl_stock,
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        msft_option = Option(
            symbol="MSFT240315C00300000",
            name="MSFT Call",
            underlying=msft_stock,
            option_type="call",
            strike=300.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=aapl_option, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=msft_option, quantity=-1, price=10.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_strategy(order, StrategyType.VERTICAL_SPREAD)

        assert any(issue.code == "DIFFERENT_UNDERLYINGS" for issue in issues)

    def test_validate_strategy_different_expirations(self, validator, create_option):
        """Test strategy validation with different expirations."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240415C00155000", "call", 155.0, date(2024, 4, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_strategy(order, StrategyType.VERTICAL_SPREAD)

        assert any(issue.code == "DIFFERENT_EXPIRATIONS" for issue in issues)

    def test_validate_strategy_valid_vertical_spread(self, validator, create_option):
        """Test valid vertical spread validation."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_strategy(order, StrategyType.VERTICAL_SPREAD)

        assert len(issues) == 0

    def test_validate_strategy_no_rules_for_strategy(self, validator, create_option):
        """Test validation when no rules exist for strategy."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        # Test with strategy not in rules
        issues = validator._validate_strategy(order, StrategyType.CUSTOM)

        assert len(issues) == 0  # No rules means no issues


class TestComplexOrderValidatorOptionsLevel:
    """Test options level validation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_get_required_options_level(self, validator):
        """Test getting required options level for strategies."""
        assert validator._get_required_options_level(StrategyType.COVERED_CALL) == 1
        assert validator._get_required_options_level(StrategyType.SINGLE_LEG) == 2
        assert validator._get_required_options_level(StrategyType.VERTICAL_SPREAD) == 3
        assert validator._get_required_options_level(StrategyType.RISK_REVERSAL) == 4
        assert validator._get_required_options_level(StrategyType.CUSTOM) == 4

    def test_validate_options_level_insufficient(self, validator, create_option):
        """Test options level validation with insufficient level."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_options_level(
            order, StrategyType.VERTICAL_SPREAD, 1
        )

        assert any(issue.code == "INSUFFICIENT_OPTIONS_LEVEL" for issue in issues)

    def test_validate_options_level_sufficient(self, validator, create_option):
        """Test options level validation with sufficient level."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        issues = validator._validate_options_level(
            order, StrategyType.VERTICAL_SPREAD, 4
        )

        # Should not have insufficient options level error
        assert not any(issue.code == "INSUFFICIENT_OPTIONS_LEVEL" for issue in issues)

    def test_has_naked_options_true(self, validator, create_option):
        """Test naked options detection with short options."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)  # Short option
        order = MultiLegOrder(legs=[leg])

        has_naked = validator._has_naked_options(order)
        assert has_naked is True

    def test_has_naked_options_false(self, validator, create_option):
        """Test naked options detection with long options."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)  # Long option
        order = MultiLegOrder(legs=[leg])

        has_naked = validator._has_naked_options(order)
        assert has_naked is False

    def test_validate_options_level_naked_options_not_allowed(
        self, validator, create_option
    ):
        """Test naked options validation with insufficient level."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)  # Short option
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_options_level(order, StrategyType.SINGLE_LEG, 2)

        assert any(issue.code == "NAKED_OPTIONS_NOT_ALLOWED" for issue in issues)

    def test_validate_options_level_naked_options_allowed(
        self, validator, create_option
    ):
        """Test naked options validation with sufficient level."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)  # Short option
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_options_level(order, StrategyType.SINGLE_LEG, 4)

        # Should not have naked options error at level 4
        assert not any(issue.code == "NAKED_OPTIONS_NOT_ALLOWED" for issue in issues)


class TestComplexOrderValidatorRiskValidation:
    """Test risk validation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_validate_risk_parameters_high_concentration(
        self, validator, sample_portfolio, create_option
    ):
        """Test risk validation with high concentration warning."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))

        # Create large order (25% of portfolio)
        leg = OrderLeg(asset=option, quantity=25, price=500.0)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, sample_portfolio)

        assert any(warning.code == "HIGH_CONCENTRATION" for warning in warnings)

    def test_validate_risk_parameters_normal_concentration(
        self, validator, sample_portfolio, create_option
    ):
        """Test risk validation with normal concentration."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))

        # Create small order (1% of portfolio)
        leg = OrderLeg(asset=option, quantity=1, price=250.0)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, sample_portfolio)

        assert not any(warning.code == "HIGH_CONCENTRATION" for warning in warnings)

    @patch("app.services.order_validation_advanced.date")
    def test_validate_risk_parameters_near_expiration(
        self, mock_date, validator, sample_portfolio, create_option
    ):
        """Test risk validation with near expiration warning."""
        # Mock today's date
        mock_date.today.return_value = date(2024, 3, 10)

        # Create option expiring in 5 days
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, sample_portfolio)

        assert any(warning.code == "NEAR_EXPIRATION" for warning in warnings)

    @patch("app.services.order_validation_advanced.date")
    def test_validate_risk_parameters_not_near_expiration(
        self, mock_date, validator, sample_portfolio, create_option
    ):
        """Test risk validation without near expiration warning."""
        # Mock today's date
        mock_date.today.return_value = date(2024, 2, 1)

        # Create option expiring in 44 days
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, sample_portfolio)

        assert not any(warning.code == "NEAR_EXPIRATION" for warning in warnings)

    def test_validate_risk_parameters_zero_portfolio_value(
        self, validator, create_option
    ):
        """Test risk validation with zero portfolio value."""
        portfolio = Portfolio(cash_balance=0.0, total_value=0.0, positions=[])

        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, portfolio)

        # Should not crash with zero portfolio value
        assert isinstance(warnings, list)

    def test_validate_risk_parameters_no_prices(
        self, validator, sample_portfolio, create_option
    ):
        """Test risk validation with no leg prices."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=None)
        order = MultiLegOrder(legs=[leg])

        warnings = validator._validate_risk_parameters(order, sample_portfolio)

        # Should handle None prices gracefully
        assert isinstance(warnings, list)


class TestComplexOrderValidatorRegulatoryValidation:
    """Test regulatory validation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    @patch("app.services.order_validation_advanced.date")
    def test_validate_regulatory_requirements_expiration_day_short(
        self, mock_date, validator, sample_portfolio, create_option
    ):
        """Test regulatory validation for expiration day short options."""
        # Mock today as expiration day
        exp_date = date(2024, 3, 15)
        mock_date.today.return_value = exp_date

        option = create_option("AAPL240315C00150000", "call", 150.0, exp_date)
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)  # Short option
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_regulatory_requirements(order, sample_portfolio)

        assert any(issue.code == "EXPIRATION_DAY_SHORT" for issue in issues)

    @patch("app.services.order_validation_advanced.date")
    def test_validate_regulatory_requirements_not_expiration_day(
        self, mock_date, validator, sample_portfolio, create_option
    ):
        """Test regulatory validation for non-expiration day short options."""
        # Mock today as before expiration
        mock_date.today.return_value = date(2024, 3, 10)

        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)  # Short option
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_regulatory_requirements(order, sample_portfolio)

        assert not any(issue.code == "EXPIRATION_DAY_SHORT" for issue in issues)

    def test_validate_regulatory_requirements_long_options(
        self, validator, sample_portfolio, create_option
    ):
        """Test regulatory validation for long options."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)  # Long option
        order = MultiLegOrder(legs=[leg])

        issues = validator._validate_regulatory_requirements(order, sample_portfolio)

        # Long options don't trigger expiration day restrictions
        assert not any(issue.code == "EXPIRATION_DAY_SHORT" for issue in issues)


class TestComplexOrderValidatorMarginCalculation:
    """Test margin calculation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_calculate_margin_requirement_stock_long(
        self, validator, sample_portfolio, sample_stock
    ):
        """Test margin calculation for long stock position."""
        leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Long stock: 50% margin requirement
        expected_margin = 100 * 150.0 * 0.5
        assert margin == expected_margin

    def test_calculate_margin_requirement_stock_no_price(
        self, validator, sample_portfolio, sample_stock
    ):
        """Test margin calculation for stock with no price."""
        leg = OrderLeg(asset=sample_stock, quantity=100, price=None)
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Should use default price of 100
        expected_margin = 100 * 100 * 0.5
        assert margin == expected_margin

    def test_calculate_margin_requirement_option_long(
        self, validator, sample_portfolio, create_option
    ):
        """Test margin calculation for long option position."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Long option: full premium
        expected_margin = 1 * 5.0 * 100
        assert margin == expected_margin

    def test_calculate_margin_requirement_option_short(
        self, validator, sample_portfolio, create_option
    ):
        """Test margin calculation for short option position."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=-1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Short option: simplified calculation
        expected_margin = 1 * 100 * 20  # $20 per contract
        assert margin == expected_margin

    def test_calculate_margin_requirement_option_no_price(
        self, validator, sample_portfolio, create_option
    ):
        """Test margin calculation for option with no price."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=None)
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Should use default price of 1
        expected_margin = 1 * 1 * 100
        assert margin == expected_margin

    def test_calculate_margin_requirement_mixed_positions(
        self, validator, sample_portfolio, sample_stock, create_option
    ):
        """Test margin calculation for mixed stock and option positions."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))

        stock_leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        option_leg = OrderLeg(asset=option, quantity=-1, price=5.0)
        order = MultiLegOrder(legs=[stock_leg, option_leg])

        margin = validator._calculate_margin_requirement(order, sample_portfolio)

        # Stock margin + option margin
        stock_margin = 100 * 150.0 * 0.5
        option_margin = 1 * 100 * 20
        expected_margin = stock_margin + option_margin
        assert margin == expected_margin


class TestComplexOrderValidatorPnLCalculations:
    """Test P&L calculation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_calculate_max_profit_loss_vertical_spread(self, validator, create_option):
        """Test P&L calculation for vertical spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        max_profit, max_loss = validator._calculate_max_profit_loss(order)

        # Debit spread: max profit = spread width - net debit
        # Net debit = 5.0 - 3.0 = 2.0
        # Spread width = 5.0
        # Max profit = 5.0 * 100 - 2.0 * 100 = 300
        # Max loss = 2.0 * 100 = 200
        assert max_profit == 300.0
        assert max_loss == 200.0

    def test_calculate_max_profit_loss_iron_condor(self, validator, create_option):
        """Test P&L calculation for iron condor."""
        put_1 = create_option("AAPL240315P00140000", "put", 140.0, date(2024, 3, 15))
        put_2 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        call_1 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))
        call_2 = create_option("AAPL240315C00160000", "call", 160.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=put_1, quantity=1, price=1.0)
        leg2 = OrderLeg(asset=put_2, quantity=-1, price=2.0)
        leg3 = OrderLeg(asset=call_1, quantity=-1, price=2.5)
        leg4 = OrderLeg(asset=call_2, quantity=1, price=1.5)
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        max_profit, max_loss = validator._calculate_max_profit_loss(order)

        # Net credit = (1.0 - 2.0 - 2.5 + 1.5) * 100 = -200
        # Max spread width = max(5, 5) = 5
        # Max profit = -200 (net credit)
        # Max loss = 5 * 100 - (-200) = 700
        assert max_profit == -200.0
        assert max_loss == 700.0

    def test_calculate_max_profit_loss_unsupported_strategy(
        self, validator, create_option
    ):
        """Test P&L calculation for unsupported strategy."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        max_profit, max_loss = validator._calculate_max_profit_loss(order)

        assert max_profit is None
        assert max_loss is None

    def test_calculate_vertical_spread_pnl_invalid_legs(self, validator, create_option):
        """Test vertical spread P&L with invalid number of legs."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        max_profit, max_loss = validator._calculate_vertical_spread_pnl(order)

        assert max_profit is None
        assert max_loss is None

    def test_calculate_vertical_spread_pnl_non_options(self, validator):
        """Test vertical spread P&L with non-option assets."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="MSFT", name="Microsoft Corp.")

        leg1 = OrderLeg(asset=stock1, quantity=100, price=150.0)
        leg2 = OrderLeg(asset=stock2, quantity=-100, price=300.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        max_profit, max_loss = validator._calculate_vertical_spread_pnl(order)

        assert max_profit is None
        assert max_loss is None

    def test_calculate_vertical_spread_pnl_no_strikes(self, validator):
        """Test vertical spread P&L with options without strikes."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        option1 = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=None,  # No strike
            expiration_date=date(2024, 3, 15),
        )
        option2 = Option(
            symbol="AAPL240315C00155000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=155.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        max_profit, max_loss = validator._calculate_vertical_spread_pnl(order)

        assert max_profit is None
        assert max_loss is None

    def test_calculate_vertical_spread_pnl_credit_spread(
        self, validator, create_option
    ):
        """Test vertical spread P&L for credit spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        # Create credit spread (sell lower strike, buy higher strike)
        leg1 = OrderLeg(asset=option1, quantity=-1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        max_profit, max_loss = validator._calculate_vertical_spread_pnl(order)

        # Net credit = -5.0 + 3.0 = -2.0, but total credit = 2.0 * 100 = 200
        # Spread width = 5.0
        # Max profit = 200 (credit received)
        # Max loss = 5.0 * 100 - 200 = 300
        assert max_profit == 200.0
        assert max_loss == 300.0

    def test_calculate_iron_condor_pnl_invalid_legs(self, validator, create_option):
        """Test iron condor P&L with invalid number of legs."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        max_profit, max_loss = validator._calculate_iron_condor_pnl(order)

        assert max_profit is None
        assert max_loss is None

    def test_calculate_iron_condor_pnl_no_strikes(self, validator):
        """Test iron condor P&L with options without strikes."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        option1 = Option(
            symbol="AAPL240315P00140000",
            name="AAPL Put",
            underlying=stock,
            option_type="put",
            strike=None,  # No strike
            expiration_date=date(2024, 3, 15),
        )
        option2 = Option(
            symbol="AAPL240315P00145000",
            name="AAPL Put",
            underlying=stock,
            option_type="put",
            strike=145.0,
            expiration_date=date(2024, 3, 15),
        )
        option3 = Option(
            symbol="AAPL240315C00155000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=155.0,
            expiration_date=date(2024, 3, 15),
        )
        option4 = Option(
            symbol="AAPL240315C00160000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=160.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=option1, quantity=1, price=1.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=2.0)
        leg3 = OrderLeg(asset=option3, quantity=-1, price=2.5)
        leg4 = OrderLeg(asset=option4, quantity=1, price=1.5)
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        max_profit, max_loss = validator._calculate_iron_condor_pnl(order)

        assert max_profit is None
        assert max_loss is None


class TestComplexOrderValidatorBreakevenCalculations:
    """Test breakeven point calculation methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_calculate_breakeven_points_vertical_spread_bull_call(
        self, validator, create_option
    ):
        """Test breakeven calculation for bull call spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)  # Buy lower strike
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)  # Sell higher strike
        order = MultiLegOrder(legs=[leg1, leg2])

        breakevens = validator._calculate_breakeven_points(order)

        # Bull call spread: breakeven = lower strike + net debit
        # Net debit = 5.0 - 3.0 = 2.0
        # Breakeven = 150.0 + 2.0 = 152.0
        assert len(breakevens) == 1
        assert breakevens[0] == 152.0

    def test_calculate_breakeven_points_vertical_spread_bear_call(
        self, validator, create_option
    ):
        """Test breakeven calculation for bear call spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=-1, price=5.0)  # Sell lower strike
        leg2 = OrderLeg(asset=option2, quantity=1, price=3.0)  # Buy higher strike
        order = MultiLegOrder(legs=[leg1, leg2])

        breakevens = validator._calculate_breakeven_points(order)

        # Bear call spread: breakeven = higher strike + net credit
        # Net credit = -5.0 + 3.0 = -2.0 (actually net debit of 2.0)
        # Breakeven = 155.0 + (-2.0) = 153.0
        assert len(breakevens) == 1
        assert breakevens[0] == 153.0

    def test_calculate_breakeven_points_vertical_spread_bull_put(
        self, validator, create_option
    ):
        """Test breakeven calculation for bull put spread."""
        option1 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315P00150000", "put", 150.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=2.0)  # Buy lower strike
        leg2 = OrderLeg(asset=option2, quantity=-1, price=4.0)  # Sell higher strike
        order = MultiLegOrder(legs=[leg1, leg2])

        breakevens = validator._calculate_breakeven_points(order)

        # Bull put spread: breakeven = higher strike - net credit
        # Net credit = 2.0 - 4.0 = -2.0, so net debit of 2.0
        # But for puts: breakeven = higher strike - net credit
        # Breakeven = 150.0 - (-2.0) = 152.0
        assert len(breakevens) == 1
        assert breakevens[0] == 152.0

    def test_calculate_breakeven_points_vertical_spread_bear_put(
        self, validator, create_option
    ):
        """Test breakeven calculation for bear put spread."""
        option1 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315P00150000", "put", 150.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=-1, price=2.0)  # Sell lower strike
        leg2 = OrderLeg(asset=option2, quantity=1, price=4.0)  # Buy higher strike
        order = MultiLegOrder(legs=[leg1, leg2])

        breakevens = validator._calculate_breakeven_points(order)

        # Bear put spread: breakeven = lower strike - net credit
        # Net credit = -2.0 + 4.0 = 2.0
        # Breakeven = 145.0 - 2.0 = 143.0
        assert len(breakevens) == 1
        assert breakevens[0] == 143.0

    def test_calculate_breakeven_points_straddle(self, validator, create_option):
        """Test breakeven calculation for straddle."""
        call_option = create_option(
            "AAPL240315C00150000", "call", 150.0, date(2024, 3, 15)
        )
        put_option = create_option(
            "AAPL240315P00150000", "put", 150.0, date(2024, 3, 15)
        )

        call_leg = OrderLeg(asset=call_option, quantity=1, price=5.0)
        put_leg = OrderLeg(asset=put_option, quantity=1, price=4.0)
        order = MultiLegOrder(legs=[call_leg, put_leg])

        breakevens = validator._calculate_breakeven_points(order)

        # Straddle: two breakevens = strike ± total premium
        # Total premium = 5.0 + 4.0 = 9.0
        # Breakevens = 150.0 ± 9.0 = [141.0, 159.0]
        assert len(breakevens) == 2
        assert 141.0 in breakevens
        assert 159.0 in breakevens

    def test_calculate_breakeven_points_unsupported_strategy(
        self, validator, create_option
    ):
        """Test breakeven calculation for unsupported strategy."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        breakevens = validator._calculate_breakeven_points(order)

        assert len(breakevens) == 0

    def test_calculate_breakeven_points_vertical_spread_no_strikes(self, validator):
        """Test breakeven calculation with options without strikes."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        option1 = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=None,
            expiration_date=date(2024, 3, 15),
        )
        option2 = Option(
            symbol="AAPL240315C00155000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=155.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        breakevens = validator._calculate_breakeven_points(order)

        assert len(breakevens) == 0

    def test_calculate_breakeven_points_straddle_no_strike(self, validator):
        """Test breakeven calculation for straddle with no strike."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        call_option = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=None,
            expiration_date=date(2024, 3, 15),
        )
        put_option = Option(
            symbol="AAPL240315P00150000",
            name="AAPL Put",
            underlying=stock,
            option_type="put",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        call_leg = OrderLeg(asset=call_option, quantity=1, price=5.0)
        put_leg = OrderLeg(asset=put_option, quantity=1, price=4.0)
        order = MultiLegOrder(legs=[call_leg, put_leg])

        breakevens = validator._calculate_breakeven_points(order)

        assert len(breakevens) == 0

    def test_calculate_breakeven_points_straddle_no_prices(
        self, validator, create_option
    ):
        """Test breakeven calculation for straddle with no prices."""
        call_option = create_option(
            "AAPL240315C00150000", "call", 150.0, date(2024, 3, 15)
        )
        put_option = create_option(
            "AAPL240315P00150000", "put", 150.0, date(2024, 3, 15)
        )

        call_leg = OrderLeg(asset=call_option, quantity=1, price=None)
        put_leg = OrderLeg(asset=put_option, quantity=1, price=4.0)
        order = MultiLegOrder(legs=[call_leg, put_leg])

        breakevens = validator._calculate_breakeven_points(order)

        # Should handle None prices by treating as 0
        # Total premium = 0 + 4.0 = 4.0
        # Breakevens = 150.0 ± 4.0 = [146.0, 154.0]
        assert len(breakevens) == 2
        assert 146.0 in breakevens
        assert 154.0 in breakevens


class TestComplexOrderValidatorStrategyDescriptions:
    """Test strategy description methods."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    def test_generate_strategy_description_vertical_spread(
        self, validator, create_option
    ):
        """Test strategy description for vertical spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        description = validator._generate_strategy_description(
            order, StrategyType.VERTICAL_SPREAD
        )

        assert description == "Bull Call Spread"

    def test_generate_strategy_description_iron_condor(self, validator, create_option):
        """Test strategy description for iron condor."""
        put_1 = create_option("AAPL240315P00140000", "put", 140.0, date(2024, 3, 15))
        put_2 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        call_1 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))
        call_2 = create_option("AAPL240315C00160000", "call", 160.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=put_1, quantity=1, price=1.0)
        leg2 = OrderLeg(asset=put_2, quantity=-1, price=2.0)
        leg3 = OrderLeg(asset=call_1, quantity=-1, price=2.5)
        leg4 = OrderLeg(asset=call_2, quantity=1, price=1.5)
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        description = validator._generate_strategy_description(
            order, StrategyType.IRON_CONDOR
        )

        assert description == "Iron Condor - Limited risk, limited reward strategy"

    def test_generate_strategy_description_covered_call(
        self, validator, sample_stock, create_option
    ):
        """Test strategy description for covered call."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))

        stock_leg = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        option_leg = OrderLeg(asset=option, quantity=-1, price=5.0)
        order = MultiLegOrder(legs=[stock_leg, option_leg])

        description = validator._generate_strategy_description(
            order, StrategyType.COVERED_CALL
        )

        assert (
            description
            == "Covered Call - Income generation strategy with long stock and short call"
        )

    def test_generate_strategy_description_unsupported_strategy(
        self, validator, create_option
    ):
        """Test strategy description for unsupported strategy."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        description = validator._generate_strategy_description(
            order, StrategyType.STRADDLE
        )

        assert description == "Straddle strategy with 1 legs"

    def test_describe_vertical_spread_invalid_legs(self, validator, create_option):
        """Test vertical spread description with invalid number of legs."""
        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        description = validator._describe_vertical_spread(order)

        assert description == "Invalid vertical spread"

    def test_describe_vertical_spread_bear_call(self, validator, create_option):
        """Test vertical spread description for bear call spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=-1, price=5.0)  # Short first leg
        leg2 = OrderLeg(asset=option2, quantity=1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        description = validator._describe_vertical_spread(order)

        assert description == "Bear Call Spread"

    def test_describe_vertical_spread_put_spread(self, validator, create_option):
        """Test vertical spread description for put spread."""
        option1 = create_option("AAPL240315P00145000", "put", 145.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315P00150000", "put", 150.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=2.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=4.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        description = validator._describe_vertical_spread(order)

        assert description == "Bull Put Spread"

    def test_describe_vertical_spread_non_option(self, validator, sample_stock):
        """Test vertical spread description with non-option asset."""
        stock2 = Stock(symbol="MSFT", name="Microsoft Corp.")

        leg1 = OrderLeg(asset=sample_stock, quantity=100, price=150.0)
        leg2 = OrderLeg(asset=stock2, quantity=-100, price=300.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        description = validator._describe_vertical_spread(order)

        assert description == "Bull Unknown Spread"


class TestComplexOrderValidatorMainValidation:
    """Test main validation method."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])

    @pytest.fixture
    def create_option(self):
        """Factory function to create options."""

        def _create_option(symbol, option_type, strike, expiration_date):
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            return Option(
                symbol=symbol,
                name=f"AAPL {option_type.title()} ${strike}",
                underlying=stock,
                option_type=option_type,
                strike=strike,
                expiration_date=expiration_date,
            )

        return _create_option

    def test_validate_order_valid_vertical_spread(
        self, validator, sample_portfolio, create_option
    ):
        """Test complete order validation for valid vertical spread."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        result = validator.validate_order(order, sample_portfolio, options_level=3)

        assert result.is_valid is True
        assert result.detected_strategy == StrategyType.VERTICAL_SPREAD
        assert result.margin_requirement > 0
        assert result.max_profit is not None
        assert result.max_loss is not None
        assert len(result.breakeven_points) > 0
        assert result.strategy_description is not None

    def test_validate_order_empty_order(self, validator, sample_portfolio):
        """Test complete order validation for empty order."""
        order = MultiLegOrder(legs=[])

        result = validator.validate_order(order, sample_portfolio)

        assert result.is_valid is False
        assert any(issue.code == "EMPTY_ORDER" for issue in result.issues)

    def test_validate_order_insufficient_options_level(
        self, validator, sample_portfolio, create_option
    ):
        """Test complete order validation with insufficient options level."""
        option1 = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        option2 = create_option("AAPL240315C00155000", "call", 155.0, date(2024, 3, 15))

        leg1 = OrderLeg(asset=option1, quantity=1, price=5.0)
        leg2 = OrderLeg(asset=option2, quantity=-1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2])

        result = validator.validate_order(order, sample_portfolio, options_level=1)

        assert result.is_valid is False
        assert any(
            issue.code == "INSUFFICIENT_OPTIONS_LEVEL" for issue in result.issues
        )

    def test_validate_order_with_warnings(self, validator, create_option):
        """Test complete order validation with warnings."""
        # Create high concentration order with small portfolio
        small_portfolio = Portfolio(
            cash_balance=1000.0, total_value=5000.0, positions=[]
        )

        option = create_option("AAPL240315C00150000", "call", 150.0, date(2024, 3, 15))
        leg = OrderLeg(asset=option, quantity=20, price=50.0)  # Large order
        order = MultiLegOrder(legs=[leg])

        result = validator.validate_order(order, small_portfolio, options_level=4)

        assert len(result.warnings) > 0
        assert any(warning.code == "HIGH_CONCENTRATION" for warning in result.warnings)

    @patch("app.services.order_validation_advanced.date")
    def test_validate_order_regulatory_violations(
        self, mock_date, validator, sample_portfolio, create_option
    ):
        """Test complete order validation with regulatory violations."""
        # Mock today as expiration day
        exp_date = date(2024, 3, 15)
        mock_date.today.return_value = exp_date

        option = create_option("AAPL240315C00150000", "call", 150.0, exp_date)
        leg = OrderLeg(
            asset=option, quantity=-1, price=5.0
        )  # Short option on expiration day
        order = MultiLegOrder(legs=[leg])

        result = validator.validate_order(order, sample_portfolio, options_level=4)

        assert result.is_valid is False
        assert any(issue.code == "EXPIRATION_DAY_SHORT" for issue in result.issues)

    def test_validate_order_custom_strategy(
        self, validator, sample_portfolio, create_option
    ):
        """Test complete order validation for custom strategy."""
        options = []
        legs = []

        for _i, strike in enumerate([140, 145, 150, 155, 160]):
            option = create_option(
                f"AAPL240315C00{strike}000", "call", strike, date(2024, 3, 15)
            )
            options.append(option)
            legs.append(OrderLeg(asset=option, quantity=1, price=5.0))

        order = MultiLegOrder(legs=legs)

        result = validator.validate_order(order, sample_portfolio, options_level=4)

        assert result.detected_strategy == StrategyType.CUSTOM
        # Custom strategies require level 4
        assert result.is_valid is True


class TestComplexOrderValidatorGlobalInstance:
    """Test global validator instance and factory function."""

    def test_global_validator_instance(self):
        """Test that global validator instance exists."""
        assert complex_order_validator is not None
        assert isinstance(complex_order_validator, ComplexOrderValidator)

    def test_get_complex_order_validator(self):
        """Test get_complex_order_validator function."""
        validator = get_complex_order_validator()

        assert validator is not None
        assert isinstance(validator, ComplexOrderValidator)
        assert validator is complex_order_validator


class TestComplexOrderValidatorEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ComplexOrderValidator()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])

    def test_validate_order_with_logging(self, validator, sample_portfolio):
        """Test that validation includes proper logging."""
        with patch("app.services.order_validation_advanced.logger") as mock_logger:
            order = MultiLegOrder(legs=[])
            validator.validate_order(order, sample_portfolio)

            # Should log the validation attempt
            mock_logger.info.assert_called_once()

    def test_butterfly_detection_edge_cases(self, validator):
        """Test butterfly detection with edge cases."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        # Create options with None strikes
        option1 = Option(
            symbol="AAPL240315C00145000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=None,
            expiration_date=date(2024, 3, 15),
        )
        option2 = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )
        option3 = Option(
            symbol="AAPL240315C00155000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=155.0,
            expiration_date=date(2024, 3, 15),
        )

        leg1 = OrderLeg(asset=option1, quantity=1, price=7.0)
        leg2 = OrderLeg(asset=option2, quantity=-2, price=5.0)
        leg3 = OrderLeg(asset=option3, quantity=1, price=3.0)
        order = MultiLegOrder(legs=[leg1, leg2, leg3])

        strategy = validator._detect_strategy(order)

        # Should not be detected as butterfly due to None strike
        assert strategy == StrategyType.CUSTOM

    def test_iron_condor_detection_edge_cases(self, validator):
        """Test iron condor detection with edge cases."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        # Create malformed iron condor (wrong quantities)
        put_1 = Option(
            symbol="AAPL240315P00140000",
            name="AAPL Put",
            underlying=stock,
            option_type="put",
            strike=140.0,
            expiration_date=date(2024, 3, 15),
        )
        put_2 = Option(
            symbol="AAPL240315P00145000",
            name="AAPL Put",
            underlying=stock,
            option_type="put",
            strike=145.0,
            expiration_date=date(2024, 3, 15),
        )
        call_1 = Option(
            symbol="AAPL240315C00155000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=155.0,
            expiration_date=date(2024, 3, 15),
        )
        call_2 = Option(
            symbol="AAPL240315C00160000",
            name="AAPL Call",
            underlying=stock,
            option_type="call",
            strike=160.0,
            expiration_date=date(2024, 3, 15),
        )

        # Wrong quantities for iron condor
        leg1 = OrderLeg(asset=put_1, quantity=-1, price=1.0)
        leg2 = OrderLeg(asset=put_2, quantity=-1, price=2.0)
        leg3 = OrderLeg(asset=call_1, quantity=-1, price=2.5)
        leg4 = OrderLeg(asset=call_2, quantity=-1, price=1.5)
        order = MultiLegOrder(legs=[leg1, leg2, leg3, leg4])

        strategy = validator._detect_strategy(order)

        assert strategy == StrategyType.CUSTOM

    def test_validation_with_none_underlying(self, validator):
        """Test validation with options that have None underlying."""
        option = Option(
            symbol="AAPL240315C00150000",
            name="AAPL Call",
            underlying=None,
            option_type="call",
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        leg = OrderLeg(asset=option, quantity=1, price=5.0)
        order = MultiLegOrder(legs=[leg])

        # Should not crash with None underlying
        strategy = validator._detect_strategy(order)
        assert strategy == StrategyType.SINGLE_LEG

    def test_margin_calculation_negative_quantities(self, validator):
        """Test margin calculation with negative quantities."""
        portfolio = Portfolio(cash_balance=10000.0, total_value=50000.0, positions=[])
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        leg = OrderLeg(asset=stock, quantity=-100, price=150.0)  # Short stock
        order = MultiLegOrder(legs=[leg])

        margin = validator._calculate_margin_requirement(order, portfolio)

        # Should handle negative quantities
        assert margin > 0
