"""
Pydantic schemas for Order data.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, Dict
from datetime import datetime
from enum import Enum

from app.models.assets import Asset, asset_factory


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    BTO = "buy_to_open"
    STO = "sell_to_open"
    BTC = "buy_to_close"
    STC = "sell_to_close"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


class OrderCondition(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


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
