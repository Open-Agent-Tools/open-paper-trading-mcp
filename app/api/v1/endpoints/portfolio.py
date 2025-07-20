from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions import NotFoundError
from app.models.trading import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService, trading_service

router = APIRouter()


def get_trading_service() -> TradingService:
    """Dependency to get trading service instance."""
    return trading_service


@router.get("/", response_model=Portfolio)
async def get_portfolio(service: TradingService = Depends(get_trading_service)):
    return await service.get_portfolio()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(service: TradingService = Depends(get_trading_service)):
    return await service.get_portfolio_summary()


@router.get("/positions", response_model=list[Position])
async def get_positions(service: TradingService = Depends(get_trading_service)):
    return await service.get_positions()


@router.get("/position/{symbol}", response_model=Position)
async def get_position(
    symbol: str, service: TradingService = Depends(get_trading_service)
):
    try:
        return await service.get_position(symbol)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/position/{symbol}/greeks")
async def get_position_greeks(
    symbol: str, service: TradingService = Depends(get_trading_service)
):
    """Get Greeks for a specific position."""
    try:
        return await service.get_position_greeks(symbol)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/greeks")
async def get_portfolio_greeks(service: TradingService = Depends(get_trading_service)):
    """Get aggregated Greeks for entire portfolio."""
    try:
        return await service.get_portfolio_greeks()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating portfolio Greeks: {e!s}"
        )


@router.get("/strategies")
async def get_portfolio_strategies(
    service: TradingService = Depends(get_trading_service),
):
    """Get strategy analysis for portfolio."""
    try:
        return await service.get_portfolio_strategies()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing strategies: {e!s}"
        )
