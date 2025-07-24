"""
MCP tools for paper trading account operations.

These tools provide account information, portfolio data, and position management
following the MCP_TOOLS.md specification.
"""

from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def account_info() -> dict[str, Any]:
    """
    Gets basic Robinhood account information.
    """
    try:
        # Get account data from trading service
        service = get_trading_service()
        account = await service._get_account()

        data = {
            "account_id": account.id,
            "account_type": "paper_trading",
            "status": "active",
            "owner": account.owner,
            "created_at": account.created_at.isoformat() + "Z",
            "updated_at": account.updated_at.isoformat() + "Z",
            "cash_balance": account.cash_balance,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("account_info", e)


async def portfolio() -> dict[str, Any]:
    """
    Provides a high-level overview of the portfolio.
    """
    try:
        portfolio = await get_trading_service().get_portfolio()
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


async def account_details() -> dict[str, Any]:
    """
    Gets comprehensive account details including buying power and cash balances.
    """
    try:
        portfolio = await get_trading_service().get_portfolio()
        summary = await get_trading_service().get_portfolio_summary()

        data = {
            "account_id": "DEMO_ACCOUNT",
            "cash_balance": portfolio.cash_balance,
            "buying_power": portfolio.cash_balance,  # For paper trading, buying power = cash balance
            "total_value": summary.total_value,
            "invested_value": summary.invested_value,
            "day_trades_remaining": 3,  # Placeholder for PDT rules
            "account_type": "paper_trading",
            "margin_enabled": False,
            "options_level": 3,
            "crypto_enabled": False,
        }
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("account_details", e)


async def positions() -> dict[str, Any]:
    """
    Gets current stock positions with quantities and values.
    """
    try:
        positions = await get_trading_service().get_positions()
        positions_data = []
        for pos in positions:
            positions_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "market_value": pos.quantity * (pos.current_price or 0),
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_percent": (
                        (
                            (pos.unrealized_pnl or 0)
                            / ((pos.avg_price or 0) * pos.quantity)
                        )
                        * 100
                        if (pos.avg_price or 0) * pos.quantity > 0
                        else 0
                    ),
                    "realized_pnl": pos.realized_pnl,
                }
            )
        return success_response(positions_data)
    except Exception as e:
        return handle_tool_exception("positions", e)
