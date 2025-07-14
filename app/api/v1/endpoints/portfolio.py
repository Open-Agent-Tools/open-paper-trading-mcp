from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime

router = APIRouter()


class Position(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0


class Portfolio(BaseModel):
    cash_balance: float
    total_value: float
    positions: List[Position]
    daily_pnl: float
    total_pnl: float


class PortfolioSummary(BaseModel):
    total_value: float
    cash_balance: float
    invested_value: float
    daily_pnl: float
    daily_pnl_percent: float
    total_pnl: float
    total_pnl_percent: float


# Mock portfolio data
mock_portfolio = {
    "cash_balance": 10000.0,
    "positions": [
        Position(
            symbol="AAPL",
            quantity=10,
            avg_price=145.00,
            current_price=150.00,
            unrealized_pnl=50.0
        ),
        Position(
            symbol="GOOGL",
            quantity=2,
            avg_price=2850.00,
            current_price=2800.00,
            unrealized_pnl=-100.0
        ),
    ]
}


@router.get("/", response_model=Portfolio)
async def get_portfolio():
    positions = mock_portfolio["positions"]
    total_invested = sum(pos.quantity * pos.current_price for pos in positions)
    total_value = mock_portfolio["cash_balance"] + total_invested
    total_pnl = sum(pos.unrealized_pnl for pos in positions)
    
    return Portfolio(
        cash_balance=mock_portfolio["cash_balance"],
        total_value=total_value,
        positions=positions,
        daily_pnl=total_pnl,
        total_pnl=total_pnl
    )


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    positions = mock_portfolio["positions"]
    invested_value = sum(pos.quantity * pos.current_price for pos in positions)
    total_value = mock_portfolio["cash_balance"] + invested_value
    total_pnl = sum(pos.unrealized_pnl for pos in positions)
    
    return PortfolioSummary(
        total_value=total_value,
        cash_balance=mock_portfolio["cash_balance"],
        invested_value=invested_value,
        daily_pnl=total_pnl,
        daily_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
        total_pnl=total_pnl,
        total_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0
    )


@router.get("/positions", response_model=List[Position])
async def get_positions():
    return mock_portfolio["positions"]


@router.get("/position/{symbol}", response_model=Position)
async def get_position(symbol: str):
    for position in mock_portfolio["positions"]:
        if position.symbol.upper() == symbol.upper():
            return position
    raise HTTPException(status_code=404, detail="Position not found")