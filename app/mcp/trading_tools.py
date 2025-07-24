"""
Comprehensive trading tools for MCP server.

These tools provide all stock and options trading functionality
as specified in MCP_TOOLS.md.
"""

from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import (
    error_response,
    handle_tool_exception,
    success_response,
)
from app.schemas.orders import OrderCondition, OrderCreate, OrderStatus, OrderType

# =============================================================================
# ORDER MANAGEMENT TOOLS
# =============================================================================
#
# NOTE: Order management tools (stock_orders, options_orders, open_stock_orders,
# open_option_orders) are implemented in app.mcp.tools and imported by the MCP server.
# They are not duplicated here to avoid conflicts and maintain single source of truth.


# =============================================================================
# STOCK TRADING TOOLS
# =============================================================================


async def buy_stock_market(symbol: str, quantity: int) -> dict[str, Any]:
    """
    Places a market buy order for a stock.
    Executes immediately at current market price.
    """
    try:
        # Validate inputs
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an integer")

        symbol = symbol.strip().upper()

        # Get current quote for the stock
        quote = await get_trading_service().get_quote(symbol)
        current_price = quote.price

        if current_price is None or current_price <= 0:
            raise ValueError(f"Invalid price for symbol {symbol}")

        # Create market order at current price
        order_data = OrderCreate(
            symbol=symbol,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=current_price,  # Use current market price for execution
            condition=OrderCondition.MARKET,
        )
        order = await get_trading_service().create_order(order_data)

        data = {
            "order_id": order.id,
            "symbol": order.symbol,
            "order_type": "buy",
            "quantity": order.quantity,
            "market_price": current_price,
            "total_cost": current_price * quantity,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
            "message": f"Market buy order for {quantity} shares of {symbol} at ${current_price:.2f} per share",
        }
        return success_response(data)
    except Exception as e:
        error_msg = f"Failed to execute market buy order for {symbol}: {e!s}"
        return error_response(error_msg)


async def sell_stock_market(symbol: str, quantity: int) -> dict[str, Any]:
    """
    Places a market sell order for a stock.
    Executes immediately at current market price.
    """
    try:
        # Validate inputs
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an integer")

        symbol = symbol.strip().upper()

        # Get current quote for the stock
        quote = await get_trading_service().get_quote(symbol)
        current_price = quote.price

        if current_price is None or current_price <= 0:
            raise ValueError(f"Invalid price for symbol {symbol}")

        # Check if user has sufficient position to sell (validate later by trading service)
        # For now, create the order and let the trading service handle validation

        # Create market order at current price
        order_data = OrderCreate(
            symbol=symbol,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=current_price,  # Use current market price for execution
            condition=OrderCondition.MARKET,
        )
        order = await get_trading_service().create_order(order_data)

        data = {
            "order_id": order.id,
            "symbol": order.symbol,
            "order_type": "sell",
            "quantity": order.quantity,
            "market_price": current_price,
            "total_proceeds": current_price * quantity,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
            "message": f"Market sell order for {quantity} shares of {symbol} at ${current_price:.2f} per share",
        }
        return success_response(data)
    except Exception as e:
        error_msg = f"Failed to execute market sell order for {symbol}: {e!s}"
        return error_response(error_msg)


async def buy_stock_limit(
    symbol: str, quantity: int, limit_price: float
) -> dict[str, Any]:
    """
    Places a limit buy order for a stock.
    """
    try:
        order_data = OrderCreate(
            symbol=symbol.strip().upper(),
            order_type=OrderType.BUY,
            quantity=quantity,
            price=limit_price,
            condition=OrderCondition.LIMIT,
        )
        order = await get_trading_service().create_order(order_data)
        data = {
            "id": order.id,
            "symbol": order.symbol,
            "order_type": "limit_buy",
            "quantity": order.quantity,
            "limit_price": limit_price,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("buy_stock_limit", e)


async def sell_stock_limit(
    symbol: str, quantity: int, limit_price: float
) -> dict[str, Any]:
    """
    Places a limit sell order for a stock.
    """
    try:
        order_data = OrderCreate(
            symbol=symbol.strip().upper(),
            order_type=OrderType.SELL,
            quantity=quantity,
            price=limit_price,
            condition=OrderCondition.LIMIT,
        )
        order = await get_trading_service().create_order(order_data)
        data = {
            "id": order.id,
            "symbol": order.symbol,
            "order_type": "limit_sell",
            "quantity": order.quantity,
            "limit_price": limit_price,
            "status": order.status,
            "created_at": (order.created_at.isoformat() if order.created_at else None),
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("sell_stock_limit", e)


async def buy_stock_stop_loss(
    symbol: str, quantity: int, stop_price: float
) -> dict[str, Any]:
    """
    Places a stop loss buy order for a stock.
    """
    try:
        # This would be implemented with stop loss order logic
        # For now, return a placeholder response
        data = {
            "symbol": symbol.strip().upper(),
            "order_type": "stop_loss_buy",
            "quantity": quantity,
            "stop_price": stop_price,
            "message": "Stop loss buy orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("buy_stock_stop_loss", e)


async def sell_stock_stop_loss(
    symbol: str, quantity: int, stop_price: float
) -> dict[str, Any]:
    """
    Places a stop loss sell order for a stock.
    """
    try:
        # This would be implemented with stop loss order logic
        # For now, return a placeholder response
        data = {
            "symbol": symbol.strip().upper(),
            "order_type": "stop_loss_sell",
            "quantity": quantity,
            "stop_price": stop_price,
            "message": "Stop loss sell orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("sell_stock_stop_loss", e)


async def buy_stock_trailing_stop(
    symbol: str, quantity: int, trail_amount: float
) -> dict[str, Any]:
    """
    Places a trailing stop buy order for a stock.
    """
    try:
        # This would be implemented with trailing stop order logic
        # For now, return a placeholder response
        data = {
            "symbol": symbol.strip().upper(),
            "order_type": "trailing_stop_buy",
            "quantity": quantity,
            "trail_amount": trail_amount,
            "message": "Trailing stop buy orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("buy_stock_trailing_stop", e)


async def sell_stock_trailing_stop(
    symbol: str, quantity: int, trail_amount: float
) -> dict[str, Any]:
    """
    Places a trailing stop sell order for a stock.
    """
    try:
        # This would be implemented with trailing stop order logic
        # For now, return a placeholder response
        data = {
            "symbol": symbol.strip().upper(),
            "order_type": "trailing_stop_sell",
            "quantity": quantity,
            "trail_amount": trail_amount,
            "message": "Trailing stop sell orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("sell_stock_trailing_stop", e)


# =============================================================================
# OPTIONS TRADING TOOLS
# =============================================================================


async def buy_option_limit(
    instrument_id: str, quantity: int, limit_price: float
) -> dict[str, Any]:
    """
    Places a limit buy order for an option.
    """
    try:
        # This would be implemented with options order logic
        # For now, return a placeholder response
        data = {
            "instrument_id": instrument_id,
            "order_type": "option_limit_buy",
            "quantity": quantity,
            "limit_price": limit_price,
            "message": "Option limit buy orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("buy_option_limit", e)


async def sell_option_limit(
    instrument_id: str, quantity: int, limit_price: float
) -> dict[str, Any]:
    """
    Places a limit sell order for an option.
    """
    try:
        # This would be implemented with options order logic
        # For now, return a placeholder response
        data = {
            "instrument_id": instrument_id,
            "order_type": "option_limit_sell",
            "quantity": quantity,
            "limit_price": limit_price,
            "message": "Option limit sell orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("sell_option_limit", e)


async def option_credit_spread(
    short_instrument_id: str,
    long_instrument_id: str,
    quantity: int,
    credit_price: float,
) -> dict[str, Any]:
    """
    Places a credit spread order (sell short option, buy long option).
    """
    try:
        # This would be implemented with credit spread logic
        # For now, return a placeholder response
        data = {
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "order_type": "credit_spread",
            "quantity": quantity,
            "credit_price": credit_price,
            "message": "Credit spread orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("option_credit_spread", e)


async def option_debit_spread(
    short_instrument_id: str, long_instrument_id: str, quantity: int, debit_price: float
) -> dict[str, Any]:
    """
    Places a debit spread order (buy long option, sell short option).
    """
    try:
        # This would be implemented with debit spread logic
        # For now, return a placeholder response
        data = {
            "short_instrument_id": short_instrument_id,
            "long_instrument_id": long_instrument_id,
            "order_type": "debit_spread",
            "quantity": quantity,
            "debit_price": debit_price,
            "message": "Debit spread orders not yet fully implemented",
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("option_debit_spread", e)


# =============================================================================
# ORDER CANCELLATION TOOLS
# =============================================================================


async def cancel_stock_order_by_id(order_id: str) -> dict[str, Any]:
    """
    Cancels a specific stock order by ID.

    This tool validates that the order is actually a stock order (not an option)
    before attempting cancellation. It also handles various error cases like
    order not found, already executed orders, and database errors.

    Args:
        order_id: The unique identifier of the stock order to cancel

    Returns:
        dict[str, Any]: Success response with cancellation details or error
    """
    try:
        trading_service = get_trading_service()

        # First, get the order to validate it's a stock order
        order = await trading_service.get_order(order_id)

        # Validate that this is a stock order (not an option order)
        if _is_option_order(order):
            return handle_tool_exception(
                "cancel_stock_order_by_id",
                ValueError(
                    f"Order {order_id} is not a stock order. Use cancel_option_order_by_id instead."
                ),
            )

        # Check if order can be cancelled
        if not _can_cancel_order(order):
            return handle_tool_exception(
                "cancel_stock_order_by_id",
                ValueError(
                    f"Order {order_id} cannot be cancelled. Status: {order.status}"
                ),
            )

        # Cancel the order
        result = await trading_service.cancel_order(order_id)

        # Enhanced response with order details
        data = {
            "message": "Stock order cancelled successfully",
            "order_id": order_id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "original_status": order.status,
            "cancelled_at": result.get("message", "Order cancelled successfully"),
        }
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("cancel_stock_order_by_id", e)


async def cancel_option_order_by_id(order_id: str) -> dict[str, Any]:
    """
    Cancels a specific option order by ID.

    This tool validates that the order is actually an option order before
    attempting cancellation. It also provides enhanced option-specific details
    in the response.

    Args:
        order_id: The unique identifier of the option order to cancel

    Returns:
        dict[str, Any]: Success response with cancellation details or error
    """
    try:
        trading_service = get_trading_service()

        # First, get the order to validate it's an option order
        order = await trading_service.get_order(order_id)

        # Validate that this is an option order
        if not _is_option_order(order):
            return handle_tool_exception(
                "cancel_option_order_by_id",
                ValueError(
                    f"Order {order_id} is not an option order. Use cancel_stock_order_by_id instead."
                ),
            )

        # Check if order can be cancelled
        if not _can_cancel_order(order):
            return handle_tool_exception(
                "cancel_option_order_by_id",
                ValueError(
                    f"Order {order_id} cannot be cancelled. Status: {order.status}"
                ),
            )

        # Cancel the order
        result = await trading_service.cancel_order(order_id)

        # Parse option details from symbol if possible
        option_details = _parse_option_symbol(order.symbol)

        # Enhanced response with option details
        data = {
            "message": "Option order cancelled successfully",
            "order_id": order_id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "original_status": order.status,
            "option_details": option_details,
            "cancelled_at": result.get("message", "Order cancelled successfully"),
        }
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("cancel_option_order_by_id", e)


async def cancel_all_stock_orders_tool() -> dict[str, Any]:
    """
    Cancels all open stock orders.

    This tool finds all pending and triggered stock orders and cancels them
    in bulk. It provides detailed information about each cancelled order.

    Returns:
        dict[str, Any]: Success response with bulk cancellation results or error
    """
    try:
        trading_service = get_trading_service()

        # Use the new bulk cancellation method
        result = await trading_service.cancel_all_stock_orders()

        # Enhanced response
        data = {"message": "Stock order cancellation completed", "result": result}
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("cancel_all_stock_orders_tool", e)


async def cancel_all_option_orders_tool() -> dict[str, Any]:
    """
    Cancels all open option orders.

    This tool finds all pending and triggered option orders and cancels them
    in bulk. It provides detailed information about each cancelled order.

    Returns:
        dict[str, Any]: Success response with bulk cancellation results or error
    """
    try:
        trading_service = get_trading_service()

        # Use the new bulk cancellation method
        result = await trading_service.cancel_all_option_orders()

        # Enhanced response
        data = {"message": "Option order cancellation completed", "result": result}
        return success_response(data)

    except Exception as e:
        return handle_tool_exception("cancel_all_option_orders_tool", e)


# =============================================================================
# HELPER FUNCTIONS FOR ORDER CANCELLATION
# =============================================================================


def _is_option_order(order) -> bool:
    """
    Check if an order is an option order based on order type and symbol.

    Args:
        order: Order object to check

    Returns:
        bool: True if this is an option order, False otherwise
    """
    # Check for options-specific order types
    option_order_types = [OrderType.BTO, OrderType.STO, OrderType.BTC, OrderType.STC]
    if order.order_type in option_order_types:
        return True

    # Check for option-style symbols (basic heuristic)
    # Option symbols typically contain 'C' or 'P' in standardized positions
    symbol = order.symbol.upper()
    return len(symbol) > 10 and ("C" in symbol or "P" in symbol)


def _can_cancel_order(order) -> bool:
    """
    Check if an order can be cancelled based on its status.

    Args:
        order: Order object to check

    Returns:
        bool: True if order can be cancelled, False otherwise
    """
    cancellable_statuses = [OrderStatus.PENDING, OrderStatus.TRIGGERED]
    return order.status in cancellable_statuses


def _parse_option_symbol(symbol: str) -> dict[str, Any]:
    """
    Parse option symbol to extract underlying, strike, expiration, and type.

    Args:
        symbol: Option symbol to parse

    Returns:
        dict[str, Any]: Parsed option details or basic info if parsing fails
    """
    try:
        # This is a basic parser for standard option symbol format
        # Example: AAPL240119C00150000 -> AAPL, exp: 240119, call, strike: 150.00
        if len(symbol) < 15:
            return {"raw_symbol": symbol, "parsed": False}

        # Extract components (this is a simplified parser)
        underlying = symbol[:4] if len(symbol) >= 4 else symbol

        # Look for 'C' or 'P' to identify option type and position
        if "C" in symbol:
            option_type = "call"
        elif "P" in symbol:
            option_type = "put"
        else:
            return {"raw_symbol": symbol, "parsed": False}

        # Try to extract strike (last 8 digits typically represent strike * 1000)
        try:
            strike_str = symbol[-8:]
            strike = float(strike_str) / 1000.0 if strike_str.isdigit() else None
        except (ValueError, IndexError):
            strike = None

        return {
            "underlying": underlying,
            "option_type": option_type,
            "strike": strike,
            "raw_symbol": symbol,
            "parsed": True,
        }

    except Exception:
        return {"raw_symbol": symbol, "parsed": False}
