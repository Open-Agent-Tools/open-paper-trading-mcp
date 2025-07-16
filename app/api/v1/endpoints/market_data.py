"""
REST API endpoints for unified market data operations.

These endpoints now route through TradingService for consistency
with the unified architecture pattern.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any
from app.services.trading_service import trading_service, TradingService

router = APIRouter()


def get_trading_service() -> TradingService:
    """Dependency to get trading service instance."""
    return trading_service


@router.get("/price/{symbol}", response_model=Dict[str, Any])
async def get_stock_price_endpoint(
    symbol: str, service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Get current stock price and basic metrics.
    
    This endpoint provides unified access to stock pricing data
    that works with both test data and live market data.
    """
    try:
        result = service.get_stock_price(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stock price: {str(e)}")


@router.get("/info/{symbol}", response_model=Dict[str, Any]) 
async def get_stock_info_endpoint(
    symbol: str, service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.
    
    This endpoint provides unified access to company data
    that works with both test data and live market data.
    """
    try:
        result = service.get_stock_info(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stock info: {str(e)}")


@router.get("/history/{symbol}", response_model=Dict[str, Any])
async def get_price_history_endpoint(
    symbol: str,
    period: str = Query("week", description="Time period: day, week, month, 3month, year, 5year"),
    service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Get historical price data for a stock.
    
    This endpoint provides unified access to historical data
    that works with both test data and live market data.
    """
    try:
        result = service.get_price_history(symbol, period)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting price history: {str(e)}")


@router.get("/news/{symbol}", response_model=Dict[str, Any])
async def get_stock_news_endpoint(
    symbol: str, service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Get news stories for a stock.
    
    This endpoint provides unified access to news data
    that works with both test data and live market data.
    """
    try:
        result = service.get_stock_news(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stock news: {str(e)}")


@router.get("/movers", response_model=Dict[str, Any])
async def get_top_movers_endpoint(
    service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Get top movers in the market.
    
    This endpoint provides unified access to market movers data
    that works with both test data and live market data.
    """
    try:
        result = service.get_top_movers()
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting top movers: {str(e)}")


@router.get("/search", response_model=Dict[str, Any])
async def search_stocks_endpoint(
    query: str = Query(..., description="Search query (symbol or company name)"),
    service: TradingService = Depends(get_trading_service)
) -> Dict[str, Any]:
    """
    Search for stocks by symbol or company name.
    
    This endpoint provides unified access to stock search
    that works with both test data and live market data.
    """
    try:
        result = service.search_stocks(query)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching stocks: {str(e)}")
