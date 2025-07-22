"""
Advanced validation for complex order combinations.

This module provides sophisticated validation for multi-leg orders,
spread strategies, and complex option combinations.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from ..models.assets import Asset, Option, Stock
from ..schemas.orders import MultiLegOrder
from ..schemas.positions import Portfolio

logger = logging.getLogger(__name__)


class StrategyType(str, Enum):
    """Recognized trading strategies."""

    SINGLE_LEG = "single_leg"
    VERTICAL_SPREAD = "vertical_spread"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    COLLAR = "collar"
    RISK_REVERSAL = "risk_reversal"
    CUSTOM = "custom"


@dataclass
class ValidationIssue:
    """Represents a validation issue."""

    severity: str  # error, warning, info
    code: str
    message: str
    field: str | None = None
    leg_index: int | None = None


@dataclass
class StrategyValidation:
    """Strategy-specific validation rules."""

    strategy_type: StrategyType
    min_legs: int
    max_legs: int
    required_asset_types: list[str]
    same_underlying: bool = True
    same_expiration: bool = True
    strike_relationship: str | None = None  # ascending, descending, etc.


@dataclass
class ComplexOrderValidationResult:
    """Result of complex order validation."""

    is_valid: bool
    detected_strategy: StrategyType
    issues: list[ValidationIssue]
    warnings: list[ValidationIssue]
    info: list[ValidationIssue]
    margin_requirement: float
    max_profit: float | None = None
    max_loss: float | None = None
    breakeven_points: list[float] = field(default_factory=list)
    strategy_description: str | None = None


class ComplexOrderValidator:
    """
    Validates complex multi-leg orders and option strategies.

    Provides comprehensive validation including:
    - Strategy recognition and validation
    - Risk/reward calculations
    - Margin requirement computation
    - Regulatory compliance checks
    """

    def __init__(self):
        self.strategy_rules = self._initialize_strategy_rules()

    def validate_order(
        self, order: MultiLegOrder, portfolio: Portfolio, options_level: int = 2
    ) -> ComplexOrderValidationResult:
        """
        Validate a complex multi-leg order.

        Args:
            order: Multi-leg order to validate
            portfolio: Current portfolio state
            options_level: User's options trading level (0-4)

        Returns:
            Comprehensive validation result
        """
        logger.info(f"Validating complex order with {len(order.legs)} legs")

        issues: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        info: list[ValidationIssue] = []

        # Basic validation
        basic_issues = self._validate_basic_requirements(order)
        issues.extend(basic_issues)

        # Detect strategy type
        detected_strategy = self._detect_strategy(order)

        # Strategy-specific validation
        if detected_strategy != StrategyType.CUSTOM:
            strategy_issues = self._validate_strategy(order, detected_strategy)
            issues.extend(strategy_issues)

        # Options level validation
        level_issues = self._validate_options_level(
            order, detected_strategy, options_level
        )
        issues.extend(level_issues)

        # Risk validation
        risk_warnings = self._validate_risk_parameters(order, portfolio)
        warnings.extend(risk_warnings)

        # Regulatory validation
        reg_issues = self._validate_regulatory_requirements(order, portfolio)
        issues.extend(reg_issues)

        # Calculate strategy metrics
        margin_requirement = self._calculate_margin_requirement(order, portfolio)
        max_profit, max_loss = self._calculate_max_profit_loss(order)
        breakeven_points = self._calculate_breakeven_points(order)

        # Generate strategy description
        strategy_description = self._generate_strategy_description(
            order, detected_strategy
        )

        # Determine overall validity
        is_valid = len([i for i in issues if i.severity == "error"]) == 0

        return ComplexOrderValidationResult(
            is_valid=is_valid,
            detected_strategy=detected_strategy,
            issues=issues,
            warnings=warnings,
            info=info,
            margin_requirement=margin_requirement,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=breakeven_points,
            strategy_description=strategy_description,
        )

    def _initialize_strategy_rules(self) -> dict[StrategyType, StrategyValidation]:
        """Initialize validation rules for each strategy type."""
        return {
            StrategyType.VERTICAL_SPREAD: StrategyValidation(
                strategy_type=StrategyType.VERTICAL_SPREAD,
                min_legs=2,
                max_legs=2,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=True,
                strike_relationship="different",
            ),
            StrategyType.CALENDAR_SPREAD: StrategyValidation(
                strategy_type=StrategyType.CALENDAR_SPREAD,
                min_legs=2,
                max_legs=2,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=False,
                strike_relationship="same",
            ),
            StrategyType.STRADDLE: StrategyValidation(
                strategy_type=StrategyType.STRADDLE,
                min_legs=2,
                max_legs=2,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=True,
                strike_relationship="same",
            ),
            StrategyType.STRANGLE: StrategyValidation(
                strategy_type=StrategyType.STRANGLE,
                min_legs=2,
                max_legs=2,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=True,
                strike_relationship="different",
            ),
            StrategyType.BUTTERFLY: StrategyValidation(
                strategy_type=StrategyType.BUTTERFLY,
                min_legs=3,
                max_legs=3,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=True,
                strike_relationship="ascending",
            ),
            StrategyType.IRON_CONDOR: StrategyValidation(
                strategy_type=StrategyType.IRON_CONDOR,
                min_legs=4,
                max_legs=4,
                required_asset_types=["option"],
                same_underlying=True,
                same_expiration=True,
                strike_relationship="ascending",
            ),
            StrategyType.COVERED_CALL: StrategyValidation(
                strategy_type=StrategyType.COVERED_CALL,
                min_legs=2,
                max_legs=2,
                required_asset_types=["stock", "option"],
                same_underlying=True,
                same_expiration=False,
            ),
            StrategyType.PROTECTIVE_PUT: StrategyValidation(
                strategy_type=StrategyType.PROTECTIVE_PUT,
                min_legs=2,
                max_legs=2,
                required_asset_types=["stock", "option"],
                same_underlying=True,
                same_expiration=False,
            ),
        }

    def _validate_basic_requirements(
        self, order: MultiLegOrder
    ) -> list[ValidationIssue]:
        """Validate basic order requirements."""
        issues = []

        # Check for empty order
        if not order.legs:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="EMPTY_ORDER",
                    message="Order must have at least one leg",
                )
            )
            return issues

        # Check for duplicate symbols
        symbols = [leg.asset.symbol for leg in order.legs]
        if len(symbols) != len(set(symbols)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_SYMBOLS",
                    message="Order contains duplicate symbols",
                )
            )

        # Validate each leg
        for i, leg in enumerate(order.legs):
            # Check quantity
            if leg.quantity == 0:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="ZERO_QUANTITY",
                        message="Leg quantity cannot be zero",
                        leg_index=i,
                    )
                )

            # Check asset validity
            if not isinstance(leg.asset, Asset):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_ASSET",
                        message="Invalid asset in leg",
                        leg_index=i,
                    )
                )

        return issues

    def _detect_strategy(self, order: MultiLegOrder) -> StrategyType:
        """Detect the type of options strategy."""
        if len(order.legs) == 1:
            return StrategyType.SINGLE_LEG

        if len(order.legs) == 2:
            return self._detect_two_leg_strategy(order)
        elif len(order.legs) == 3:
            return self._detect_three_leg_strategy(order)
        elif len(order.legs) == 4:
            return self._detect_four_leg_strategy(order)

        return StrategyType.CUSTOM

    def _detect_two_leg_strategy(self, order: MultiLegOrder) -> StrategyType:
        """Detect two-leg strategies."""
        leg1, leg2 = order.legs[0], order.legs[1]
        asset1, asset2 = leg1.asset, leg2.asset

        # Check for stock + option combinations
        if isinstance(asset1, Stock) and isinstance(asset2, Option):
            if leg1.quantity > 0 and leg2.quantity < 0:  # Long stock, short call
                if asset2.option_type == "call":
                    return StrategyType.COVERED_CALL
            elif leg1.quantity > 0 and leg2.quantity > 0:  # Long stock, long put
                if asset2.option_type == "put":
                    return StrategyType.PROTECTIVE_PUT

        # Both options
        if isinstance(asset1, Option) and isinstance(asset2, Option):
            # Same underlying check
            if asset1.underlying.symbol != asset2.underlying.symbol:
                return StrategyType.CUSTOM

            # Same strike, same expiration
            if (
                asset1.strike == asset2.strike
                and asset1.expiration_date == asset2.expiration_date
            ) and asset1.option_type != asset2.option_type:
                return StrategyType.STRADDLE

            # Different strikes, same expiration
            if (
                asset1.strike != asset2.strike
                and asset1.expiration_date == asset2.expiration_date
            ):
                if asset1.option_type == asset2.option_type:
                    return StrategyType.VERTICAL_SPREAD
                else:
                    return StrategyType.STRANGLE

            # Same strike, different expiration
            if (
                asset1.strike == asset2.strike
                and asset1.expiration_date != asset2.expiration_date
            ) and asset1.option_type == asset2.option_type:
                return StrategyType.CALENDAR_SPREAD

        return StrategyType.CUSTOM

    def _detect_three_leg_strategy(self, order: MultiLegOrder) -> StrategyType:
        """Detect three-leg strategies."""
        # Check if all legs are options on same underlying
        assets = [leg.asset for leg in order.legs]

        if not all(isinstance(a, Option) for a in assets):
            return StrategyType.CUSTOM

        underlyings = {a.underlying.symbol for a in assets}
        if len(underlyings) != 1:
            return StrategyType.CUSTOM

        # Check for butterfly pattern
        strikes = sorted([a.strike for a in assets])
        quantities = [
            leg.quantity for leg in sorted(order.legs, key=lambda l: l.asset.strike)
        ]

        # Classic butterfly: +1, -2, +1 or -1, +2, -1
        if len(set(strikes)) == 3 and (
            quantities[0] * quantities[2] > 0
            and quantities[1] == -2 * quantities[0]
        ):
            return StrategyType.BUTTERFLY

        return StrategyType.CUSTOM

    def _detect_four_leg_strategy(self, order: MultiLegOrder) -> StrategyType:
        """Detect four-leg strategies."""
        # Check if all legs are options on same underlying
        assets = [leg.asset for leg in order.legs]

        if not all(isinstance(a, Option) for a in assets):
            return StrategyType.CUSTOM

        underlyings = {a.underlying.symbol for a in assets}
        if len(underlyings) != 1:
            return StrategyType.CUSTOM

        # Sort by strike
        sorted_legs = sorted(order.legs, key=lambda l: l.asset.strike)

        # Check for iron condor pattern
        # Two puts (lower strikes) and two calls (higher strikes)
        put_legs = [l for l in sorted_legs if l.asset.option_type == "put"]
        call_legs = [l for l in sorted_legs if l.asset.option_type == "call"]

        if len(put_legs) == 2 and len(call_legs) == 2:
            # Check quantities: sell inner, buy outer
            if (
                put_legs[0].quantity > 0
                and put_legs[1].quantity < 0
                and call_legs[0].quantity < 0
                and call_legs[1].quantity > 0
            ):
                return StrategyType.IRON_CONDOR

        # Check for iron butterfly
        if len({a.strike for a in assets}) == 3:
            middle_strike = sorted({a.strike for a in assets})[1]
            middle_legs = [l for l in order.legs if l.asset.strike == middle_strike]

            if len(middle_legs) == 2:
                return StrategyType.IRON_BUTTERFLY

        return StrategyType.CUSTOM

    def _validate_strategy(
        self, order: MultiLegOrder, strategy_type: StrategyType
    ) -> list[ValidationIssue]:
        """Validate order against strategy rules."""
        issues = []

        rules = self.strategy_rules.get(strategy_type)
        if not rules:
            return issues

        # Check leg count
        if len(order.legs) < rules.min_legs or len(order.legs) > rules.max_legs:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_LEG_COUNT",
                    message=f"{strategy_type} requires {rules.min_legs}-{rules.max_legs} legs",
                )
            )

        # Check asset types
        asset_types = [
            "option" if isinstance(leg.asset, Option) else "stock" for leg in order.legs
        ]

        for required_type in rules.required_asset_types:
            if required_type not in asset_types:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="MISSING_ASSET_TYPE",
                        message=f"{strategy_type} requires {required_type}",
                    )
                )

        # Check underlying consistency
        if rules.same_underlying:
            underlyings = set()
            for leg in order.legs:
                if isinstance(leg.asset, Option):
                    underlyings.add(leg.asset.underlying.symbol)
                elif isinstance(leg.asset, Stock):
                    underlyings.add(leg.asset.symbol)

            if len(underlyings) > 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="DIFFERENT_UNDERLYINGS",
                        message=f"{strategy_type} requires same underlying for all legs",
                    )
                )

        # Check expiration consistency
        if rules.same_expiration:
            expirations = set()
            for leg in order.legs:
                if isinstance(leg.asset, Option):
                    expirations.add(leg.asset.expiration_date)

            if len(expirations) > 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="DIFFERENT_EXPIRATIONS",
                        message=f"{strategy_type} requires same expiration for all option legs",
                    )
                )

        return issues

    def _validate_options_level(
        self, order: MultiLegOrder, strategy_type: StrategyType, options_level: int
    ) -> list[ValidationIssue]:
        """Validate order against user's options trading level."""
        issues = []

        required_level = self._get_required_options_level(strategy_type)

        if required_level > options_level:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INSUFFICIENT_OPTIONS_LEVEL",
                    message=f"{strategy_type} requires options level {required_level}, you have level {options_level}",
                )
            )

        # Check for naked options
        has_naked_options = self._has_naked_options(order)
        if has_naked_options and options_level < 4:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="NAKED_OPTIONS_NOT_ALLOWED",
                    message="Naked options require level 4 options trading",
                )
            )

        return issues

    def _get_required_options_level(self, strategy_type: StrategyType) -> int:
        """Get required options level for a strategy."""
        level_map = {
            StrategyType.SINGLE_LEG: 2,
            StrategyType.COVERED_CALL: 1,
            StrategyType.PROTECTIVE_PUT: 2,
            StrategyType.VERTICAL_SPREAD: 3,
            StrategyType.CALENDAR_SPREAD: 3,
            StrategyType.DIAGONAL_SPREAD: 3,
            StrategyType.STRADDLE: 3,
            StrategyType.STRANGLE: 3,
            StrategyType.BUTTERFLY: 3,
            StrategyType.CONDOR: 3,
            StrategyType.IRON_CONDOR: 3,
            StrategyType.IRON_BUTTERFLY: 3,
            StrategyType.COLLAR: 3,
            StrategyType.RISK_REVERSAL: 4,
            StrategyType.CUSTOM: 4,
        }

        return level_map.get(strategy_type, 4)

    def _has_naked_options(self, order: MultiLegOrder) -> bool:
        """Check if order contains naked (uncovered) short options."""
        # Simplified check - in reality would check against portfolio
        for leg in order.legs:
            if isinstance(leg.asset, Option) and leg.quantity < 0:
                # Short option - check if covered
                # This is simplified - real check would verify coverage
                return True

        return False

    def _validate_risk_parameters(
        self, order: MultiLegOrder, portfolio: Portfolio
    ) -> list[ValidationIssue]:
        """Validate risk parameters of the order."""
        warnings = []

        # Calculate total order value
        total_value = 0.0
        for leg in order.legs:
            if leg.price:
                total_value += abs(leg.quantity * leg.price)

        # Check concentration
        if portfolio.total_value > 0:
            concentration = total_value / portfolio.total_value
            if concentration > 0.20:  # 20% warning
                warnings.append(
                    ValidationIssue(
                        severity="warning",
                        code="HIGH_CONCENTRATION",
                        message=f"Order represents {concentration:.1%} of portfolio value",
                    )
                )

        # Check for earnings/events
        for leg in order.legs:
            if isinstance(leg.asset, Option):
                days_to_expiry = (leg.asset.expiration_date - date.today()).days
                if days_to_expiry < 7:
                    warnings.append(
                        ValidationIssue(
                            severity="warning",
                            code="NEAR_EXPIRATION",
                            message=f"Option {leg.asset.symbol} expires in {days_to_expiry} days",
                            leg_index=order.legs.index(leg),
                        )
                    )

        return warnings

    def _validate_regulatory_requirements(
        self, order: MultiLegOrder, portfolio: Portfolio
    ) -> list[ValidationIssue]:
        """Validate regulatory requirements."""
        issues = []

        # Pattern Day Trader check
        # Simplified - would need transaction history

        # Options exercise/assignment risk
        for leg in order.legs:
            if isinstance(leg.asset, Option) and leg.quantity < 0:
                # Short option - check for assignment risk
                if leg.asset.expiration_date == date.today():
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="EXPIRATION_DAY_SHORT",
                            message="Cannot sell options on expiration day",
                            leg_index=order.legs.index(leg),
                        )
                    )

        return issues

    def _calculate_margin_requirement(
        self, order: MultiLegOrder, portfolio: Portfolio
    ) -> float:
        """Calculate margin requirement for the order."""
        # Simplified margin calculation
        margin = 0.0

        for leg in order.legs:
            if isinstance(leg.asset, Stock):
                # Stock margin - 50% for initial
                if leg.quantity > 0:
                    margin += abs(leg.quantity * (leg.price or 100)) * 0.5

            elif isinstance(leg.asset, Option):
                if leg.quantity > 0:
                    # Long options - pay full premium
                    margin += abs(leg.quantity * (leg.price or 1) * 100)
                else:
                    # Short options - complex calculation
                    # Simplified version
                    margin += abs(leg.quantity * 100 * 20)  # $20 per contract

        return margin

    def _calculate_max_profit_loss(
        self, order: MultiLegOrder
    ) -> tuple[float | None, float | None]:
        """Calculate maximum profit and loss for the strategy."""
        strategy_type = self._detect_strategy(order)

        if strategy_type == StrategyType.VERTICAL_SPREAD:
            return self._calculate_vertical_spread_pnl(order)
        elif strategy_type == StrategyType.IRON_CONDOR:
            return self._calculate_iron_condor_pnl(order)
        # Add more strategy calculations as needed

        return None, None

    def _calculate_vertical_spread_pnl(
        self, order: MultiLegOrder
    ) -> tuple[float | None, float | None]:
        """Calculate P&L for vertical spread."""
        if len(order.legs) != 2:
            return None, None

        leg1, leg2 = order.legs[0], order.legs[1]

        # Ensure both are options
        if not (isinstance(leg1.asset, Option) and isinstance(leg2.asset, Option)):
            return None, None

        # Calculate spread width
        spread_width = abs(leg1.asset.strike - leg2.asset.strike)

        # Net credit/debit
        net_credit = 0.0
        if leg1.price and leg2.price:
            net_credit = (leg1.price * leg1.quantity + leg2.price * leg2.quantity) * 100

        # Determine if credit or debit spread
        if net_credit > 0:
            # Credit spread
            max_profit = net_credit
            max_loss = (spread_width * 100) - net_credit
        else:
            # Debit spread
            max_profit = (spread_width * 100) + net_credit  # net_credit is negative
            max_loss = -net_credit

        return max_profit, max_loss

    def _calculate_iron_condor_pnl(
        self, order: MultiLegOrder
    ) -> tuple[float | None, float | None]:
        """Calculate P&L for iron condor."""
        if len(order.legs) != 4:
            return None, None

        # Sort legs by strike
        sorted_legs = sorted(order.legs, key=lambda l: l.asset.strike)

        # Calculate net credit
        net_credit = 0.0
        for leg in order.legs:
            if leg.price:
                net_credit += leg.price * leg.quantity * 100

        # Calculate spread widths
        put_spread_width = sorted_legs[1].asset.strike - sorted_legs[0].asset.strike
        call_spread_width = sorted_legs[3].asset.strike - sorted_legs[2].asset.strike

        max_spread_width = max(put_spread_width, call_spread_width)

        max_profit = net_credit
        max_loss = (max_spread_width * 100) - net_credit

        return max_profit, max_loss

    def _calculate_breakeven_points(self, order: MultiLegOrder) -> list[float]:
        """Calculate breakeven points for the strategy."""
        strategy_type = self._detect_strategy(order)
        breakevens = []

        if strategy_type == StrategyType.VERTICAL_SPREAD:
            # Single breakeven point
            if len(order.legs) == 2:
                leg1, leg2 = order.legs[0], order.legs[1]
                if isinstance(leg1.asset, Option) and isinstance(leg2.asset, Option):
                    net_credit = 0.0
                    if leg1.price and leg2.price:
                        net_credit = (
                            leg1.price * leg1.quantity + leg2.price * leg2.quantity
                        )

                    if leg1.asset.option_type == "call":
                        # Call spread
                        if leg1.quantity > 0:
                            # Bull call spread
                            breakevens.append(leg1.asset.strike + net_credit)
                        else:
                            # Bear call spread
                            breakevens.append(leg2.asset.strike + net_credit)
                    else:
                        # Put spread
                        if leg1.quantity > 0:
                            # Bull put spread
                            breakevens.append(leg2.asset.strike - net_credit)
                        else:
                            # Bear put spread
                            breakevens.append(leg1.asset.strike - net_credit)

        elif strategy_type == StrategyType.STRADDLE:
            # Two breakeven points
            if len(order.legs) == 2:
                strike = order.legs[0].asset.strike
                total_premium = 0.0
                for leg in order.legs:
                    if leg.price:
                        total_premium += abs(leg.price)

                breakevens.append(strike - total_premium)
                breakevens.append(strike + total_premium)

        return breakevens

    def _generate_strategy_description(
        self, order: MultiLegOrder, strategy_type: StrategyType
    ) -> str:
        """Generate human-readable strategy description."""
        if strategy_type == StrategyType.VERTICAL_SPREAD:
            return self._describe_vertical_spread(order)
        elif strategy_type == StrategyType.IRON_CONDOR:
            return self._describe_iron_condor(order)
        elif strategy_type == StrategyType.COVERED_CALL:
            return self._describe_covered_call(order)
        # Add more descriptions as needed

        return f"{strategy_type.value.replace('_', ' ').title()} strategy with {len(order.legs)} legs"

    def _describe_vertical_spread(self, order: MultiLegOrder) -> str:
        """Describe a vertical spread."""
        if len(order.legs) != 2:
            return "Invalid vertical spread"

        leg1, _leg2 = order.legs[0], order.legs[1]

        # Determine spread type
        position = "Bull" if leg1.quantity > 0 else "Bear"

        if isinstance(leg1.asset, Option):
            option_type = leg1.asset.option_type.title()
        else:
            option_type = "Unknown"

        return f"{position} {option_type} Spread"

    def _describe_iron_condor(self, order: MultiLegOrder) -> str:
        """Describe an iron condor."""
        return "Iron Condor - Limited risk, limited reward strategy"

    def _describe_covered_call(self, order: MultiLegOrder) -> str:
        """Describe a covered call."""
        return (
            "Covered Call - Income generation strategy with long stock and short call"
        )


# Global complex order validator
complex_order_validator = ComplexOrderValidator()


def get_complex_order_validator() -> ComplexOrderValidator:
    """Get the global complex order validator."""
    return complex_order_validator
