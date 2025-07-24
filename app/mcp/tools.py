from datetime import datetime
from typing import Any

from app.mcp.response_utils import (
    error_response,
    handle_tool_exception,
    success_response,
)
from app.models.assets import Option, asset_factory
from app.schemas.orders import OrderCondition, OrderCreate, OrderType
from app.services.trading_service import TradingService

# MCP tools will receive TradingService instance as dependency
_trading_service: TradingService | None = None


def set_mcp_trading_service(service: TradingService) -> None:
    """Set the trading service for MCP tools."""
    global _trading_service
    _trading_service = service


def get_mcp_trading_service() -> TradingService:
    """Get the trading service for MCP tools."""
    if _trading_service is None:
        raise RuntimeError("TradingService not initialized for MCP tools")
    return _trading_service


# Direct function parameters replace Pydantic models per MCP_TOOLS.md spec


async def get_stock_quote(symbol: str) -> dict[str, Any]:
    """Get a stock quote."""
    try:
        quote_data = await get_mcp_trading_service().get_stock_price(symbol)
        if "error" in quote_data:
            return error_response(quote_data["error"])

        data = {
            "symbol": quote_data.get("symbol"),
            "price": quote_data.get("price"),
            "change": quote_data.get("change"),
            "change_percent": quote_data.get("change_percent"),
            "volume": quote_data.get("volume"),
            "ask_price": quote_data.get("ask_price"),
            "bid_price": quote_data.get("bid_price"),
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_stock_quote", e)


async def create_buy_order(symbol: str, quantity: int, price: float) -> dict[str, Any]:
    """Create a buy order for a stock (limit order)."""
    try:
        # Validate inputs
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price <= 0:
            raise ValueError("Price must be positive")

        symbol = symbol.strip().upper()

        order_data = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=price,
            condition=OrderCondition.LIMIT,  # Changed to LIMIT since price is specified
        )
        order = await get_mcp_trading_service().create_order(order_data)
        data = {
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "total_cost": price * quantity,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
            "message": f"Buy limit order for {quantity} shares of {symbol} at ${price:.2f} per share",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_buy_order", e)


async def create_sell_order(symbol: str, quantity: int, price: float) -> dict[str, Any]:
    """Create a sell order for a stock (limit order)."""
    try:
        # Validate inputs
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price <= 0:
            raise ValueError("Price must be positive")

        symbol = symbol.strip().upper()

        order_data = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=price,
            condition=OrderCondition.LIMIT,  # Changed to LIMIT since price is specified
        )
        order = await get_mcp_trading_service().create_order(order_data)
        data = {
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "total_proceeds": price * quantity,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
            "message": f"Sell limit order for {quantity} shares of {symbol} at ${price:.2f} per share",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_sell_order", e)


async def stock_orders() -> dict[str, Any]:
    """Get all stock trading orders."""
    try:
        orders = await get_mcp_trading_service().get_orders()
        stock_orders_data = []
        for order in orders:
            # Filter for stock orders by checking if the symbol is a stock
            # Stock symbols are typically shorter and don't contain option patterns
            asset = asset_factory(order.symbol)
            if asset and asset.asset_type == "stock":
                stock_orders_data.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status,
                        "created_at": (
                            order.created_at.isoformat() if order.created_at else None
                        ),
                        "filled_at": (
                            order.filled_at.isoformat() if order.filled_at else None
                        ),
                    }
                )
        data = {
            "stock_orders": stock_orders_data,
            "count": len(stock_orders_data),
            "order_types": ["stock"],
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("stock_orders", e)


async def options_orders() -> dict[str, Any]:
    """Get all options trading orders."""
    try:
        orders = await get_mcp_trading_service().get_orders()
        option_orders_data = []
        for order in orders:
            # Filter for option orders by checking if the symbol is an option
            asset = asset_factory(order.symbol)
            if asset and isinstance(asset, Option):
                option_orders_data.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "underlying_symbol": (
                            asset.underlying.symbol if asset.underlying else None
                        ),
                        "option_type": asset.option_type,
                        "strike": asset.strike,
                        "expiration_date": (
                            asset.expiration_date.isoformat()
                            if asset.expiration_date
                            else None
                        ),
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status,
                        "created_at": (
                            order.created_at.isoformat() if order.created_at else None
                        ),
                        "filled_at": (
                            order.filled_at.isoformat() if order.filled_at else None
                        ),
                    }
                )
        data = {
            "option_orders": option_orders_data,
            "count": len(option_orders_data),
            "order_types": ["option"],
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("options_orders", e)


async def open_stock_orders() -> dict[str, Any]:
    """Get all open stock trading orders (pending, triggered, partially filled)."""
    try:
        orders = await get_mcp_trading_service().get_orders()
        open_stock_orders_data = []
        open_statuses = ["pending", "triggered", "partially_filled"]

        for order in orders:
            # Filter for stock orders that are open
            asset = asset_factory(order.symbol)
            if (
                asset
                and asset.asset_type == "stock"
                and order.status.lower() in open_statuses
            ):
                open_stock_orders_data.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status,
                        "created_at": (
                            order.created_at.isoformat() if order.created_at else None
                        ),
                    }
                )
        data = {
            "open_stock_orders": open_stock_orders_data,
            "count": len(open_stock_orders_data),
            "order_types": ["stock"],
            "statuses_included": open_statuses,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("open_stock_orders", e)


async def open_option_orders() -> dict[str, Any]:
    """Get all open option trading orders (pending, triggered, partially filled)."""
    try:
        orders = await get_mcp_trading_service().get_orders()
        open_option_orders_data = []
        open_statuses = ["pending", "triggered", "partially_filled"]

        for order in orders:
            # Filter for option orders that are open
            asset = asset_factory(order.symbol)
            if (
                asset
                and isinstance(asset, Option)
                and order.status.lower() in open_statuses
            ):
                open_option_orders_data.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "underlying_symbol": (
                            asset.underlying.symbol if asset.underlying else None
                        ),
                        "option_type": asset.option_type,
                        "strike": asset.strike,
                        "expiration_date": (
                            asset.expiration_date.isoformat()
                            if asset.expiration_date
                            else None
                        ),
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status,
                        "created_at": (
                            order.created_at.isoformat() if order.created_at else None
                        ),
                    }
                )
        data = {
            "open_option_orders": open_option_orders_data,
            "count": len(open_option_orders_data),
            "order_types": ["option"],
            "statuses_included": open_statuses,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("open_option_orders", e)


async def get_order(order_id: str) -> dict[str, Any]:
    """Get a specific order by ID."""
    try:
        order = await get_mcp_trading_service().get_order(order_id)
        data = {
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_order", e)


async def cancel_stock_order_by_id(order_id: str) -> dict[str, Any]:
    """Cancel a specific stock order by ID."""
    try:
        # First check if order exists and is a stock order
        order = await get_mcp_trading_service().get_order(order_id)

        # Determine if it's a stock order
        asset = asset_factory(order.symbol)
        if asset is None:
            return error_response(
                f"Could not determine asset type for symbol: {order.symbol}"
            )
        if hasattr(asset, "asset_type") and asset.asset_type != "stock":
            return error_response(
                f"Order {order_id} is not a stock order (symbol: {order.symbol})"
            )

        # Cancel the order
        result = await get_mcp_trading_service().cancel_order(order_id)

        data = {
            "message": "Stock order cancelled successfully",
            "order_id": order_id,
            "symbol": order.symbol,
            "details": result,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("cancel_stock_order_by_id", e)


async def cancel_option_order_by_id(order_id: str) -> dict[str, Any]:
    """Cancel a specific option order by ID."""
    try:
        # First check if order exists and is an option order
        order = await get_mcp_trading_service().get_order(order_id)

        # Determine if it's an option order
        asset = asset_factory(order.symbol)
        if not isinstance(asset, Option):
            return error_response(
                f"Order {order_id} is not an option order (symbol: {order.symbol})"
            )

        # Cancel the order
        result = await get_mcp_trading_service().cancel_order(order_id)

        data = {
            "message": "Option order cancelled successfully",
            "order_id": order_id,
            "symbol": order.symbol,
            "option_details": {
                "underlying": asset.underlying.symbol if asset.underlying else None,
                "strike": asset.strike,
                "expiration_date": (
                    asset.expiration_date.isoformat() if asset.expiration_date else None
                ),
                "option_type": asset.option_type,
            },
            "details": result,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("cancel_option_order_by_id", e)


async def cancel_all_stock_orders_tool() -> dict[str, Any]:
    """Cancel all pending and triggered stock orders."""
    try:
        result = await get_mcp_trading_service().cancel_all_stock_orders()
        data = {"message": "Stock order cancellation completed", "result": result}
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("cancel_all_stock_orders_tool", e)


async def cancel_all_option_orders_tool() -> dict[str, Any]:
    """Cancel all pending and triggered option orders."""
    try:
        result = await get_mcp_trading_service().cancel_all_option_orders()
        data = {"message": "Option order cancellation completed", "result": result}
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("cancel_all_option_orders_tool", e)


async def portfolio() -> dict[str, Any]:
    """Get complete portfolio information."""
    try:
        portfolio = await get_mcp_trading_service().get_portfolio()
        positions_data = []
        for pos in portfolio.positions:
            positions_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
            )

        data = {
            "cash_balance": portfolio.cash_balance,
            "total_value": portfolio.total_value,
            "positions": positions_data,
            "daily_pnl": portfolio.daily_pnl,
            "total_pnl": portfolio.total_pnl,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("portfolio", e)


async def get_portfolio() -> dict[str, Any]:
    """Get complete portfolio information (deprecated - use portfolio() instead)."""
    return await portfolio()


async def account_details() -> dict[str, Any]:
    """Get portfolio summary with key metrics."""
    try:
        summary = await get_mcp_trading_service().get_portfolio_summary()
        data = {
            "total_value": summary.total_value,
            "cash_balance": summary.cash_balance,
            "invested_value": summary.invested_value,
            "daily_pnl": summary.daily_pnl,
            "daily_pnl_percent": summary.daily_pnl_percent,
            "total_pnl": summary.total_pnl,
            "total_pnl_percent": summary.total_pnl_percent,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("account_details", e)


async def get_portfolio_summary() -> dict[str, Any]:
    """Get portfolio summary with key metrics (deprecated - use account_details() instead)."""
    return await account_details()


async def positions() -> dict[str, Any]:
    """Get all portfolio positions."""
    try:
        positions = await get_mcp_trading_service().get_positions()
        positions_data = []
        for pos in positions:
            positions_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
            )
        return success_response(positions_data)
    except Exception as e:
        return handle_tool_exception("positions", e)


async def get_all_positions() -> dict[str, Any]:
    """Get all portfolio positions (deprecated - use positions() instead)."""
    return await positions()


async def get_position(symbol: str) -> dict[str, Any]:
    """Get a specific position by symbol."""
    try:
        position = await get_mcp_trading_service().get_position(symbol)
        data = {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": position.current_price,
            "unrealized_pnl": position.unrealized_pnl,
            "realized_pnl": position.realized_pnl,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_position", e)


# ============================================================================
# PHASE 4: OPTIONS-SPECIFIC MCP TOOLS
# ============================================================================

# Options-specific functions now use direct parameters


async def get_options_chain(
    symbol: str,
    expiration_date: str | None = None,
    min_strike: float | None = None,
    max_strike: float | None = None,
) -> dict[str, Any]:
    """Get options chain for an underlying symbol with filtering capabilities."""
    try:
        # Parse expiration date if provided
        expiration = None
        if expiration_date:
            expiration = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain_data = await get_mcp_trading_service().get_formatted_options_chain(
            symbol,
            expiration_date=expiration,
            min_strike=min_strike,
            max_strike=max_strike,
        )

        return success_response(chain_data)

    except Exception as e:
        return handle_tool_exception("get_options_chain", e)


async def get_expiration_dates(symbol: str) -> dict[str, Any]:
    """Get available expiration dates for an underlying symbol."""
    try:
        dates = get_mcp_trading_service().get_expiration_dates(symbol)
        dates_data = [d.isoformat() for d in dates]

        data = {
            "underlying_symbol": symbol,
            "expiration_dates": dates_data,
            "count": len(dates_data),
        }
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("get_expiration_dates", e)


async def create_multi_leg_order(
    legs: list[dict[str, Any]], order_type: str = "limit"
) -> dict[str, Any]:
    """Create a multi-leg options order (spreads, straddles, etc.)."""
    try:
        order = await get_mcp_trading_service().create_multi_leg_order_from_request(
            legs, order_type
        )

        # Convert legs for response
        legs_data = []
        for leg in order.legs:
            legs_data.append(
                {
                    "symbol": leg.asset.symbol,
                    "quantity": leg.quantity,
                    "order_type": leg.order_type,
                    "price": leg.price,
                }
            )

        data = {
            "id": order.id,
            "legs": legs_data,
            "net_price": order.net_price,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
        }
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("create_multi_leg_order", e)


async def calculate_option_greeks(
    option_symbol: str, underlying_price: float | None = None
) -> dict[str, Any]:
    """Calculate Greeks for an option symbol."""
    try:
        greeks = await get_mcp_trading_service().calculate_greeks(
            option_symbol, underlying_price=underlying_price
        )

        # Add option details
        asset = asset_factory(option_symbol)
        result: dict[str, Any] = dict(greeks)  # Copy the greeks dict
        if isinstance(asset, Option):
            result.update(
                {
                    "option_symbol": option_symbol,
                    "underlying_symbol": asset.underlying.symbol,
                    "strike": asset.strike,
                    "expiration_date": asset.expiration_date.isoformat(),
                    "option_type": asset.option_type.lower(),
                    "days_to_expiration": asset.get_days_to_expiration(),
                }
            )

        return success_response(result)

    except Exception as e:
        return handle_tool_exception("calculate_option_greeks", e)


async def simulate_option_expiration(
    processing_date: str | None = None, dry_run: bool = True
) -> dict[str, Any]:
    """Simulate option expiration processing for current portfolio."""
    try:
        result = await get_mcp_trading_service().simulate_expiration(
            processing_date=processing_date,
            dry_run=dry_run,
        )
        return success_response(result)

    except Exception as e:
        return handle_tool_exception("simulate_option_expiration", e)


# Additional functions with direct parameters


async def find_tradable_options(
    symbol: str, expiration_date: str | None = None, option_type: str | None = None
) -> dict[str, Any]:
    """
    Find tradable options for a symbol with optional filtering.

    This function provides a unified interface for options discovery
    that works with both test data and live market data.
    """
    try:
        result = await get_mcp_trading_service().find_tradable_options(
            symbol, expiration_date, option_type
        )
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("find_tradable_options", e)


async def get_option_market_data(option_id: str) -> dict[str, Any]:
    """
    Get market data for a specific option contract.

    Provides comprehensive option market data including Greeks,
    pricing, and volume information.
    """
    try:
        result = await get_mcp_trading_service().get_option_market_data(option_id)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("get_option_market_data", e)


async def get_strategy_analysis(
    symbols: list[str], strategy_type: str | None = None
) -> dict[str, Any]:
    """Analyze trading strategies for given symbols."""
    try:
        # This would interface with strategy analysis service
        # For now, return a placeholder response
        data = {
            "symbols": symbols,
            "strategy_type": strategy_type,
            "analysis": "Strategy analysis functionality not yet implemented",
            "recommendation": "Hold",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_strategy_analysis", e)
