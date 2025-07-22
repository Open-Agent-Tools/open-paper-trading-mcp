"""
MCP tools for options data operations.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.services.trading_service import TradingService

trading_service = TradingService()


class GetOptionsChainsArgs(BaseModel):
    symbol: str = Field(
        ..., description="Stock symbol to get option chains for (e.g., AAPL, GOOGL)"
    )


class FindTradableOptionsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    expiration_date: str | None = Field(
        None, description="Expiration date in YYYY-MM-DD format"
    )
    option_type: str | None = Field(None, description="Option type: 'call' or 'put'")


class GetOptionMarketDataArgs(BaseModel):
    option_id: str = Field(..., description="Unique option contract ID")


async def get_options_chains(args: GetOptionsChainsArgs) -> dict[str, Any]:
    """
    Get complete option chains for a stock symbol.
    """
    try:
        # Use TradingService to get options chain
        chain_data = await trading_service.get_formatted_options_chain(
            args.symbol.strip().upper()
        )
        return chain_data
    except Exception as e:
        return {"error": str(e)}


async def find_tradable_options(args: FindTradableOptionsArgs) -> dict[str, Any]:
    """
    Find tradable options for a symbol with optional filtering.
    """
    try:
        result = await trading_service.find_tradable_options(
            args.symbol.strip().upper(), args.expiration_date, args.option_type
        )
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_option_market_data(args: GetOptionMarketDataArgs) -> dict[str, Any]:
    """
    Get market data for a specific option contract.
    """
    try:
        result = await trading_service.get_option_market_data(args.option_id)
        return result
    except Exception as e:
        return {"error": str(e)}
