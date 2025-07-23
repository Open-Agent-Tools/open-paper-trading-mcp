"""
MCP tools for options data operations.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.services.trading_service import TradingService

# MCP tools will receive TradingService instance as dependency
_trading_service: TradingService | None = None


def set_mcp_trading_service(service: TradingService) -> None:
    """Set the trading service for MCP tools."""
    global _trading_service
    _trading_service = service


def get_mcp_trading_service() -> TradingService:
    """Get the trading service for MCP tools."""
    if _trading_service is None:
        raise RuntimeError("TradingService not initialized for MCP tools")
    return _trading_service


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
        chain_data = await get_mcp_trading_service().get_formatted_options_chain(
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
        result = await get_mcp_trading_service().find_tradable_options(
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
        result = await get_mcp_trading_service().get_option_market_data(args.option_id)
        return result
    except Exception as e:
        return {"error": str(e)}
