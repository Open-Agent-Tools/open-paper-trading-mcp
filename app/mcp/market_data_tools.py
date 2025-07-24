"""
MCP tools for unified market data operations.

These tools now route through TradingService for consistency
with the unified architecture pattern.
"""

from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def get_stock_price(symbol: str) -> dict[str, Any]:
    """
    Get current stock price and basic metrics.

    This function now routes through TradingService for unified data access.
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_price(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_stock_price", e)


async def get_stock_info(symbol: str) -> dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_info(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_stock_info", e)


async def get_price_history(symbol: str, period: str = "week") -> dict[str, Any]:
    """
    Get historical price data for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_price_history(symbol, period)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_price_history", e)


async def get_stock_news(symbol: str) -> dict[str, Any]:
    """
    Get news stories for a stock.

    This function now routes through TradingService for unified data access.
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_news(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_stock_news", e)


async def get_top_movers() -> dict[str, Any]:
    """
    Get top movers in the market.

    This function now routes through TradingService for unified data access.
    """
    try:
        result = await get_trading_service().get_top_movers()
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_top_movers", e)


async def search_stocks(query: str) -> dict[str, Any]:
    """
    Search for stocks by symbol or company name.

    This function now routes through TradingService for unified data access.
    """
    query = query.strip()

    try:
        result = await get_trading_service().search_stocks(query)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("search_stocks", e)


# Legacy alias - kept for backward compatibility
async def search_stocks_tool_legacy(query: str) -> dict[str, Any]:
    """
    Legacy alias for search_stocks_tool.
    """
    return await search_stocks_tool(query)


# =============================================================================
# REQUIRED MCP TOOLS WITH DIRECT PARAMETERS (NO PYDANTIC MODELS)
# =============================================================================


async def stock_price(symbol: str) -> dict[str, Any]:
    """
    Get current stock price and basic metrics.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        dict[str, Any]: Current price data with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_price(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("stock_price", e)


async def stock_info(symbol: str) -> dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        dict[str, Any]: Company information with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_info(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("stock_info", e)


async def search_stocks_tool(query: str) -> dict[str, Any]:
    """
    Search for stocks by symbol or company name.

    Args:
        query: Search query (symbol or company name)

    Returns:
        dict[str, Any]: Search results with standardized response format
    """
    query = query.strip()

    try:
        result = await get_trading_service().search_stocks(query)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("search_stocks_tool", e)


async def market_hours() -> dict[str, Any]:
    """
    Get current market hours and status.

    Returns:
        dict[str, Any]: Market hours information with standardized response format
    """
    try:
        result = await get_trading_service().get_market_hours()
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("market_hours", e)


async def price_history(symbol: str, period: str = "week") -> dict[str, Any]:
    """
    Get historical price data for a stock.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')
        period: Time period (default: 'week')

    Returns:
        dict[str, Any]: Historical price data with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_price_history(symbol, period)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("price_history", e)


async def stock_ratings(symbol: str) -> dict[str, Any]:
    """
    Get analyst ratings for a stock.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        dict[str, Any]: Analyst ratings with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_ratings(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("stock_ratings", e)


async def stock_events(symbol: str) -> dict[str, Any]:
    """
    Get corporate events for a stock (for owned positions).

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        dict[str, Any]: Corporate events with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_events(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("stock_events", e)


async def stock_level2_data(symbol: str) -> dict[str, Any]:
    """
    Get Level II market data for a stock (Gold subscription required).

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        dict[str, Any]: Level II market data with standardized response format
    """
    symbol = symbol.strip().upper()

    try:
        result = await get_trading_service().get_stock_level2_data(symbol)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("stock_level2_data", e)


# =============================================================================
# EXISTING FUNCTIONS (kept for compatibility)
# =============================================================================
