"""
Core system tools for MCP server operations.

These tools provide system-level functionality like health checks,
tool listing, and market status information.
"""

from datetime import UTC
from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


# NOTE: list_tools is provided automatically by FastMCP and does not need to be implemented manually


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

            from app.storage.database import get_async_session

            async for session in get_async_session():
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
