"""
Account and order validation service.

Adapted from reference implementation with enhanced validation capabilities.
"""

from typing import List, Optional, Any
from datetime import datetime, date

from ..schemas.orders import MultiLegOrder, Order, OrderLeg, OrderType
from ..models.trading import Position
from ..models.assets import Asset, Option


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class AccountValidator:
    """
    Validates account state after orders and ensures trading rules compliance.
    """

    def __init__(self, margin_service: Optional[Any] = None) -> None:
        self.margin_service = margin_service

    def validate_account_state(
        self,
        cash_balance: float,
        positions: List[Position],
        maintenance_margin: float = 0.0,
    ) -> bool:
        """
        Validate account state after an order execution.

        Args:
            cash_balance: Current cash balance
            positions: Current positions
            maintenance_margin: Required maintenance margin

        Returns:
            True if valid

        Raises:
            ValidationError: If account is in invalid state
        """

        # Check for negative cash
        if cash_balance < 0:
            raise ValidationError(
                f"Insufficient cash: Account balance is ${cash_balance:,.2f}"
            )

        # Check margin requirements
        if cash_balance < maintenance_margin:
            raise ValidationError(
                f"Insufficient cash for margin requirements. "
                f"Cash: ${cash_balance:,.2f}, Required margin: ${maintenance_margin:,.2f}"
            )

        return True

    def validate_order_pre_execution(
        self,
        order: MultiLegOrder,
        cash_balance: float,
        positions: List[Position],
        estimated_cost: float,
    ) -> bool:
        """
        Validate order before execution.

        Args:
            order: Order to validate
            cash_balance: Current cash balance
            positions: Current positions
            estimated_cost: Estimated cash cost of order

        Returns:
            True if order can be executed

        Raises:
            ValidationError: If order is invalid
        """

        # Validate order structure
        self._validate_order_structure(order)

        # Validate sufficient cash for order
        if cash_balance + estimated_cost < 0:  # Negative cost means cash out
            raise ValidationError(
                f"Insufficient cash for order. "
                f"Cash: ${cash_balance:,.2f}, Required: ${-estimated_cost:,.2f}"
            )

        # Validate closing orders have sufficient positions
        self._validate_closing_positions(order.legs, positions)

        # Validate options-specific rules
        self._validate_options_rules(order.legs)

        return True

    def _validate_order_structure(self, order: MultiLegOrder) -> None:
        """Validate basic order structure."""

        if not order.legs:
            raise ValidationError("Order must have at least one leg")

        # Check for duplicate assets
        symbols = [
            self._get_symbol(leg.asset)
            if isinstance(leg.asset, Asset)
            else str(leg.asset)
            for leg in order.legs
        ]
        if len(symbols) != len(set(symbols)):
            raise ValidationError("Duplicate assets not allowed in multi-leg orders")

        # Validate each leg
        for i, leg in enumerate(order.legs):
            self._validate_leg(leg, f"Leg {i + 1}")

    def _validate_leg(self, leg: OrderLeg, leg_name: str) -> None:
        """Validate individual order leg."""

        if leg.quantity == 0:
            raise ValidationError(f"{leg_name}: Quantity cannot be zero")

        # Validate quantity/price signs based on order type
        if leg.order_type in [OrderType.BUY, OrderType.BTO, OrderType.BTC]:
            if leg.quantity < 0:
                raise ValidationError(
                    f"{leg_name}: Buy orders must have positive quantity"
                )
            if leg.price is not None and leg.price < 0:
                raise ValidationError(
                    f"{leg_name}: Buy orders must have positive price"
                )

        elif leg.order_type in [OrderType.SELL, OrderType.STO, OrderType.STC]:
            if leg.quantity > 0:
                raise ValidationError(
                    f"{leg_name}: Sell orders must have negative quantity"
                )
            if leg.price is not None and leg.price > 0:
                raise ValidationError(
                    f"{leg_name}: Sell orders must have negative price"
                )

    def _validate_closing_positions(
        self, legs: List[OrderLeg], positions: List[Position]
    ) -> None:
        """Validate sufficient positions exist for closing orders."""

        for leg in legs:
            if leg.order_type in [OrderType.BTC, OrderType.STC]:
                symbol = (
                    self._get_symbol(leg.asset)
                    if isinstance(leg.asset, Asset)
                    else str(leg.asset)
                )

                # Find positions that can be closed by this leg
                closable_positions = [
                    pos
                    for pos in positions
                    if pos.symbol == symbol
                    and self._positions_are_closable(pos.quantity, leg.quantity)
                ]

                if not closable_positions:
                    raise ValidationError(
                        f"No available positions to close for {symbol} "
                        f"(order type: {leg.order_type})"
                    )

                # Check sufficient quantity
                available_quantity = sum(
                    abs(pos.quantity) for pos in closable_positions
                )
                required_quantity = abs(leg.quantity)

                if available_quantity < required_quantity:
                    raise ValidationError(
                        f"Insufficient position quantity to close for {symbol}. "
                        f"Required: {required_quantity}, Available: {available_quantity}"
                    )

    def _validate_options_rules(self, legs: List[OrderLeg]) -> None:
        """Validate options-specific trading rules."""

        for leg in legs:
            if isinstance(leg.asset, Option):
                # Check expiration date
                if leg.asset.expiration_date < date.today():
                    raise ValidationError(
                        f"Cannot trade expired option: {leg.asset.symbol} "
                        f"(expired {leg.asset.expiration_date})"
                    )

                # Check strike price reasonableness
                if leg.asset.strike <= 0:
                    raise ValidationError(
                        f"Invalid strike price for option: {leg.asset.symbol} "
                        f"(strike: ${leg.asset.strike})"
                    )

                # Validate option symbol format
                if not self._is_valid_option_symbol(leg.asset.symbol):
                    raise ValidationError(
                        f"Invalid option symbol format: {leg.asset.symbol}"
                    )

    def validate_position_limits(
        self,
        positions: List[Position],
        max_position_size: Optional[float] = None,
        max_total_exposure: Optional[float] = None,
    ) -> bool:
        """
        Validate position size and exposure limits.

        Args:
            positions: Current positions
            max_position_size: Maximum size for any single position
            max_total_exposure: Maximum total portfolio exposure

        Returns:
            True if within limits

        Raises:
            ValidationError: If limits exceeded
        """

        if max_position_size is not None:
            for position in positions:
                position_value = abs(position.market_value or 0)
                if position_value > max_position_size:
                    raise ValidationError(
                        f"Position size limit exceeded for {position.symbol}: "
                        f"${position_value:,.2f} > ${max_position_size:,.2f}"
                    )

        if max_total_exposure is not None:
            total_exposure = sum(abs(pos.market_value or 0) for pos in positions)
            if total_exposure > max_total_exposure:
                raise ValidationError(
                    f"Total exposure limit exceeded: "
                    f"${total_exposure:,.2f} > ${max_total_exposure:,.2f}"
                )

        return True

    def validate_risk_limits(
        self,
        positions: List[Position],
        max_daily_loss: Optional[float] = None,
        max_portfolio_delta: Optional[float] = None,
    ) -> bool:
        """
        Validate risk-based limits.

        Args:
            positions: Current positions
            max_daily_loss: Maximum allowed daily loss
            max_portfolio_delta: Maximum portfolio delta exposure

        Returns:
            True if within limits

        Raises:
            ValidationError: If limits exceeded
        """

        if max_daily_loss is not None:
            daily_pnl = sum(pos.unrealized_pnl or 0 for pos in positions)
            if daily_pnl < -max_daily_loss:
                raise ValidationError(
                    f"Daily loss limit exceeded: "
                    f"${daily_pnl:,.2f} loss > ${max_daily_loss:,.2f} limit"
                )

        if max_portfolio_delta is not None:
            portfolio_delta = sum(pos.delta or 0 for pos in positions)
            if abs(portfolio_delta) > max_portfolio_delta:
                raise ValidationError(
                    f"Portfolio delta limit exceeded: "
                    f"{portfolio_delta:.2f} > {max_portfolio_delta:.2f} limit"
                )

        return True

    def _get_symbol(self, asset: Asset) -> str:
        """Get symbol from asset."""
        return asset.symbol if hasattr(asset, "symbol") else str(asset)

    def _positions_are_closable(
        self, position_quantity: int, order_quantity: int
    ) -> bool:
        """Check if position can be closed by order (opposite signs)."""
        from math import copysign

        return copysign(1, position_quantity) == (copysign(1, order_quantity) * -1)

    def _is_valid_option_symbol(self, symbol: str) -> bool:
        """Validate option symbol format."""
        # Basic validation - should be at least 15 characters for standard format
        # AAPL240119C00195000 = 16 characters
        return len(symbol) >= 15 and ("C0" in symbol or "P0" in symbol)


class OrderValidator:
    """
    Specialized validator for order-specific rules.
    """

    def __init__(self) -> None:
        self.account_validator = AccountValidator()

    def validate_simple_order(self, order: Order) -> bool:
        """Validate a simple single-leg order."""

        # Convert to multi-leg for validation
        multi_leg = MultiLegOrder(
            id=order.id,
            legs=[order.to_leg()],
            condition=order.condition,
            limit_price=order.price,
        )

        self.account_validator._validate_order_structure(multi_leg)
        return True

    def validate_order_timing(self, order: MultiLegOrder) -> bool:
        """Validate order timing rules."""

        # Check market hours (placeholder - would integrate with market calendar)
        datetime.now()

        # For options, check days to expiration
        for leg in order.legs:
            if isinstance(leg.asset, Option):
                days_to_exp = (leg.asset.expiration_date - date.today()).days
                if days_to_exp < 0:
                    raise ValidationError(
                        f"Cannot trade expired option: {leg.asset.symbol}"
                    )
                if days_to_exp == 0:
                    # Same-day expiration warning (could be converted to error)
                    pass

        return True

    def validate_strategy_rules(self, order: MultiLegOrder) -> bool:
        """Validate strategy-specific rules."""

        # For multi-leg orders, check for valid strategy combinations
        if len(order.legs) > 1:
            self._validate_multi_leg_strategy(order)

        return True

    def _validate_multi_leg_strategy(self, order: MultiLegOrder) -> None:
        """Validate multi-leg strategy makes sense."""

        # Basic validation - could be expanded with strategy recognition
        opening_legs = [
            leg
            for leg in order.legs
            if leg.order_type in [OrderType.BTO, OrderType.STO]
        ]
        closing_legs = [
            leg
            for leg in order.legs
            if leg.order_type in [OrderType.BTC, OrderType.STC]
        ]

        # Don't allow mixing opening and closing in same order for now
        if opening_legs and closing_legs:
            raise ValidationError(
                "Cannot mix opening and closing legs in the same order"
            )


# Convenience function for basic account validation
def validate_account_state(
    cash_balance: float, positions: List[Position], maintenance_margin: float = 0.0
) -> bool:
    """
    Quick account validation function.

    Args:
        cash_balance: Current cash balance
        positions: Current positions
        maintenance_margin: Required maintenance margin

    Returns:
        True if valid

    Raises:
        ValidationError: If account invalid
    """
    validator = AccountValidator()
    return validator.validate_account_state(cash_balance, positions, maintenance_margin)
