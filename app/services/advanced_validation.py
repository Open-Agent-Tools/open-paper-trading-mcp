"""
Advanced order validation service with comprehensive pre-trade checks.

Enhanced from basic validation with options-specific rules,
compliance validation, and sophisticated pre-trade checks.
"""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.models.assets import Option, asset_factory
from app.models.quotes import OptionQuote, Quote
from app.schemas.orders import MultiLegOrder, Order
from app.services.strategies import AdvancedStrategyAnalyzer
from app.services.validation import AccountValidator


class ValidationSeverity(str, Enum):
    """Validation message severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationRule(str, Enum):
    """Validation rule categories."""

    BASIC = "basic"
    OPTIONS = "options"
    COMPLIANCE = "compliance"
    STRATEGY = "strategy"
    LIQUIDITY = "liquidity"


class ValidationMessage(BaseModel):
    """Validation result message."""

    rule: ValidationRule = Field(..., description="Validation rule category")
    severity: ValidationSeverity = Field(..., description="Message severity")
    code: str = Field(..., description="Unique validation code")
    message: str = Field(..., description="Human-readable message")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional details"
    )
    suggested_action: str | None = Field(
        None, description="Suggested corrective action"
    )


class ValidationResult(BaseModel):
    """Comprehensive validation result."""

    is_valid: bool = Field(..., description="Overall validation status")
    can_execute: bool = Field(..., description="Whether order can be executed")
    messages: list[ValidationMessage] = Field(
        default_factory=list, description="Validation messages"
    )
    estimated_cost: float = Field(0.0, description="Estimated order cost")

    @property
    def errors(self) -> list[ValidationMessage]:
        """Get error messages."""
        return [
            msg
            for msg in self.messages
            if msg.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        ]

    @property
    def warnings(self) -> list[ValidationMessage]:
        """Get warning messages."""
        return [
            msg for msg in self.messages if msg.severity == ValidationSeverity.WARNING
        ]

    @property
    def infos(self) -> list[ValidationMessage]:
        """Get info messages."""
        return [msg for msg in self.messages if msg.severity == ValidationSeverity.INFO]


class AccountLimits(BaseModel):
    """Account trading limits and restrictions."""

    max_position_size: float = Field(
        100000.0, description="Maximum position size in dollars"
    )
    max_daily_trades: int = Field(100, description="Maximum trades per day")
    max_options_contracts: int = Field(1000, description="Maximum options contracts")
    max_delta_exposure: float = Field(10000.0, description="Maximum portfolio delta")
    max_theta_decay: float = Field(500.0, description="Maximum daily theta decay")
    max_vega_exposure: float = Field(5000.0, description="Maximum vega exposure")

    # Options-specific limits
    max_naked_options: int = Field(50, description="Maximum naked option positions")
    min_days_to_expiration: int = Field(
        1, description="Minimum days to expiration for new positions"
    )
    max_strike_distance: float = Field(
        0.5, description="Maximum strike distance from ATM (as percentage)"
    )

    # Pattern day trader rules
    is_pdt: bool = Field(False, description="Pattern day trader status")
    day_trades_used: int = Field(0, description="Day trades used in rolling period")

    # Account type restrictions
    options_level: int = Field(2, description="Options trading level (1-4)")


class AdvancedOrderValidator:
    """
    Advanced order validation with comprehensive pre-trade checks.

    Validates orders against:
    - Basic order requirements (cash, position availability)
    - Options-specific rules (expiration, strikes)
    - Regulatory compliance (PDT)
    - Strategy-specific validation
    - Liquidity and execution feasibility
    """

    def __init__(self) -> None:
        self.basic_validator = AccountValidator()
        self.strategy_analyzer = AdvancedStrategyAnalyzer()

    def validate_order(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        account_limits: AccountLimits | None = None,
    ) -> ValidationResult:
        """
        Perform comprehensive order validation.

        Args:
            account_data: Account state with positions and cash
            order: Order to validate
            current_quotes: Current market quotes
            account_limits: Account limits and restrictions

        Returns:
            ValidationResult with detailed analysis
        """
        if account_limits is None:
            account_limits = AccountLimits(
                max_position_size=100000.0,
                max_daily_trades=100,
                max_options_contracts=1000,
                max_delta_exposure=10000.0,
                max_theta_decay=500.0,
                max_vega_exposure=5000.0,
                max_naked_options=50,
                min_days_to_expiration=1,
                max_strike_distance=0.5,
                is_pdt=False,
                day_trades_used=0,
                options_level=2,
            )

        result = ValidationResult(
            is_valid=True,
            can_execute=True,
            estimated_cost=0.0,
        )

        # Basic validation
        self._validate_basic_requirements(account_data, order, current_quotes, result)

        # Options-specific validation
        if self._is_options_order(order):
            self._validate_options_requirements(
                order, current_quotes, account_limits, result
            )

        # Compliance validation
        self._validate_compliance_rules(account_data, order, account_limits, result)

        # Strategy validation
        self._validate_strategy_rules(account_data, order, current_quotes, result)

        # Liquidity validation
        self._validate_liquidity_requirements(order, current_quotes, result)

        # Determine final validation status
        has_errors = any(
            msg.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
            for msg in result.messages
        )
        result.is_valid = not has_errors
        result.can_execute = result.is_valid

        return result

    def _validate_basic_requirements(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        result: ValidationResult,
    ) -> None:
        """Validate basic order requirements."""

        # Use existing basic validator
        try:
            self.basic_validator.validate_account_state(
                cash_balance=account_data.get("cash_balance", 0.0),
                positions=account_data.get("positions", []),
            )

        except ValidationError as e:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.BASIC,
                    severity=ValidationSeverity.ERROR,
                    code="BASIC_VALIDATION",
                    message=str(e),
                    suggested_action=None,
                )
            )
        except Exception as e:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.BASIC,
                    severity=ValidationSeverity.ERROR,
                    code="BASIC_VALIDATION_ERROR",
                    message=f"Basic validation failed: {e!s}",
                    suggested_action=None,
                )
            )

    def _validate_options_requirements(
        self,
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        account_limits: AccountLimits,
        result: ValidationResult,
    ) -> None:
        """Validate options-specific requirements."""

        # Get all option symbols in the order
        option_symbols = []
        if isinstance(order, MultiLegOrder):
            option_symbols = [
                leg.asset.symbol for leg in order.legs if isinstance(leg.asset, Option)
            ]
        elif isinstance(order, Order) and isinstance(
            asset_factory(order.symbol), Option
        ):
            option_symbols = [order.symbol]

        for symbol in option_symbols:
            asset = asset_factory(symbol)
            if not isinstance(asset, Option):
                continue

            # Expiration validation
            self._validate_expiration_date(asset, account_limits, result)

            # Strike price validation
            self._validate_strike_price(asset, current_quotes, account_limits, result)

            # Liquidity validation for options
            self._validate_option_liquidity(symbol, current_quotes, result)

    def _validate_expiration_date(
        self, option: Option, account_limits: AccountLimits, result: ValidationResult
    ) -> None:
        """Validate option expiration date."""

        days_to_expiration = (option.expiration_date - date.today()).days

        # Check minimum days to expiration
        if days_to_expiration < account_limits.min_days_to_expiration:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=ValidationSeverity.ERROR,
                    code="EXPIRATION_TOO_CLOSE",
                    message=f"Option expires in {days_to_expiration} days, minimum is {account_limits.min_days_to_expiration}",
                    details={
                        "symbol": option.symbol,
                        "days_to_expiration": days_to_expiration,
                        "minimum_required": account_limits.min_days_to_expiration,
                    },
                    suggested_action="Choose option with later expiration date",
                )
            )

        # Warn about very close expiration
        elif days_to_expiration <= 7:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=ValidationSeverity.WARNING,
                    code="EXPIRATION_WARNING",
                    message=f"Option expires in {days_to_expiration} days",
                    details={
                        "symbol": option.symbol,
                        "days_to_expiration": days_to_expiration,
                    },
                    suggested_action="Consider longer-dated options",
                )
            )

        # Check for expired options
        if days_to_expiration < 0:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=ValidationSeverity.CRITICAL,
                    code="OPTION_EXPIRED",
                    message=f"Option has already expired on {option.expiration_date}",
                    details={
                        "symbol": option.symbol,
                        "expiration_date": option.expiration_date.isoformat(),
                    },
                    suggested_action="Choose a valid, unexpired option",
                )
            )

    def _validate_strike_price(
        self,
        option: Option,
        current_quotes: dict[str, Quote | OptionQuote],
        account_limits: AccountLimits,
        result: ValidationResult,
    ) -> None:
        """Validate strike price reasonableness."""

        # Get underlying price
        underlying_quote = current_quotes.get(option.underlying.symbol)
        if not underlying_quote:
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=ValidationSeverity.WARNING,
                    code="NO_UNDERLYING_QUOTE",
                    message=f"Cannot validate strike price - no quote for {option.underlying.symbol}",
                    details={"underlying_symbol": option.underlying.symbol},
                    suggested_action="Ensure market data is available for the underlying asset",
                )
            )
            return

        underlying_price = underlying_quote.price
        if underlying_price is None or underlying_price <= 0:
            return

        # Calculate strike distance from ATM
        option_strike = option.strike
        if option_strike is None:
            return
        strike_distance = abs(option_strike - underlying_price) / underlying_price

        # Check maximum strike distance
        if strike_distance > account_limits.max_strike_distance:
            severity = (
                ValidationSeverity.WARNING
                if strike_distance < 1.0
                else ValidationSeverity.ERROR
            )
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=severity,
                    code="STRIKE_TOO_FAR",
                    message=f"Strike ${option.strike:.2f} is {strike_distance:.1%} from ATM (${underlying_price:.2f})",
                    details={
                        "symbol": option.symbol,
                        "strike": option.strike,
                        "underlying_price": underlying_price,
                        "distance_percent": strike_distance,
                        "max_allowed": account_limits.max_strike_distance,
                    },
                    suggested_action="Consider strikes closer to current price",
                )
            )

        # Warn about deep ITM/OTM options
        if strike_distance > 0.2 and underlying_price is not None:  # More than 20% from ATM
            moneyness = (
                "ITM" if option.get_intrinsic_value(underlying_price) > 0 else "OTM"
            )
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.OPTIONS,
                    severity=ValidationSeverity.INFO,
                    code="DEEP_MONEYNESS",
                    message=f"Deep {moneyness} option - {strike_distance:.1%} from ATM",
                    details={
                        "symbol": option.symbol,
                        "moneyness": moneyness,
                        "distance_percent": strike_distance,
                    },
                    suggested_action=None,
                )
            )

    # def _validate_greeks_limits(
    #     self,
    #     account_data: Dict[str, Any],
    #     order: Union[Order, MultiLegOrder],
    #     current_quotes: Dict[str, Union[Quote, OptionQuote]],
    #     account_limits: AccountLimits,
    #     result: ValidationResult,
    # ) -> None:
    #     """Validate Greeks exposure limits."""

    #     # Calculate current portfolio Greeks
    #     positions = account_data.get("positions", [])
    #     current_greeks = self.strategy_analyzer.aggregate_strategy_greeks(
    #         positions, current_quotes
    #     )

    #     # Estimate Greeks impact of new order (simplified)
    #     order_delta_impact = 0.0
    #     order_theta_impact = 0.0

    #     # This would need more sophisticated calculation in a real implementation
    #     # For now, we'll do a basic estimate

    #     # Check delta limits
    #     new_delta = current_greeks.delta + order_delta_impact
    #     if abs(new_delta) > account_limits.max_delta_exposure:
    #         result.messages.append(
    #             ValidationMessage(
    #                 rule=ValidationRule.RISK,
    #                 severity=ValidationSeverity.WARNING,
    #                 code="DELTA_LIMIT_EXCEEDED",
    #                 message=f"Order would increase delta exposure to {new_delta:.0f} (limit: {account_limits.max_delta_exposure:.0f})",
    #                 details={
    #                     "current_delta": current_greeks.delta,
    #                     "order_impact": order_delta_impact,
    #                     "new_delta": new_delta,
    #                     "limit": account_limits.max_delta_exposure,
    #                 },
    #                 suggested_action="Consider delta hedging",
    #             )
    #         )

    #     # Check theta decay limits
    #     new_theta = current_greeks.theta + order_theta_impact
    #     if abs(new_theta) > account_limits.max_theta_decay:
    #         result.messages.append(
    #             ValidationMessage(
    #                 rule=ValidationRule.RISK,
    #                 severity=ValidationSeverity.WARNING,
    #                 code="THETA_LIMIT_EXCEEDED",
    #                 message=f"Order would increase theta decay to {new_theta:.2f}/day (limit: {account_limits.max_theta_decay:.2f})",
    #                 details={
    #                     "current_theta": current_greeks.theta,
    #                     "order_impact": order_theta_impact,
    #                     "new_theta": new_theta,
    #                     "limit": account_limits.max_theta_decay,
    #                 },
    #                 suggested_action="Monitor time decay risk",
    #             )
    #         )

    def _validate_compliance_rules(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder,
        account_limits: AccountLimits,
        result: ValidationResult,
    ) -> None:
        """Validate regulatory compliance rules."""

        # Pattern Day Trader rules
        if (account_limits.is_pdt and account_limits.day_trades_used >= 3 and 
            self._is_potential_day_trade(order, account_data)):
            result.messages.append(
                ValidationMessage(
                    rule=ValidationRule.COMPLIANCE,
                    severity=ValidationSeverity.ERROR,
                    code="PDT_LIMIT_EXCEEDED",
                    message="Pattern Day Trader limit exceeded - cannot place day trade",
                    details={
                        "day_trades_used": account_limits.day_trades_used,
                        "pdt_status": account_limits.is_pdt,
                    },
                    suggested_action="Wait until next trading day or avoid day trading",
                )
            )

        # Options trading level validation
        if self._is_options_order(order):
            required_level = self._get_required_options_level(order)
            if required_level > account_limits.options_level:
                result.messages.append(
                    ValidationMessage(
                        rule=ValidationRule.COMPLIANCE,
                        severity=ValidationSeverity.ERROR,
                        code="OPTIONS_LEVEL_INSUFFICIENT",
                        message=f"Order requires options level {required_level}, account has level {account_limits.options_level}",
                        details={
                            "required_level": required_level,
                            "account_level": account_limits.options_level,
                        },
                        suggested_action="Upgrade options trading level",
                    )
                )

    def _validate_strategy_rules(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        result: ValidationResult,
    ) -> None:
        """Validate strategy-specific rules."""

        # For multi-leg orders, validate strategy coherence
        if isinstance(order, MultiLegOrder):
            self._validate_multileg_strategy(order, current_quotes, result)

        # Check for conflicting positions
        self._validate_position_conflicts(order, account_data, result)

    def _validate_liquidity_requirements(
        self,
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        result: ValidationResult,
    ) -> None:
        """Validate liquidity and execution feasibility."""

        symbols = []
        if isinstance(order, Order):
            symbols = [order.symbol]
        elif isinstance(order, MultiLegOrder):
            symbols = [leg.asset.symbol for leg in order.legs]

        for symbol in symbols:
            quote = current_quotes.get(symbol)
            if not quote:
                result.messages.append(
                    ValidationMessage(
                        rule=ValidationRule.LIQUIDITY,
                        severity=ValidationSeverity.WARNING,
                        code="NO_QUOTE_AVAILABLE",
                        message=f"No current quote available for {symbol}",
                        details={"symbol": symbol},
                        suggested_action="Wait for market quote or check symbol",
                    )
                )
                continue

            # Check bid-ask spread
            if (
                hasattr(quote, "bid")
                and hasattr(quote, "ask")
                and quote.bid
                and quote.ask
            ):
                spread_percent = (
                    (quote.ask - quote.bid) / quote.price
                    if quote.price and quote.price > 0
                    else 0
                )

                if spread_percent > 0.1:  # Spread wider than 10%
                    result.messages.append(
                        ValidationMessage(
                            rule=ValidationRule.LIQUIDITY,
                            severity=ValidationSeverity.WARNING,
                            code="WIDE_SPREAD",
                            message=f"Wide bid-ask spread for {symbol}: {spread_percent:.1%}",
                            details={
                                "symbol": symbol,
                                "spread_percent": spread_percent,
                                "bid": quote.bid,
                                "ask": quote.ask,
                            },
                            suggested_action="Consider using limit orders",
                        )
                    )

    def _validate_option_liquidity(
        self,
        symbol: str,
        current_quotes: dict[str, Quote | OptionQuote],
        result: ValidationResult,
    ) -> None:
        """Validate option-specific liquidity."""

        quote = current_quotes.get(symbol)
        if not isinstance(quote, OptionQuote):
            return

        # Check volume
        if hasattr(quote, "volume") and quote.volume is not None and quote.volume < 10:
            result.messages.append(
                    ValidationMessage(
                        rule=ValidationRule.LIQUIDITY,
                        severity=ValidationSeverity.WARNING,
                        code="LOW_OPTION_VOLUME",
                        message=f"Low volume for {symbol}: {quote.volume} contracts",
                        details={"symbol": symbol, "volume": quote.volume},
                        suggested_action="Consider more liquid options",
                    )
                )

        # Check open interest
        if (hasattr(quote, "open_interest") and quote.open_interest is not None and 
            quote.open_interest < 50):
            result.messages.append(
                    ValidationMessage(
                        rule=ValidationRule.LIQUIDITY,
                        severity=ValidationSeverity.INFO,
                        code="LOW_OPEN_INTEREST",
                        message=f"Low open interest for {symbol}: {quote.open_interest} contracts",
                        details={
                            "symbol": symbol,
                            "open_interest": quote.open_interest,
                        },
                        suggested_action=None,
                    )
                )

    def _calculate_estimated_cost(
        self,
        order: Order | MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
    ) -> float:
        """Calculate estimated cost of order."""

        total_cost = 0.0

        if isinstance(order, Order):
            quote = current_quotes.get(order.symbol)
            if quote:
                asset = asset_factory(order.symbol)
                multiplier = 100 if isinstance(asset, Option) else 1
                price = order.price if order.price else quote.price
                if price is not None:
                    total_cost = abs(order.quantity) * price * multiplier

        elif isinstance(order, MultiLegOrder):
            for leg in order.legs:
                quote = current_quotes.get(leg.asset.symbol)
                if quote:
                    multiplier = 100 if isinstance(leg.asset, Option) else 1
                    price = leg.price if leg.price else quote.price
                    if price is not None:
                        total_cost += abs(leg.quantity) * price * multiplier

        return total_cost

    def _is_options_order(self, order: Order | MultiLegOrder) -> bool:
        """Check if order involves options."""
        if isinstance(order, MultiLegOrder):
            return any(isinstance(leg.asset, Option) for leg in order.legs)
        else:
            return isinstance(asset_factory(order.symbol), Option)

    def _is_potential_day_trade(
        self, order: Order | MultiLegOrder, account_data: dict[str, Any]
    ) -> bool:
        """Check if order could be a day trade."""
        # Basic implementation - check if we have existing positions
        # In a real implementation, this would check trade history
        return False

    def _get_required_options_level(self, order: Order | MultiLegOrder) -> int:
        """Get required options level for order."""
        # Basic implementation - return level based on order complexity
        if isinstance(order, MultiLegOrder):
            return 3  # Multi-leg orders require level 3
        else:
            return 2  # Single options require level 2

    def _validate_multileg_strategy(
        self,
        order: MultiLegOrder,
        current_quotes: dict[str, Quote | OptionQuote],
        result: ValidationResult,
    ) -> None:
        """Validate multi-leg strategy coherence."""
        # Basic implementation - check that all legs are options
        for leg in order.legs:
            if not isinstance(leg.asset, Option):
                result.messages.append(
                    ValidationMessage(
                        rule=ValidationRule.STRATEGY,
                        severity=ValidationSeverity.WARNING,
                        code="MIXED_STRATEGY",
                        message=f"Mixed strategy contains non-option: {leg.asset.symbol}",
                        details={"symbol": leg.asset.symbol},
                        suggested_action="Consider using single-leg orders for stocks",
                    )
                )

    def _validate_position_conflicts(
        self,
        order: Order | MultiLegOrder,
        account_data: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate for position conflicts."""
        # Basic implementation - placeholder for position conflict checks
        pass


# Convenience functions
def validate_order_comprehensive(
    account_data: dict[str, Any],
    order: Order | MultiLegOrder,
    current_quotes: dict[str, Quote | OptionQuote],
    account_limits: AccountLimits | None = None,
) -> ValidationResult:
    """Perform comprehensive order validation."""
    validator = AdvancedOrderValidator()
    return validator.validate_order(account_data, order, current_quotes, account_limits)


def create_default_account_limits(
    options_level: int = 2, is_pdt: bool = False
) -> AccountLimits:
    """Create default account limits based on account type."""
    return AccountLimits(
        options_level=options_level,
        is_pdt=is_pdt,
        max_position_size=50000.0 if options_level >= 3 else 25000.0,
        max_options_contracts=500 if options_level >= 3 else 100,
        max_daily_trades=100,
        max_delta_exposure=10000.0,
        max_theta_decay=500.0,
        max_vega_exposure=5000.0,
        max_naked_options=50,
        min_days_to_expiration=1,
        max_strike_distance=0.5,
        day_trades_used=0,
    )
