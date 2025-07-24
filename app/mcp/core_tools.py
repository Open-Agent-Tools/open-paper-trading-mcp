"""
Core system tools for MCP server operations.

These tools provide system-level functionality like health checks,
tool listing, and market status information.
"""

from datetime import UTC
from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def list_tools() -> dict[str, Any]:
    """
    Provides a comprehensive list of all available MCP tools and their descriptions.

    Returns information about all registered tools organized by category.
    """
    try:
        tools_data = {
            "total_tools": 60,
            "version": "v0.5.0",
            "categories": {
                "core_system": ["list_tools", "health_check"],
                "account_portfolio": [
                    "account_info",
                    "portfolio",
                    "account_details",
                    "positions",
                ],
                "market_data": [
                    "get_stock_price",
                    "get_stock_info",
                    "search_stocks_tool",
                    "market_hours",
                    "get_price_history",
                    "stock_ratings",
                    "stock_events",
                    "stock_level2_data",
                    "search_stocks",
                    "price_history",  # alias
                    "stock_price",  # alias
                    "stock_info",  # alias
                ],
                "order_management": [
                    "stock_orders",
                    "options_orders",
                    "open_stock_orders",
                    "open_option_orders",
                ],
                "options_trading": [
                    "options_chains",
                    "find_options",
                    "option_market_data",
                    "option_historicals",
                    "aggregate_option_positions",
                    "all_option_positions",
                    "open_option_positions",
                ],
                "stock_trading": [
                    "buy_stock_market",
                    "sell_stock_market",
                    "buy_stock_limit",
                    "sell_stock_limit",
                    "buy_stock_stop_loss",
                    "sell_stock_stop_loss",
                    "buy_stock_trailing_stop",
                    "sell_stock_trailing_stop",
                ],
                "options_orders": [
                    "buy_option_limit",
                    "sell_option_limit",
                    "option_credit_spread",
                    "option_debit_spread",
                ],
                "order_cancellation": [
                    "cancel_stock_order_by_id",
                    "cancel_option_order_by_id",
                    "cancel_all_stock_orders_tool",
                    "cancel_all_option_orders_tool",
                ],
                "legacy_tools": [
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
                    "find_tradable_options",
                    "get_option_market_data",
                ],
            },
            "description": "Open Paper Trading MCP Tools for comprehensive paper trading and market data access",
            "implementation_status": {
                "core_system": "100% implemented (2/2)",
                "account_portfolio": "100% implemented (4/4)",
                "market_data": "100% implemented (15/15)",
                "order_management": "100% implemented (4/4)",
                "options_trading": "100% implemented (7/7)",
                "stock_trading": "100% implemented (8/8)",
                "options_orders": "100% implemented (4/4)",
                "order_cancellation": "100% implemented (4/4)",
                "legacy_tools": "100% implemented (13/13)",
            },
        }
        return success_response(tools_data)
    except Exception as e:
        return handle_tool_exception("list_tools", e)


async def health_check() -> dict[str, Any]:
    """
    Gets health status of the MCP server and its components.

    Performs actual health checks on system components including:
    - Trading service connectivity
    - Database connectivity
    - Market data adapter status
    - System resource usage
    """
    import time
    from datetime import datetime

    import psutil

    try:
        # Get current timestamp
        current_time = datetime.now(UTC)
        timestamp = current_time.isoformat().replace("+00:00", "Z")

        # Initialize component statuses
        components = {}
        overall_status = "healthy"

        # Check trading service
        try:
            trading_service = get_trading_service()
            # Test basic service functionality by getting adapter info
            if (
                hasattr(trading_service, "quote_adapter")
                and trading_service.quote_adapter
            ):
                components["trading_service"] = "operational"
            else:
                components["trading_service"] = "degraded"
                overall_status = "degraded"
        except Exception:
            components["trading_service"] = "down"
            overall_status = "unhealthy"

        # Check database connectivity
        try:
            # Import here to avoid circular dependencies
            from sqlalchemy import text

            from app.storage.database import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                # Simple test query
                result = await session.execute(text("SELECT 1"))
                if result:
                    components["database"] = "operational"
                else:
                    components["database"] = "degraded"
                    overall_status = "degraded"
        except Exception:
            components["database"] = "down"
            overall_status = "unhealthy"

        # Check market data adapter
        try:
            trading_service = get_trading_service()
            if hasattr(trading_service, "quote_adapter"):
                # Test adapter by checking its type
                adapter_type = type(trading_service.quote_adapter).__name__
                if "TestData" in adapter_type:
                    components["market_data"] = "operational (test)"
                else:
                    components["market_data"] = "operational"
            else:
                components["market_data"] = "down"
                overall_status = "unhealthy"
        except Exception:
            components["market_data"] = "down"
            overall_status = "unhealthy"

        # Get system resource usage
        try:
            memory_info = psutil.virtual_memory()
            memory_usage_mb = round(memory_info.used / (1024 * 1024), 2)
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except Exception:
            memory_usage_mb = 0
            cpu_percent = 0

        # Get process uptime (approximation)
        try:
            process = psutil.Process()
            uptime_seconds = round(time.time() - process.create_time())
        except Exception:
            uptime_seconds = 0

        data = {
            "status": overall_status,
            "timestamp": timestamp,
            "version": "v0.5.0",
            "components": components,
            "system_metrics": {
                "uptime_seconds": uptime_seconds,
                "memory_usage_mb": memory_usage_mb,
                "cpu_percent": cpu_percent,
            },
            "mcp_server": "operational",
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("health_check", e)


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
