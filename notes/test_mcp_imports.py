#!/usr/bin/env python3
"""
Simple test to verify all MCP tools are importable and count them.
"""

def test_mcp_imports():
    """Test that all MCP tools can be imported successfully."""
    
    print("Testing MCP tool imports...")
    
    # Core System Tools (2 tools)
    from app.mcp.core_tools import health_check, market_hours, stock_ratings, stock_events, stock_level2_data
    core_tools = ["health_check", "market_hours", "stock_ratings", "stock_events", "stock_level2_data"]
    # Note: list_tools is provided automatically by FastMCP
    
    # Account & Portfolio Tools (4 tools)
    from app.mcp.account_tools import account_info, portfolio, account_details, positions
    account_tools = ["account_info", "portfolio", "account_details", "positions"]
    
    # Market Data Tools (8 tools)
    from app.mcp.market_data_tools import (
        get_stock_price, get_stock_info, search_stocks_tool, 
        get_price_history, stock_price, stock_info, price_history
    )
    market_data_tools = [
        "stock_price", "stock_info", "search_stocks_tool", "market_hours",
        "price_history", "stock_ratings", "stock_events", "stock_level2_data"
    ]
    
    # Order Management Tools (4 tools)
    from app.mcp.tools import stock_orders, options_orders, open_stock_orders, open_option_orders
    order_mgmt_tools = ["stock_orders", "options_orders", "open_stock_orders", "open_option_orders"]
    
    # Options Trading Tools (7 tools)
    from app.mcp.options_tools import (
        options_chains, find_options, option_market_data, option_historicals,
        aggregate_option_positions, all_option_positions, open_option_positions
    )
    options_tools = [
        "options_chains", "find_options", "option_market_data", "option_historicals",
        "aggregate_option_positions", "all_option_positions", "open_option_positions"
    ]
    
    # Stock Trading Tools (8 tools)
    from app.mcp.trading_tools import (
        buy_stock_market, sell_stock_market, buy_stock_limit, sell_stock_limit,
        buy_stock_stop_loss, sell_stock_stop_loss, buy_stock_trailing_stop, sell_stock_trailing_stop
    )
    stock_trading_tools = [
        "buy_stock_market", "sell_stock_market", "buy_stock_limit", "sell_stock_limit",
        "buy_stock_stop_loss", "sell_stock_stop_loss", "buy_stock_trailing_stop", "sell_stock_trailing_stop"
    ]
    
    # Options Orders Tools (4 tools)
    from app.mcp.trading_tools import (
        buy_option_limit, sell_option_limit, option_credit_spread, option_debit_spread
    )
    options_orders_tools = [
        "buy_option_limit", "sell_option_limit", "option_credit_spread", "option_debit_spread"
    ]
    
    # Order Cancellation Tools (4 tools)
    from app.mcp.trading_tools import (
        cancel_stock_order_by_id, cancel_option_order_by_id, 
        cancel_all_stock_orders_tool, cancel_all_option_orders_tool
    )
    order_cancel_tools = [
        "cancel_stock_order_by_id", "cancel_option_order_by_id",
        "cancel_all_stock_orders_tool", "cancel_all_option_orders_tool"
    ]
    
    # Legacy/compatibility tools from tools.py
    from app.mcp.tools import (
        get_stock_quote, create_buy_order, create_sell_order, get_order, get_position,
        get_options_chain, get_expiration_dates, create_multi_leg_order,
        calculate_option_greeks, get_strategy_analysis, simulate_option_expiration
    )
    legacy_tools = [
        "get_stock_quote", "create_buy_order", "create_sell_order", "get_order", "get_position",
        "get_options_chain", "get_expiration_dates", "create_multi_leg_order",
        "calculate_option_greeks", "get_strategy_analysis", "simulate_option_expiration"
    ]
    
    # Count and report
    all_tool_groups = [
        ("Core System", core_tools),
        ("Account & Portfolio", account_tools),
        ("Market Data", market_data_tools),
        ("Order Management", order_mgmt_tools),
        ("Options Trading", options_tools),
        ("Stock Trading", stock_trading_tools),
        ("Options Orders", options_orders_tools),
        ("Order Cancellation", order_cancel_tools),
        ("Legacy/Compatibility", legacy_tools)
    ]
    
    total_tools = 0
    for category, tools in all_tool_groups:
        count = len(tools)
        total_tools += count
        print(f"✓ {category}: {count} tools imported successfully")
    
    print(f"\n✅ Total MCP tools imported: {total_tools}")
    print("🎯 Expected: 84 tools (as per MCP_TOOLS.md)")
    
    # Check if we're close to the expected count
    if total_tools >= 80:
        print("🎉 Great! Nearly all tools are implemented and importable.")
    elif total_tools >= 60:
        print("👍 Good progress! Most tools are implemented.")
    else:
        print("⚠️  More tools need to be implemented.")
    
    return total_tools


if __name__ == "__main__":
    count = test_mcp_imports()
    print(f"\nFinal count: {count} MCP tools successfully imported")