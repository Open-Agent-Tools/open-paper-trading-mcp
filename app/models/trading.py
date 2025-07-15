from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, Dict, Any
from datetime import datetime, date
from enum import Enum
from .assets import Asset, Option, asset_factory


class OrderType(str, Enum):
    """Order types for trading operations."""
    BUY = "buy"
    SELL = "sell"
    BTO = "buy_to_open"
    STO = "sell_to_open"
    BTC = "buy_to_close"
    STC = "sell_to_close"


class OrderStatus(str, Enum):
    """Order status values."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


class OrderCondition(str, Enum):
    """Order execution conditions."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order side for multi-leg orders."""
    BUY = "buy"
    SELL = "sell"





class StockQuote(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    price: float = Field(..., description="Current stock price")
    change: float = Field(..., description="Price change from previous close")
    change_percent: float = Field(
        ..., description="Percentage change from previous close"
    )
    volume: int = Field(..., description="Trading volume")
    last_updated: datetime = Field(..., description="Last update timestamp")


class Position(BaseModel):
    """Enhanced position model with options support and Greeks."""

    symbol: str = Field(..., description="Asset symbol")
    quantity: int = Field(..., description="Number of shares/contracts owned")
    avg_price: float = Field(..., description="Average purchase price (cost basis)")
    current_price: Optional[float] = Field(None, description="Current market price")
    unrealized_pnl: Optional[float] = Field(None, description="Unrealized profit/loss")
    realized_pnl: float = Field(default=0.0, description="Realized profit/loss")

    # Asset information
    asset: Optional[Asset] = Field(None, description="Asset object with details")

    # Options-specific fields (None for stocks)
    option_type: Optional[str] = Field(None, description="Option type: call or put")
    strike: Optional[float] = Field(None, description="Strike price")
    expiration_date: Optional[date] = Field(None, description="Expiration date")
    underlying_symbol: Optional[str] = Field(
        None, description="Underlying asset symbol"
    )

    # Greeks (for options positions)
    delta: Optional[float] = Field(None, description="Position delta")
    gamma: Optional[float] = Field(None, description="Position gamma")
    theta: Optional[float] = Field(None, description="Position theta")
    vega: Optional[float] = Field(None, description="Position vega")
    rho: Optional[float] = Field(None, description="Position rho")
    iv: Optional[float] = Field(None, description="Implied volatility")

    @validator("asset", pre=True)
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

    def update_market_data(self, current_price: float, quote: Optional[Any] = None) -> None:
        """Update position with current market data and Greeks."""
        self.current_price = current_price
        self.unrealized_pnl = self.calculate_unrealized_pnl(current_price)

        # Update Greeks if quote provided and this is an options position
        if quote is not None and self.is_option and hasattr(quote, "delta"):
            delta_val = getattr(quote, "delta", None)
            self.delta = delta_val * self.quantity * self.multiplier if delta_val is not None else None
            
            gamma_val = getattr(quote, "gamma", None)
            self.gamma = gamma_val * self.quantity * self.multiplier if gamma_val is not None else None
            
            theta_val = getattr(quote, "theta", None)
            self.theta = theta_val * self.quantity * self.multiplier if theta_val is not None else None
            
            vega_val = getattr(quote, "vega", None)
            self.vega = vega_val * self.quantity * self.multiplier if vega_val is not None else None
            
            rho_val = getattr(quote, "rho", None)
            self.rho = rho_val * self.quantity * self.multiplier if rho_val is not None else None
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

    def simulate_close(self, current_price: Optional[float] = None) -> Dict[str, Union[float, str]]:
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


class OrderLeg(BaseModel):
    """Single leg of a potentially multi-leg order."""
    asset: Union[str, Asset] = Field(..., description="Asset symbol or Asset object")
    quantity: int = Field(..., description="Quantity (positive for buy, negative for sell)")
    order_type: OrderType = Field(..., description="Order type (BTO/STO/BTC/STC for options)")
    price: Optional[float] = Field(None, description="Price per share/contract (None for market orders)")

    @validator("asset", pre=True)
    def normalize_asset(cls, v: Union[str, Asset]) -> Optional[Asset]:
        return asset_factory(v) if isinstance(v, str) else v

    @validator("quantity")
    def set_quantity_sign(cls, v: int, values: Dict[str, object]) -> int:
        order_type = values.get("order_type")
        if order_type in [OrderType.SELL, OrderType.STO, OrderType.STC]:
            return -abs(v)
        else:
            return abs(v)

    @validator("price")
    def set_price_sign(cls, v: Optional[float], values: Dict[str, object]) -> Optional[float]:
        if v is None:
            return v
        order_type = values.get("order_type")
        if order_type in [OrderType.SELL, OrderType.STO, OrderType.STC]:
            return -abs(v)
        else:
            return abs(v)


class Order(BaseModel):
    """Single-leg order (backwards compatible)."""
    id: Optional[str] = None
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: Optional[float] = Field(None, description="Price per share (None for market)")
    condition: OrderCondition = Field(OrderCondition.MARKET, description="Order condition")
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    def to_leg(self) -> OrderLeg:
        return OrderLeg(
            asset=self.symbol,
            quantity=self.quantity,
            order_type=self.order_type,
            price=self.price,
        )


class MultiLegOrder(BaseModel):
    """Multi-leg order for complex strategies."""
    id: Optional[str] = None
    legs: List[OrderLeg] = Field(..., description="Order legs")
    condition: OrderCondition = Field(OrderCondition.MARKET, description="Order condition")
    limit_price: Optional[float] = Field(None, description="Net limit price for the strategy")
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    @validator("legs")
    def validate_no_duplicate_assets(cls, v: List[OrderLeg]) -> List[OrderLeg]:
        symbols = [leg.asset.symbol if hasattr(leg.asset, "symbol") else str(leg.asset) for leg in v]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate assets not allowed in multi-leg orders")
        return v

    def add_leg(self, asset: Union[str, Asset], quantity: int, order_type: OrderType, price: Optional[float] = None) -> "MultiLegOrder":
        new_leg = OrderLeg(asset=asset, quantity=quantity, order_type=order_type, price=price)
        self.legs.append(new_leg)
        return self

    def buy_to_open(self, asset: Union[str, Asset], quantity: int, price: Optional[float] = None) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.BTO, price)

    def sell_to_open(self, asset: Union[str, Asset], quantity: int, price: Optional[float] = None) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.STO, price)

    def buy_to_close(self, asset: Union[str, Asset], quantity: int, price: Optional[float] = None) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.BTC, price)

    def sell_to_close(self, asset: Union[str, Asset], quantity: int, price: Optional[float] = None) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.STC, price)

    @property
    def net_price(self) -> Optional[float]:
        if any(leg.price is None for leg in self.legs):
            return None
        return sum(leg.price * abs(leg.quantity) for leg in self.legs if leg.price is not None)

    @property
    def is_opening_order(self) -> bool:
        return any(leg.order_type in [OrderType.BTO, OrderType.STO] for leg in self.legs)

    @property
    def is_closing_order(self) -> bool:
        return any(leg.order_type in [OrderType.BTC, OrderType.STC] for leg in self.legs)


class OrderCreate(BaseModel):
    """Create a simple order."""
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: Optional[float] = Field(None, description="Price per share (None for market)")
    condition: OrderCondition = Field(OrderCondition.MARKET, description="Order condition")


class OrderLegCreate(BaseModel):
    """Create an order leg for multi-leg orders."""
    asset: str = Field(..., description="Asset symbol")
    quantity: int = Field(..., description="Quantity to trade")
    order_type: OrderType = Field(..., description="Order type (BTO/STO/BTC/STC)")
    price: Optional[float] = Field(None, description="Price per share/contract")


class MultiLegOrderCreate(BaseModel):
    """Create a multi-leg order."""
    legs: List[OrderLegCreate] = Field(..., description="Order legs")
    condition: OrderCondition = Field(OrderCondition.MARKET, description="Order condition")
    limit_price: Optional[float] = Field(None, description="Net limit price")
