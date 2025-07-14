from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from app.services.trading_service import trading_service
from app.models.trading import OrderCreate, OrderType


# Initialize FastMCP
mcp = FastMCP("Open Paper Trading MCP")


class GetQuoteArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get quote for (e.g., AAPL, GOOGL)")


class CreateOrderArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float = Field(..., gt=0, description="Price per share")


class GetOrderArgs(BaseModel):
    order_id: str = Field(..., description="Order ID to retrieve")


class CancelOrderArgs(BaseModel):
    order_id: str = Field(..., description="Order ID to cancel")


class GetPositionArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get position for")


@mcp.tool()
def get_stock_quote(args: GetQuoteArgs) -> str:
    """[DEPRECATED] Get current stock quote for a symbol."""
    try:
        quote = trading_service.get_quote(args.symbol)
        return json.dumps({
            "symbol": quote.symbol,
            "price": quote.price,
            "change": quote.change,
            "change_percent": quote.change_percent,
            "volume": quote.volume,
            "last_updated": quote.last_updated.isoformat()
        }, indent=2)
    except Exception as e:
        return f"Error getting quote: {str(e)}"


@mcp.tool()
def create_buy_order(args: CreateOrderArgs) -> str:
    """Create a buy order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.BUY,
            quantity=args.quantity,
            price=args.price
        )
        order = trading_service.create_order(order_data)
        return json.dumps({
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None
        }, indent=2)
    except Exception as e:
        return f"Error creating buy order: {str(e)}"


@mcp.tool()
def create_sell_order(args: CreateOrderArgs) -> str:
    """Create a sell order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.SELL,
            quantity=args.quantity,
            price=args.price
        )
        order = trading_service.create_order(order_data)
        return json.dumps({
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None
        }, indent=2)
    except Exception as e:
        return f"Error creating sell order: {str(e)}"


@mcp.tool()
def get_all_orders() -> str:
    """Get all trading orders."""
    try:
        orders = trading_service.get_orders()
        orders_data = []
        for order in orders:
            orders_data.append({
                "id": order.id,
                "symbol": order.symbol,
                "order_type": order.order_type,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None
            })
        return json.dumps(orders_data, indent=2)
    except Exception as e:
        return f"Error getting orders: {str(e)}"


@mcp.tool()
def get_order(args: GetOrderArgs) -> str:
    """Get a specific order by ID."""
    try:
        order = trading_service.get_order(args.order_id)
        return json.dumps({
            "id": order.id,
            "symbol": order.symbol,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None
        }, indent=2)
    except Exception as e:
        return f"Error getting order: {str(e)}"


@mcp.tool()
def cancel_order(args: CancelOrderArgs) -> str:
    """Cancel a specific order."""
    try:
        result = trading_service.cancel_order(args.order_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error cancelling order: {str(e)}"


@mcp.tool()
def get_portfolio() -> str:
    """Get complete portfolio information."""
    try:
        portfolio = trading_service.get_portfolio()
        positions_data = []
        for pos in portfolio.positions:
            positions_data.append({
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl
            })
        
        return json.dumps({
            "cash_balance": portfolio.cash_balance,
            "total_value": portfolio.total_value,
            "positions": positions_data,
            "daily_pnl": portfolio.daily_pnl,
            "total_pnl": portfolio.total_pnl
        }, indent=2)
    except Exception as e:
        return f"Error getting portfolio: {str(e)}"


@mcp.tool()
def get_portfolio_summary() -> str:
    """Get portfolio summary with key metrics."""
    try:
        summary = trading_service.get_portfolio_summary()
        return json.dumps({
            "total_value": summary.total_value,
            "cash_balance": summary.cash_balance,
            "invested_value": summary.invested_value,
            "daily_pnl": summary.daily_pnl,
            "daily_pnl_percent": summary.daily_pnl_percent,
            "total_pnl": summary.total_pnl,
            "total_pnl_percent": summary.total_pnl_percent
        }, indent=2)
    except Exception as e:
        return f"Error getting portfolio summary: {str(e)}"


@mcp.tool()
def get_all_positions() -> str:
    """Get all portfolio positions."""
    try:
        positions = trading_service.get_positions()
        positions_data = []
        for pos in positions:
            positions_data.append({
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl
            })
        return json.dumps(positions_data, indent=2)
    except Exception as e:
        return f"Error getting positions: {str(e)}"


@mcp.tool()
def get_position(args: GetPositionArgs) -> str:
    """Get a specific position by symbol."""
    try:
        position = trading_service.get_position(args.symbol)
        return json.dumps({
            "symbol": position.symbol,
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": position.current_price,
            "unrealized_pnl": position.unrealized_pnl,
            "realized_pnl": position.realized_pnl
        }, indent=2)
    except Exception as e:
        return f"Error getting position: {str(e)}"