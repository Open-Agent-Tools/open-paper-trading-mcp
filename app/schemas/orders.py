"""
Order-related API schemas.

This module contains all Pydantic models for order management:
- Order types and statuses (enums)
- Single and multi-leg order schemas
- Order creation and validation schemas
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.models.assets import Asset, asset_factory
from app.schemas.validation import OrderValidationMixin, validate_symbol


class OrderType(str, Enum):
    """Order types for trading operations."""

    BUY = "buy"
    SELL = "sell"
    BTO = "buy_to_open"
    STO = "sell_to_open"
    BTC = "buy_to_close"
    STC = "sell_to_close"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """Order status values."""

    PENDING = "pending"
    TRIGGERED = "triggered"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    EXPIRED = "expired"


class OrderCondition(str, Enum):
    """Order execution conditions."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderTimeInForce(str, Enum):
    """Order time in force values."""

    DAY = "day"  # Day order
    GTC = "gtc"  # Good 'til cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class OrderSide(str, Enum):
    """Order side for multi-leg orders."""

    BUY = "buy"
    SELL = "sell"


class OrderLeg(BaseModel):
    """Single leg of a potentially multi-leg order."""

    asset: Asset = Field(..., description="Asset symbol or Asset object")
    quantity: int = Field(
        ..., description="Quantity (positive for buy, negative for sell)"
    )
    order_type: OrderType = Field(
        ..., description="Order type (BTO/STO/BTC/STC for options)"
    )
    price: float | None = Field(
        None, description="Price per share/contract (None for market orders)"
    )

    @field_validator("asset", mode="before")
    @classmethod
    def normalize_asset(cls, v: str | Asset) -> Asset:
        result = asset_factory(v) if isinstance(v, str) else v
        if result is None:
            raise ValueError(f"Invalid asset: {v}")
        return result

    @field_validator("quantity")
    @classmethod
    def set_quantity_sign(cls, v: int, info: ValidationInfo) -> int:
        order_type = info.data.get("order_type")
        if order_type in [OrderType.SELL, OrderType.STO, OrderType.STC]:
            return -abs(v)
        else:
            return abs(v)

    @field_validator("price")
    @classmethod
    def set_price_sign(cls, v: float | None, info: ValidationInfo) -> float | None:
        if v is None:
            return v
        order_type = info.data.get("order_type")
        if order_type in [OrderType.SELL, OrderType.STO, OrderType.STC]:
            return -abs(v)
        else:
            return abs(v)


class Order(BaseModel, OrderValidationMixin):
    """Single-leg order (backwards compatible)."""

    id: str | None = None
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")

    @field_validator("symbol")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate and normalize symbol format."""
        return validate_symbol(v)

    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float | None = Field(None, description="Price per share (None for market)")
    condition: OrderCondition = Field(
        OrderCondition.MARKET, description="Order condition"
    )
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime | None = None
    filled_at: datetime | None = None

    # Advanced order trigger fields
    stop_price: float | None = Field(None, description="Stop price for stop orders")
    trail_percent: float | None = Field(
        None, description="Trail percentage for trailing stops"
    )
    trail_amount: float | None = Field(
        None, description="Trail amount for trailing stops"
    )

    # Additional attributes for compatibility
    legs: list[OrderLeg] = Field(
        default_factory=list, description="Order legs (empty for single-leg orders)"
    )
    net_price: float | None = Field(None, description="Net price for the order")

    def to_leg(self) -> OrderLeg:
        return OrderLeg(
            asset=self.symbol,  # type: ignore[arg-type]  # Validator will convert str to Asset
            quantity=self.quantity,
            order_type=self.order_type,
            price=self.price,
        )

    @field_validator("stop_price")
    @classmethod
    def validate_stop_price_requirement(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        """Validate stop price is provided for stop orders."""
        order_type = info.data.get("order_type")
        if order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT] and v is None:
            raise ValueError(f"Stop price is required for {order_type} orders")
        return v

    @field_validator("trail_percent")
    @classmethod
    def validate_trail_requirements(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        """Validate trail requirements for trailing stop orders."""
        order_type = info.data.get("order_type")
        trail_amount = info.data.get("trail_amount")

        if order_type == OrderType.TRAILING_STOP:
            if v is None and trail_amount is None:
                raise ValueError(
                    "Trailing stop orders require either trail_percent or trail_amount"
                )
            if v is not None and trail_amount is not None:
                raise ValueError(
                    "Trailing stop orders cannot have both trail_percent and trail_amount"
                )
        return v


class MultiLegOrder(BaseModel):
    """Multi-leg order for complex strategies."""

    id: str | None = None
    legs: list[OrderLeg] = Field(..., description="Order legs")
    condition: OrderCondition = Field(
        OrderCondition.MARKET, description="Order condition"
    )
    limit_price: float | None = Field(
        None, description="Net limit price for the strategy"
    )
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime | None = None
    filled_at: datetime | None = None

    @field_validator("legs")
    @classmethod
    def validate_no_duplicate_assets(cls, v: list[OrderLeg]) -> list[OrderLeg]:
        symbols = [
            leg.asset.symbol if hasattr(leg.asset, "symbol") else str(leg.asset)
            for leg in v
        ]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate assets not allowed in multi-leg orders")
        return v

    def add_leg(
        self,
        asset: str | Asset,
        quantity: int,
        order_type: OrderType,
        price: float | None = None,
    ) -> "MultiLegOrder":
        # Convert string to Asset if needed
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        if asset_obj is None:
            raise ValueError(f"Invalid asset: {asset}")
        new_leg = OrderLeg(
            asset=asset_obj, quantity=quantity, order_type=order_type, price=price
        )
        self.legs.append(new_leg)
        return self

    def buy_to_open(
        self, asset: str | Asset, quantity: int, price: float | None = None
    ) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.BTO, price)

    def sell_to_open(
        self, asset: str | Asset, quantity: int, price: float | None = None
    ) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.STO, price)

    def buy_to_close(
        self, asset: str | Asset, quantity: int, price: float | None = None
    ) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.BTC, price)

    def sell_to_close(
        self, asset: str | Asset, quantity: int, price: float | None = None
    ) -> "MultiLegOrder":
        return self.add_leg(asset, quantity, OrderType.STC, price)

    @property
    def net_price(self) -> float | None:
        if any(leg.price is None for leg in self.legs):
            return None
        return sum(
            leg.price * abs(leg.quantity) for leg in self.legs if leg.price is not None
        )

    @property
    def is_opening_order(self) -> bool:
        return any(
            leg.order_type in [OrderType.BTO, OrderType.STO] for leg in self.legs
        )

    @property
    def is_closing_order(self) -> bool:
        return any(
            leg.order_type in [OrderType.BTC, OrderType.STC] for leg in self.legs
        )


class OrderCreate(BaseModel):
    """Create a simple order."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float | None = Field(None, description="Price per share (None for market)")
    condition: OrderCondition = Field(
        OrderCondition.MARKET, description="Order condition"
    )

    # Advanced order trigger fields
    stop_price: float | None = Field(None, description="Stop price for stop orders")
    trail_percent: float | None = Field(
        None, description="Trail percentage for trailing stops"
    )
    trail_amount: float | None = Field(
        None, description="Trail amount for trailing stops"
    )

    @field_validator("stop_price")
    @classmethod
    def validate_stop_price_requirement(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        """Validate stop price is provided for stop orders."""
        order_type = info.data.get("order_type")
        if order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT] and v is None:
            raise ValueError(f"Stop price is required for {order_type} orders")
        return v

    @field_validator("trail_percent")
    @classmethod
    def validate_trail_requirements(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        """Validate trail requirements for trailing stop orders."""
        order_type = info.data.get("order_type")
        trail_amount = info.data.get("trail_amount")

        if order_type == OrderType.TRAILING_STOP:
            if v is None and trail_amount is None:
                raise ValueError(
                    "Trailing stop orders require either trail_percent or trail_amount"
                )
            if v is not None and trail_amount is not None:
                raise ValueError(
                    "Trailing stop orders cannot have both trail_percent and trail_amount"
                )
        return v


class OrderLegCreate(BaseModel):
    """Create an order leg for multi-leg orders."""

    asset: str = Field(..., description="Asset symbol")
    quantity: int = Field(..., description="Quantity to trade")
    order_type: OrderType = Field(..., description="Order type (BTO/STO/BTC/STC)")
    price: float | None = Field(None, description="Price per share/contract")


class MultiLegOrderCreate(BaseModel):
    """Create a multi-leg order."""

    legs: list[OrderLegCreate] = Field(..., description="Order legs")
    condition: OrderCondition = Field(
        OrderCondition.MARKET, description="Order condition"
    )
    limit_price: float | None = Field(None, description="Net limit price")
