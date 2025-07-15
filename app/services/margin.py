"""
Maintenance margin calculation service for options trading.

Adapted from paperbroker with enhanced naked option calculations and modern Python patterns.
Calculates margin requirements for various trading strategies according to standard rules.

Margin Rules Summary:
- Long positions: No margin required
- Short stock: 100% of market value
- Covered strategies: No additional margin
- Debit spreads: No margin (already paid)
- Credit spreads: Strike width × 100 × quantity
- Naked options: Complex calculation based on underlying price and volatility
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.assets import Option, Call, Put
from ..models.trading import Position
from .strategies import (
    BasicStrategy,
    AssetStrategy,
    SpreadStrategy,
    CoveredStrategy,
    StrategyType,
    SpreadType,
    group_into_basic_strategies,
)


class MarginRequirement(BaseModel):
    """Margin requirement breakdown for a strategy."""

    strategy_id: str = Field(..., description="Strategy identifier")
    strategy_type: StrategyType = Field(..., description="Strategy classification")
    margin_requirement: float = Field(ge=0, description="Required margin amount")
    calculation_method: str = Field(..., description="Method used for calculation")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Calculation details"
    )


class MarginCalculationResult(BaseModel):
    """Complete margin calculation result."""

    total_margin_requirement: float = Field(ge=0, description="Total margin required")
    strategy_margins: List[MarginRequirement] = Field(
        default_factory=list, description="Per-strategy margins"
    )
    calculation_timestamp: datetime = Field(
        default_factory=datetime.now, description="Calculation time"
    )
    quote_source: Optional[str] = Field(None, description="Quote data source")
    warnings: List[str] = Field(
        default_factory=list, description="Calculation warnings"
    )


class MaintenanceMarginService:
    """Service for calculating maintenance margin requirements."""

    # Standard margin rates (can be configured)
    NAKED_CALL_MIN_RATE = 0.20  # 20% of underlying value
    NAKED_PUT_MIN_RATE = 0.20  # 20% of strike price
    SHORT_STOCK_RATE = 1.0  # 100% of market value

    def __init__(self, quote_adapter=None):
        """
        Initialize margin service.

        Args:
            quote_adapter: Quote adapter for current market prices
        """
        self.quote_adapter = quote_adapter

    def calculate_maintenance_margin(
        self,
        positions: Optional[List[Position]] = None,
        strategies: Optional[List[BasicStrategy]] = None,
        quote_adapter=None,
    ) -> MarginCalculationResult:
        """
        Calculate total maintenance margin requirement.

        Args:
            positions: List of positions (will be grouped into strategies)
            strategies: Pre-grouped strategies (takes precedence over positions)
            quote_adapter: Quote adapter override

        Returns:
            Complete margin calculation result
        """
        # Use provided quote adapter or fallback
        adapter = quote_adapter or self.quote_adapter

        # Group positions into strategies if not provided
        if strategies is None:
            if positions is None:
                positions = []
            strategies = group_into_basic_strategies(positions)

        result = MarginCalculationResult(
            total_margin_requirement=0.0,
            quote_source=(
                getattr(adapter, "__class__", {}).get("__name__", "unknown")
                if adapter
                else None
            ),
        )

        # Calculate margin for each strategy
        for i, strategy in enumerate(strategies):
            strategy_id = f"strategy_{i}_{strategy.strategy_type}"

            try:
                margin_req = self._calculate_strategy_margin(strategy, adapter)
                margin_req.strategy_id = strategy_id

                result.strategy_margins.append(margin_req)
                result.total_margin_requirement += margin_req.margin_requirement

            except Exception as e:
                warning = f"Failed to calculate margin for {strategy_id}: {str(e)}"
                result.warnings.append(warning)

        return result

    def _calculate_strategy_margin(
        self, strategy: BasicStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin requirement for a single strategy."""

        if strategy.strategy_type == StrategyType.ASSET:
            return self._calculate_asset_margin(strategy, quote_adapter)
        elif strategy.strategy_type == StrategyType.SPREAD:
            return self._calculate_spread_margin(strategy, quote_adapter)
        elif strategy.strategy_type == StrategyType.COVERED:
            return self._calculate_covered_margin(strategy, quote_adapter)
        elif strategy.strategy_type == StrategyType.OFFSET:
            return self._calculate_offset_margin(strategy, quote_adapter)
        else:
            return MarginRequirement(
                strategy_id="",
                strategy_type=strategy.strategy_type,
                margin_requirement=0.0,
                calculation_method="unknown_strategy",
                details={"error": "Unknown strategy type"},
            )

    def _calculate_asset_margin(
        self, strategy: AssetStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin for asset (stock/option) strategy."""

        if strategy.direction == "long":
            # Long positions require no margin
            return MarginRequirement(
                strategy_id="",
                strategy_type=StrategyType.ASSET,
                margin_requirement=0.0,
                calculation_method="long_position_no_margin",
                details={
                    "asset": strategy.asset.symbol,
                    "quantity": strategy.quantity,
                    "direction": strategy.direction,
                },
            )

        # Short positions
        if isinstance(strategy.asset, Option):
            return self._calculate_naked_option_margin(strategy, quote_adapter)
        else:
            return self._calculate_short_stock_margin(strategy, quote_adapter)

    def _calculate_short_stock_margin(
        self, strategy: AssetStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin for short stock position."""

        if quote_adapter is None:
            raise ValueError(
                "Quote adapter required for short stock margin calculation"
            )

        quote = quote_adapter.get_quote(strategy.asset)
        if quote is None or quote.price is None:
            raise ValueError(f"No quote available for {strategy.asset.symbol}")

        # Short stock margin = 100% of market value
        margin = abs(strategy.quantity) * quote.price * self.SHORT_STOCK_RATE

        return MarginRequirement(
            strategy_id="",
            strategy_type=StrategyType.ASSET,
            margin_requirement=margin,
            calculation_method="short_stock_100_percent",
            details={
                "asset": strategy.asset.symbol,
                "quantity": strategy.quantity,
                "price": quote.price,
                "margin_rate": self.SHORT_STOCK_RATE,
            },
        )

    def _calculate_naked_option_margin(
        self, strategy: AssetStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin for naked option position."""

        if not isinstance(strategy.asset, Option):
            raise ValueError("Expected Option asset for naked option calculation")

        if quote_adapter is None:
            # Return None to indicate calculation not possible
            return MarginRequirement(
                strategy_id="",
                strategy_type=StrategyType.ASSET,
                margin_requirement=0.0,
                calculation_method="naked_option_no_quotes",
                details={
                    "asset": strategy.asset.symbol,
                    "error": "Quote adapter required for naked option margin",
                },
            )

        option = strategy.asset

        # Get underlying quote
        underlying_quote = quote_adapter.get_quote(option.underlying)
        if underlying_quote is None or underlying_quote.price is None:
            raise ValueError(f"No underlying quote for {option.underlying.symbol}")

        # Get option quote for premium
        option_quote = quote_adapter.get_quote(option)
        option_premium = (
            option_quote.price if option_quote and option_quote.price else 0.0
        )

        if isinstance(option, Call):
            margin = self._calculate_naked_call_margin(
                option, underlying_quote.price, option_premium, abs(strategy.quantity)
            )
            method = "naked_call_standard"
        else:  # Put
            margin = self._calculate_naked_put_margin(
                option, underlying_quote.price, option_premium, abs(strategy.quantity)
            )
            method = "naked_put_standard"

        return MarginRequirement(
            strategy_id="",
            strategy_type=StrategyType.ASSET,
            margin_requirement=margin,
            calculation_method=method,
            details={
                "asset": option.symbol,
                "underlying_price": underlying_quote.price,
                "strike": option.strike,
                "option_premium": option_premium,
                "quantity": strategy.quantity,
                "option_type": option.option_type,
            },
        )

    def _calculate_naked_call_margin(
        self, call: Call, underlying_price: float, premium: float, quantity: int
    ) -> float:
        """
        Calculate naked call margin using standard formula.

        Naked Call Margin = (Premium + MAX(20% × Underlying - OTM, 10% × Underlying)) × 100 × Quantity
        Where OTM = MAX(0, Strike - Underlying) for calls
        """
        # Out-of-the-money amount
        otm_amount = max(0, call.strike - underlying_price)

        # Standard calculation: 20% of underlying minus out-of-money amount
        standard_calc = (self.NAKED_CALL_MIN_RATE * underlying_price) - otm_amount

        # Minimum 10% of underlying value
        minimum_calc = 0.10 * underlying_price

        # Take the maximum
        margin_per_share = premium + max(standard_calc, minimum_calc)

        # Total margin (100 shares per contract)
        return margin_per_share * 100 * quantity

    def _calculate_naked_put_margin(
        self, put: Put, underlying_price: float, premium: float, quantity: int
    ) -> float:
        """
        Calculate naked put margin using standard formula.

        Naked Put Margin = (Premium + MAX(20% × Underlying - OTM, 10% × Strike)) × 100 × Quantity
        Where OTM = MAX(0, Underlying - Strike) for puts
        """
        # Out-of-the-money amount
        otm_amount = max(0, underlying_price - put.strike)

        # Standard calculation: 20% of underlying minus out-of-money amount
        standard_calc = (self.NAKED_PUT_MIN_RATE * underlying_price) - otm_amount

        # Minimum 10% of strike price
        minimum_calc = 0.10 * put.strike

        # Take the maximum
        margin_per_share = premium + max(standard_calc, minimum_calc)

        # Total margin (100 shares per contract)
        return margin_per_share * 100 * quantity

    def _calculate_spread_margin(
        self, strategy: SpreadStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin for spread strategy."""

        if strategy.spread_type == SpreadType.DEBIT:
            # Debit spreads require no margin (premium already paid)
            return MarginRequirement(
                strategy_id="",
                strategy_type=StrategyType.SPREAD,
                margin_requirement=0.0,
                calculation_method="debit_spread_no_margin",
                details={
                    "spread_type": strategy.spread_type.value,
                    "option_type": strategy.option_type,
                    "sell_strike": strategy.sell_option.strike,
                    "buy_strike": strategy.buy_option.strike,
                },
            )

        # Credit spreads: margin = strike width × 100 × quantity
        if strategy.option_type == "put":
            strike_width = strategy.sell_option.strike - strategy.buy_option.strike
        else:  # call
            strike_width = strategy.buy_option.strike - strategy.sell_option.strike

        margin = strike_width * 100 * strategy.quantity

        return MarginRequirement(
            strategy_id="",
            strategy_type=StrategyType.SPREAD,
            margin_requirement=margin,
            calculation_method="credit_spread_strike_width",
            details={
                "spread_type": strategy.spread_type.value,
                "option_type": strategy.option_type,
                "sell_strike": strategy.sell_option.strike,
                "buy_strike": strategy.buy_option.strike,
                "strike_width": strike_width,
                "quantity": strategy.quantity,
            },
        )

    def _calculate_covered_margin(
        self, strategy: CoveredStrategy, quote_adapter
    ) -> MarginRequirement:
        """Calculate margin for covered strategy."""

        # Covered strategies require no additional margin
        return MarginRequirement(
            strategy_id="",
            strategy_type=StrategyType.COVERED,
            margin_requirement=0.0,
            calculation_method="covered_position_no_margin",
            details={
                "underlying": strategy.asset.symbol,
                "option": strategy.sell_option.symbol,
                "option_type": strategy.sell_option.option_type,
                "strike": strategy.sell_option.strike,
            },
        )

    def _calculate_offset_margin(self, strategy, quote_adapter) -> MarginRequirement:
        """Calculate margin for offset strategy."""

        # Offset strategies typically require no additional margin
        return MarginRequirement(
            strategy_id="",
            strategy_type=StrategyType.OFFSET,
            margin_requirement=0.0,
            calculation_method="offset_position_no_margin",
            details={"asset": strategy.asset.symbol, "quantity": strategy.quantity},
        )

    def get_portfolio_margin_breakdown(
        self, positions: List[Position], quote_adapter=None
    ) -> Dict[str, Any]:
        """Get detailed margin breakdown by underlying asset."""

        adapter = quote_adapter or self.quote_adapter
        result = self.calculate_maintenance_margin(
            positions=positions, quote_adapter=adapter
        )

        # Group by underlying
        breakdown = {}

        for margin_req in result.strategy_margins:
            # Extract underlying from details
            underlying = "unknown"
            if "asset" in margin_req.details:
                asset_symbol = margin_req.details["asset"]
                if len(asset_symbol) > 6:  # Likely an option symbol
                    underlying = (
                        asset_symbol.split("_")[0]
                        if "_" in asset_symbol
                        else asset_symbol[:4]
                    )
                else:
                    underlying = asset_symbol

            if underlying not in breakdown:
                breakdown[underlying] = {
                    "total_margin": 0.0,
                    "strategies": [],
                    "strategy_count": 0,
                }

            breakdown[underlying]["total_margin"] += margin_req.margin_requirement
            breakdown[underlying]["strategies"].append(margin_req)
            breakdown[underlying]["strategy_count"] += 1

        return {
            "total_margin": result.total_margin_requirement,
            "by_underlying": breakdown,
            "calculation_time": result.calculation_timestamp,
            "warnings": result.warnings,
        }


# Convenience functions
def calculate_maintenance_margin(
    positions: Optional[List[Position]] = None,
    strategies: Optional[List[BasicStrategy]] = None,
    quote_adapter=None,
) -> float:
    """Calculate total maintenance margin requirement."""
    service = MaintenanceMarginService(quote_adapter)
    result = service.calculate_maintenance_margin(positions, strategies, quote_adapter)
    return result.total_margin_requirement


def get_margin_breakdown(
    positions: List[Position], quote_adapter=None
) -> Dict[str, Any]:
    """Get detailed margin breakdown for positions."""
    service = MaintenanceMarginService(quote_adapter)
    return service.get_portfolio_margin_breakdown(positions, quote_adapter)
