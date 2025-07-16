"""
MCP tools for live market data operations.
"""
import asyncio
from typing import Any, Dict, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import robin_stocks.robinhood as rh
from app.auth.session_manager import get_session_manager
from app.core.logging import logger

mcp = FastMCP("Market Data Tools")

class GetStockPriceArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get price for (e.g., AAPL, GOOGL)")

class GetStockInfoArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get information for (e.g., AAPL, GOOGL)")

class GetPriceHistoryArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    period: str = Field("week", description="Time period: day, week, month, 3month, year, 5year")

class GetStockNewsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")

class SearchStocksArgs(BaseModel):
    query: str = Field(..., description="Search query (symbol or company name)")

@mcp.tool()
async def get_stock_price(args: GetStockPriceArgs) -> Dict[str, Any]:
    """
    Get current stock price and basic metrics.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Getting stock price for {symbol}")

    try:
        loop = asyncio.get_event_loop()
        
        price_data = await loop.run_in_executor(None, rh.get_latest_price, symbol, "ask_price")
        quote_data_list = await loop.run_in_executor(None, rh.get_quotes, symbol)

        if not price_data or not price_data[0] or not quote_data_list:
            return {"error": f"No price data found for symbol: {symbol}"}

        quote_data = quote_data_list[0]
        current_price = float(price_data[0])
        previous_close = float(quote_data.get("previous_close", 0))
        change = current_price - previous_close
        change_percent = (change / previous_close * 100) if previous_close else 0.0

        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "price": current_price,
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "previous_close": previous_close,
            "volume": int(quote_data.get("volume", 0)),
            "ask_price": float(quote_data.get("ask_price", 0)),
            "bid_price": float(quote_data.get("bid_price", 0)),
            "last_trade_price": float(quote_data.get("last_trade_price", 0)),
        }
    except Exception as e:
        logger.error(f"Error getting stock price for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_stock_info(args: GetStockInfoArgs) -> Dict[str, Any]:
    """
    Get detailed company information and fundamentals for a stock.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Getting stock info for {symbol}")

    try:
        loop = asyncio.get_event_loop()

        fundamentals_list = await loop.run_in_executor(None, rh.get_fundamentals, symbol)
        instruments_list = await loop.run_in_executor(None, rh.get_instruments_by_symbols, symbol)

        if not fundamentals_list or not instruments_list:
            return {"error": f"No company information found for symbol: {symbol}"}

        fundamental = fundamentals_list[0]
        instrument = instruments_list[0]
        
        company_name = await loop.run_in_executor(None, rh.get_name_by_symbol, symbol)

        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "company_name": company_name or instrument.get("simple_name", "N/A"),
            "sector": fundamental.get("sector", "N/A"),
            "industry": fundamental.get("industry", "N/A"),
            "description": fundamental.get("description", "N/A"),
            "market_cap": fundamental.get("market_cap", "N/A"),
            "pe_ratio": fundamental.get("pe_ratio", "N/A"),
            "dividend_yield": fundamental.get("dividend_yield", "N/A"),
            "high_52_weeks": fundamental.get("high_52_weeks", "N/A"),
            "low_52_weeks": fundamental.get("low_52_weeks", "N/A"),
            "average_volume": fundamental.get("average_volume", "N/A"),
            "tradeable": instrument.get("tradeable", False),
        }
    except Exception as e:
        logger.error(f"Error getting stock info for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_price_history(args: GetPriceHistoryArgs) -> Dict[str, Any]:
    """
    Get historical price data for a stock.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Getting price history for {symbol} over {args.period}")

    try:
        loop = asyncio.get_event_loop()

        interval_map = {
            "day": "5minute",
            "week": "hour",
            "month": "day",
            "3month": "day",
            "year": "week",
            "5year": "week",
        }
        interval = interval_map.get(args.period, "day")

        historical_data = await loop.run_in_executor(
            None, rh.get_stock_historicals, symbol, interval, args.period, "regular"
        )

        if not historical_data:
            return {"error": f"No historical data found for {symbol} over {args.period}"}

        price_points = [
            {
                "date": data_point.get("begins_at", "N/A"),
                "open": float(data_point.get("open_price", 0)),
                "high": float(data_point.get("high_price", 0)),
                "low": float(data_point.get("low_price", 0)),
                "close": float(data_point.get("close_price", 0)),
                "volume": int(data_point.get("volume", 0)),
            }
            for data_point in historical_data
            if data_point and data_point.get("close_price")
        ]

        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "period": args.period,
            "interval": interval,
            "data_points": price_points,
        }
    except Exception as e:
        logger.error(f"Error getting price history for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_stock_news(args: GetStockNewsArgs) -> Dict[str, Any]:
    """
    Get news stories for a stock.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    symbol = args.symbol.strip().upper()
    logger.info(f"Getting news for {symbol}")

    try:
        loop = asyncio.get_event_loop()
        news_data = await loop.run_in_executor(None, rh.get_news, symbol)

        if not news_data:
            return {"error": f"No news data found for symbol: {symbol}"}

        session_manager.update_last_successful_call()

        return {
            "symbol": symbol,
            "news": news_data,
        }
    except Exception as e:
        logger.error(f"Error getting news for {symbol}: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_top_movers() -> Dict[str, Any]:
    """
    Get top 20 movers on Robinhood.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    logger.info("Getting top movers")

    try:
        loop = asyncio.get_event_loop()
        movers_data = await loop.run_in_executor(None, rh.get_top_movers)

        if not movers_data:
            return {"error": "No top movers data found"}

        session_manager.update_last_successful_call()

        return {"movers": movers_data}
    except Exception as e:
        logger.error(f"Error getting top movers: {e}")
        return {"error": str(e)}

@mcp.tool()
async def search_stocks(args: SearchStocksArgs) -> Dict[str, Any]:
    """
    Search for stocks by symbol or company name.
    """
    session_manager = get_session_manager()
    if not await session_manager.ensure_authenticated():
        return {"error": "Authentication failed"}

    query = args.query.strip()
    logger.info(f"Searching for stocks with query: {query}")

    try:
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(None, rh.find_instrument_data, query)

        if not search_results:
            return {
                "query": query,
                "results": [],
                "message": f"No stocks found matching query: {query}",
            }

        results = [
            {
                "symbol": item.get("symbol", "").upper(),
                "name": item.get("simple_name", "N/A"),
                "tradeable": item.get("tradeable", False),
            }
            for item in search_results
            if item.get("symbol")
        ]

        session_manager.update_last_successful_call()

        return {
            "query": query,
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error searching for stocks with query {query}: {e}")
        return {"error": str(e)}
