from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.orders import Order, OrderCreate, MultiLegOrderCreate
from app.models.trading import StockQuote
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


@router.get("/quote/{symbol}/enhanced")
async def get_enhanced_quote(symbol: str):
    """Get enhanced quote with Greeks for options."""
    try:
        quote = trading_service.get_enhanced_quote(symbol)

        # Convert to dict for JSON response
        result = {
            "symbol": quote.symbol,
            "price": quote.price,
            "bid": getattr(quote, "bid", None),
            "ask": getattr(quote, "ask", None),
            "volume": getattr(quote, "volume", None),
            "quote_date": quote.quote_date.isoformat(),
            "asset_type": "option" if hasattr(quote, "delta") else "stock",
        }

        # Add Greeks if available (for options)
        if hasattr(quote, "delta"):
            result.update(
                {
                    "delta": quote.delta,
                    "gamma": quote.gamma,
                    "theta": quote.theta,
                    "vega": quote.vega,
                    "rho": quote.rho,
                    "iv": getattr(quote, "iv", None),
                    "underlying_price": getattr(quote, "underlying_price", None),
                }
            )

        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/order/multi-leg")
async def create_multi_leg_order_basic(order: MultiLegOrderCreate):
    """Create multi-leg order (basic endpoint)."""
    try:
        return trading_service.create_multi_leg_order(order)
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
