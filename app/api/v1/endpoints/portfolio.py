from fastapi import APIRouter, HTTPException
from typing import List

from app.models.trading import Position, Portfolio, PortfolioSummary
from app.services.trading_service import trading_service
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.get("/", response_model=Portfolio)
async def get_portfolio():
    return trading_service.get_portfolio()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    return trading_service.get_portfolio_summary()


@router.get("/positions", response_model=List[Position])
async def get_positions():
    return trading_service.get_positions()


@router.get("/position/{symbol}", response_model=Position)
async def get_position(symbol: str):
    try:
        return trading_service.get_position(symbol)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
