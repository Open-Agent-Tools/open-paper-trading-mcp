from fastapi import APIRouter, Depends

from app.core.dependencies import get_trading_service
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService

router = APIRouter()


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
    # Custom exceptions are handled by the global exception handler
    return await service.get_position(symbol)


@router.get("/position/{symbol}/greeks")
async def get_position_greeks(
    symbol: str, service: TradingService = Depends(get_trading_service)
):
    """Get Greeks for a specific position."""
    # Custom exceptions are handled by the global exception handler
    # TradingService should raise ValidationError for ValueError cases
    return await service.get_position_greeks(symbol)


@router.get("/greeks")
async def get_portfolio_greeks(service: TradingService = Depends(get_trading_service)):
    """Get aggregated Greeks for entire portfolio."""
    # Custom exceptions are handled by the global exception handler
    return await service.get_portfolio_greeks()


@router.get("/strategies")
async def get_portfolio_strategies(
    service: TradingService = Depends(get_trading_service),
):
    """Get strategy analysis for portfolio."""
    # Custom exceptions are handled by the global exception handler
    return await service.get_portfolio_strategies()
