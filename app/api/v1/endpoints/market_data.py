"""
API endpoints for market data.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
# TODO: get_stock_info not implemented yet
# from app.mcp.market_data_tools import get_stock_info, GetStockInfoArgs
# TODO: get_stock_price not implemented yet
# from app.mcp.market_data_tools import get_stock_price, GetStockPriceArgs
# TODO: MCP tools are not exported as regular functions, only via @mcp.tool() decorator
# from app.mcp.market_data_tools import search_stocks, SearchStocksArgs

router = APIRouter()

# TODO: Implement get_stock_price function first
# @router.get("/price/{symbol}", response_model=Dict[str, Any])
# async def get_price(symbol: str):
#     """
#     Get the current price of a stock.
#     """
#     result = await get_stock_price(GetStockPriceArgs(symbol=symbol))
#     if "error" in result:
#         raise HTTPException(status_code=404, detail=result["error"])
#     return result

# TODO: MCP functions not exported
# from app.mcp.market_data_tools import get_price_history, GetPriceHistoryArgs
# from app.mcp.market_data_tools import get_stock_news, GetStockNewsArgs
# from app.mcp.market_data_tools import get_top_movers
# from app.mcp.market_data_tools import search_stocks, SearchStocksArgs

# TODO: Re-enable when MCP functions are properly exported
# @router.get("/search", response_model=Dict[str, Any])
# async def search(query: str):
#     """
#     Search for stocks by symbol or company name.
#     """
#     result = await search_stocks(SearchStocksArgs(query=query))
#     if "error" in result:
#         raise HTTPException(status_code=404, detail=result["error"])
#     return result
