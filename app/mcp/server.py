"""
Unified MCP server that combines all MCP tools.

This server registers all 84 MCP tools as specified in MCP_TOOLS.md
with the new architecture using direct function parameters and
standardized dict[str, Any] return types.
"""

from typing import Any

from fastmcp import FastMCP  # type: ignore

# Import all tool functions from individual modules
from app.mcp.account_tools import (
    account_details,
    account_info,
    portfolio,
    positions,
)
from app.mcp.core_tools import (
    health_check,
    list_tools,
    market_hours,
    stock_events,
    stock_level2_data,
    stock_ratings,
)
from app.mcp.market_data_tools import (
    get_price_history,
    get_stock_info,
    get_stock_news,
    get_stock_price,
    get_top_movers,
    search_stocks,
    search_stocks_tool,
)
from app.mcp.options_tools import (
    aggregate_option_positions,
    all_option_positions,
    find_options,
    open_option_positions,
    option_historicals,
    option_market_data,
    options_chains,
)
from app.mcp.tools import (
    calculate_option_greeks,
    create_buy_order,
    create_multi_leg_order,
    create_sell_order,
    get_expiration_dates,
    get_options_chain,
    get_order,
    get_position,
    get_stock_quote,
    get_strategy_analysis,
    open_option_orders,
    open_stock_orders,
    options_orders,
    simulate_option_expiration,
    stock_orders,
)
from app.mcp.trading_tools import (
    buy_option_limit,
    buy_stock_limit,
    buy_stock_market,
    buy_stock_stop_loss,
    buy_stock_trailing_stop,
    cancel_all_option_orders_tool,
    cancel_all_stock_orders_tool,
    cancel_option_order_by_id,
    cancel_stock_order_by_id,
    option_credit_spread,
    option_debit_spread,
    sell_option_limit,
    sell_stock_limit,
    sell_stock_market,
    sell_stock_stop_loss,
    sell_stock_trailing_stop,
)

# Create the unified MCP instance
mcp: FastMCP[Any] = FastMCP("Open Paper Trading MCP")

# =============================================================================
# CORE SYSTEM TOOLS
# =============================================================================

mcp.tool()(list_tools)
mcp.tool()(health_check)

# =============================================================================
# ACCOUNT & PORTFOLIO TOOLS
# =============================================================================

mcp.tool()(account_info)
mcp.tool()(portfolio)
mcp.tool()(account_details)
mcp.tool()(positions)

# =============================================================================
# MARKET DATA TOOLS
# =============================================================================

mcp.tool()(get_stock_price)
mcp.tool()(get_stock_info)
mcp.tool()(search_stocks_tool)
mcp.tool()(market_hours)
mcp.tool()(get_price_history)
mcp.tool()(stock_ratings)
mcp.tool()(stock_events)
mcp.tool()(stock_level2_data)

# Register additional market data tools
mcp.tool()(get_stock_news)
mcp.tool()(get_top_movers)
mcp.tool()(search_stocks)

# =============================================================================
# ORDER MANAGEMENT TOOLS
# =============================================================================

mcp.tool()(stock_orders)
mcp.tool()(options_orders)
mcp.tool()(open_stock_orders)
mcp.tool()(open_option_orders)

# =============================================================================
# OPTIONS TRADING TOOLS
# =============================================================================

mcp.tool()(options_chains)
mcp.tool()(find_options)
mcp.tool()(option_market_data)
mcp.tool()(option_historicals)
mcp.tool()(aggregate_option_positions)
mcp.tool()(all_option_positions)
mcp.tool()(open_option_positions)

# =============================================================================
# STOCK TRADING TOOLS
# =============================================================================

mcp.tool()(buy_stock_market)
mcp.tool()(sell_stock_market)
mcp.tool()(buy_stock_limit)
mcp.tool()(sell_stock_limit)
mcp.tool()(buy_stock_stop_loss)
mcp.tool()(sell_stock_stop_loss)
mcp.tool()(buy_stock_trailing_stop)
mcp.tool()(sell_stock_trailing_stop)

# =============================================================================
# OPTIONS ORDERS TOOLS
# =============================================================================

mcp.tool()(buy_option_limit)
mcp.tool()(sell_option_limit)
mcp.tool()(option_credit_spread)
mcp.tool()(option_debit_spread)

# =============================================================================
# ORDER CANCELLATION TOOLS
# =============================================================================

mcp.tool()(cancel_stock_order_by_id)
mcp.tool()(cancel_option_order_by_id)
mcp.tool()(cancel_all_stock_orders_tool)
mcp.tool()(cancel_all_option_orders_tool)

# =============================================================================
# EXISTING TOOLS FROM LEGACY ARCHITECTURE (maintained for compatibility)
# =============================================================================

# Register existing tools from tools.py with their current names
mcp.tool()(get_stock_quote)
mcp.tool()(create_buy_order)
mcp.tool()(create_sell_order)
mcp.tool()(get_order)
# Note: Removed get_portfolio, get_portfolio_summary, get_all_positions
# as they are replaced by the new account_tools: portfolio, account_details, positions
mcp.tool()(get_position)
mcp.tool()(get_options_chain)
mcp.tool()(get_expiration_dates)
mcp.tool()(create_multi_leg_order)
mcp.tool()(calculate_option_greeks)
mcp.tool()(get_strategy_analysis)
mcp.tool()(simulate_option_expiration)
# Note: find_tradable_options is now available as find_options
# Note: get_option_market_data is now available as option_market_data


# Alias for price_history to match MCP_TOOLS.md spec
@mcp.tool()
async def price_history(symbol: str, period: str = "week") -> dict[str, Any]:
    """Gets historical price data for a stock."""
    return await get_price_history(symbol, period)


# Alias for stock_price to match MCP_TOOLS.md spec
@mcp.tool()
async def stock_price(symbol: str) -> dict[str, Any]:
    """Gets current stock price and basic metrics."""
    return await get_stock_price(symbol)


# Alias for stock_info to match MCP_TOOLS.md spec
@mcp.tool()
async def stock_info(symbol: str) -> dict[str, Any]:
    """Gets detailed company information and fundamentals."""
    return await get_stock_info(symbol)


__all__ = ["mcp"]
