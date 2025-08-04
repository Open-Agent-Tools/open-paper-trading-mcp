"""
MCP Tools for Open Paper Trading
Trading tools for AI agents including account and portfolio management
"""

import asyncio

# Import for type annotation
from typing import TYPE_CHECKING, Any

from fastmcp import Context, FastMCP

from app.core.id_utils import validate_optional_account_id
from app.core.service_factory import create_trading_service, get_trading_service
from app.core.user_context import user_context_manager

if TYPE_CHECKING:
    from app.services.trading_service import TradingService


def get_fresh_trading_service(account_id: str | None = None) -> "TradingService":
    """Get a fresh TradingService instance for MCP tool calls.

    This creates a new instance instead of using the singleton to avoid
    thread-local database session issues in the async execution context.

    Args:
        account_id: Account ID to determine account owner, defaults to UI_TESTER_WES
    """

    # Map common account IDs to their owners, fallback to the account_id as owner
    account_owner = "UI_TESTER_WES"  # Default for UITESTER01 and unknown accounts

    if account_id == "P34B193B2S":
        account_owner = "default"
    elif account_id and account_id != "UITESTER01":
        account_owner = account_id  # Use account_id as owner for unknown accounts

    return create_trading_service(account_owner)


def run_async_safely(coro):
    """Safely run async coroutine in sync context"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we need to run in a new thread with a new event loop
            import threading

            result_container = []
            exception_container = []

            def run_in_new_loop():
                """Run coroutine in a new event loop in a separate thread"""
                try:
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(coro)
                        result_container.append(result)
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception_container.append(e)

            # Run in a separate thread
            thread = threading.Thread(target=run_in_new_loop)
            thread.start()
            thread.join(timeout=30)  # 30 second timeout

            if thread.is_alive():
                raise TimeoutError("Async operation timed out after 30 seconds")

            if exception_container:
                raise exception_container[0]

            if result_container:
                return result_container[0]
            else:
                raise RuntimeError("No result returned from async operation")
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(coro)


# Initialize FastMCP instance
mcp: FastMCP = FastMCP("Open Paper Trading MCP")


@mcp.tool
def list_tools() -> dict[str, Any]:
    """List all available MCP tools with their descriptions"""
    try:
        # Get tools from FastMCP instance
        tools_dict = run_async_safely(mcp.get_tools())

        # Format tools for user-friendly display
        tools_list = []
        for tool_name, tool_info in tools_dict.items():
            tools_list.append(
                {
                    "name": tool_name,
                    "description": tool_info.description or "No description available",
                }
            )

        # Sort alphabetically by name
        tools_list.sort(key=lambda x: x["name"])

        return {
            "success": True,
            "tools": tools_list,
            "count": len(tools_list),
            "message": f"Found {len(tools_list)} available tools",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to list tools: {e!s}",
        }


@mcp.tool
def health_check() -> str:
    """Check the health status of the trading system"""
    return "MCP Server is healthy and operational"


@mcp.tool
def get_account_balance(account_id: str | None = None) -> dict[str, Any]:
    """Get the current account balance and basic account information

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)

        service = get_trading_service()
        balance = run_async_safely(service.get_account_balance(account_id))

        account_msg = f" for account {account_id}" if account_id else ""
        return {
            "success": True,
            "balance": balance,
            "currency": "USD",
            "account_id": account_id,
            "message": f"Account balance{account_msg}: ${balance:,.2f}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve account balance: {e!s}",
        }


@mcp.tool
def debug_context_info(ctx: Context) -> dict[str, Any]:
    """Debug tool to inspect MCP context and user mapping information"""
    try:
        context_info = user_context_manager.log_context_info(ctx)
        resolved_account_id = user_context_manager.get_account_id_for_tool(ctx)

        return {
            "success": True,
            "context_info": context_info,
            "resolved_account_id": resolved_account_id,
            "message": "Context information retrieved successfully",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve context information: {e!s}",
        }


@mcp.tool
def get_account_info(ctx: Context, account_id: str | None = None) -> dict[str, Any]:
    """Get comprehensive account information including balance and basic details

    Args:
        account_id: Optional 10-character account ID. If not provided, uses account from context.
    """
    try:
        # Get account ID from context if not provided
        context_account_id = user_context_manager.get_account_id_for_tool(
            ctx, account_id
        )

        # Validate account_id parameter
        resolved_account_id = validate_optional_account_id(context_account_id) or "UITESTER01"

        service = get_trading_service()

        # Use the new get_account_info method
        account_info = run_async_safely(service.get_account_info(resolved_account_id))

        return {
            "success": True,
            "account": {**account_info, "currency": "USD"},
            "message": f"Account {account_info['account_id']} retrieved successfully",
        }

    except Exception as e:
        # Get the resolved account ID for error reporting
        try:
            context_account_id = user_context_manager.get_account_id_for_tool(
                ctx, account_id
            )
            resolved_account_id = context_account_id or account_id or "UITESTER01"
        except Exception:
            resolved_account_id = account_id or "UITESTER01"

        return {
            "success": False,
            "error": str(e),
            "account_id": resolved_account_id,
            "message": f"Failed to retrieve account information: {e!s}",
        }


@mcp.tool
def get_portfolio(account_id: str | None = None) -> dict[str, Any]:
    """Get comprehensive portfolio information including positions and performance

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)

        service = get_trading_service()
        portfolio = run_async_safely(service.get_portfolio(account_id))

        # Convert positions to serializable format
        positions_data = []
        for position in portfolio.positions:
            positions_data.append(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "average_cost": position.avg_price,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "unrealized_pnl": position.unrealized_pnl,
                    "asset_type": "option" if position.is_option else "stock",
                    "side": "long" if position.quantity > 0 else "short",
                }
            )

        account_msg = f" for account {account_id}" if account_id else ""
        return {
            "success": True,
            "portfolio": {
                "cash_balance": portfolio.cash_balance,
                "total_value": portfolio.total_value,
                "daily_pnl": portfolio.daily_pnl,
                "total_pnl": portfolio.total_pnl,
                "positions_count": len(portfolio.positions),
                "positions": positions_data,
            },
            "account_id": account_id,
            "message": f"Portfolio{account_msg} retrieved with {len(portfolio.positions)} positions",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve portfolio: {e!s}",
        }


@mcp.tool
def get_portfolio_summary(account_id: str | None = None) -> dict[str, Any]:
    """Get portfolio summary with key performance metrics

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)

        service = get_trading_service()
        summary = run_async_safely(service.get_portfolio_summary(account_id))

        account_msg = f" for account {account_id}" if account_id else ""
        return {
            "success": True,
            "summary": {
                "total_value": summary.total_value,
                "cash_balance": summary.cash_balance,
                "invested_value": summary.invested_value,
                "daily_pnl": summary.daily_pnl,
                "daily_pnl_percent": summary.daily_pnl_percent,
                "total_pnl": summary.total_pnl,
                "total_pnl_percent": summary.total_pnl_percent,
            },
            "account_id": account_id,
            "message": f"Portfolio{account_msg} value: ${summary.total_value:,.2f}, Daily P&L: ${summary.daily_pnl:,.2f} ({summary.daily_pnl_percent:.2f}%)",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve portfolio summary: {e!s}",
        }


@mcp.tool
def get_all_accounts() -> dict[str, Any]:
    """Get summary of all accounts with their IDs, creation dates, and balances"""
    try:
        service = get_trading_service()
        accounts_summary = run_async_safely(service.get_all_accounts_summary())

        # Convert to serializable format
        accounts_data = []
        for account in accounts_summary.accounts:
            accounts_data.append(
                {
                    "account_id": account.id,
                    "owner": account.owner,
                    "created_at": account.created_at.isoformat(),
                    "starting_balance": account.starting_balance,
                    "current_balance": account.current_balance,
                    "change": account.current_balance - account.starting_balance,
                    "change_percent": (
                        (account.current_balance - account.starting_balance)
                        / account.starting_balance
                        * 100
                    )
                    if account.starting_balance > 0
                    else 0,
                }
            )

        return {
            "success": True,
            "accounts": accounts_data,
            "summary": {
                "total_count": accounts_summary.total_count,
                "total_starting_balance": accounts_summary.total_starting_balance,
                "total_current_balance": accounts_summary.total_current_balance,
                "total_change": accounts_summary.total_current_balance
                - accounts_summary.total_starting_balance,
                "total_change_percent": (
                    (
                        accounts_summary.total_current_balance
                        - accounts_summary.total_starting_balance
                    )
                    / accounts_summary.total_starting_balance
                    * 100
                )
                if accounts_summary.total_starting_balance > 0
                else 0,
            },
            "message": f"Found {accounts_summary.total_count} accounts with total value ${accounts_summary.total_current_balance:,.2f}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve accounts: {e!s}",
        }


@mcp.tool
def account_details(account_id: str | None = None) -> dict[str, Any]:
    """Get comprehensive account details including buying power and cash balances

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)

        service = get_trading_service()
        account_info = run_async_safely(service.get_account_info(account_id))
        portfolio = run_async_safely(service.get_portfolio(account_id))

        # Calculate additional details
        positions_count = len(portfolio.positions)
        invested_value = sum(
            pos.quantity * (pos.current_price or 0) for pos in portfolio.positions
        )
        buying_power = account_info["cash_balance"] * 2  # 2:1 margin (simplified)

        account_msg = f" for account {account_id}" if account_id else ""

        return {
            "success": True,
            "account_details": {
                "account_id": account_info["account_id"],
                "owner": account_info["owner"],
                "cash_balance": account_info["cash_balance"],
                "buying_power": buying_power,
                "total_value": account_info["total_value"],
                "invested_value": invested_value,
                "positions_count": positions_count,
                "starting_balance": account_info["starting_balance"],
                "created_at": account_info["created_at"],
                "updated_at": account_info["updated_at"],
                "performance": {
                    "total_gain_loss": account_info["total_value"]
                    - account_info["starting_balance"],
                    "total_gain_loss_percent": (
                        (account_info["total_value"] - account_info["starting_balance"])
                        / account_info["starting_balance"]
                        * 100
                    )
                    if account_info["starting_balance"] > 0
                    else 0,
                    "cash_ratio": (
                        account_info["cash_balance"] / account_info["total_value"] * 100
                    )
                    if account_info["total_value"] > 0
                    else 100,
                    "invested_ratio": (
                        invested_value / account_info["total_value"] * 100
                    )
                    if account_info["total_value"] > 0
                    else 0,
                },
                "currency": "USD",
            },
            "account_id": account_id,
            "message": f"Account details{account_msg}: ${account_info['total_value']:,.2f} total value, ${buying_power:,.2f} buying power",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve account details: {e!s}",
        }


@mcp.tool
def positions(account_id: str | None = None) -> dict[str, Any]:
    """Get current stock positions with quantities and values

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)

        service = get_trading_service()
        portfolio = run_async_safely(service.get_portfolio(account_id))

        # Extract and format positions
        positions_data = []
        total_value = 0
        total_cost_basis = 0

        for position in portfolio.positions:
            market_value = position.market_value or 0
            cost_basis = position.avg_price * position.quantity
            unrealized_pnl = position.unrealized_pnl or 0

            total_value += market_value
            total_cost_basis += cost_basis

            positions_data.append(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "avg_price": position.avg_price,
                    "current_price": position.current_price,
                    "market_value": market_value,
                    "cost_basis": cost_basis,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_percent": (
                        (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
                    ),
                    "asset_type": "option" if position.is_option else "stock",
                    "side": "long" if position.quantity > 0 else "short",
                    # Options-specific fields (None for stocks)
                    "option_type": position.option_type,
                    "strike": position.strike,
                    "expiration_date": position.expiration_date.isoformat()
                    if position.expiration_date
                    else None,
                    "underlying_symbol": position.underlying_symbol,
                }
            )

        # Sort positions by market value (descending)
        positions_data.sort(key=lambda x: x["market_value"], reverse=True)

        account_msg = f" for account {account_id}" if account_id else ""
        total_pnl = total_value - total_cost_basis

        return {
            "success": True,
            "positions": positions_data,
            "summary": {
                "total_positions": len(positions_data),
                "total_market_value": total_value,
                "total_cost_basis": total_cost_basis,
                "total_unrealized_pnl": total_pnl,
                "total_unrealized_pnl_percent": (
                    (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0
                ),
            },
            "account_id": account_id,
            "message": f"Portfolio{account_msg}: {len(positions_data)} positions worth ${total_value:,.2f}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve positions: {e!s}",
        }


@mcp.tool
def stock_price(symbol: str) -> dict[str, Any]:
    """Get current stock price and basic metrics

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()
        price_data = run_async_safely(service.get_stock_price(symbol))

        return {
            "success": True,
            "symbol": symbol,
            "price_data": price_data,
            "message": f"Stock price for {symbol}: ${price_data.get('price', 'N/A')}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "message": f"Failed to get stock price for {symbol}: {e!s}",
        }


@mcp.tool
def stock_info(symbol: str) -> dict[str, Any]:
    """Get detailed company information and fundamentals

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()
        info_data = run_async_safely(service.get_stock_info(symbol))

        return {
            "success": True,
            "symbol": symbol,
            "info": info_data,
            "message": f"Company information for {symbol} retrieved successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "message": f"Failed to get stock info for {symbol}: {e!s}",
        }


@mcp.tool
def search_stocks_tool(query: str) -> dict[str, Any]:
    """Search for stocks by symbol or company name

    Args:
        query: Search query (symbol or company name)
    """
    try:
        service = get_trading_service()
        search_results = run_async_safely(service.search_stocks(query))

        return {
            "success": True,
            "query": query,
            "results": search_results,
            "message": f"Found {len(search_results.get('results', []))} results for '{query}'",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "message": f"Failed to search stocks for '{query}': {e!s}",
        }


@mcp.tool
def market_hours() -> dict[str, Any]:
    """Get current market hours and status"""
    try:
        service = get_trading_service()
        hours_data = run_async_safely(service.get_market_hours())

        return {
            "success": True,
            "market_hours": hours_data,
            "message": f"Market status: {hours_data.get('status', 'Unknown')}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to get market hours: {e!s}",
        }


@mcp.tool
def price_history(symbol: str, period: str = "week") -> dict[str, Any]:
    """Get historical price data for a stock

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        period: Time period ("day", "week", "month", "3month", "year", "5year")
    """
    try:
        service = get_trading_service()
        history_data = run_async_safely(service.get_price_history(symbol, period))

        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "history": history_data,
            "message": f"Price history for {symbol} ({period}) retrieved successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "period": period,
            "message": f"Failed to get price history for {symbol}: {e!s}",
        }


@mcp.tool
def stock_ratings(symbol: str) -> dict[str, Any]:
    """Get analyst ratings for a stock

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()
        ratings_data = run_async_safely(service.get_stock_ratings(symbol))

        return {
            "success": True,
            "symbol": symbol,
            "ratings": ratings_data,
            "message": f"Analyst ratings for {symbol} retrieved successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "message": f"Failed to get stock ratings for {symbol}: {e!s}",
        }


@mcp.tool
def stock_events(symbol: str) -> dict[str, Any]:
    """Get corporate events for a stock (for owned positions)

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()
        events_data = run_async_safely(service.get_stock_events(symbol))

        return {
            "success": True,
            "symbol": symbol,
            "events": events_data,
            "message": f"Corporate events for {symbol} retrieved successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "message": f"Failed to get stock events for {symbol}: {e!s}",
        }


@mcp.tool
def stock_level2_data(symbol: str) -> dict[str, Any]:
    """Get Level II market data for a stock (Gold subscription required)

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()
        level2_data = run_async_safely(service.get_stock_level2_data(symbol))

        return {
            "success": True,
            "symbol": symbol,
            "level2": level2_data,
            "message": f"Level II data for {symbol} retrieved successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "message": f"Failed to get Level II data for {symbol}: {e!s}",
        }


@mcp.tool
def stock_orders() -> dict[str, Any]:
    """Retrieve a list of recent stock order history and their statuses"""
    try:
        service = get_trading_service()
        all_orders = run_async_safely(service.get_orders())

        # Filter for stock orders only (exclude options)
        stock_orders = [
            order
            for order in all_orders
            if order.symbol and not getattr(order, "is_option", False)
        ]

        # Convert orders to serializable format
        orders_data = []
        for order in stock_orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "condition": order.condition,
                    "price": order.price,
                    "stop_price": order.stop_price,
                    "status": order.status,
                    "created_at": order.created_at.isoformat()
                    if order.created_at
                    else None,
                    "filled_at": order.filled_at.isoformat()
                    if order.filled_at
                    else None,
                }
            )

        return {
            "success": True,
            "orders": orders_data,
            "count": len(orders_data),
            "message": f"Retrieved {len(orders_data)} stock orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve stock orders: {e!s}",
        }


@mcp.tool
def options_orders() -> dict[str, Any]:
    """Retrieve a list of recent options order history and their statuses"""
    try:
        service = get_trading_service()
        all_orders = run_async_safely(service.get_orders())

        # Filter for options orders only
        option_orders = [
            order
            for order in all_orders
            if getattr(order, "is_option", False)
            or (order.symbol and ("_" in order.symbol or len(order.symbol) > 5))
        ]

        # Convert orders to serializable format
        orders_data = []
        for order in option_orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "condition": order.condition,
                    "price": order.price,
                    "stop_price": order.stop_price,
                    "status": order.status,
                    "created_at": order.created_at.isoformat()
                    if order.created_at
                    else None,
                    "filled_at": order.filled_at.isoformat()
                    if order.filled_at
                    else None,
                }
            )

        return {
            "success": True,
            "orders": orders_data,
            "count": len(orders_data),
            "message": f"Retrieved {len(orders_data)} options orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve options orders: {e!s}",
        }


@mcp.tool
def open_stock_orders() -> dict[str, Any]:
    """Retrieve all open stock orders"""
    try:
        service = get_trading_service()
        all_orders = run_async_safely(service.get_orders())

        # Filter for open stock orders only
        open_stock_orders = [
            order
            for order in all_orders
            if (
                order.status in ["pending", "queued", "confirmed", "partially_filled"]
                and order.symbol
                and not getattr(order, "is_option", False)
            )
        ]

        # Convert orders to serializable format
        orders_data = []
        for order in open_stock_orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "condition": order.condition,
                    "price": order.price,
                    "stop_price": order.stop_price,
                    "status": order.status,
                    "created_at": order.created_at.isoformat()
                    if order.created_at
                    else None,
                }
            )

        return {
            "success": True,
            "orders": orders_data,
            "count": len(orders_data),
            "message": f"Retrieved {len(orders_data)} open stock orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve open stock orders: {e!s}",
        }


@mcp.tool
def open_option_orders() -> dict[str, Any]:
    """Retrieve all open option orders"""
    try:
        service = get_trading_service()
        all_orders = run_async_safely(service.get_orders())

        # Filter for open option orders only
        open_option_orders = [
            order
            for order in all_orders
            if (
                order.status in ["pending", "queued", "confirmed", "partially_filled"]
                and (
                    getattr(order, "is_option", False)
                    or (order.symbol and ("_" in order.symbol or len(order.symbol) > 5))
                )
            )
        ]

        # Convert orders to serializable format
        orders_data = []
        for order in open_option_orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "condition": order.condition,
                    "price": order.price,
                    "stop_price": order.stop_price,
                    "status": order.status,
                    "created_at": order.created_at.isoformat()
                    if order.created_at
                    else None,
                }
            )

        return {
            "success": True,
            "orders": orders_data,
            "count": len(orders_data),
            "message": f"Retrieved {len(orders_data)} open option orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve open option orders: {e!s}",
        }


@mcp.tool
def option_chain(underlying: str, expiration_date: str | None = None) -> dict[str, Any]:
    """Get complete options chain for an underlying stock

    Args:
        underlying: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format
    """
    try:
        service = get_trading_service()

        # Parse expiration date if provided
        exp_date = None
        if expiration_date:
            from datetime import datetime

            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        chain = run_async_safely(service.get_options_chain(underlying, exp_date))

        # Convert to serializable format
        calls_data = []
        puts_data = []

        for option_quote in chain.calls:
            calls_data.append(
                {
                    "symbol": option_quote.symbol,
                    "strike": option_quote.strike,
                    "expiration": option_quote.expiration_date.isoformat()
                    if option_quote.expiration_date
                    else None,
                    "price": option_quote.price,
                    "bid": option_quote.bid,
                    "ask": option_quote.ask,
                    "volume": option_quote.volume,
                    "open_interest": option_quote.open_interest,
                    "implied_volatility": option_quote.implied_volatility,
                }
            )

        for option_quote in chain.puts:
            puts_data.append(
                {
                    "symbol": option_quote.symbol,
                    "strike": option_quote.strike,
                    "expiration": option_quote.expiration_date.isoformat()
                    if option_quote.expiration_date
                    else None,
                    "price": option_quote.price,
                    "bid": option_quote.bid,
                    "ask": option_quote.ask,
                    "volume": option_quote.volume,
                    "open_interest": option_quote.open_interest,
                    "implied_volatility": option_quote.implied_volatility,
                }
            )

        return {
            "success": True,
            "underlying": underlying,
            "expiration_filter": expiration_date,
            "chain": {
                "calls": calls_data,
                "puts": puts_data,
                "calls_count": len(calls_data),
                "puts_count": len(puts_data),
            },
            "message": f"Options chain for {underlying}: {len(calls_data)} calls, {len(puts_data)} puts",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "underlying": underlying,
            "expiration_filter": expiration_date,
            "message": f"Failed to get options chain for {underlying}: {e!s}",
        }


@mcp.tool
def option_quote(option_symbol: str) -> dict[str, Any]:
    """Get market data for a specific option contract

    Args:
        option_symbol: Option symbol (e.g., "AAPL240119C00150000")
    """
    try:
        service = get_trading_service()
        market_data = run_async_safely(service.get_option_market_data(option_symbol))

        if "error" in market_data:
            return {
                "success": False,
                "error": market_data["error"],
                "option_symbol": option_symbol,
                "message": f"Failed to get option quote: {market_data['error']}",
            }

        return {
            "success": True,
            "option_symbol": option_symbol,
            "quote": market_data,
            "message": f"Option quote for {option_symbol}: ${market_data.get('price', 'N/A')}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "option_symbol": option_symbol,
            "message": f"Failed to get option quote for {option_symbol}: {e!s}",
        }


@mcp.tool
def option_greeks(
    option_symbol: str, underlying_price: float | None = None
) -> dict[str, Any]:
    """Calculate option Greeks (delta, gamma, theta, vega, rho)

    Args:
        option_symbol: Option symbol (e.g., "AAPL240119C00150000")
        underlying_price: Optional underlying stock price for calculation
    """
    try:
        service = get_trading_service()
        greeks = run_async_safely(
            service.calculate_greeks(option_symbol, underlying_price)
        )

        return {
            "success": True,
            "option_symbol": option_symbol,
            "underlying_price": underlying_price,
            "greeks": greeks,
            "message": f"Greeks calculated for {option_symbol}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "option_symbol": option_symbol,
            "underlying_price": underlying_price,
            "message": f"Failed to calculate Greeks for {option_symbol}: {e!s}",
        }


@mcp.tool
def find_options(
    symbol: str, expiration_date: str | None = None, option_type: str | None = None
) -> dict[str, Any]:
    """Find tradable options for a stock with optional filtering

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format
        option_type: Optional filter for "call" or "put"
    """
    try:
        service = get_trading_service()
        options_data = run_async_safely(
            service.find_tradable_options(symbol, expiration_date, option_type)
        )

        return {
            "success": True,
            "symbol": symbol,
            "filters": {
                "expiration_date": expiration_date,
                "option_type": option_type,
            },
            "options": options_data,
            "message": f"Found {len(options_data.get('options', []))} tradable options for {symbol}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "filters": {
                "expiration_date": expiration_date,
                "option_type": option_type,
            },
            "message": f"Failed to find options for {symbol}: {e!s}",
        }


@mcp.tool
def option_expirations(underlying: str) -> dict[str, Any]:
    """Get available expiration dates for options on an underlying stock

    Args:
        underlying: Stock symbol (e.g., "AAPL")
    """
    try:
        service = get_trading_service()

        # Get full options chain to extract expiration dates
        chain = run_async_safely(service.get_options_chain(underlying))

        # Extract unique expiration dates
        expirations = set()
        for option_quote in chain.calls + chain.puts:
            if option_quote.expiration_date:
                expirations.add(option_quote.expiration_date.isoformat())

        expiration_list = sorted(expirations)

        return {
            "success": True,
            "underlying": underlying,
            "expirations": expiration_list,
            "count": len(expiration_list),
            "message": f"Found {len(expiration_list)} expiration dates for {underlying}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "underlying": underlying,
            "message": f"Failed to get option expirations for {underlying}: {e!s}",
        }


@mcp.tool
def option_strikes(
    underlying: str, expiration_date: str | None = None, option_type: str | None = None
) -> dict[str, Any]:
    """Get available strike prices for options on an underlying stock

    Args:
        underlying: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format
        option_type: Optional filter for "call" or "put"
    """
    try:
        service = get_trading_service()

        # Parse expiration date if provided
        exp_date = None
        if expiration_date:
            from datetime import datetime

            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain = run_async_safely(service.get_options_chain(underlying, exp_date))

        # Extract strikes based on filters
        strikes = set()
        options_to_check = []

        if option_type == "call":
            options_to_check = chain.calls
        elif option_type == "put":
            options_to_check = chain.puts
        else:
            options_to_check = chain.calls + chain.puts

        for option_quote in options_to_check:
            if option_quote.strike:
                strikes.add(option_quote.strike)

        strike_list = sorted(strikes)

        return {
            "success": True,
            "underlying": underlying,
            "filters": {
                "expiration_date": expiration_date,
                "option_type": option_type,
            },
            "strikes": strike_list,
            "count": len(strike_list),
            "message": f"Found {len(strike_list)} strike prices for {underlying}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "underlying": underlying,
            "filters": {
                "expiration_date": expiration_date,
                "option_type": option_type,
            },
            "message": f"Failed to get option strikes for {underlying}: {e!s}",
        }


# Set 5: Stock Trading Tools (8 tools)


@mcp.tool
def buy_stock(
    symbol: str,
    quantity: float,
    order_type: str = "market",
    price: float | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a buy order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        order_type: Order type ("market", "limit", "stop", "stop_limit")
        price: Limit/stop price (required for limit/stop orders)
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # Map order_type to OrderCondition
        condition_map = {
            "market": OrderCondition.MARKET,
            "limit": OrderCondition.LIMIT,
            "stop": OrderCondition.STOP,
            "stop_limit": OrderCondition.STOP_LIMIT,
        }

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=price,
            condition=condition_map.get(order_type, OrderCondition.MARKET),
            stop_price=price if order_type in ["stop", "stop_limit"] else None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "account_id": account_id,
            "message": f"Buy order placed successfully for {quantity} shares of {symbol}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "account_id": account_id,
            "message": f"Failed to place buy order for {symbol}: {e!s}",
        }


@mcp.tool
def sell_stock(
    symbol: str,
    quantity: float,
    order_type: str = "market",
    price: float | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a sell order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to sell
        order_type: Order type ("market", "limit", "stop", "stop_limit")
        price: Limit/stop price (required for limit/stop orders)
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # Map order_type to OrderCondition
        condition_map = {
            "market": OrderCondition.MARKET,
            "limit": OrderCondition.LIMIT,
            "stop": OrderCondition.STOP,
            "stop_limit": OrderCondition.STOP_LIMIT,
        }

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=price,
            condition=condition_map.get(order_type, OrderCondition.MARKET),
            stop_price=price if order_type in ["stop", "stop_limit"] else None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "account_id": account_id,
            "message": f"Sell order placed successfully for {quantity} shares of {symbol}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "account_id": account_id,
            "message": f"Failed to place sell order for {symbol}: {e!s}",
        }


@mcp.tool
def buy_stock_limit(
    symbol: str, quantity: float, limit_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a limit buy order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        limit_price: Maximum price to pay per share
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Limit buy order placed for {quantity} shares of {symbol} at ${limit_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place limit buy order for {symbol}: {e!s}",
        }


@mcp.tool
def sell_stock_limit(
    symbol: str, quantity: float, limit_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a limit sell order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to sell
        limit_price: Minimum price to accept per share
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Limit sell order placed for {quantity} shares of {symbol} at ${limit_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place limit sell order for {symbol}: {e!s}",
        }


@mcp.tool
def buy_stock_stop(
    symbol: str, quantity: float, stop_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a stop buy order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        stop_price: Stop trigger price
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=stop_price,
            condition=OrderCondition.STOP,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "stop",
            "stop_price": stop_price,
            "account_id": account_id,
            "message": f"Stop buy order placed for {quantity} shares of {symbol} with stop at ${stop_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "stop",
            "stop_price": stop_price,
            "account_id": account_id,
            "message": f"Failed to place stop buy order for {symbol}: {e!s}",
        }


@mcp.tool
def sell_stock_stop(
    symbol: str, quantity: float, stop_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a stop sell order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to sell
        stop_price: Stop trigger price
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=stop_price,
            condition=OrderCondition.STOP,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "stop",
            "stop_price": stop_price,
            "account_id": account_id,
            "message": f"Stop sell order placed for {quantity} shares of {symbol} with stop at ${stop_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "stop",
            "stop_price": stop_price,
            "account_id": account_id,
            "message": f"Failed to place stop sell order for {symbol}: {e!s}",
        }


@mcp.tool
def buy_stock_stop_limit(
    symbol: str,
    quantity: float,
    stop_price: float,
    limit_price: float,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a stop-limit buy order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        stop_price: Stop trigger price
        limit_price: Maximum price to pay once triggered
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=limit_price,
            stop_price=stop_price,
            condition=OrderCondition.STOP_LIMIT,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "stop_limit",
            "stop_price": stop_price,
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Stop-limit buy order placed for {quantity} shares of {symbol} (stop: ${stop_price}, limit: ${limit_price})",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "order_type": "stop_limit",
            "stop_price": stop_price,
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place stop-limit buy order for {symbol}: {e!s}",
        }


@mcp.tool
def sell_stock_stop_limit(
    symbol: str,
    quantity: float,
    stop_price: float,
    limit_price: float,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a stop-limit sell order for stocks

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        quantity: Number of shares to sell
        stop_price: Stop trigger price
        limit_price: Minimum price to accept once triggered
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=limit_price,
            stop_price=stop_price,
            condition=OrderCondition.STOP_LIMIT,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "stop_limit",
            "stop_price": stop_price,
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Stop-limit sell order placed for {quantity} shares of {symbol} (stop: ${stop_price}, limit: ${limit_price})",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "order_type": "stop_limit",
            "stop_price": stop_price,
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place stop-limit sell order for {symbol}: {e!s}",
        }


# ============================================================================
# SET 6: OPTIONS TRADING TOOLS (4 tools)
# ============================================================================


@mcp.tool
def buy_option_limit(
    instrument_id: str, quantity: int, limit_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a limit buy order for an option

    Args:
        instrument_id: The option instrument ID
        quantity: Number of option contracts to buy
        limit_price: Maximum price per contract
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=instrument_id,  # Use instrument_id as symbol for options
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "instrument_id": instrument_id,
            "side": "buy",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Limit buy order placed for {quantity} option contracts of {instrument_id} at ${limit_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "instrument_id": instrument_id,
            "side": "buy",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place limit buy order for option {instrument_id}: {e!s}",
        }


@mcp.tool
def sell_option_limit(
    instrument_id: str, quantity: int, limit_price: float, account_id: str | None = None
) -> dict[str, Any]:
    """Place a limit sell order for an option

    Args:
        instrument_id: The option instrument ID
        quantity: Number of option contracts to sell
        limit_price: Minimum price per contract
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order_create = OrderCreate(
            symbol=instrument_id,  # Use instrument_id as symbol for options
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = run_async_safely(service.create_order(order_create))

        return {
            "success": True,
            "order": order,
            "instrument_id": instrument_id,
            "side": "sell",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Limit sell order placed for {quantity} option contracts of {instrument_id} at ${limit_price}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "instrument_id": instrument_id,
            "side": "sell",
            "quantity": quantity,
            "order_type": "limit",
            "limit_price": limit_price,
            "account_id": account_id,
            "message": f"Failed to place limit sell order for option {instrument_id}: {e!s}",
        }


@mcp.tool
def option_credit_spread(
    short_instrument_id: str,
    long_instrument_id: str,
    quantity: int,
    credit_price: float,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a credit spread order (sell short option, buy long option)

    Args:
        short_instrument_id: The option instrument ID to sell (short leg)
        long_instrument_id: The option instrument ID to buy (long leg)
        quantity: Number of spread contracts
        credit_price: Net credit received per spread
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # For now, implement as two separate orders (sell then buy)
        # In a real system, this would be a single multi-leg order

        # Sell the short leg
        short_order_create = OrderCreate(
            symbol=short_instrument_id,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=credit_price,  # Simplified: use credit price for short leg
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        short_order = run_async_safely(service.create_order(short_order_create))

        # Buy the long leg
        long_order_create = OrderCreate(
            symbol=long_instrument_id,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=0.01,  # Simplified: minimal price for long leg protection
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        long_order = run_async_safely(service.create_order(long_order_create))

        return {
            "success": True,
            "short_order": short_order,
            "long_order": long_order,
            "strategy": "credit_spread",
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "quantity": quantity,
            "credit_price": credit_price,
            "account_id": account_id,
            "message": f"Credit spread placed: sold {quantity} contracts of {short_instrument_id}, bought {quantity} contracts of {long_instrument_id} for ${credit_price} credit",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "strategy": "credit_spread",
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "quantity": quantity,
            "credit_price": credit_price,
            "account_id": account_id,
            "message": f"Failed to place credit spread: {e!s}",
        }


@mcp.tool
def option_debit_spread(
    short_instrument_id: str,
    long_instrument_id: str,
    quantity: int,
    debit_price: float,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Place a debit spread order (buy long option, sell short option)

    Args:
        short_instrument_id: The option instrument ID to sell (short leg)
        long_instrument_id: The option instrument ID to buy (long leg)
        quantity: Number of spread contracts
        debit_price: Net debit paid per spread
        account_id: Optional account ID (uses default if not specified)
    """
    try:
        account_id = validate_optional_account_id(account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # For now, implement as two separate orders (buy then sell)
        # In a real system, this would be a single multi-leg order

        # Buy the long leg
        long_order_create = OrderCreate(
            symbol=long_instrument_id,
            order_type=OrderType.BUY,
            quantity=int(quantity),
            price=debit_price,  # Simplified: use debit price for long leg
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        long_order = run_async_safely(service.create_order(long_order_create))

        # Sell the short leg
        short_order_create = OrderCreate(
            symbol=short_instrument_id,
            order_type=OrderType.SELL,
            quantity=int(quantity),
            price=0.01,  # Simplified: minimal price for short leg
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        short_order = run_async_safely(service.create_order(short_order_create))

        return {
            "success": True,
            "long_order": long_order,
            "short_order": short_order,
            "strategy": "debit_spread",
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "quantity": quantity,
            "debit_price": debit_price,
            "account_id": account_id,
            "message": f"Debit spread placed: bought {quantity} contracts of {long_instrument_id}, sold {quantity} contracts of {short_instrument_id} for ${debit_price} debit",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "strategy": "debit_spread",
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "quantity": quantity,
            "debit_price": debit_price,
            "account_id": account_id,
            "message": f"Failed to place debit spread: {e!s}",
        }


# =============================================================================
# Set 7: Order Cancellation Tools (4 tools)
# =============================================================================


@mcp.tool
def cancel_stock_order_by_id(order_id: str) -> dict[str, Any]:
    """Cancel a specific stock order by its ID

    Args:
        order_id: The ID of the stock order to cancel
    """
    try:
        service = get_trading_service()
        result = run_async_safely(service.cancel_order(order_id))

        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "order_id": order_id,
                "message": f"Failed to cancel stock order {order_id}: {result['error']}",
            }

        return {
            "success": True,
            "order_id": order_id,
            "result": result,
            "message": f"Stock order {order_id} cancelled successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "order_id": order_id,
            "message": f"Failed to cancel stock order {order_id}: {e!s}",
        }


@mcp.tool
def cancel_option_order_by_id(order_id: str) -> dict[str, Any]:
    """Cancel a specific option order by its ID

    Args:
        order_id: The ID of the option order to cancel
    """
    try:
        service = get_trading_service()
        result = run_async_safely(service.cancel_order(order_id))

        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "order_id": order_id,
                "message": f"Failed to cancel option order {order_id}: {result['error']}",
            }

        return {
            "success": True,
            "order_id": order_id,
            "result": result,
            "message": f"Option order {order_id} cancelled successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "order_id": order_id,
            "message": f"Failed to cancel option order {order_id}: {e!s}",
        }


@mcp.tool
def cancel_all_stock_orders_tool() -> dict[str, Any]:
    """Cancel all open stock orders"""
    try:
        service = get_trading_service()
        result = run_async_safely(service.cancel_all_stock_orders())

        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "message": f"Failed to cancel all stock orders: {result['error']}",
            }

        total_cancelled = result.get("total_cancelled", 0)
        return {
            "success": True,
            "total_cancelled": total_cancelled,
            "cancelled_orders": result.get("cancelled_orders", []),
            "message": f"Successfully cancelled {total_cancelled} stock orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to cancel all stock orders: {e!s}",
        }


@mcp.tool
def cancel_all_option_orders_tool() -> dict[str, Any]:
    """Cancel all open option orders"""
    try:
        service = get_trading_service()
        result = run_async_safely(service.cancel_all_option_orders())

        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "message": f"Failed to cancel all option orders: {result['error']}",
            }

        total_cancelled = result.get("total_cancelled", 0)
        return {
            "success": True,
            "total_cancelled": total_cancelled,
            "cancelled_orders": result.get("cancelled_orders", []),
            "message": f"Successfully cancelled {total_cancelled} option orders",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to cancel all option orders: {e!s}",
        }


# Export the MCP instance for integration with FastAPI
__all__ = ["mcp"]
