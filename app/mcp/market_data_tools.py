"""
MCP tools for unified market data operations.

These tools now route through TradingService for consistency
with the unified architecture pattern.
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


class GetStockPriceArgs(BaseModel):
    symbol: str = Field(
        ..., description="Stock symbol to get price for (e.g., AAPL, GOOGL)"
    )


class GetStockInfoArgs(BaseModel):
    symbol: str = Field(
        ..., description="Stock symbol to get information for (e.g., AAPL, GOOGL)"
    )


class GetPriceHistoryArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    period: str = Field(
        "week", description="Time period: day, week, month, 3month, year, 5year"
    )


class GetStockNewsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")


class SearchStocksArgs(BaseModel):
    query: str = Field(..., description="Search query (symbol or company name)")


async def get_stock_price(args: GetStockPriceArgs) -> dict[str, Any]:
    """
    Get current stock price and basic metrics.

    This function now routes through TradingService for unified data access.
    """
    symbol = args.symbol.strip().upper()

    try:
        result = await get_mcp_trading_service().get_stock_price(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_stock_info(args: GetStockInfoArgs) -> dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = args.symbol.strip().upper()

    try:
        result = await get_mcp_trading_service().get_stock_info(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_price_history(args: GetPriceHistoryArgs) -> dict[str, Any]:
    """
    Get historical price data for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = args.symbol.strip().upper()

    try:
        result = await get_mcp_trading_service().get_price_history(symbol, args.period)
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_stock_news(args: GetStockNewsArgs) -> dict[str, Any]:
    """
    Get news stories for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = args.symbol.strip().upper()

    try:
        result = await get_mcp_trading_service().get_stock_news(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_top_movers() -> dict[str, Any]:
    """
    Get top movers in the market.

    This function now routes through TradingService for unified data access.
    """
    try:
        result = await get_mcp_trading_service().get_top_movers()
        return result
    except Exception as e:
        return {"error": str(e)}


async def search_stocks(args: SearchStocksArgs) -> dict[str, Any]:
    """
    Search for stocks by symbol or company name.

    This function now routes through TradingService for unified data access.
    """
    query = args.query.strip()

    try:
        result = await get_mcp_trading_service().search_stocks(query)
        return result
    except Exception as e:
        return {"error": str(e)}
