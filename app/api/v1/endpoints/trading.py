from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

router = APIRouter()


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


class Order(BaseModel):
    id: Optional[str] = None
    symbol: str
    order_type: OrderType
    quantity: int
    price: float
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None


class OrderCreate(BaseModel):
    symbol: str
    order_type: OrderType
    quantity: int
    price: float


class StockQuote(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    last_updated: datetime


# Mock data storage
orders_db = []
mock_quotes = {
    "AAPL": StockQuote(
        symbol="AAPL",
        price=150.00,
        change=2.50,
        change_percent=1.69,
        volume=1000000,
        last_updated=datetime.now()
    ),
    "GOOGL": StockQuote(
        symbol="GOOGL",
        price=2800.00,
        change=-15.00,
        change_percent=-0.53,
        volume=500000,
        last_updated=datetime.now()
    ),
}


@router.get("/quote/{symbol}", response_model=StockQuote)
async def get_quote(symbol: str):
    if symbol.upper() not in mock_quotes:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return mock_quotes[symbol.upper()]


@router.post("/order", response_model=Order)
async def create_order(order: OrderCreate):
    new_order = Order(
        id=f"order_{len(orders_db) + 1}",
        symbol=order.symbol.upper(),
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        created_at=datetime.now()
    )
    orders_db.append(new_order)
    return new_order


@router.get("/orders", response_model=List[Order])
async def get_orders():
    return orders_db


@router.get("/order/{order_id}", response_model=Order)
async def get_order(order_id: str):
    for order in orders_db:
        if order.id == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")


@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    for order in orders_db:
        if order.id == order_id:
            order.status = OrderStatus.CANCELLED
            return {"message": "Order cancelled successfully"}
    raise HTTPException(status_code=404, detail="Order not found")