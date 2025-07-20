"""
Schema validation utilities and mixins.

Provides common validation rules and utilities for API schemas to ensure
data consistency and business rule compliance.
"""

from datetime import date, datetime

from pydantic import ValidationInfo, field_validator


class SchemaValidationMixin:
    """Mixin class providing common validation rules for trading schemas."""

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """Validate that quantity is not zero."""
        if v == 0:
            raise ValueError("Quantity cannot be zero")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float | None) -> float | None:
        """Validate that price is positive when provided."""
        if v is not None and v <= 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("cash_balance")
    @classmethod
    def validate_cash_balance(cls, v: float) -> float:
        """Validate cash balance is not negative."""
        if v < 0:
            raise ValueError("Cash balance cannot be negative")
        return v


class OrderValidationMixin:
    """Validation mixin specifically for order schemas."""

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        """Validate order type is supported."""
        valid_types = [
            "buy",
            "sell",
            "buy_to_open",
            "sell_to_open",
            "buy_to_close",
            "sell_to_close",
        ]
        if v not in valid_types:
            raise ValueError(f"Invalid order type: {v}. Must be one of: {valid_types}")
        return v

    @field_validator("price")
    @classmethod
    def validate_order_price(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        """Validate price based on order condition."""
        # If we have access to the condition field
        if hasattr(info.data, "condition") and info.data.get("condition") == "limit":
            if v is None:
                raise ValueError("Limit orders must have a price specified")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """Validate that quantity is not zero."""
        if v == 0:
            raise ValueError("Quantity cannot be zero")
        return v


class PositionValidationMixin:
    """Validation mixin specifically for position schemas."""

    @field_validator("avg_price")
    @classmethod
    def validate_avg_price(cls, v: float) -> float:
        """Validate average price is positive."""
        if v <= 0:
            raise ValueError("Average price must be positive")
        return v

    @field_validator("strike")
    @classmethod
    def validate_strike(cls, v: float | None) -> float | None:
        """Validate strike price for options."""
        if v is not None and v <= 0:
            raise ValueError("Strike price must be positive")
        return v

    @field_validator("expiration_date")
    @classmethod
    def validate_expiration_date(cls, v: date | None) -> date | None:
        """Validate expiration date is in the future."""
        if v is not None and v < date.today():
            raise ValueError("Expiration date must be in the future")
        return v

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str | None) -> str | None:
        """Validate option type."""
        if v is not None and v not in ["call", "put"]:
            raise ValueError('Option type must be "call" or "put"')
        return v


class AccountValidationMixin:
    """Validation mixin specifically for account schemas."""

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str | None) -> str | None:
        """Validate owner field."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Owner cannot be empty")
        return v.strip() if v else v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate name field."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return v.strip() if v else v

    @field_validator("cash_balance")
    @classmethod
    def validate_cash_balance(cls, v: float) -> float:
        """Validate cash balance is not negative."""
        if v < 0:
            raise ValueError("Cash balance cannot be negative")
        return v


def validate_symbol(symbol: str) -> str:
    """
    Validate trading symbol format.

    Args:
        symbol: Symbol to validate

    Returns:
        Cleaned symbol

    Raises:
        ValueError: If symbol is invalid
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string")

    symbol = symbol.strip().upper()

    if len(symbol) == 0:
        raise ValueError("Symbol cannot be empty")

    if len(symbol) > 20:
        raise ValueError("Symbol too long (max 20 characters)")

    # Basic symbol format validation
    # Allow letters, numbers, and common option symbol characters
    valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    if not all(c in valid_chars for c in symbol[:4]):  # First 4 chars should be alpha
        raise ValueError(f"Invalid symbol format: {symbol}")

    return symbol


def validate_percentage(value: float | None, field_name: str = "value") -> float | None:
    """
    Validate percentage values (e.g., for Greeks).

    Args:
        value: Percentage value to validate
        field_name: Name of field for error messages

    Returns:
        Validated percentage

    Raises:
        ValueError: If percentage is invalid
    """
    if value is None:
        return None

    if not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number")

    # Allow reasonable ranges for Greeks and other percentages
    if abs(value) > 10:  # 1000% seems like a reasonable upper bound
        raise ValueError(f"{field_name} seems unreasonably large: {value}")

    return float(value)


def validate_pnl(value: float | None, field_name: str = "P&L") -> float | None:
    """
    Validate profit/loss values.

    Args:
        value: P&L value to validate
        field_name: Name of field for error messages

    Returns:
        Validated P&L

    Raises:
        ValueError: If P&L is invalid
    """
    if value is None:
        return None

    if not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number")

    # Check for unreasonably large P&L values
    if abs(value) > 1_000_000_000:  # $1B seems like reasonable upper bound
        raise ValueError(f"{field_name} seems unreasonably large: {value}")

    return float(value)


def validate_order_against_account(order, account) -> bool:
    """
    Validate order is compatible with account.

    Args:
        order: Order object to validate
        account: Account object to validate against

    Returns:
        True if order is valid for account

    Raises:
        ValueError: If order is invalid for account
    """
    # Check account has sufficient balance for buy orders
    if hasattr(order, "order_type") and order.order_type in ["buy", "buy_to_open"]:
        if order.price and order.quantity:
            order_cost = order.price * order.quantity
            if order_cost > account.cash_balance:
                raise ValueError(
                    f"Insufficient funds: Order cost ${order_cost:.2f} "
                    f"exceeds account balance ${account.cash_balance:.2f}"
                )

    # Validate symbol format if present
    if hasattr(order, "symbol"):
        try:
            validate_symbol(order.symbol)
        except ValueError as e:
            raise ValueError(f"Invalid order symbol: {e}") from e

    return True


def validate_position_consistency(position) -> bool:
    """
    Validate position data consistency.

    Args:
        position: Position object to validate

    Returns:
        True if position data is consistent

    Raises:
        ValueError: If position data is inconsistent
    """
    # Check unrealized P&L calculation
    if (
        hasattr(position, "current_price")
        and hasattr(position, "avg_price")
        and hasattr(position, "quantity")
        and hasattr(position, "unrealized_pnl")
    ) and position.current_price and position.avg_price and position.quantity:
        expected_pnl = (
            position.current_price - position.avg_price
        ) * position.quantity

        # Allow small floating point differences
        if (
            position.unrealized_pnl
            and abs(position.unrealized_pnl - expected_pnl) > 0.01
        ):
            raise ValueError(
                f"Inconsistent P&L calculation: Expected ${expected_pnl:.2f}, "
                f"got ${position.unrealized_pnl:.2f}"
            )

    # Validate that avg_price is positive for actual positions
    if hasattr(position, "avg_price") and hasattr(position, "quantity"):
        if position.quantity != 0 and position.avg_price and position.avg_price <= 0:
            raise ValueError("Average price must be positive for non-zero positions")

    # Validate option-specific fields consistency
    if hasattr(position, "option_type") and position.option_type:
        # If it's an option, check option-specific fields
        if hasattr(position, "strike") and hasattr(position, "expiration_date"):
            if not position.strike or position.strike <= 0:
                raise ValueError("Options must have a positive strike price")

            if position.expiration_date and position.expiration_date < date.today():
                raise ValueError("Option expiration date cannot be in the past")

        # Validate option type
        if position.option_type not in ["call", "put"]:
            raise ValueError('Option type must be "call" or "put"')

    return True


def validate_portfolio_consistency(portfolio) -> bool:
    """
    Validate portfolio data consistency.

    Args:
        portfolio: Portfolio object to validate

    Returns:
        True if portfolio data is consistent

    Raises:
        ValueError: If portfolio data is inconsistent
    """
    if not hasattr(portfolio, "positions") or not hasattr(portfolio, "cash_balance"):
        raise ValueError("Portfolio must have positions and cash_balance attributes")

    # Validate each position
    for position in portfolio.positions:
        validate_position_consistency(position)

    # Validate total value calculation if present
    if hasattr(portfolio, "total_value"):
        expected_total = portfolio.cash_balance
        if portfolio.positions:
            for position in portfolio.positions:
                if hasattr(position, "current_price") and hasattr(position, "quantity"):
                    if position.current_price and position.quantity:
                        expected_total += position.current_price * abs(
                            position.quantity
                        )

        if portfolio.total_value and abs(portfolio.total_value - expected_total) > 0.01:
            raise ValueError(
                f"Inconsistent total value: Expected ${expected_total:.2f}, "
                f"got ${portfolio.total_value:.2f}"
            )

    return True


class ValidationHelpers:
    """Helper class with static validation methods."""

    @staticmethod
    def is_market_hours(check_time: datetime | None = None) -> bool:
        """
        Check if it's during market hours.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if during market hours
        """
        if check_time is None:
            check_time = datetime.now()

        # Simple check for weekdays 9:30 AM - 4:00 PM ET
        # In production, this would need proper timezone handling
        weekday = check_time.weekday()
        hour = check_time.hour
        minute = check_time.minute

        # Monday (0) to Friday (4)
        if weekday > 4:
            return False

        # 9:30 AM to 4:00 PM
        market_open = (hour > 9) or (hour == 9 and minute >= 30)
        market_close = hour < 16

        return market_open and market_close

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Normalize symbol format.

        Args:
            symbol: Raw symbol

        Returns:
            Normalized symbol
        """
        return validate_symbol(symbol)

    @staticmethod
    def calculate_spread_percentage(
        bid: float | None, ask: float | None
    ) -> float | None:
        """
        Calculate bid-ask spread percentage.

        Args:
            bid: Bid price
            ask: Ask price

        Returns:
            Spread percentage or None if cannot calculate
        """
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return None

        if ask <= bid:
            return None  # Invalid spread

        mid_price = (bid + ask) / 2
        spread = ask - bid

        return (spread / mid_price) * 100
