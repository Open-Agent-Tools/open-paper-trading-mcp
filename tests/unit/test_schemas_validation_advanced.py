"""
Advanced test coverage for validation schemas.

Tests validation mixins, utility functions, consistency validators,
business rule validation, and complex validation scenarios.
"""

from datetime import date, datetime

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.validation import (
    AccountValidationMixin,
    OrderValidationMixin,
    PositionValidationMixin,
    SchemaValidationMixin,
    ValidationHelpers,
    validate_order_against_account,
    validate_percentage,
    validate_pnl,
    validate_portfolio_consistency,
    validate_position_consistency,
    validate_symbol,
)


class TestValidateSymbol:
    """Test validate_symbol utility function."""

    def test_validate_symbol_basic_stock(self):
        """Test validating basic stock symbols."""
        assert validate_symbol("AAPL") == "AAPL"
        assert validate_symbol("GOOGL") == "GOOGL"
        assert validate_symbol("MSFT") == "MSFT"

    def test_validate_symbol_lowercase_normalization(self):
        """Test symbol normalization to uppercase."""
        assert validate_symbol("aapl") == "AAPL"
        assert validate_symbol("googl") == "GOOGL"
        assert validate_symbol("Msft") == "MSFT"

    def test_validate_symbol_whitespace_trimming(self):
        """Test symbol whitespace trimming."""
        assert validate_symbol("  AAPL  ") == "AAPL"
        assert validate_symbol("\tGOOGL\n") == "GOOGL"
        assert validate_symbol(" MSFT ") == "MSFT"

    def test_validate_symbol_empty_string(self):
        """Test validation of empty symbol."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol("")
        assert "Symbol cannot be empty" in str(exc_info.value)

    def test_validate_symbol_none_input(self):
        """Test validation of None symbol."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol(None)
        assert "Symbol must be a non-empty string" in str(exc_info.value)

    def test_validate_symbol_non_string_input(self):
        """Test validation of non-string symbol."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol(123)
        assert "Symbol must be a non-empty string" in str(exc_info.value)

    def test_validate_symbol_whitespace_only(self):
        """Test validation of whitespace-only symbol."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol("   ")
        assert "Symbol cannot be empty" in str(exc_info.value)

    def test_validate_symbol_too_long(self):
        """Test validation of overly long symbol."""
        long_symbol = "A" * 21  # 21 characters
        with pytest.raises(ValueError) as exc_info:
            validate_symbol(long_symbol)
        assert "Symbol too long" in str(exc_info.value)

    def test_validate_symbol_max_length(self):
        """Test validation of symbol at max length."""
        max_length_symbol = "A" * 20  # 20 characters (max allowed)
        assert validate_symbol(max_length_symbol) == max_length_symbol

    def test_validate_symbol_invalid_characters(self):
        """Test validation of symbols with invalid characters."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol("AAPL@")  # @ is not allowed in first 4 chars
        assert "Invalid symbol format" in str(exc_info.value)

    def test_validate_symbol_numbers_allowed(self):
        """Test that numbers are allowed in symbols."""
        # Some ETFs and funds have numbers
        assert validate_symbol("SPY5") == "SPY5"
        assert validate_symbol("QQQ1") == "QQQ1"

    def test_validate_symbol_valid_characters_only(self):
        """Test symbols with only valid characters."""
        assert validate_symbol("ABCD") == "ABCD"
        assert validate_symbol("XYZ1") == "XYZ1"
        assert validate_symbol("ABC0") == "ABC0"


class TestValidatePercentage:
    """Test validate_percentage utility function."""

    def test_validate_percentage_valid_values(self):
        """Test validation of valid percentage values."""
        assert validate_percentage(0.0) == 0.0
        assert validate_percentage(0.5) == 0.5
        assert validate_percentage(-0.25) == -0.25
        assert validate_percentage(1.0) == 1.0
        assert validate_percentage(-1.0) == -1.0

    def test_validate_percentage_none_value(self):
        """Test validation of None percentage."""
        assert validate_percentage(None) is None

    def test_validate_percentage_integer_input(self):
        """Test validation of integer percentage."""
        assert validate_percentage(5) == 5.0
        assert validate_percentage(-2) == -2.0

    def test_validate_percentage_reasonable_bounds(self):
        """Test validation within reasonable bounds."""
        assert validate_percentage(5.0) == 5.0
        assert validate_percentage(-3.5) == -3.5
        assert validate_percentage(10.0) == 10.0  # Edge of reasonable range

    def test_validate_percentage_unreasonably_large(self):
        """Test validation of unreasonably large percentage."""
        with pytest.raises(ValueError) as exc_info:
            validate_percentage(15.0)  # > 10 (1000%)
        assert "seems unreasonably large" in str(exc_info.value)

    def test_validate_percentage_unreasonably_small(self):
        """Test validation of unreasonably small percentage."""
        with pytest.raises(ValueError) as exc_info:
            validate_percentage(-15.0)  # < -10 (-1000%)
        assert "seems unreasonably large" in str(exc_info.value)

    def test_validate_percentage_non_numeric(self):
        """Test validation of non-numeric percentage."""
        with pytest.raises(ValueError) as exc_info:
            validate_percentage("5%")
        assert "must be a number" in str(exc_info.value)

    def test_validate_percentage_custom_field_name(self):
        """Test validation with custom field name."""
        with pytest.raises(ValueError) as exc_info:
            validate_percentage(15.0, "delta")
        assert "delta seems unreasonably large" in str(exc_info.value)


class TestValidatePnl:
    """Test validate_pnl utility function."""

    def test_validate_pnl_valid_values(self):
        """Test validation of valid P&L values."""
        assert validate_pnl(0.0) == 0.0
        assert validate_pnl(1000.0) == 1000.0
        assert validate_pnl(-500.0) == -500.0
        assert validate_pnl(1_000_000.0) == 1_000_000.0

    def test_validate_pnl_none_value(self):
        """Test validation of None P&L."""
        assert validate_pnl(None) is None

    def test_validate_pnl_integer_input(self):
        """Test validation of integer P&L."""
        assert validate_pnl(1000) == 1000.0
        assert validate_pnl(-500) == -500.0

    def test_validate_pnl_large_but_reasonable(self):
        """Test validation of large but reasonable P&L."""
        large_pnl = 999_999_999.0  # Just under 1 billion
        assert validate_pnl(large_pnl) == large_pnl

    def test_validate_pnl_unreasonably_large_positive(self):
        """Test validation of unreasonably large positive P&L."""
        with pytest.raises(ValueError) as exc_info:
            validate_pnl(1_000_000_001.0)  # Over 1 billion
        assert "seems unreasonably large" in str(exc_info.value)

    def test_validate_pnl_unreasonably_large_negative(self):
        """Test validation of unreasonably large negative P&L."""
        with pytest.raises(ValueError) as exc_info:
            validate_pnl(-1_000_000_001.0)  # Loss over 1 billion
        assert "seems unreasonably large" in str(exc_info.value)

    def test_validate_pnl_non_numeric(self):
        """Test validation of non-numeric P&L."""
        with pytest.raises(ValueError) as exc_info:
            validate_pnl("$1000")
        assert "must be a number" in str(exc_info.value)

    def test_validate_pnl_custom_field_name(self):
        """Test validation with custom field name."""
        with pytest.raises(ValueError) as exc_info:
            validate_pnl(1_000_000_001.0, "unrealized_pnl")
        assert "unrealized_pnl seems unreasonably large" in str(exc_info.value)


class TestValidateOrderAgainstAccount:
    """Test validate_order_against_account function."""

    def test_validate_order_sufficient_funds(self):
        """Test validation of order with sufficient funds."""

        class MockOrder:
            order_type = "buy"
            price = 100.0
            quantity = 10
            symbol = "AAPL"

        class MockAccount:
            cash_balance = 2000.0

        order = MockOrder()
        account = MockAccount()

        # Should not raise exception
        result = validate_order_against_account(order, account)
        assert result is True

    def test_validate_order_insufficient_funds(self):
        """Test validation of order with insufficient funds."""

        class MockOrder:
            order_type = "buy"
            price = 100.0
            quantity = 20  # $2000 order
            symbol = "AAPL"

        class MockAccount:
            cash_balance = 1500.0  # Not enough

        order = MockOrder()
        account = MockAccount()

        with pytest.raises(ValueError) as exc_info:
            validate_order_against_account(order, account)
        assert "Insufficient funds" in str(exc_info.value)

    def test_validate_order_buy_to_open_insufficient_funds(self):
        """Test validation of buy_to_open order with insufficient funds."""

        class MockOrder:
            order_type = "buy_to_open"
            price = 50.0
            quantity = 100
            symbol = "AAPL240119C00195000"

        class MockAccount:
            cash_balance = 3000.0  # Need $5000

        order = MockOrder()
        account = MockAccount()

        with pytest.raises(ValueError) as exc_info:
            validate_order_against_account(order, account)
        assert "Insufficient funds" in str(exc_info.value)

    def test_validate_order_sell_no_funds_check(self):
        """Test validation of sell order doesn't check funds."""

        class MockOrder:
            order_type = "sell"
            price = 100.0
            quantity = 10
            symbol = "AAPL"

        class MockAccount:
            cash_balance = 0.0  # No cash, but selling

        order = MockOrder()
        account = MockAccount()

        # Should pass since we're selling
        result = validate_order_against_account(order, account)
        assert result is True

    def test_validate_order_market_order_no_price(self):
        """Test validation of market order with no price."""

        class MockOrder:
            order_type = "buy"
            price = None  # Market order
            quantity = 10
            symbol = "AAPL"

        class MockAccount:
            cash_balance = 5000.0

        order = MockOrder()
        account = MockAccount()

        # Should pass since price is None
        result = validate_order_against_account(order, account)
        assert result is True

    def test_validate_order_invalid_symbol(self):
        """Test validation of order with invalid symbol."""

        class MockOrder:
            order_type = "buy"
            price = 100.0
            quantity = 10
            symbol = ""  # Invalid symbol

        class MockAccount:
            cash_balance = 2000.0

        order = MockOrder()
        account = MockAccount()

        with pytest.raises(ValueError) as exc_info:
            validate_order_against_account(order, account)
        assert "Invalid order symbol" in str(exc_info.value)


class TestValidatePositionConsistency:
    """Test validate_position_consistency function."""

    def test_validate_position_consistent_pnl(self):
        """Test validation of position with consistent P&L."""

        class MockPosition:
            current_price = 105.0
            avg_price = 100.0
            quantity = 100
            unrealized_pnl = 500.0  # (105-100) * 100 = 500

        position = MockPosition()

        result = validate_position_consistency(position)
        assert result is True

    def test_validate_position_inconsistent_pnl(self):
        """Test validation of position with inconsistent P&L."""

        class MockPosition:
            current_price = 105.0
            avg_price = 100.0
            quantity = 100
            unrealized_pnl = 1000.0  # Should be 500, not 1000

        position = MockPosition()

        with pytest.raises(ValueError) as exc_info:
            validate_position_consistency(position)
        assert "Inconsistent P&L calculation" in str(exc_info.value)

    def test_validate_position_pnl_tolerance(self):
        """Test P&L validation with floating point tolerance."""

        class MockPosition:
            current_price = 100.01
            avg_price = 100.0
            quantity = 100
            unrealized_pnl = 1.0  # Should be 1.0, within tolerance

        position = MockPosition()

        result = validate_position_consistency(position)
        assert result is True

    def test_validate_position_zero_quantity_positive_price(self):
        """Test validation of zero quantity with positive avg price."""

        class MockPosition:
            avg_price = 100.0
            quantity = 0  # Zero quantity
            unrealized_pnl = None

        position = MockPosition()

        result = validate_position_consistency(position)
        assert result is True

    def test_validate_position_nonzero_quantity_zero_price(self):
        """Test validation of non-zero quantity with zero avg price."""

        class MockPosition:
            avg_price = 0.0  # Invalid for non-zero position
            quantity = 100
            unrealized_pnl = None

        position = MockPosition()

        with pytest.raises(ValueError) as exc_info:
            validate_position_consistency(position)
        assert "Average price must be positive" in str(exc_info.value)

    def test_validate_position_option_fields_valid(self):
        """Test validation of option position with valid fields."""

        class MockPosition:
            option_type = "call"
            strike = 195.0
            expiration_date = date(2025, 1, 19)  # Future date
            avg_price = 5.50
            quantity = 10

        position = MockPosition()

        result = validate_position_consistency(position)
        assert result is True

    def test_validate_position_option_zero_strike(self):
        """Test validation of option with zero strike."""

        class MockPosition:
            option_type = "call"
            strike = 0.0  # Invalid strike
            expiration_date = date(2025, 1, 19)
            avg_price = 5.50
            quantity = 10

        position = MockPosition()

        with pytest.raises(ValueError) as exc_info:
            validate_position_consistency(position)
        assert "positive strike price" in str(exc_info.value)

    def test_validate_position_option_past_expiration(self):
        """Test validation of option with past expiration."""

        class MockPosition:
            option_type = "put"
            strike = 190.0
            expiration_date = date(2020, 1, 19)  # Past date
            avg_price = 4.25
            quantity = 10

        position = MockPosition()

        with pytest.raises(ValueError) as exc_info:
            validate_position_consistency(position)
        assert "cannot be in the past" in str(exc_info.value)

    def test_validate_position_invalid_option_type(self):
        """Test validation of invalid option type."""

        class MockPosition:
            option_type = "invalid"  # Invalid type
            strike = 195.0
            expiration_date = date(2025, 1, 19)
            avg_price = 5.50
            quantity = 10

        position = MockPosition()

        with pytest.raises(ValueError) as exc_info:
            validate_position_consistency(position)
        assert 'must be "call" or "put"' in str(exc_info.value)


class TestValidatePortfolioConsistency:
    """Test validate_portfolio_consistency function."""

    def test_validate_portfolio_basic_consistency(self):
        """Test validation of basic portfolio consistency."""

        class MockPosition:
            current_price = 105.0
            quantity = 100

        class MockPortfolio:
            cash_balance = 10000.0
            total_value = 20500.0  # 10000 cash + 10500 positions
            positions = [MockPosition()]

        portfolio = MockPortfolio()

        result = validate_portfolio_consistency(portfolio)
        assert result is True

    def test_validate_portfolio_missing_attributes(self):
        """Test validation of portfolio missing required attributes."""

        class MockPortfolio:
            # Missing positions and cash_balance
            pass

        portfolio = MockPortfolio()

        with pytest.raises(ValueError) as exc_info:
            validate_portfolio_consistency(portfolio)
        assert "must have positions and cash_balance attributes" in str(exc_info.value)

    def test_validate_portfolio_inconsistent_total_value(self):
        """Test validation of portfolio with inconsistent total value."""

        class MockPosition:
            current_price = 105.0
            quantity = 100

        class MockPortfolio:
            cash_balance = 10000.0
            total_value = 25000.0  # Wrong total (should be ~20500)
            positions = [MockPosition()]

        portfolio = MockPortfolio()

        with pytest.raises(ValueError) as exc_info:
            validate_portfolio_consistency(portfolio)
        assert "Inconsistent total value" in str(exc_info.value)

    def test_validate_portfolio_empty_positions(self):
        """Test validation of portfolio with no positions."""

        class MockPortfolio:
            cash_balance = 10000.0
            total_value = 10000.0
            positions = []

        portfolio = MockPortfolio()

        result = validate_portfolio_consistency(portfolio)
        assert result is True

    def test_validate_portfolio_position_validation_failure(self):
        """Test portfolio validation fails when position validation fails."""

        class MockPosition:
            avg_price = 0.0  # Invalid for non-zero position
            quantity = 100

        class MockPortfolio:
            cash_balance = 10000.0
            positions = [MockPosition()]

        portfolio = MockPortfolio()

        with pytest.raises(ValueError) as exc_info:
            validate_portfolio_consistency(portfolio)
        assert "Average price must be positive" in str(exc_info.value)


class TestValidationHelpers:
    """Test ValidationHelpers class methods."""

    def test_is_market_hours_weekday_market_open(self):
        """Test is_market_hours during weekday market hours."""
        # Monday at 2 PM (14:00)
        market_time = datetime(2024, 1, 15, 14, 0, 0)  # Monday

        result = ValidationHelpers.is_market_hours(market_time)
        assert result is True

    def test_is_market_hours_weekday_before_open(self):
        """Test is_market_hours before market open."""
        # Monday at 8 AM (before 9:30)
        early_time = datetime(2024, 1, 15, 8, 0, 0)  # Monday

        result = ValidationHelpers.is_market_hours(early_time)
        assert result is False

    def test_is_market_hours_weekday_after_close(self):
        """Test is_market_hours after market close."""
        # Monday at 5 PM (after 4:00)
        late_time = datetime(2024, 1, 15, 17, 0, 0)  # Monday

        result = ValidationHelpers.is_market_hours(late_time)
        assert result is False

    def test_is_market_hours_weekend(self):
        """Test is_market_hours on weekend."""
        # Saturday at 2 PM
        weekend_time = datetime(2024, 1, 13, 14, 0, 0)  # Saturday

        result = ValidationHelpers.is_market_hours(weekend_time)
        assert result is False

    def test_is_market_hours_edge_case_930am(self):
        """Test is_market_hours at exactly 9:30 AM."""
        # Monday at 9:30 AM exactly
        open_time = datetime(2024, 1, 15, 9, 30, 0)  # Monday

        result = ValidationHelpers.is_market_hours(open_time)
        assert result is True

    def test_is_market_hours_edge_case_4pm(self):
        """Test is_market_hours at exactly 4:00 PM."""
        # Monday at 4:00 PM exactly
        close_time = datetime(2024, 1, 15, 16, 0, 0)  # Monday

        result = ValidationHelpers.is_market_hours(close_time)
        assert result is False  # Market closes at 4:00

    def test_is_market_hours_default_now(self):
        """Test is_market_hours with default parameter (now)."""
        # Just test that it doesn't crash - result depends on when test runs
        result = ValidationHelpers.is_market_hours()
        assert isinstance(result, bool)

    def test_normalize_symbol(self):
        """Test normalize_symbol method."""
        assert ValidationHelpers.normalize_symbol("aapl") == "AAPL"
        assert ValidationHelpers.normalize_symbol("  GOOGL  ") == "GOOGL"

    def test_calculate_spread_percentage_valid(self):
        """Test calculate_spread_percentage with valid inputs."""
        # Bid $99, Ask $101, Mid $100, Spread $2, Percentage 2%
        result = ValidationHelpers.calculate_spread_percentage(99.0, 101.0)
        assert result == 2.0

    def test_calculate_spread_percentage_narrow_spread(self):
        """Test calculate_spread_percentage with narrow spread."""
        # Bid $100.49, Ask $100.51, Mid $100.50, Spread $0.02, Percentage ~0.02%
        result = ValidationHelpers.calculate_spread_percentage(100.49, 100.51)
        expected = ((100.51 - 100.49) / 100.50) * 100
        assert abs(result - expected) < 0.001

    def test_calculate_spread_percentage_none_inputs(self):
        """Test calculate_spread_percentage with None inputs."""
        assert ValidationHelpers.calculate_spread_percentage(None, 101.0) is None
        assert ValidationHelpers.calculate_spread_percentage(99.0, None) is None
        assert ValidationHelpers.calculate_spread_percentage(None, None) is None

    def test_calculate_spread_percentage_zero_prices(self):
        """Test calculate_spread_percentage with zero prices."""
        assert ValidationHelpers.calculate_spread_percentage(0.0, 101.0) is None
        assert ValidationHelpers.calculate_spread_percentage(99.0, 0.0) is None

    def test_calculate_spread_percentage_negative_prices(self):
        """Test calculate_spread_percentage with negative prices."""
        assert ValidationHelpers.calculate_spread_percentage(-99.0, 101.0) is None
        assert ValidationHelpers.calculate_spread_percentage(99.0, -101.0) is None

    def test_calculate_spread_percentage_inverted_spread(self):
        """Test calculate_spread_percentage with bid > ask."""
        # Invalid: bid higher than ask
        result = ValidationHelpers.calculate_spread_percentage(101.0, 99.0)
        assert result is None


class TestSchemaValidationMixin:
    """Test SchemaValidationMixin validation methods."""

    def test_schema_validation_mixin_integration(self):
        """Test SchemaValidationMixin integration with Pydantic model."""

        class TestModel(BaseModel, SchemaValidationMixin):
            quantity: int
            price: float | None = None
            cash_balance: float

        # Valid model
        model = TestModel(quantity=100, price=150.0, cash_balance=10000.0)
        assert model.quantity == 100
        assert model.price == 150.0
        assert model.cash_balance == 10000.0

    def test_schema_validation_mixin_quantity_zero(self):
        """Test SchemaValidationMixin quantity validation."""

        class TestModel(BaseModel, SchemaValidationMixin):
            quantity: int

        with pytest.raises(ValidationError) as exc_info:
            TestModel(quantity=0)

        error = exc_info.value.errors()[0]
        assert "Quantity cannot be zero" in error["msg"]

    def test_schema_validation_mixin_negative_price(self):
        """Test SchemaValidationMixin price validation."""

        class TestModel(BaseModel, SchemaValidationMixin):
            price: float

        with pytest.raises(ValidationError) as exc_info:
            TestModel(price=-150.0)

        error = exc_info.value.errors()[0]
        assert "Price must be positive" in error["msg"]

    def test_schema_validation_mixin_negative_cash_balance(self):
        """Test SchemaValidationMixin cash balance validation."""

        class TestModel(BaseModel, SchemaValidationMixin):
            cash_balance: float

        with pytest.raises(ValidationError) as exc_info:
            TestModel(cash_balance=-1000.0)

        error = exc_info.value.errors()[0]
        assert "Cash balance cannot be negative" in error["msg"]


class TestOrderValidationMixin:
    """Test OrderValidationMixin validation methods."""

    def test_order_validation_mixin_integration(self):
        """Test OrderValidationMixin integration with Pydantic model."""

        class TestOrderModel(BaseModel, OrderValidationMixin):
            order_type: str
            quantity: int
            price: float | None = None
            stop_price: float | None = None
            trail_percent: float | None = None
            trail_amount: float | None = None

        model = TestOrderModel(order_type="buy", quantity=100, price=150.0)
        assert model.order_type == "buy"
        assert model.quantity == 100
        assert model.price == 150.0

    def test_order_validation_mixin_invalid_order_type(self):
        """Test OrderValidationMixin order type validation."""

        class TestOrderModel(BaseModel, OrderValidationMixin):
            order_type: str

        with pytest.raises(ValidationError) as exc_info:
            TestOrderModel(order_type="invalid_type")

        error = exc_info.value.errors()[0]
        assert "Invalid order type" in error["msg"]

    def test_order_validation_mixin_valid_order_types(self):
        """Test OrderValidationMixin accepts all valid order types."""

        class TestOrderModel(BaseModel, OrderValidationMixin):
            order_type: str

        valid_types = [
            "buy",
            "sell",
            "buy_to_open",
            "sell_to_open",
            "buy_to_close",
            "sell_to_close",
            "stop_loss",
            "stop_limit",
            "trailing_stop",
        ]

        for order_type in valid_types:
            model = TestOrderModel(order_type=order_type)
            assert model.order_type == order_type


class TestPositionValidationMixin:
    """Test PositionValidationMixin validation methods."""

    def test_position_validation_mixin_integration(self):
        """Test PositionValidationMixin integration with Pydantic model."""

        class TestPositionModel(BaseModel, PositionValidationMixin):
            avg_price: float
            strike: float | None = None
            expiration_date: date | None = None
            option_type: str | None = None

        model = TestPositionModel(
            avg_price=150.0,
            strike=195.0,
            expiration_date=date(2025, 1, 19),
            option_type="call",
        )
        assert model.avg_price == 150.0
        assert model.strike == 195.0
        assert model.option_type == "call"

    def test_position_validation_mixin_zero_avg_price(self):
        """Test PositionValidationMixin avg price validation."""

        class TestPositionModel(BaseModel, PositionValidationMixin):
            avg_price: float

        with pytest.raises(ValidationError) as exc_info:
            TestPositionModel(avg_price=0.0)

        error = exc_info.value.errors()[0]
        assert "Average price must be positive" in error["msg"]

    def test_position_validation_mixin_zero_strike(self):
        """Test PositionValidationMixin strike validation."""

        class TestPositionModel(BaseModel, PositionValidationMixin):
            strike: float

        with pytest.raises(ValidationError) as exc_info:
            TestPositionModel(strike=0.0)

        error = exc_info.value.errors()[0]
        assert "Strike price must be positive" in error["msg"]

    def test_position_validation_mixin_past_expiration(self):
        """Test PositionValidationMixin expiration date validation."""

        class TestPositionModel(BaseModel, PositionValidationMixin):
            expiration_date: date

        with pytest.raises(ValidationError) as exc_info:
            TestPositionModel(expiration_date=date(2020, 1, 1))

        error = exc_info.value.errors()[0]
        assert "Expiration date must be in the future" in error["msg"]

    def test_position_validation_mixin_invalid_option_type(self):
        """Test PositionValidationMixin option type validation."""

        class TestPositionModel(BaseModel, PositionValidationMixin):
            option_type: str

        with pytest.raises(ValidationError) as exc_info:
            TestPositionModel(option_type="invalid")

        error = exc_info.value.errors()[0]
        assert 'Option type must be "call" or "put"' in error["msg"]


class TestAccountValidationMixin:
    """Test AccountValidationMixin validation methods."""

    def test_account_validation_mixin_integration(self):
        """Test AccountValidationMixin integration with Pydantic model."""

        class TestAccountModel(BaseModel, AccountValidationMixin):
            owner: str | None = None
            name: str | None = None
            cash_balance: float

        model = TestAccountModel(
            owner="John Doe", name="Trading Account", cash_balance=10000.0
        )
        assert model.owner == "John Doe"
        assert model.name == "Trading Account"
        assert model.cash_balance == 10000.0

    def test_account_validation_mixin_empty_owner(self):
        """Test AccountValidationMixin empty owner validation."""

        class TestAccountModel(BaseModel, AccountValidationMixin):
            owner: str

        with pytest.raises(ValidationError) as exc_info:
            TestAccountModel(owner="")

        error = exc_info.value.errors()[0]
        assert "Owner cannot be empty" in error["msg"]

    def test_account_validation_mixin_whitespace_owner(self):
        """Test AccountValidationMixin whitespace-only owner validation."""

        class TestAccountModel(BaseModel, AccountValidationMixin):
            owner: str

        with pytest.raises(ValidationError) as exc_info:
            TestAccountModel(owner="   ")

        error = exc_info.value.errors()[0]
        assert "Owner cannot be empty" in error["msg"]

    def test_account_validation_mixin_owner_trimming(self):
        """Test AccountValidationMixin owner trimming."""

        class TestAccountModel(BaseModel, AccountValidationMixin):
            owner: str

        model = TestAccountModel(owner="  John Doe  ")
        assert model.owner == "John Doe"

    def test_account_validation_mixin_negative_cash_balance(self):
        """Test AccountValidationMixin cash balance validation."""

        class TestAccountModel(BaseModel, AccountValidationMixin):
            cash_balance: float

        with pytest.raises(ValidationError) as exc_info:
            TestAccountModel(cash_balance=-1000.0)

        error = exc_info.value.errors()[0]
        assert "Cash balance cannot be negative" in error["msg"]


class TestValidationComplexScenarios:
    """Test complex validation scenarios and edge cases."""

    def test_validation_multiple_mixins(self):
        """Test model with multiple validation mixins."""

        class ComplexModel(BaseModel, SchemaValidationMixin, OrderValidationMixin):
            order_type: str
            quantity: int
            price: float | None = None
            cash_balance: float

        model = ComplexModel(
            order_type="buy", quantity=100, price=150.0, cash_balance=10000.0
        )
        assert model.order_type == "buy"
        assert model.quantity == 100
        assert model.price == 150.0
        assert model.cash_balance == 10000.0

    def test_validation_mixin_method_resolution_order(self):
        """Test method resolution order with multiple mixins."""

        class TestModel(BaseModel, SchemaValidationMixin, OrderValidationMixin):
            quantity: int  # Both mixins have quantity validators

        # Should use the last mixin's validator (OrderValidationMixin)
        with pytest.raises(ValidationError) as exc_info:
            TestModel(quantity=0)

        error = exc_info.value.errors()[0]
        # Should use OrderValidationMixin's message
        assert "Quantity cannot be zero" in error["msg"]

    def test_validation_business_rule_combinations(self):
        """Test combinations of business validation rules."""

        # Test order with multiple validation constraints
        class MockOrder:
            order_type = "buy_to_open"  # Should check funds
            price = 50.0
            quantity = 100  # $5000 order
            symbol = "AAPL240119C00195000"  # Valid option symbol

        class MockAccount:
            cash_balance = 6000.0  # Just enough funds

        order = MockOrder()
        account = MockAccount()

        result = validate_order_against_account(order, account)
        assert result is True

    def test_validation_floating_point_precision(self):
        """Test validation with floating point precision issues."""

        class MockPosition:
            current_price = 100.333333333
            avg_price = 100.0
            quantity = 3
            unrealized_pnl = 1.0  # Should be 0.999999999, within tolerance

        position = MockPosition()

        result = validate_position_consistency(position)
        assert result is True

    def test_validation_extreme_values_handling(self):
        """Test validation with extreme but valid values."""
        # Very large percentage (but within bounds)
        result = validate_percentage(9.99)  # Just under 10
        assert result == 9.99

        # Very large P&L (but within bounds)
        result = validate_pnl(999_999_999.0)  # Just under 1 billion
        assert result == 999_999_999.0
