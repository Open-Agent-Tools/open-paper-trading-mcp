"""
Strategy models and types.

This module contains the core strategy models, enums, and data structures
for the trading strategy system.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...models.assets import Asset, Option, asset_factory
from ...models.trading import Position


class StrategyType(str, Enum):
    """Strategy classification types."""

    BASIC = "basic"
    ASSET = "asset"
    OFFSET = "offset"
    SPREAD = "spread"
    COVERED = "covered"


class SpreadType(str, Enum):
    """Spread strategy subtypes."""

    CREDIT = "credit"
    DEBIT = "debit"


class ComplexStrategyType(str, Enum):
    """Complex multi-leg strategy types."""

    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    STRANGLE = "strangle"
    STRADDLE = "straddle"
    COLLAR = "collar"
    RATIO_SPREAD = "ratio_spread"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"


class BasicStrategy(BaseModel):
    """Base class for all trading strategies."""

    strategy_type: StrategyType = Field(
        default=StrategyType.BASIC, description="Strategy classification"
    )
    quantity: int = Field(default=1, description="Strategy quantity (contracts/shares)")

    model_config = ConfigDict(use_enum_values=True)


class AssetStrategy(BasicStrategy):
    """Strategy involving long or short positions in an asset."""

    strategy_type: Literal[StrategyType.ASSET] = Field(default=StrategyType.ASSET)
    asset: Asset = Field(..., description="Asset being held")
    direction: str = Field(..., description="Position direction (long/short)")

    def __init__(self, asset: str | Asset, quantity: int = 1, **data: Any) -> None:
        # Normalize asset
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        if asset_obj is None:
            raise ValueError(f"Could not create asset from: {asset}")

        # Determine direction
        direction = "short" if quantity < 0 else "long"

        super().__init__(quantity=quantity, **data)
        self.asset = asset_obj
        self.direction = direction


class OffsetStrategy(BasicStrategy):
    """Strategy with simultaneous long and short positions in same asset."""

    strategy_type: Literal[StrategyType.OFFSET] = Field(default=StrategyType.OFFSET)
    asset: Asset = Field(..., description="Asset being offset")

    def __init__(self, asset: str | Asset, quantity: int = 1, **data: Any) -> None:
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        if asset_obj is None:
            raise ValueError(f"Could not create asset from: {asset}")

        super().__init__(quantity=quantity, **data)
        self.asset = asset_obj


class SpreadStrategy(BasicStrategy):
    """Options spread strategy."""

    strategy_type: Literal[StrategyType.SPREAD] = Field(default=StrategyType.SPREAD)
    sell_option: Option = Field(..., description="Option being sold")
    buy_option: Option = Field(..., description="Option being bought")
    option_type: str = Field(..., description="Option type (call/put)")
    spread_type: SpreadType = Field(
        ..., description="Spread classification (credit/debit)"
    )

    def __init__(
        self, sell_option: Option, buy_option: Option, quantity: int = 1, **data: Any
    ) -> None:
        # Validation
        if sell_option.option_type != buy_option.option_type:
            raise ValueError("SpreadStrategy: option types must match")

        if sell_option.underlying.symbol != buy_option.underlying.symbol:
            raise ValueError("SpreadStrategy: underlying assets must match")

        if sell_option.strike == buy_option.strike:
            raise ValueError("SpreadStrategy: strikes must be different")

        # Determine spread type based on option type and strikes
        option_type = sell_option.option_type

        if option_type == "put":
            spread_type = (
                SpreadType.CREDIT
                if sell_option.strike > buy_option.strike
                else SpreadType.DEBIT
            )
        else:  # call
            spread_type = (
                SpreadType.CREDIT
                if sell_option.strike < buy_option.strike
                else SpreadType.DEBIT
            )

        super().__init__(quantity=abs(quantity), **data)
        self.sell_option = sell_option
        self.buy_option = buy_option
        self.option_type = option_type
        self.spread_type = spread_type


class CoveredStrategy(BasicStrategy):
    """Strategy where underlying asset covers a short option."""

    strategy_type: Literal[StrategyType.COVERED] = Field(default=StrategyType.COVERED)
    asset: Asset = Field(..., description="Underlying asset providing cover")
    sell_option: Option = Field(..., description="Option being sold")

    def __init__(
        self,
        asset: str | Asset,
        sell_option: Option,
        quantity: int = 1,
        **data: Any,
    ) -> None:
        # Normalize asset
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        if asset_obj is None:
            raise ValueError(f"Could not create asset from: {asset}")

        # Validation
        if asset_obj.symbol != sell_option.underlying.symbol:
            raise ValueError("CoveredStrategy: option underlying must match asset")

        super().__init__(quantity=abs(quantity), **data)
        self.asset = asset_obj
        self.sell_option = sell_option


class ComplexStrategy(BasicStrategy):
    """Multi-leg complex strategy."""

    strategy_type: Literal[StrategyType.SPREAD] = Field(default=StrategyType.SPREAD)
    complex_type: ComplexStrategyType = Field(
        ..., description="Complex strategy subtype"
    )
    legs: list[Position] = Field(..., description="Strategy legs")
    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    net_credit: float = Field(0.0, description="Net credit/debit (positive = credit)")
    max_profit: float | None = Field(None, description="Maximum profit potential")
    max_loss: float | None = Field(None, description="Maximum loss potential")
    breakeven_points: list[float] = Field(
        default_factory=list, description="Breakeven prices"
    )


class StrategyPnL(BaseModel):
    """Advanced P&L calculation for strategy positions."""

    strategy_type: str = Field(..., description="Strategy type identifier")
    strategy_name: str = Field(..., description="Human-readable strategy name")
    unrealized_pnl: float = Field(0.0, description="Current unrealized P&L")
    realized_pnl: float = Field(0.0, description="Realized P&L from closed positions")
    total_pnl: float = Field(0.0, description="Total P&L (realized + unrealized)")
    pnl_percent: float = Field(0.0, description="P&L as percentage of cost basis")
    cost_basis: float = Field(0.0, description="Total cost basis of strategy")
    market_value: float = Field(0.0, description="Current market value")
    max_profit: float | None = Field(None, description="Maximum theoretical profit")
    max_loss: float | None = Field(None, description="Maximum theoretical loss")
    breakeven_points: list[float] = Field(
        default_factory=list, description="Breakeven prices"
    )
    days_held: int = Field(0, description="Days strategy has been held")
    annualized_return: float | None = Field(
        None, description="Annualized return percentage"
    )


class StrategyGreeks(BaseModel):
    """Aggregated Greeks for strategy positions."""

    delta: float = Field(0.0, description="Total delta exposure")
    gamma: float = Field(0.0, description="Total gamma exposure")
    theta: float = Field(0.0, description="Total theta decay per day")
    vega: float = Field(0.0, description="Total vega sensitivity")
    rho: float = Field(0.0, description="Total rho sensitivity")

    # Dollar-denominated Greeks
    delta_dollars: float = Field(0.0, description="Delta in dollar terms")
    gamma_dollars: float = Field(0.0, description="Gamma in dollar terms")
    theta_dollars: float = Field(0.0, description="Theta in dollar terms")

    # Normalized Greeks (per $1000 invested)
    delta_normalized: float = Field(0.0, description="Delta per $1000 invested")
    gamma_normalized: float = Field(0.0, description="Gamma per $1000 invested")
    theta_normalized: float = Field(0.0, description="Theta per $1000 invested")
    vega_normalized: float = Field(0.0, description="Vega per $1000 invested")
