"""
General trading API schemas.

This module contains Pydantic models for general trading functionality:
- Stock quotes and market data
- Asset-related schemas that aren't orders or positions
"""

from datetime import datetime

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    price: float = Field(..., description="Current stock price")
    change: float = Field(..., description="Price change from previous close")
    change_percent: float = Field(
        ..., description="Percentage change from previous close"
    )
    volume: int = Field(..., description="Trading volume")
    last_updated: datetime = Field(..., description="Last update timestamp")
