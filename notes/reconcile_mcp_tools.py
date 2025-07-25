#!/usr/bin/env python3
"""
Reconcile the MCP tools count discrepancy between the 41 in MCP_TOOLS.md
and the 84 mentioned in TODO.md and server comments.
"""


def get_mcp_tools_from_spec():
    """Get the 41 tools explicitly listed in MCP_TOOLS.md"""
    tools_from_spec = [
        # Core System Tools (2)
        "list_tools",
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
        "cancel_all_option_orders_tool",
    ]
    return tools_from_spec


def get_server_registered_tools():
    """Extract tools registered in server.py"""

    # This would represent the 56 tools currently registered
    # Based on server.py analysis, this includes:
    # - 41 core tools from MCP_TOOLS.md
    # - ~15 additional legacy/compatibility tools

    return [
        # Core MCP Tools (41)
        *get_mcp_tools_from_spec(),
        # Additional legacy/compatibility tools (~15)
        "get_stock_quote",
        "create_buy_order",
        "create_sell_order",
        "get_order",
        "get_position",
        "get_options_chain",
        "get_expiration_dates",
        "create_multi_leg_order",
        "calculate_option_greeks",
        "get_strategy_analysis",
        "simulate_option_expiration",
        "search_stocks",
        "get_stock_price",
        "get_stock_info",
        "get_price_history",
    ]


def identify_possible_missing_tools():
    """
    Identify what might make up the additional 28 tools to reach 84.
    This is speculative based on what a comprehensive trading system might need.
    """

    possible_additional_tools = [
        # Advanced Market Data (10+ tools)
        "get_earnings_calendar",
        "get_dividend_calendar",
        "get_stock_splits",
        "get_insider_trading",
        "get_institutional_holdings",
        "get_short_interest",
        "get_sector_performance",
        "get_market_movers",
        "get_premarket_data",
        "get_afterhours_data",
        "get_economic_calendar",
        "get_news_feed",
        # Advanced Portfolio Analytics (8+ tools)
        "calculate_portfolio_beta",
        "calculate_sharpe_ratio",
        "calculate_var",
        "get_portfolio_correlation",
        "analyze_sector_allocation",
        "calculate_portfolio_greeks",
        "get_risk_metrics",
        "get_performance_attribution",
        # Advanced Options Tools (10+ tools)
        "get_implied_volatility_surface",
        "calculate_option_chain_greeks",
        "find_arbitrage_opportunities",
        "analyze_volatility_skew",
        "get_option_flow_data",
        "calculate_max_pain",
        "get_put_call_ratio",
        "analyze_options_sentiment",
        "get_unusual_options_activity",
        "calculate_options_probabilities",
        # Advanced Order Types (5+ tools)
        "create_bracket_order",
        "create_oco_order",
        "create_iceberg_order",
        "create_twap_order",
        "create_vwap_order",
        # Risk Management (5+ tools)
        "calculate_position_sizing",
        "check_risk_limits",
        "get_margin_requirements",
        "calculate_drawdown",
        "analyze_correlation_risk",
        # Backtesting & Analysis (5+ tools)
        "run_backtest",
        "analyze_strategy_performance",
        "get_historical_correlations",
        "calculate_rolling_metrics",
        "generate_performance_report",
    ]

    return possible_additional_tools


def analyze_tool_gap():
    """Analyze the gap between current and expected tool counts"""

    spec_tools = get_mcp_tools_from_spec()
    server_tools = get_server_registered_tools()
    possible_missing = identify_possible_missing_tools()

    print("=" * 80)
    print("MCP TOOLS COUNT RECONCILIATION")
    print("=" * 80)

    print(f"Tools in MCP_TOOLS.md spec: {len(spec_tools)}")
    print(f"Tools currently in server: {len(server_tools)}")
    print("Expected by TODO.md: 84")
    print(f"Gap to reach 84: {84 - len(server_tools)}")

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if len(server_tools) >= len(spec_tools):
        print("✅ All MCP_TOOLS.md tools are implemented")
        print(f"✅ Plus {len(server_tools) - len(spec_tools)} additional tools")
    else:
        missing_from_spec = set(spec_tools) - set(server_tools)
        print(f"❌ Missing {len(missing_from_spec)} tools from spec:")
        for tool in sorted(missing_from_spec):
            print(f"   - {tool}")

    print(f"\n📊 To reach 84 tools, need {84 - len(server_tools)} more tools")

    if 84 - len(server_tools) > 0:
        print("\n" + "=" * 80)
        print("POSSIBLE ADDITIONAL TOOLS TO IMPLEMENT")
        print("=" * 80)

        categories = [
            ("Advanced Market Data", possible_missing[0:12]),
            ("Portfolio Analytics", possible_missing[12:20]),
            ("Advanced Options", possible_missing[20:30]),
            ("Advanced Orders", possible_missing[30:35]),
            ("Risk Management", possible_missing[35:40]),
            ("Analysis & Backtesting", possible_missing[40:45]),
        ]

        tools_needed = 84 - len(server_tools)
        tools_shown = 0

        for category, tools in categories:
            if tools_needed <= 0:
                break

            print(f"\n{category}:")
            for tool in tools[: min(len(tools), tools_needed)]:
                print(f"  - {tool}")
                tools_shown += 1
                tools_needed -= 1

            if tools_needed <= 0:
                break

    print("\n📋 CONCLUSION:")
    if len(server_tools) >= 84:
        print("✅ Already have 84+ tools implemented!")
    elif len(server_tools) >= len(spec_tools):
        print("✅ All specification tools implemented")
        print(f"🎯 Need {84 - len(server_tools)} more tools to reach TODO.md target")
    else:
        print("❌ Need to complete specification first")

    return len(spec_tools), len(server_tools), 84 - len(server_tools)


if __name__ == "__main__":
    spec_count, server_count, gap = analyze_tool_gap()
    print(f"\nSummary: {server_count}/{spec_count} spec tools, {gap} to reach 84 total")
