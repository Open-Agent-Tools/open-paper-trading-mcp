from typing import Any

from fastapi import APIRouter, Request

from app.core.dependencies import get_trading_service
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService

router = APIRouter()


@router.get("/", response_model=Portfolio)
async def get_portfolio(request: Request) -> Portfolio:
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(request: Request) -> PortfolioSummary:
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio_summary()


@router.get("/positions", response_model=list[Position])
async def get_positions(request: Request) -> list[Position]:
    service: TradingService = get_trading_service(request)
    return await service.get_positions()


@router.get("/position/{symbol}", response_model=Position)
async def get_position(
    symbol: str,
    request: Request,
) -> Position:
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_position(symbol)


@router.get("/position/{symbol}/greeks")
async def get_position_greeks(
    symbol: str,
    request: Request,
) -> dict[str, Any]:
    """Get Greeks for a specific position."""
    # Custom exceptions are handled by the global exception handler
    # TradingService should raise ValidationError for ValueError cases
    service: TradingService = get_trading_service(request)
    return await service.get_position_greeks(symbol)


@router.get("/greeks")
async def get_portfolio_greeks(request: Request) -> dict[str, Any]:
    """Get aggregated Greeks for entire portfolio."""
    # Custom exceptions are handled by the global exception handler
    service: TradingService = get_trading_service(request)
    return await service.get_portfolio_greeks()
