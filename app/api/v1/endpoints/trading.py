from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.dependencies import get_trading_service
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.orders import MultiLegOrderCreate, Order, OrderCreate
from app.schemas.trading import StockQuote
from app.services.trading_service import TradingService

router = APIRouter()


@router.get("/quote/{symbol}", response_model=StockQuote, deprecated=True)
async def get_quote(
    symbol: str,
    request: Request,
):
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_quote(symbol)


@router.post("/order", response_model=Order)
async def create_order(
    order: OrderCreate,
    request: Request,
):
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.create_order(order)


@router.get("/orders", response_model=list[Order])
async def get_orders(request: Request):
    service: TradingService = get_trading_service(request)
    return await service.get_orders()


@router.get("/order/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    request: Request,
):
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_order(order_id)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    request: Request,
):
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.cancel_order(order_id)


@router.get("/quote/{symbol}/enhanced")
async def get_enhanced_quote(
    symbol: str,
    request: Request,
):
    """Get enhanced quote with Greeks for options."""
    service: TradingService = get_trading_service(request)
    try:
        quote = await service.get_enhanced_quote(symbol)

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
async def create_multi_leg_order_basic(
    order: MultiLegOrderCreate,
    request: Request,
):
    """Create multi-leg order (basic endpoint)."""
    service: TradingService = get_trading_service(request)
    try:
        return await service.create_multi_leg_order(order)
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
