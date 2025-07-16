"""
Position and portfolio API schemas.

This module contains all Pydantic models for position management:
- Position models with options support and Greeks
- Portfolio and portfolio summary schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union, Dict, Any
from datetime import date
from app.models.assets import Asset, Option, asset_factory


class Position(BaseModel):
    """Enhanced position model with options support and Greeks."""

    symbol: str = Field(..., description="Asset symbol")
    quantity: int = Field(..., description="Number of shares/contracts owned")
    avg_price: float = Field(..., description="Average purchase price (cost basis)")
    current_price: Optional[float] = Field(
        default=None, description="Current market price"
    )
    unrealized_pnl: Optional[float] = Field(
        default=None, description="Unrealized profit/loss"
    )
    realized_pnl: float = Field(default=0.0, description="Realized profit/loss")

    # Asset information
    asset: Optional[Asset] = Field(
        default=None, description="Asset object with details"
    )

    # Options-specific fields (None for stocks)
    option_type: Optional[str] = Field(
        default=None, description="Option type: call or put"
    )
    strike: Optional[float] = Field(default=None, description="Strike price")
    expiration_date: Optional[date] = Field(default=None, description="Expiration date")
    underlying_symbol: Optional[str] = Field(
        default=None, description="Underlying asset symbol"
    )

    # Greeks (for options positions)
    delta: Optional[float] = Field(default=None, description="Position delta")
    gamma: Optional[float] = Field(default=None, description="Position gamma")
    theta: Optional[float] = Field(default=None, description="Position theta")
    vega: Optional[float] = Field(default=None, description="Position vega")
    rho: Optional[float] = Field(default=None, description="Position rho")
    iv: Optional[float] = Field(default=None, description="Implied volatility")

    @field_validator("asset", mode="before")
    def normalize_asset(cls, v: Union[str, Asset]) -> Optional[Asset]:
        if isinstance(v, str):
            return asset_factory(v)
        return v

    @property
    def is_option(self) -> bool:
        """Check if this is an options position."""
        return isinstance(self.asset, Option) or self.option_type is not None

    @property
    def multiplier(self) -> int:
        """Position multiplier (100 for options, 1 for stocks)."""
        return 100 if self.is_option else 1

    @property
    def total_cost_basis(self) -> float:
        """Total cost basis of the position."""
        return abs(self.avg_price * self.quantity) * self.multiplier

    @property
    def market_value(self) -> Optional[float]:
        """Current market value of the position."""
        if self.current_price is None:
            return None
        return self.current_price * self.quantity * self.multiplier

    @property
    def total_pnl(self) -> Optional[float]:
        """Total profit/loss (unrealized + realized)."""
        if self.unrealized_pnl is None:
            return self.realized_pnl
        return self.unrealized_pnl + self.realized_pnl

    @property
    def pnl_percent(self) -> Optional[float]:
        """P&L as percentage of cost basis."""
        if self.total_pnl is None or self.total_cost_basis == 0:
            return None
        return (self.total_pnl / self.total_cost_basis) * 100

    def calculate_unrealized_pnl(
        self, current_price: Optional[float] = None
    ) -> Optional[float]:
        """Calculate unrealized P&L with optional price override."""
        price = current_price or self.current_price
        if price is None:
            return None

        # For long positions: (current_price - avg_price) * quantity * multiplier
        # For short positions: (avg_price - current_price) * quantity * multiplier
        pnl = (price - self.avg_price) * self.quantity * self.multiplier
        return pnl

    def update_market_data(
        self, current_price: float, quote: Optional[Any] = None
    ) -> None:
        """Update position with current market data and Greeks."""
        self.current_price = current_price
        self.unrealized_pnl = self.calculate_unrealized_pnl(current_price)

        # Update Greeks if quote provided and this is an options position
        if quote is not None and self.is_option and hasattr(quote, "delta"):
            delta_val = getattr(quote, "delta", None)
            self.delta = (
                delta_val * self.quantity * self.multiplier
                if delta_val is not None
                else None
            )

            gamma_val = getattr(quote, "gamma", None)
            self.gamma = (
                gamma_val * self.quantity * self.multiplier
                if gamma_val is not None
                else None
            )

            theta_val = getattr(quote, "theta", None)
            self.theta = (
                theta_val * self.quantity * self.multiplier
                if theta_val is not None
                else None
            )

            vega_val = getattr(quote, "vega", None)
            self.vega = (
                vega_val * self.quantity * self.multiplier
                if vega_val is not None
                else None
            )

            rho_val = getattr(quote, "rho", None)
            self.rho = (
                rho_val * self.quantity * self.multiplier
                if rho_val is not None
                else None
            )
            self.iv = getattr(quote, "iv", None)

    def get_close_cost(self, current_price: Optional[float] = None) -> Optional[float]:
        """Cost to close the position (negative means you receive money)."""
        price = current_price or self.current_price
        if price is None:
            return None

        # To close: opposite action of opening
        # Long position: sell (negative cost = receive money)
        # Short position: buy (positive cost = pay money)
        return -price * self.quantity * self.multiplier

    def simulate_close(
        self, current_price: Optional[float] = None
    ) -> Dict[str, Union[float, str]]:
        """Simulate closing the position and return impact."""
        price = current_price or self.current_price
        if price is None:
            return {"error": "No price available"}

        close_cost = self.get_close_cost(price)
        realized_pnl = self.calculate_unrealized_pnl(price)

        if close_cost is None or realized_pnl is None:
            return {"error": "Unable to calculate close cost or realized PnL"}

        return {
            "close_cost": close_cost,
            "realized_pnl": realized_pnl,
            "total_realized_pnl": self.realized_pnl + realized_pnl,
            "cash_impact": close_cost,  # Negative means cash increases
        }


class Portfolio(BaseModel):
    cash_balance: float = Field(..., description="Available cash balance")
    total_value: float = Field(..., description="Total portfolio value")
    positions: List[Position] = Field(..., description="List of current positions")
    daily_pnl: float = Field(..., description="Daily profit/loss")
    total_pnl: float = Field(..., description="Total profit/loss")


class PortfolioSummary(BaseModel):
    total_value: float = Field(..., description="Total portfolio value")
    cash_balance: float = Field(..., description="Available cash balance")
    invested_value: float = Field(..., description="Value of invested positions")
    daily_pnl: float = Field(..., description="Daily profit/loss")
    daily_pnl_percent: float = Field(..., description="Daily P&L percentage")
    total_pnl: float = Field(..., description="Total profit/loss")
    total_pnl_percent: float = Field(..., description="Total P&L percentage")
