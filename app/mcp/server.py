"""
Unified MCP server that combines all MCP tools.
"""

from typing import Any

from fastmcp import FastMCP  # type: ignore

from app.mcp.market_data_tools import (
    get_price_history,
    get_stock_info,
    get_stock_news,
    get_stock_price,
    get_top_movers,
    search_stocks,
)

# Import all tool functions from individual modules
from app.mcp.tools import (
    calculate_option_greeks,
    cancel_order,
    create_buy_order,
    create_multi_leg_order,
    create_sell_order,
    find_tradable_options,
    get_all_orders,
    get_all_positions,
    get_expiration_dates,
    get_option_market_data,
    get_options_chain,
    get_order,
    get_portfolio,
    get_portfolio_summary,
    get_position,
    get_stock_quote,
    get_strategy_analysis,
    simulate_option_expiration,
)

# Removed direct Robinhood options tools imports

# Create the unified MCP instance
mcp: FastMCP[Any] = FastMCP("Open Paper Trading MCP")

# Register all tools from tools.py
mcp.tool()(get_stock_quote)
mcp.tool()(create_buy_order)
mcp.tool()(create_sell_order)
mcp.tool()(get_all_orders)
mcp.tool()(get_order)
mcp.tool()(cancel_order)
mcp.tool()(get_portfolio)
mcp.tool()(get_portfolio_summary)
mcp.tool()(get_all_positions)
mcp.tool()(get_position)
mcp.tool()(get_options_chain)
mcp.tool()(get_expiration_dates)
mcp.tool()(create_multi_leg_order)
mcp.tool()(calculate_option_greeks)
mcp.tool()(get_strategy_analysis)
mcp.tool()(simulate_option_expiration)
mcp.tool()(find_tradable_options)
mcp.tool()(get_option_market_data)

# Register all async tools from market_data_tools.py
mcp.tool()(get_stock_price)
mcp.tool()(get_stock_info)
mcp.tool()(get_price_history)
mcp.tool()(get_stock_news)
mcp.tool()(get_top_movers)
mcp.tool()(search_stocks)

# Note: Removed direct Robinhood options tools to maintain unified architecture
# All options data now flows through TradingService for consistency

# Note: account_tools.py doesn't have any tools defined yet

__all__ = ["mcp"]
