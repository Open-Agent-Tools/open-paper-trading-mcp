"""
MCP tools for live options data operations.
"""
import asyncio
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import robin_stocks.robinhood as rh
from app.auth.session_manager import get_session_manager
from app.core.logging import logger

mcp = FastMCP("Options Data Tools")

class GetOptionsChainsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get option chains for (e.g., AAPL, GOOGL)")

class FindTradableOptionsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    expiration_date: Optional[str] = Field(None, description="Expiration date in YYYY-MM-DD format")
    option_type: Optional[str] = Field(None, description="Option type: 'call' or 'put'")

class GetOptionMarketDataArgs(BaseModel):
    option_id: str = Field(..., description="Unique option contract ID")

@mcp.tool()
async def get_options_chains(args: GetOptionsChainsArgs) -> Dict[str, Any]:
    """
    Get complete option chains for a stock symbol.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Getting option chains for {symbol}")

    try:
        loop = asyncio.get_event_loop()
        chains_data = await loop.run_in_executor(None, rh.options.get_chains, symbol)

        if not chains_data:
            return {
                "symbol": symbol,
                "chains": [],
                "total_contracts": 0,
                "message": "No option chains found",
            }
        
        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "chains": chains_data,
            "total_contracts": len(chains_data),
        }
    except Exception as e:
        logger.error(f"Error getting option chains for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def find_tradable_options(args: FindTradableOptionsArgs) -> Dict[str, Any]:
    """
    Find tradable options for a symbol with optional filtering.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Finding tradable options for {symbol} with filters: expiration={args.expiration_date}, type={args.option_type}")

    try:
        loop = asyncio.get_event_loop()
        options_data = await loop.run_in_executor(
            None,
            rh.options.find_tradable_options,
            symbol,
            args.expiration_date,
            args.option_type,
        )

        if not options_data:
            return {
                "symbol": symbol,
                "filters": {
                    "expiration_date": args.expiration_date,
                    "option_type": args.option_type,
                },
                "options": [],
                "total_found": 0,
                "message": "No tradable options found",
            }

        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "filters": {
                "expiration_date": args.expiration_date,
                "option_type": args.option_type,
            },
            "options": options_data,
            "total_found": len(options_data),
        }
    except Exception as e:
        logger.error(f"Error finding tradable options for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_option_market_data(args: GetOptionMarketDataArgs) -> Dict[str, Any]:
    """
    Get market data for a specific option contract by ID.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    logger.info(f"Getting market data for option ID: {args.option_id}")

    try:
        loop = asyncio.get_event_loop()
        market_data = await loop.run_in_executor(
            None,
            rh.options.get_option_market_data_by_id,
            args.option_id,
        )

        if not market_data:
            return {
                "option_id": args.option_id,
                "error": "No market data found for this option",
            }

        session_manager.update_last_successful_call()

        return {
            "option_id": args.option_id,
            "market_data": market_data,
        }
    except Exception as e:
        logger.error(f"Error getting market data for option ID {args.option_id}: {e}")
        return {"error": str(e)}