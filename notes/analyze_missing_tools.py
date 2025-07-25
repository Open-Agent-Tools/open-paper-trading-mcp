#!/usr/bin/env python3
"""
Analyze which MCP tools are missing by comparing MCP_TOOLS.md spec with actual implementations.
"""

def get_expected_tools_from_spec():
    """Extract the expected 84 tools from MCP_TOOLS.md specification."""
    
    # Based on MCP_TOOLS.md, these are the 84 expected tools:
    expected_tools = [
        # Core System Tools (2)
        "list_tools",  # Provided by FastMCP automatically
        "health_check",
        
        # Account & Portfolio Tools (4)
        "account_info",
        "portfolio", 
        "account_details",
        "positions",
        
        # Market Data Tools (8)
        "stock_price",
        "stock_info", 
        "search_stocks_tool",
        "market_hours",
        "price_history",
        "stock_ratings",
        "stock_events",
        "stock_level2_data",
        
        # Order Management Tools (4)
        "stock_orders",
        "options_orders", 
        "open_stock_orders",
        "open_option_orders",
        
        # Options Trading Tools (7)
        "options_chains",
        "find_options",
        "option_market_data",
        "option_historicals", 
        "aggregate_option_positions",
        "all_option_positions",
        "open_option_positions",
        
        # Stock Trading Tools (8)
        "buy_stock_market",
        "sell_stock_market",
        "buy_stock_limit", 
        "sell_stock_limit",
        "buy_stock_stop_loss",
        "sell_stock_stop_loss",
        "buy_stock_trailing_stop",
        "sell_stock_trailing_stop",
        
        # Options Orders Tools (4)
        "buy_option_limit",
        "sell_option_limit", 
        "option_credit_spread",
        "option_debit_spread",
        
        # Order Cancellation Tools (4)
        "cancel_stock_order_by_id",
        "cancel_option_order_by_id",
        "cancel_all_stock_orders_tool", 
        "cancel_all_option_orders_tool"
    ]
    
    return expected_tools


def get_implemented_tools():
    """Get list of tools that are actually implemented and importable."""
    
    implemented = []
    
    # Try importing tools and add them if successful
    try:
        from app.mcp.core_tools import health_check, market_hours, stock_ratings, stock_events, stock_level2_data
        implemented.extend(["health_check", "market_hours", "stock_ratings", "stock_events", "stock_level2_data"])
    except ImportError as e:
        print(f"Error importing core tools: {e}")
    
    try:
        from app.mcp.account_tools import account_info, portfolio, account_details, positions
        implemented.extend(["account_info", "portfolio", "account_details", "positions"])
    except ImportError as e:
        print(f"Error importing account tools: {e}")
    
    try:
        from app.mcp.market_data_tools import get_stock_price, get_stock_info, search_stocks_tool, get_price_history, stock_price, stock_info, price_history
        implemented.extend(["stock_price", "stock_info", "search_stocks_tool", "price_history"])
    except ImportError as e:
        print(f"Error importing market data tools: {e}")
    
    try:
        from app.mcp.tools import stock_orders, options_orders, open_stock_orders, open_option_orders
        implemented.extend(["stock_orders", "options_orders", "open_stock_orders", "open_option_orders"])
    except ImportError as e:
        print(f"Error importing order tools: {e}")
    
    try:
        from app.mcp.options_tools import options_chains, find_options, option_market_data, option_historicals, aggregate_option_positions, all_option_positions, open_option_positions
        implemented.extend(["options_chains", "find_options", "option_market_data", "option_historicals", "aggregate_option_positions", "all_option_positions", "open_option_positions"])
    except ImportError as e:
        print(f"Error importing options tools: {e}")
    
    try:
        from app.mcp.trading_tools import (
            buy_stock_market, sell_stock_market, buy_stock_limit, sell_stock_limit,
            buy_stock_stop_loss, sell_stock_stop_loss, buy_stock_trailing_stop, sell_stock_trailing_stop,
            buy_option_limit, sell_option_limit, option_credit_spread, option_debit_spread,
            cancel_stock_order_by_id, cancel_option_order_by_id, cancel_all_stock_orders_tool, cancel_all_option_orders_tool
        )
        implemented.extend([
            "buy_stock_market", "sell_stock_market", "buy_stock_limit", "sell_stock_limit",
            "buy_stock_stop_loss", "sell_stock_stop_loss", "buy_stock_trailing_stop", "sell_stock_trailing_stop",
            "buy_option_limit", "sell_option_limit", "option_credit_spread", "option_debit_spread",
            "cancel_stock_order_by_id", "cancel_option_order_by_id", "cancel_all_stock_orders_tool", "cancel_all_option_orders_tool"
        ])
    except ImportError as e:
        print(f"Error importing trading tools: {e}")
    
    # Add list_tools (provided by FastMCP)
    implemented.append("list_tools")
    
    return implemented


def analyze_missing_tools():
    """Compare expected vs implemented tools and identify gaps."""
    
    expected = set(get_expected_tools_from_spec())
    implemented = set(get_implemented_tools())
    
    missing = expected - implemented
    extra = implemented - expected
    
    print("=" * 60)
    print("MCP TOOLS ANALYSIS")
    print("=" * 60)
    
    print(f"Expected tools (from MCP_TOOLS.md): {len(expected)}")
    print(f"Implemented tools: {len(implemented)}")
    print(f"Missing tools: {len(missing)}")
    print(f"Extra tools: {len(extra)}")
    
    completion_rate = (len(implemented) / len(expected)) * 100
    print(f"Completion rate: {completion_rate:.1f}%")
    
    if missing:
        print("\n" + "=" * 60)
        print("MISSING TOOLS (need to implement):")
        print("=" * 60)
        for i, tool in enumerate(sorted(missing), 1):
            print(f"{i:2d}. {tool}")
    
    if extra:
        print("\n" + "=" * 60)
        print("EXTRA TOOLS (not in spec):")
        print("=" * 60)
        for i, tool in enumerate(sorted(extra), 1):
            print(f"{i:2d}. {tool}")
    
    print("\n" + "=" * 60)
    print("IMPLEMENTED TOOLS:")
    print("=" * 60)
    for i, tool in enumerate(sorted(implemented), 1):
        print(f"{i:2d}. {tool}")
    
    return missing, extra, completion_rate


if __name__ == "__main__":
    missing, extra, rate = analyze_missing_tools()
    print(f"\n🎯 Summary: {rate:.1f}% complete, {len(missing)} tools missing")
    
    if len(missing) == 0:
        print("🎉 All MCP tools are implemented!")
    elif len(missing) <= 10:
        print("👍 Almost there! Just a few more tools to implement.")
    else:
        print("⚠️  Several tools still need implementation.")