"""
REST API endpoints for unified market data operations.

These endpoints now route through TradingService for consistency
with the unified architecture pattern.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.dependencies import get_trading_service
from app.services.trading_service import TradingService

router = APIRouter()


@router.get("/price/{symbol}", response_model=dict[str, Any])
async def get_stock_price_endpoint(
    symbol: str,
    request: Request,
) -> dict[str, Any]:
    """
    Get current stock price and basic metrics.

    This endpoint provides unified access to stock pricing data
    that works with both test data and live market data.
    """
    service: TradingService = get_trading_service(request)
    try:
        result = await service.get_stock_price(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting stock price: {e!s}"
        ) from e


@router.get("/info/{symbol}", response_model=dict[str, Any])
async def get_stock_info_endpoint(
    symbol: str,
    request: Request,
) -> dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.

    This endpoint provides unified access to company data
    that works with both test data and live market data.
    """
    service: TradingService = get_trading_service(request)
    try:
        result = await service.get_stock_info(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting stock info: {e!s}"
        ) from e


@router.get("/history/{symbol}", response_model=dict[str, Any])
async def get_price_history_endpoint(
    symbol: str,
    request: Request,
    period: str = Query(
        "week", description="Time period: day, week, month, 3month, year, 5year"
    ),
) -> dict[str, Any]:
    """
    Get historical price data for a stock.

    This endpoint provides unified access to historical data
    that works with both test data and live market data.
    """
    service: TradingService = get_trading_service(request)
    try:
        result = await service.get_price_history(symbol, period)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting price history: {e!s}"
        ) from e


@router.get("/search", response_model=dict[str, Any])
async def search_stocks_endpoint(
    request: Request,
    query: str = Query(..., description="Search query (symbol or company name)"),
) -> dict[str, Any]:
    """
    Search for stocks by symbol or company name.

    This endpoint provides unified access to stock search
    that works with both test data and live market data.
    """
    service: TradingService = get_trading_service(request)
    try:
        result = await service.search_stocks(query)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching stocks: {e!s}"
        ) from e
