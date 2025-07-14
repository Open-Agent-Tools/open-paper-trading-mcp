from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


class Order(BaseModel):
    id: Optional[str] = None
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float = Field(..., gt=0, description="Price per share")
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None


class OrderCreate(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float = Field(..., gt=0, description="Price per share")


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
    symbol: str = Field(..., description="Stock symbol")
    quantity: int = Field(..., description="Number of shares owned")
    avg_price: float = Field(..., description="Average purchase price")
    current_price: float = Field(..., description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized profit/loss")
    realized_pnl: float = Field(default=0.0, description="Realized profit/loss")


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
