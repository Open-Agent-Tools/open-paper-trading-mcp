from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_trading_service
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService

router = APIRouter()


@router.get("/", response_model=Portfolio)
async def get_portfolio(request: Request):
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(request: Request):
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio_summary()


@router.get("/positions", response_model=list[Position])
async def get_positions(request: Request):
    service: TradingService = get_trading_service(request)
    return await service.get_positions()


@router.get("/position/{symbol}", response_model=Position)
async def get_position(
    symbol: str,
    request: Request,
):
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_position(symbol)


@router.get("/position/{symbol}/greeks")
async def get_position_greeks(
    symbol: str,
    request: Request,
):
    """Get Greeks for a specific position."""
    # Custom exceptions are handled by the global exception handler
    # TradingService should raise ValidationError for ValueError cases
    service: TradingService = get_trading_service(request)
    return await service.get_position_greeks(symbol)


@router.get("/greeks")
async def get_portfolio_greeks(request: Request):
    """Get aggregated Greeks for entire portfolio."""
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio_greeks()


@router.get("/strategies")
async def get_portfolio_strategies(request: Request):
    """Get strategy analysis for portfolio."""
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio_strategies()
