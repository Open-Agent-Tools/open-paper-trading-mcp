from fastapi import APIRouter, HTTPException
from typing import List

from app.models.trading import Order, OrderCreate, StockQuote
from app.services.trading_service import trading_service
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()


@router.get("/quote/{symbol}", response_model=StockQuote, deprecated=True)
async def get_quote(symbol: str):
    try:
        return trading_service.get_quote(symbol)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/order", response_model=Order)
async def create_order(order: OrderCreate):
    try:
        return trading_service.create_order(order)
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders", response_model=List[Order])
async def get_orders():
    return trading_service.get_orders()


@router.get("/order/{order_id}", response_model=Order)
async def get_order(order_id: str):
    try:
        return trading_service.get_order(order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    try:
        return trading_service.cancel_order(order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
