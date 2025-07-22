"""
Unit tests for schema validation utilities.

Tests the validation rules and mixins applied to API schemas.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.schemas.positions import Position
from app.schemas.validation import (
    AccountValidationMixin,
    OrderValidationMixin,
    PositionValidationMixin,
    SchemaValidationMixin,
    ValidationHelpers,
    validate_percentage,
    validate_pnl,
    validate_symbol,
)


class TestSchemaValidationMixin:
    """Test the base schema validation mixin."""

    def test_validate_quantity_positive(self):
        """Test quantity validation for positive values."""
        # This would be tested in classes that inherit from the mixin
        # Testing the validator function directly
        assert SchemaValidationMixin.validate_quantity(100) == 100
        assert SchemaValidationMixin.validate_quantity(-50) == -50  # Negative allowed

    def test_validate_quantity_zero_rejected(self):
        """Test that zero quantity is rejected."""
        with pytest.raises(ValueError, match="Quantity cannot be zero"):
            SchemaValidationMixin.validate_quantity(0)

    def test_validate_price_positive(self):
        """Test price validation for positive values."""
        assert SchemaValidationMixin.validate_price(100.50) == 100.50
        assert SchemaValidationMixin.validate_price(None) is None

    def test_validate_price_negative_rejected(self):
        """Test that negative price is rejected."""
        with pytest.raises(ValueError, match="Price must be positive"):
            SchemaValidationMixin.validate_price(-10.0)

    def test_validate_price_zero_rejected(self):
        """Test that zero price is rejected."""
        with pytest.raises(ValueError, match="Price must be positive"):
            SchemaValidationMixin.validate_price(0.0)

    def test_validate_cash_balance_positive(self):
        """Test cash balance validation for positive values."""
        assert SchemaValidationMixin.validate_cash_balance(1000.0) == 1000.0
        assert SchemaValidationMixin.validate_cash_balance(0.0) == 0.0

    def test_validate_cash_balance_negative_rejected(self):
        """Test that negative cash balance is rejected."""
        with pytest.raises(ValueError, match="Cash balance cannot be negative"):
            SchemaValidationMixin.validate_cash_balance(-100.0)


class TestOrderValidationMixin:
    """Test order-specific validation mixin."""

    def test_validate_order_type_valid(self):
        """Test validation of valid order types."""
        valid_types = [
            "buy",
            "sell",
            "buy_to_open",
            "sell_to_open",
            "buy_to_close",
            "sell_to_close",
        ]
        for order_type in valid_types:
            assert OrderValidationMixin.validate_order_type(order_type) == order_type

    def test_validate_order_type_invalid(self):
        """Test validation of invalid order types."""
        with pytest.raises(ValueError, match="Invalid order type"):
            OrderValidationMixin.validate_order_type("invalid_type")

    def test_validate_quantity_positive(self):
        """Test order quantity validation."""
        assert OrderValidationMixin.validate_quantity(100) == 100

    def test_validate_quantity_zero_rejected(self):
        """Test that zero quantity is rejected for orders."""
        with pytest.raises(ValueError, match="Quantity cannot be zero"):
            OrderValidationMixin.validate_quantity(0)


class TestPositionValidationMixin:
    """Test position-specific validation mixin."""

    def test_validate_avg_price_positive(self):
        """Test average price validation."""
        assert PositionValidationMixin.validate_avg_price(150.0) == 150.0

    def test_validate_avg_price_negative_rejected(self):
        """Test that negative average price is rejected."""
        with pytest.raises(ValueError, match="Average price must be positive"):
            PositionValidationMixin.validate_avg_price(-150.0)

    def test_validate_avg_price_zero_rejected(self):
        """Test that zero average price is rejected."""
        with pytest.raises(ValueError, match="Average price must be positive"):
            PositionValidationMixin.validate_avg_price(0.0)

    def test_validate_strike_positive(self):
        """Test strike price validation."""
        assert PositionValidationMixin.validate_strike(150.0) == 150.0
        assert PositionValidationMixin.validate_strike(None) is None

    def test_validate_strike_negative_rejected(self):
        """Test that negative strike price is rejected."""
        with pytest.raises(ValueError, match="Strike price must be positive"):
            PositionValidationMixin.validate_strike(-150.0)

    def test_validate_expiration_date_future(self):
        """Test expiration date validation for future dates."""
        future_date = date(2025, 12, 31)
        assert (
            PositionValidationMixin.validate_expiration_date(future_date) == future_date
        )
        assert PositionValidationMixin.validate_expiration_date(None) is None

    def test_validate_expiration_date_past_rejected(self):
        """Test that past expiration dates are rejected."""
        past_date = date(2020, 1, 1)
        with pytest.raises(ValueError, match="Expiration date must be in the future"):
            PositionValidationMixin.validate_expiration_date(past_date)

    def test_validate_option_type_valid(self):
        """Test validation of valid option types."""
        assert PositionValidationMixin.validate_option_type("call") == "call"
        assert PositionValidationMixin.validate_option_type("put") == "put"
        assert PositionValidationMixin.validate_option_type(None) is None

    def test_validate_option_type_invalid(self):
        """Test validation of invalid option types."""
        with pytest.raises(ValueError, match='Option type must be "call" or "put"'):
            PositionValidationMixin.validate_option_type("invalid")


class TestAccountValidationMixin:
    """Test account-specific validation mixin."""

    def test_validate_owner_valid(self):
        """Test owner validation for valid values."""
        assert AccountValidationMixin.validate_owner("john_doe") == "john_doe"
        assert AccountValidationMixin.validate_owner("  spaced  ") == "spaced"
        assert AccountValidationMixin.validate_owner(None) is None

    def test_validate_owner_empty_rejected(self):
        """Test that empty owner is rejected."""
        with pytest.raises(ValueError, match="Owner cannot be empty"):
            AccountValidationMixin.validate_owner("   ")

    def test_validate_name_valid(self):
        """Test name validation for valid values."""
        assert AccountValidationMixin.validate_name("Test Account") == "Test Account"
        assert AccountValidationMixin.validate_name("  spaced  ") == "spaced"
        assert AccountValidationMixin.validate_name(None) is None

    def test_validate_name_empty_rejected(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            AccountValidationMixin.validate_name("   ")

    def test_validate_cash_balance(self):
        """Test cash balance validation."""
        assert AccountValidationMixin.validate_cash_balance(1000.0) == 1000.0

    def test_validate_cash_balance_negative_rejected(self):
        """Test that negative cash balance is rejected."""
        with pytest.raises(ValueError, match="Cash balance cannot be negative"):
            AccountValidationMixin.validate_cash_balance(-100.0)


class TestSymbolValidation:
    """Test symbol validation utility function."""

    def test_validate_symbol_valid(self):
        """Test validation of valid symbols."""
        assert validate_symbol("AAPL") == "AAPL"
        assert validate_symbol("aapl") == "AAPL"  # Should be uppercase
        assert validate_symbol("  GOOGL  ") == "GOOGL"  # Should be trimmed

    def test_validate_symbol_empty_rejected(self):
        """Test that empty symbols are rejected."""
        with pytest.raises(ValueError, match="Symbol must be a non-empty string"):
            validate_symbol("")

        with pytest.raises(ValueError, match="Symbol must be a non-empty string"):
            validate_symbol(None)

        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            validate_symbol("   ")

    def test_validate_symbol_too_long_rejected(self):
        """Test that overly long symbols are rejected."""
        long_symbol = "A" * 21
        with pytest.raises(ValueError, match="Symbol too long"):
            validate_symbol(long_symbol)

    def test_validate_symbol_invalid_format_rejected(self):
        """Test that invalid symbol formats are rejected."""
        with pytest.raises(ValueError, match="Invalid symbol format"):
            validate_symbol("@#$%")


class TestPercentageValidation:
    """Test percentage validation utility function."""

    def test_validate_percentage_valid(self):
        """Test validation of valid percentages."""
        assert validate_percentage(0.5) == 0.5
        assert validate_percentage(-2.5) == -2.5
        assert validate_percentage(None) is None

    def test_validate_percentage_unreasonable_rejected(self):
        """Test that unreasonably large percentages are rejected."""
        with pytest.raises(ValueError, match="seems unreasonably large"):
            validate_percentage(15.0)  # 1500%

    def test_validate_percentage_non_numeric_rejected(self):
        """Test that non-numeric values are rejected."""
        with pytest.raises(ValueError, match="must be a number"):
            validate_percentage("invalid")


class TestPnLValidation:
    """Test P&L validation utility function."""

    def test_validate_pnl_valid(self):
        """Test validation of valid P&L values."""
        assert validate_pnl(1000.50) == 1000.50
        assert validate_pnl(-500.25) == -500.25
        assert validate_pnl(None) is None

    def test_validate_pnl_unreasonable_rejected(self):
        """Test that unreasonably large P&L values are rejected."""
        with pytest.raises(ValueError, match="seems unreasonably large"):
            validate_pnl(2_000_000_000.0)  # $2B

    def test_validate_pnl_non_numeric_rejected(self):
        """Test that non-numeric P&L values are rejected."""
        with pytest.raises(ValueError, match="must be a number"):
            validate_pnl("invalid")


class TestValidationHelpers:
    """Test validation helper utilities."""

    def test_normalize_symbol(self):
        """Test symbol normalization."""
        assert ValidationHelpers.normalize_symbol("aapl") == "AAPL"
        assert ValidationHelpers.normalize_symbol("  GOOGL  ") == "GOOGL"

    def test_calculate_spread_percentage_valid(self):
        """Test spread percentage calculation."""
        spread_pct = ValidationHelpers.calculate_spread_percentage(100.0, 100.10)
        assert spread_pct is not None
        assert abs(spread_pct - 0.1) < 0.01  # Should be about 0.1%

    def test_calculate_spread_percentage_invalid(self):
        """Test spread percentage calculation with invalid data."""
        # Invalid spread (ask <= bid)
        assert ValidationHelpers.calculate_spread_percentage(100.0, 99.0) is None

        # Missing data
        assert ValidationHelpers.calculate_spread_percentage(None, 100.0) is None
        assert ValidationHelpers.calculate_spread_percentage(100.0, None) is None

        # Negative prices
        assert ValidationHelpers.calculate_spread_percentage(-10.0, 100.0) is None


class TestOrderSchemaValidation:
    """Test validation applied to Order schema instances."""

    def test_order_creation_valid(self):
        """Test creation of valid order."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING,
        )
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.price == 150.0

    def test_order_creation_invalid_quantity(self):
        """Test order creation with invalid quantity."""
        with pytest.raises(ValidationError):
            Order(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=0,  # Invalid - zero quantity
                price=150.0,
            )

    def test_order_creation_invalid_symbol(self):
        """Test order creation with invalid symbol."""
        with pytest.raises(ValidationError):
            Order(
                symbol="@#$%",  # Invalid symbol format
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
            )


class TestPositionSchemaValidation:
    """Test validation applied to Position schema instances."""

    def test_position_creation_valid(self):
        """Test creation of valid position."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=145.0,
            current_price=150.0,
            unrealized_pnl=500.0,
        )
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.avg_price == 145.0

    def test_position_creation_invalid_avg_price(self):
        """Test position creation with invalid average price."""
        with pytest.raises(ValidationError):
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=-145.0,  # Invalid - negative price
                current_price=150.0,
                unrealized_pnl=500.0,
            )


class TestAccountSchemaValidation:
    """Test validation applied to Account schema instances."""

    def test_account_creation_valid(self):
        """Test creation of valid account."""
        account = Account(
            id="test-123",
            owner="john_doe",
            cash_balance=10000.0,
            name="Test Account",
        )
        assert account.owner == "john_doe"
        assert account.cash_balance == 10000.0

    def test_account_creation_invalid_cash_balance(self):
        """Test account creation with invalid cash balance."""
        with pytest.raises(ValidationError):
            Account(
                id="test-123",
                owner="john_doe",
                cash_balance=-1000.0,  # Invalid - negative balance
                name="Test Account",
            )
