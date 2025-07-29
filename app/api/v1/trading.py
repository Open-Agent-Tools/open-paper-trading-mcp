"""
Trading API endpoints mirroring MCP tools functionality.

This module provides REST API endpoints that mirror the MCP tools,
allowing both AI agents (via MCP) and web clients (via REST API)
to access the same trading functionality.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError
from app.core.id_utils import validate_optional_account_id
from app.core.service_factory import get_trading_service
from app.schemas.orders import OrderCondition, OrderCreate, OrderType
from app.schemas.users import UserCreate, UserProfile, UserProfileSummary, UserUpdate

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])
logger = logging.getLogger(__name__)


class AccountCreate(BaseModel):
    """Schema for creating a new account."""

    owner: str = Field(
        ..., min_length=2, max_length=50, description="Account owner name"
    )
    starting_balance: float = Field(
        ..., ge=100, le=1000000, description="Starting cash balance (min $100, max $1M)"
    )


def validate_account_id_param(account_id: str | None) -> str | None:
    """Validate account_id parameter and return appropriate error response if invalid."""
    try:
        return validate_optional_account_id(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Invalid account ID format",
                "message": str(e),
                "account_id": account_id,
            },
        ) from None


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Check the health status of the trading system.

    Mirrors MCP tool: health_check

    Returns:
        Dict containing health status message
    """
    return {"status": "healthy", "message": "Trading system is operational"}


@router.get("/account/balance")
async def get_account_balance(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get the current account balance and basic account information.

    Mirrors MCP tool: get_account_balance

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.

    Returns:
        Dict containing account balance information

    Raises:
        HTTPException: If account balance cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        service = get_trading_service()
        balance = await service.get_account_balance(account_id)

        account_msg = f" for account {account_id}" if account_id else ""
        return {
            "success": True,
            "balance": balance,
            "currency": "USD",
            "account_id": account_id,
            "message": f"Account balance{account_msg}: ${balance:,.2f}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve account balance: {e!s}",
            },
        ) from e


@router.get("/account/info")
async def get_account_info(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get comprehensive account information including balance and basic details.

    Mirrors MCP tool: get_account_info

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.

    Returns:
        Dict containing comprehensive account information

    Raises:
        HTTPException: If account information cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        service = get_trading_service()

        # Use the new get_account_info method
        account_info = await service.get_account_info(account_id)

        return {
            "success": True,
            "account": {**account_info, "currency": "USD"},
            "message": f"Account {account_info['account_id']} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve account information: {e!s}",
            },
        ) from e


@router.get("/portfolio")
async def get_portfolio(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get comprehensive portfolio information including positions and performance.

    Mirrors MCP tool: get_portfolio

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.

    Returns:
        Dict containing portfolio information with all positions

    Raises:
        HTTPException: If portfolio cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        service = get_trading_service()
        portfolio = await service.get_portfolio(account_id)

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve portfolio: {e!s}",
            },
        ) from e


@router.get("/portfolio/summary")
async def get_portfolio_summary(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get portfolio summary with key performance metrics.

    Mirrors MCP tool: get_portfolio_summary

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.

    Returns:
        Dict containing portfolio performance summary

    Raises:
        HTTPException: If portfolio summary cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        service = get_trading_service()
        summary = await service.get_portfolio_summary(account_id)

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve portfolio summary: {e!s}",
            },
        ) from e


@router.get("/accounts")
async def get_all_accounts() -> dict[str, Any]:
    """
    Get summary of all accounts with ID, created date, starting balance, and current balance.

    Returns:
        Dict containing list of all account summaries

    Raises:
        HTTPException: If accounts cannot be retrieved
    """
    try:
        service = get_trading_service()
        accounts_summary = await service.get_all_accounts_summary()

        # Convert accounts to serializable format
        accounts_data = []
        for account in accounts_summary.accounts:
            accounts_data.append(
                {
                    "id": account.id,
                    "owner": account.owner,
                    "created_at": account.created_at.isoformat(),
                    "starting_balance": account.starting_balance,
                    "current_balance": account.current_balance,
                    "balance_change": account.current_balance
                    - account.starting_balance,
                    "balance_change_percent": (
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
                "total_balance_change": accounts_summary.total_current_balance
                - accounts_summary.total_starting_balance,
            },
            "message": f"Retrieved {accounts_summary.total_count} accounts",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve accounts: {e!s}",
            },
        ) from e


@router.post("/accounts")
async def create_account(account_data: AccountCreate) -> dict[str, Any]:
    """
    Create a new trading account.

    Args:
        account_data: Account creation data including owner and starting balance

    Returns:
        Dict containing the created account information

    Raises:
        HTTPException: If account creation fails
    """
    try:
        from sqlalchemy import select

        from app.core.id_utils import generate_account_id
        from app.models.database.trading import Account as DBAccount
        from app.storage.database import get_async_session

        async for db in get_async_session():
            # Check for existing account with same owner
            existing_account = await db.execute(
                select(DBAccount).where(DBAccount.owner == account_data.owner)
            )
            if existing_account.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": "Account already exists",
                        "message": f"An account with owner '{account_data.owner}' already exists",
                    },
                )

            # Create new account
            account_id = generate_account_id()

            new_account = DBAccount(
                id=account_id,
                owner=account_data.owner,
                cash_balance=account_data.starting_balance,
                starting_balance=account_data.starting_balance,
            )

            db.add(new_account)
            await db.commit()
            await db.refresh(new_account)

            return {
                "success": True,
                "account": {
                    "id": new_account.id,
                    "owner": new_account.owner,
                    "cash_balance": new_account.cash_balance,
                    "starting_balance": new_account.starting_balance,
                    "created_at": new_account.created_at.isoformat(),
                },
                "message": f"Account created successfully for {account_data.owner}",
            }

        # This should never be reached, but mypy requires it
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Database session unavailable",
                "message": "Failed to create account: Database session could not be established",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to create account: {e!s}",
            },
        ) from e


@router.get("/account/details")
async def get_account_details(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get comprehensive account details including buying power and cash balances.

    Mirrors MCP tool: account_details

    Args:
        account_id: Optional 10-character account ID for multi-account access

    Returns:
        Dict containing comprehensive account details with buying power info

    Raises:
        HTTPException: If account details cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        # Get trading service
        service = get_trading_service()

        # Get account info and portfolio for calculations
        account_info = await service.get_account_info(account_id)
        portfolio = await service.get_portfolio(account_id)

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve account details: {e!s}",
            },
        ) from e


@router.get("/positions")
async def get_positions(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get current stock positions with quantities and values.

    Mirrors MCP tool: positions

    Args:
        account_id: Optional 10-character account ID for multi-account access

    Returns:
        Dict containing current positions data with summary statistics

    Raises:
        HTTPException: If positions cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        # Get trading service and portfolio data
        service = get_trading_service()
        portfolio = await service.get_portfolio(account_id)

        # Extract and format positions
        positions_data = []
        total_value = 0.0
        total_cost_basis = 0.0

        for position in portfolio.positions:
            market_value = position.market_value or 0
            cost_basis = float(position.avg_price) * float(position.quantity)
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
        def get_market_value(x: dict[str, Any]) -> float:
            market_value = x["market_value"]
            if market_value is None:
                return 0.0
            elif isinstance(market_value, int | float):
                return float(market_value)
            else:
                return 0.0

        positions_data.sort(key=get_market_value, reverse=True)

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve positions: {e!s}",
            },
        ) from e


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """
    List all available API endpoints with their descriptions.

    Mirrors MCP tool: list_tools

    Returns:
        Dict containing list of available API endpoints
    """
    tools_list = [
        {
            "name": "get_all_accounts",
            "endpoint": "/api/v1/trading/accounts",
            "method": "GET",
            "description": "Get summary of all accounts with ID, created date, starting balance, and current balance",
        },
        {
            "name": "get_account_balance",
            "endpoint": "/api/v1/trading/account/balance",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get the current account balance and basic account information. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_account_info",
            "endpoint": "/api/v1/trading/account/info",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get comprehensive account information including balance and basic details. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_account_details",
            "endpoint": "/api/v1/trading/account/details",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get comprehensive account details including buying power and cash balances. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_portfolio",
            "endpoint": "/api/v1/trading/portfolio",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get comprehensive portfolio information including positions and performance. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_portfolio_summary",
            "endpoint": "/api/v1/trading/portfolio/summary",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get portfolio summary with key performance metrics. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_positions",
            "endpoint": "/api/v1/trading/positions",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get current stock positions with quantities and values. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "health_check",
            "endpoint": "/api/v1/trading/health",
            "method": "GET",
            "description": "Check the health status of the trading system",
        },
        {
            "name": "list_tools",
            "endpoint": "/api/v1/trading/tools",
            "method": "GET",
            "description": "List all available API endpoints with their descriptions",
        },
        {
            "name": "create_order",
            "endpoint": "/api/v1/trading/orders",
            "method": "POST",
            "description": "Create a new trading order with symbol, quantity, order type, and conditions",
        },
        {
            "name": "get_orders",
            "endpoint": "/api/v1/trading/orders",
            "method": "GET",
            "parameters": "?account_id={optional_account_id}",
            "description": "Get all orders for the account. Supports account_id parameter for multi-account access.",
        },
        {
            "name": "get_order",
            "endpoint": "/api/v1/trading/orders/{order_id}",
            "method": "GET",
            "description": "Get a specific order by ID",
        },
        {
            "name": "cancel_order",
            "endpoint": "/api/v1/trading/orders/{order_id}",
            "method": "DELETE",
            "description": "Cancel a specific order by ID",
        },
        {
            "name": "cancel_all_orders",
            "endpoint": "/api/v1/trading/orders",
            "method": "DELETE",
            "parameters": "?asset_type={stock|option}",
            "description": "Cancel all open orders, optionally filtered by asset type (stock or option)",
        },
        {
            "name": "get_stock_price",
            "endpoint": "/api/v1/trading/stock/price/{symbol}",
            "method": "GET",
            "description": "Get current stock price and basic metrics",
        },
        {
            "name": "get_stock_info",
            "endpoint": "/api/v1/trading/stock/info/{symbol}",
            "method": "GET",
            "description": "Get detailed company information and fundamentals",
        },
        {
            "name": "search_stocks",
            "endpoint": "/api/v1/trading/stocks/search",
            "method": "GET",
            "parameters": "?query={search_query}",
            "description": "Search for stocks by symbol or company name",
        },
        {
            "name": "get_market_hours",
            "endpoint": "/api/v1/trading/market/hours",
            "method": "GET",
            "description": "Get current market hours and status",
        },
        {
            "name": "get_price_history",
            "endpoint": "/api/v1/trading/stock/history/{symbol}",
            "method": "GET",
            "parameters": "?period={time_period}",
            "description": "Get historical price data for a stock",
        },
        {
            "name": "get_stock_ratings",
            "endpoint": "/api/v1/trading/stock/ratings/{symbol}",
            "method": "GET",
            "description": "Get analyst ratings for a stock",
        },
        {
            "name": "get_stock_events",
            "endpoint": "/api/v1/trading/stock/events/{symbol}",
            "method": "GET",
            "description": "Get corporate events for a stock (for owned positions)",
        },
        {
            "name": "get_stock_level2_data",
            "endpoint": "/api/v1/trading/stock/level2/{symbol}",
            "method": "GET",
            "description": "Get Level II market data for a stock (Gold subscription required)",
        },
        {
            "name": "get_stock_orders",
            "endpoint": "/api/v1/trading/orders/stocks",
            "method": "GET",
            "description": "Retrieve a list of recent stock order history and their statuses",
        },
        {
            "name": "get_options_orders",
            "endpoint": "/api/v1/trading/orders/options",
            "method": "GET",
            "description": "Retrieve a list of recent options order history and their statuses",
        },
        {
            "name": "get_open_stock_orders",
            "endpoint": "/api/v1/trading/orders/stocks/open",
            "method": "GET",
            "description": "Retrieve all open stock orders",
        },
        {
            "name": "get_open_option_orders",
            "endpoint": "/api/v1/trading/orders/options/open",
            "method": "GET",
            "description": "Retrieve all open option orders",
        },
        {
            "name": "get_option_chain",
            "endpoint": "/api/v1/trading/options/chain/{underlying}",
            "method": "GET",
            "parameters": "?expiration_date={YYYY-MM-DD}",
            "description": "Get complete options chain for an underlying stock",
        },
        {
            "name": "get_option_quote",
            "endpoint": "/api/v1/trading/options/quote/{option_symbol}",
            "method": "GET",
            "description": "Get market data for a specific option contract",
        },
        {
            "name": "get_option_greeks",
            "endpoint": "/api/v1/trading/options/greeks/{option_symbol}",
            "method": "GET",
            "parameters": "?underlying_price={price}",
            "description": "Calculate option Greeks (delta, gamma, theta, vega, rho)",
        },
        {
            "name": "find_options",
            "endpoint": "/api/v1/trading/options/find/{symbol}",
            "method": "GET",
            "parameters": "?expiration_date={YYYY-MM-DD}&option_type={call|put}",
            "description": "Find tradable options for a stock with optional filtering",
        },
        {
            "name": "get_option_expirations",
            "endpoint": "/api/v1/trading/options/expirations/{underlying}",
            "method": "GET",
            "description": "Get available expiration dates for options on an underlying stock",
        },
        {
            "name": "get_option_strikes",
            "endpoint": "/api/v1/trading/options/strikes/{underlying}",
            "method": "GET",
            "parameters": "?expiration_date={YYYY-MM-DD}&option_type={call|put}",
            "description": "Get available strike prices for options on an underlying stock",
        },
        # Set 5: Stock Trading Tools (8 endpoints)
        {
            "name": "buy_stock",
            "endpoint": "/api/v1/trading/orders/stock/buy",
            "method": "POST",
            "description": "Place a buy order for stocks with flexible order types",
        },
        {
            "name": "sell_stock",
            "endpoint": "/api/v1/trading/orders/stock/sell",
            "method": "POST",
            "description": "Place a sell order for stocks with flexible order types",
        },
        {
            "name": "buy_stock_limit",
            "endpoint": "/api/v1/trading/orders/stock/buy/limit",
            "method": "POST",
            "description": "Place a limit buy order for stocks",
        },
        {
            "name": "sell_stock_limit",
            "endpoint": "/api/v1/trading/orders/stock/sell/limit",
            "method": "POST",
            "description": "Place a limit sell order for stocks",
        },
        {
            "name": "buy_stock_stop",
            "endpoint": "/api/v1/trading/orders/stock/buy/stop",
            "method": "POST",
            "description": "Place a stop buy order for stocks",
        },
        {
            "name": "sell_stock_stop",
            "endpoint": "/api/v1/trading/orders/stock/sell/stop",
            "method": "POST",
            "description": "Place a stop sell order for stocks",
        },
        {
            "name": "buy_stock_stop_limit",
            "endpoint": "/api/v1/trading/orders/stock/buy/stop-limit",
            "method": "POST",
            "description": "Place a stop-limit buy order for stocks",
        },
        {
            "name": "sell_stock_stop_limit",
            "endpoint": "/api/v1/trading/orders/stock/sell/stop-limit",
            "method": "POST",
            "description": "Place a stop-limit sell order for stocks",
        },
    ]

    # Sort alphabetically by name
    tools_list.sort(key=lambda x: x["name"])

    return {
        "success": True,
        "tools": tools_list,
        "count": len(tools_list),
        "message": f"Found {len(tools_list)} available API endpoints",
    }


# ==================== ORDER MANAGEMENT ENDPOINTS ====================


@router.post("/orders")
async def create_order(order_data: OrderCreate) -> dict[str, Any]:
    """
    Create a new trading order.

    Args:
        order_data: Order creation data including symbol, quantity, order type, etc.

    Returns:
        Dict containing the created order information

    Raises:
        HTTPException: If order creation fails
    """
    try:
        service = get_trading_service()
        order = await service.create_order(order_data)

        return {
            "success": True,
            "order": {
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
            },
            "message": f"Order created successfully: {order.order_type} {order.quantity} {order.symbol}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to create order: {e!s}",
            },
        ) from e


@router.get("/orders")
async def get_orders(
    account_id: str | None = Query(
        None, description="Optional 10-character account ID"
    ),
) -> dict[str, Any]:
    """
    Get all orders for the account.

    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.

    Returns:
        Dict containing list of orders

    Raises:
        HTTPException: If orders cannot be retrieved
    """
    try:
        # Validate account_id parameter
        account_id = validate_account_id_param(account_id)

        service = get_trading_service()
        orders = await service.get_orders()

        orders_data = []
        for order in orders:
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

        account_msg = f" for account {account_id}" if account_id else ""
        return {
            "success": True,
            "orders": orders_data,
            "count": len(orders_data),
            "message": f"Retrieved {len(orders_data)} orders{account_msg}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "account_id": account_id,
                "message": f"Failed to retrieve orders: {e!s}",
            },
        ) from e


# ==================== ORDER HISTORY ENDPOINTS ====================


@router.get("/orders/stocks")
async def get_stock_orders() -> dict[str, Any]:
    """
    Retrieve a list of recent stock order history and their statuses.

    Mirrors MCP tool: stock_orders

    Returns:
        Dict containing list of stock orders

    Raises:
        HTTPException: If stock orders cannot be retrieved
    """
    try:
        service = get_trading_service()
        all_orders = await service.get_orders()

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve stock orders: {e!s}",
            },
        ) from e


@router.get("/orders/options")
async def get_options_orders() -> dict[str, Any]:
    """
    Retrieve a list of recent options order history and their statuses.

    Mirrors MCP tool: options_orders

    Returns:
        Dict containing list of options orders

    Raises:
        HTTPException: If options orders cannot be retrieved
    """
    try:
        service = get_trading_service()
        all_orders = await service.get_orders()

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve options orders: {e!s}",
            },
        ) from e


@router.get("/orders/stocks/open")
async def get_open_stock_orders() -> dict[str, Any]:
    """
    Retrieve all open stock orders.

    Mirrors MCP tool: open_stock_orders

    Returns:
        Dict containing list of open stock orders

    Raises:
        HTTPException: If open stock orders cannot be retrieved
    """
    try:
        service = get_trading_service()
        all_orders = await service.get_orders()

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve open stock orders: {e!s}",
            },
        ) from e


@router.get("/orders/options/open")
async def get_open_option_orders() -> dict[str, Any]:
    """
    Retrieve all open option orders.

    Mirrors MCP tool: open_option_orders

    Returns:
        Dict containing list of open option orders

    Raises:
        HTTPException: If open option orders cannot be retrieved
    """
    try:
        service = get_trading_service()
        all_orders = await service.get_orders()

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
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve open option orders: {e!s}",
            },
        ) from e


# ==================== OPTIONS TRADING INFO ENDPOINTS ====================


@router.get("/options/chain/{underlying}")
async def get_option_chain(
    underlying: str, expiration_date: str | None = Query(None)
) -> dict[str, Any]:
    """
    Get complete options chain for an underlying stock.

    Mirrors MCP tool: option_chain

    Args:
        underlying: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format

    Returns:
        Dict containing options chain data

    Raises:
        HTTPException: If options chain cannot be retrieved
    """
    try:
        service = get_trading_service()

        # Parse expiration date if provided
        exp_date = None
        if expiration_date:
            from datetime import datetime

            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        chain = await service.get_options_chain(underlying, exp_date)

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
                    "implied_volatility": option_quote.iv,
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
                    "implied_volatility": option_quote.iv,
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
        logger.error(f"Error retrieving options chain for {underlying}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "underlying": underlying,
                "expiration_filter": expiration_date,
                "message": f"Failed to get options chain for {underlying}: {e!s}",
            },
        ) from e


@router.get("/options/quote/{option_symbol}")
async def get_option_quote(option_symbol: str) -> dict[str, Any]:
    """
    Get market data for a specific option contract.

    Mirrors MCP tool: option_quote

    Args:
        option_symbol: Option symbol (e.g., "AAPL240119C00150000")

    Returns:
        Dict containing option market data

    Raises:
        HTTPException: If option quote cannot be retrieved
    """
    try:
        service = get_trading_service()
        market_data = await service.get_option_market_data(option_symbol)

        if "error" in market_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": market_data["error"],
                    "option_symbol": option_symbol,
                    "message": f"Failed to get option quote: {market_data['error']}",
                },
            )

        return {
            "success": True,
            "option_symbol": option_symbol,
            "quote": market_data,
            "message": f"Option quote for {option_symbol}: ${market_data.get('price', 'N/A')}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving option quote for {option_symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "option_symbol": option_symbol,
                "message": f"Failed to get option quote for {option_symbol}: {e!s}",
            },
        ) from e


@router.get("/options/greeks/{option_symbol}")
async def get_option_greeks(
    option_symbol: str, underlying_price: float | None = Query(None)
) -> dict[str, Any]:
    """
    Calculate option Greeks (delta, gamma, theta, vega, rho).

    Mirrors MCP tool: option_greeks

    Args:
        option_symbol: Option symbol (e.g., "AAPL240119C00150000")
        underlying_price: Optional underlying stock price for calculation

    Returns:
        Dict containing option Greeks

    Raises:
        HTTPException: If Greeks cannot be calculated
    """
    try:
        service = get_trading_service()
        greeks = await service.calculate_greeks(option_symbol, underlying_price)

        return {
            "success": True,
            "option_symbol": option_symbol,
            "underlying_price": underlying_price,
            "greeks": greeks,
            "message": f"Greeks calculated for {option_symbol}",
        }

    except Exception as e:
        logger.error(f"Error calculating Greeks for {option_symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "option_symbol": option_symbol,
                "underlying_price": underlying_price,
                "message": f"Failed to calculate Greeks for {option_symbol}: {e!s}",
            },
        ) from e


@router.get("/options/find/{symbol}")
async def find_options_endpoint(
    symbol: str,
    expiration_date: str | None = Query(None),
    option_type: str | None = Query(None),
) -> dict[str, Any]:
    """
    Find tradable options for a stock with optional filtering.

    Mirrors MCP tool: find_options

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format
        option_type: Optional filter for "call" or "put"

    Returns:
        Dict containing tradable options

    Raises:
        HTTPException: If options cannot be found
    """
    try:
        service = get_trading_service()
        options_data = await service.find_tradable_options(
            symbol, expiration_date, option_type
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
        logger.error(f"Error finding options for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "filters": {
                    "expiration_date": expiration_date,
                    "option_type": option_type,
                },
                "message": f"Failed to find options for {symbol}: {e!s}",
            },
        ) from e


@router.get("/options/expirations/{underlying}")
async def get_option_expirations(underlying: str) -> dict[str, Any]:
    """
    Get available expiration dates for options on an underlying stock.

    Mirrors MCP tool: option_expirations

    Args:
        underlying: Stock symbol (e.g., "AAPL")

    Returns:
        Dict containing expiration dates

    Raises:
        HTTPException: If expirations cannot be retrieved
    """
    try:
        service = get_trading_service()

        # Get full options chain to extract expiration dates
        chain = await service.get_options_chain(underlying)

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

    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "underlying": underlying,
                "message": f"No options data found for {underlying}",
            },
        ) from e
    except Exception as e:
        logger.error(f"Error retrieving option expirations for {underlying}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "underlying": underlying,
                "message": f"Failed to get option expirations for {underlying}: {e!s}",
            },
        ) from e


@router.get("/options/strikes/{underlying}")
async def get_option_strikes(
    underlying: str,
    expiration_date: str | None = Query(None),
    option_type: str | None = Query(None),
) -> dict[str, Any]:
    """
    Get available strike prices for options on an underlying stock.

    Mirrors MCP tool: option_strikes

    Args:
        underlying: Stock symbol (e.g., "AAPL")
        expiration_date: Optional expiration date filter in YYYY-MM-DD format
        option_type: Optional filter for "call" or "put"

    Returns:
        Dict containing strike prices

    Raises:
        HTTPException: If strikes cannot be retrieved
    """
    try:
        service = get_trading_service()

        # Parse expiration date if provided
        exp_date = None
        if expiration_date:
            from datetime import datetime

            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain = await service.get_options_chain(underlying, exp_date)

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
        logger.error(f"Error retrieving option strikes for {underlying}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "underlying": underlying,
                "filters": {
                    "expiration_date": expiration_date,
                    "option_type": option_type,
                },
                "message": f"Failed to get option strikes for {underlying}: {e!s}",
            },
        ) from e


@router.get("/orders/{order_id}")
async def get_order(order_id: str) -> dict[str, Any]:
    """
    Get a specific order by ID.

    Args:
        order_id: The order ID to retrieve

    Returns:
        Dict containing order information

    Raises:
        HTTPException: If order cannot be found or retrieved
    """
    try:
        service = get_trading_service()
        order = await service.get_order(order_id)

        return {
            "success": True,
            "order": {
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
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            },
            "message": f"Order {order_id} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "message": f"Order not found: {e!s}",
            },
        ) from e


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str) -> dict[str, Any]:
    """
    Cancel a specific order by ID.

    Args:
        order_id: The order ID to cancel

    Returns:
        Dict containing cancellation confirmation

    Raises:
        HTTPException: If order cannot be cancelled
    """
    try:
        service = get_trading_service()
        result = await service.cancel_order(order_id)

        return {
            "success": True,
            "order_id": order_id,
            "status": result.get("status", "cancelled"),
            "message": f"Order {order_id} cancelled successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "message": f"Failed to cancel order: {e!s}",
            },
        ) from e


@router.delete("/orders")
async def cancel_all_orders(
    asset_type: str | None = Query(
        None, description="Asset type filter: 'stock' or 'option'"
    ),
) -> dict[str, Any]:
    """
    Cancel all open orders, optionally filtered by asset type.

    Args:
        asset_type: Optional filter for 'stock' or 'option' orders

    Returns:
        Dict containing cancellation summary

    Raises:
        HTTPException: If orders cannot be cancelled
    """
    try:
        service = get_trading_service()

        if asset_type == "stock":
            result = await service.cancel_all_stock_orders()
        elif asset_type == "option":
            result = await service.cancel_all_option_orders()
        elif asset_type is None:
            # Cancel all orders (both stock and option)
            stock_result = await service.cancel_all_stock_orders()
            option_result = await service.cancel_all_option_orders()
            result = {
                "cancelled_count": stock_result.get("cancelled_count", 0)
                + option_result.get("cancelled_count", 0),
                "stock_orders_cancelled": stock_result.get("cancelled_count", 0),
                "option_orders_cancelled": option_result.get("cancelled_count", 0),
            }
        else:
            raise ValueError(
                f"Invalid asset_type: {asset_type}. Must be 'stock', 'option', or None"
            )

        filter_msg = f" {asset_type}" if asset_type else ""
        return {
            "success": True,
            "cancelled_count": result.get("cancelled_count", 0),
            "message": f"Cancelled {result.get('cancelled_count', 0)}{filter_msg} orders",
            **result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "asset_type": asset_type,
                "message": f"Failed to cancel orders: {e!s}",
            },
        ) from e


# ==================== MARKET DATA ENDPOINTS ====================


@router.get("/stock/price/{symbol}")
async def get_stock_price(symbol: str) -> dict[str, Any]:
    """
    Get current stock price and basic metrics.

    Mirrors MCP tool: stock_price

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict containing current stock price and basic metrics

    Raises:
        HTTPException: If stock price cannot be retrieved
    """
    try:
        service = get_trading_service()
        price_data = await service.get_stock_price(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "price_data": price_data,
            "message": f"Stock price for {symbol}: ${price_data.get('price', 'N/A')}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Failed to get stock price for {symbol}: {e!s}",
            },
        ) from e


@router.get("/stock/info/{symbol}")
async def get_stock_info(symbol: str) -> dict[str, Any]:
    """
    Get detailed company information and fundamentals.

    Mirrors MCP tool: stock_info

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict containing detailed company information

    Raises:
        HTTPException: If stock info cannot be retrieved
    """
    try:
        service = get_trading_service()
        info_data = await service.get_stock_info(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "info": info_data,
            "message": f"Company information for {symbol} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Failed to get stock info for {symbol}: {e!s}",
            },
        ) from e


@router.get("/stocks/search")
async def search_stocks(
    query: str = Query(..., description="Search query (symbol or company name)"),
) -> dict[str, Any]:
    """
    Search for stocks by symbol or company name.

    Mirrors MCP tool: search_stocks_tool

    Args:
        query: Search query (symbol or company name)

    Returns:
        Dict containing search results

    Raises:
        HTTPException: If search fails
    """
    try:
        service = get_trading_service()
        search_results = await service.search_stocks(query)

        return {
            "success": True,
            "query": query,
            "results": search_results,
            "message": f"Found {len(search_results.get('results', []))} results for '{query}'",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "query": query,
                "message": f"Failed to search stocks for '{query}': {e!s}",
            },
        ) from e


@router.get("/market/hours")
async def get_market_hours() -> dict[str, Any]:
    """
    Get current market hours and status.

    Mirrors MCP tool: market_hours

    Returns:
        Dict containing market hours and status

    Raises:
        HTTPException: If market hours cannot be retrieved
    """
    try:
        service = get_trading_service()
        hours_data = await service.get_market_hours()

        return {
            "success": True,
            "market_hours": hours_data,
            "message": f"Market status: {hours_data.get('status', 'Unknown')}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to get market hours: {e!s}",
            },
        ) from e


@router.get("/stock/history/{symbol}")
async def get_price_history(
    symbol: str,
    period: str = Query(
        "week", description="Time period (day, week, month, 3month, year, 5year)"
    ),
) -> dict[str, Any]:
    """
    Get historical price data for a stock.

    Mirrors MCP tool: price_history

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        period: Time period ("day", "week", "month", "3month", "year", "5year")

    Returns:
        Dict containing historical price data

    Raises:
        HTTPException: If price history cannot be retrieved
    """
    try:
        service = get_trading_service()
        history_data = await service.get_price_history(symbol, period)

        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "history": history_data,
            "message": f"Price history for {symbol} ({period}) retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "period": period,
                "message": f"Failed to get price history for {symbol}: {e!s}",
            },
        ) from e


@router.get("/stock/ratings/{symbol}")
async def get_stock_ratings(symbol: str) -> dict[str, Any]:
    """
    Get analyst ratings for a stock.

    Mirrors MCP tool: stock_ratings

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict containing analyst ratings

    Raises:
        HTTPException: If stock ratings cannot be retrieved
    """
    try:
        service = get_trading_service()
        ratings_data = await service.get_stock_ratings(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "ratings": ratings_data,
            "message": f"Analyst ratings for {symbol} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Failed to get stock ratings for {symbol}: {e!s}",
            },
        ) from e


@router.get("/stock/events/{symbol}")
async def get_stock_events(symbol: str) -> dict[str, Any]:
    """
    Get corporate events for a stock (for owned positions).

    Mirrors MCP tool: stock_events

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict containing corporate events

    Raises:
        HTTPException: If stock events cannot be retrieved
    """
    try:
        service = get_trading_service()
        events_data = await service.get_stock_events(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "events": events_data,
            "message": f"Corporate events for {symbol} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Failed to get stock events for {symbol}: {e!s}",
            },
        ) from e


@router.get("/stock/level2/{symbol}")
async def get_stock_level2_data(symbol: str) -> dict[str, Any]:
    """
    Get Level II market data for a stock (Gold subscription required).

    Mirrors MCP tool: stock_level2_data

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict containing Level II market data

    Raises:
        HTTPException: If Level II data cannot be retrieved
    """
    try:
        service = get_trading_service()
        level2_data = await service.get_stock_level2_data(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "level2": level2_data,
            "message": f"Level II data for {symbol} retrieved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Failed to get Level II data for {symbol}: {e!s}",
            },
        ) from e


# ==================== SET 5: STOCK TRADING ENDPOINTS ====================


class StockOrderRequest(BaseModel):
    """Schema for stock order requests."""

    symbol: str = Field(..., description="Stock ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    order_type: str = Field(default="market", description="Order type")
    price: float | None = Field(None, description="Price for limit/stop orders")
    account_id: str | None = Field(None, description="Optional account ID")


class StockLimitOrderRequest(BaseModel):
    """Schema for stock limit order requests."""

    symbol: str = Field(..., description="Stock ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    limit_price: float = Field(..., gt=0, description="Limit price")
    account_id: str | None = Field(None, description="Optional account ID")


class StockStopOrderRequest(BaseModel):
    """Schema for stock stop order requests."""

    symbol: str = Field(..., description="Stock ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    stop_price: float = Field(..., gt=0, description="Stop price")
    account_id: str | None = Field(None, description="Optional account ID")


class StockStopLimitOrderRequest(BaseModel):
    """Schema for stock stop-limit order requests."""

    symbol: str = Field(..., description="Stock ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    stop_price: float = Field(..., gt=0, description="Stop price")
    limit_price: float = Field(..., gt=0, description="Limit price")
    account_id: str | None = Field(None, description="Optional account ID")


@router.post("/orders/stock/buy")
async def buy_stock(order_request: StockOrderRequest) -> dict[str, Any]:
    """
    Place a buy order for stocks with flexible order types.

    Mirrors MCP tool: buy_stock

    Args:
        order_request: Stock order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        # Convert order_type string to OrderType enum
        if order_request.order_type.lower() == "buy":
            order_type = OrderType.BUY
        elif order_request.order_type.lower() == "sell":
            order_type = OrderType.SELL
        else:
            order_type = OrderType.BUY  # default for buy_stock function

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=order_type,
            quantity=int(order_request.quantity),
            price=order_request.price,
            condition=order_request.condition
            if hasattr(order_request, "condition")
            else OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "buy",
            "quantity": order_request.quantity,
            "order_type": order_request.order_type,
            "price": order_request.price,
            "account_id": account_id,
            "message": f"Buy order placed successfully for {order_request.quantity} shares of {order_request.symbol}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "buy",
                "quantity": order_request.quantity,
                "order_type": order_request.order_type,
                "price": order_request.price,
                "account_id": order_request.account_id,
                "message": f"Failed to place buy order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/sell")
async def sell_stock(order_request: StockOrderRequest) -> dict[str, Any]:
    """
    Place a sell order for stocks with flexible order types.

    Mirrors MCP tool: sell_stock

    Args:
        order_request: Stock order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        # Convert order_type string to OrderType enum
        if order_request.order_type.lower() == "sell":
            order_type = OrderType.SELL
        elif order_request.order_type.lower() == "buy":
            order_type = OrderType.BUY
        else:
            order_type = OrderType.SELL  # default for sell_stock function

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=order_type,
            quantity=int(order_request.quantity),
            price=order_request.price,
            condition=order_request.condition
            if hasattr(order_request, "condition")
            else OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "sell",
            "quantity": order_request.quantity,
            "order_type": order_request.order_type,
            "price": order_request.price,
            "account_id": account_id,
            "message": f"Sell order placed successfully for {order_request.quantity} shares of {order_request.symbol}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "sell",
                "quantity": order_request.quantity,
                "order_type": order_request.order_type,
                "price": order_request.price,
                "account_id": order_request.account_id,
                "message": f"Failed to place sell order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/buy/limit")
async def buy_stock_limit(order_request: StockLimitOrderRequest) -> dict[str, Any]:
    """
    Place a limit buy order for stocks.

    Mirrors MCP tool: buy_stock_limit

    Args:
        order_request: Stock limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.BUY,
            quantity=int(order_request.quantity),
            price=order_request.limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "buy",
            "quantity": order_request.quantity,
            "order_type": "limit",
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Limit buy order placed for {order_request.quantity} shares of {order_request.symbol} at ${order_request.limit_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "buy",
                "quantity": order_request.quantity,
                "order_type": "limit",
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place limit buy order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/sell/limit")
async def sell_stock_limit(order_request: StockLimitOrderRequest) -> dict[str, Any]:
    """
    Place a limit sell order for stocks.

    Mirrors MCP tool: sell_stock_limit

    Args:
        order_request: Stock limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.SELL,
            quantity=int(order_request.quantity),
            price=order_request.limit_price,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "sell",
            "quantity": order_request.quantity,
            "order_type": "limit",
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Limit sell order placed for {order_request.quantity} shares of {order_request.symbol} at ${order_request.limit_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "sell",
                "quantity": order_request.quantity,
                "order_type": "limit",
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place limit sell order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/buy/stop")
async def buy_stock_stop(order_request: StockStopOrderRequest) -> dict[str, Any]:
    """
    Place a stop buy order for stocks.

    Mirrors MCP tool: buy_stock_stop

    Args:
        order_request: Stock stop order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.STOP_LOSS,
            quantity=int(order_request.quantity),
            price=None,
            condition=OrderCondition.STOP,
            stop_price=order_request.stop_price,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "buy",
            "quantity": order_request.quantity,
            "order_type": "stop",
            "stop_price": order_request.stop_price,
            "account_id": account_id,
            "message": f"Stop buy order placed for {order_request.quantity} shares of {order_request.symbol} with stop at ${order_request.stop_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "buy",
                "quantity": order_request.quantity,
                "order_type": "stop",
                "stop_price": order_request.stop_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place stop buy order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/sell/stop")
async def sell_stock_stop(order_request: StockStopOrderRequest) -> dict[str, Any]:
    """
    Place a stop sell order for stocks.

    Mirrors MCP tool: sell_stock_stop

    Args:
        order_request: Stock stop order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.STOP_LOSS,
            quantity=int(order_request.quantity),
            price=None,
            condition=OrderCondition.STOP,
            stop_price=order_request.stop_price,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "sell",
            "quantity": order_request.quantity,
            "order_type": "stop",
            "stop_price": order_request.stop_price,
            "account_id": account_id,
            "message": f"Stop sell order placed for {order_request.quantity} shares of {order_request.symbol} with stop at ${order_request.stop_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "sell",
                "quantity": order_request.quantity,
                "order_type": "stop",
                "stop_price": order_request.stop_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place stop sell order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/buy/stop-limit")
async def buy_stock_stop_limit(
    order_request: StockStopLimitOrderRequest,
) -> dict[str, Any]:
    """
    Place a stop-limit buy order for stocks.

    Mirrors MCP tool: buy_stock_stop_limit

    Args:
        order_request: Stock stop-limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.STOP_LIMIT,
            quantity=int(order_request.quantity),
            price=order_request.limit_price,
            condition=OrderCondition.STOP_LIMIT,
            stop_price=order_request.stop_price,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "buy",
            "quantity": order_request.quantity,
            "order_type": "stop_limit",
            "stop_price": order_request.stop_price,
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Stop-limit buy order placed for {order_request.quantity} shares of {order_request.symbol} (stop: ${order_request.stop_price}, limit: ${order_request.limit_price})",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "buy",
                "quantity": order_request.quantity,
                "order_type": "stop_limit",
                "stop_price": order_request.stop_price,
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place stop-limit buy order for {order_request.symbol}: {e!s}",
            },
        ) from e


@router.post("/orders/stock/sell/stop-limit")
async def sell_stock_stop_limit(
    order_request: StockStopLimitOrderRequest,
) -> dict[str, Any]:
    """
    Place a stop-limit sell order for stocks.

    Mirrors MCP tool: sell_stock_stop_limit

    Args:
        order_request: Stock stop-limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        order_create = OrderCreate(
            symbol=order_request.symbol,
            order_type=OrderType.STOP_LIMIT,
            quantity=int(order_request.quantity),
            price=order_request.limit_price,
            condition=OrderCondition.STOP_LIMIT,
            stop_price=order_request.stop_price,
            trail_percent=None,
            trail_amount=None,
        )

        order = await service.create_order(order_create)

        return {
            "success": True,
            "order": order,
            "symbol": order_request.symbol,
            "side": "sell",
            "quantity": order_request.quantity,
            "order_type": "stop_limit",
            "stop_price": order_request.stop_price,
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Stop-limit sell order placed for {order_request.quantity} shares of {order_request.symbol} (stop: ${order_request.stop_price}, limit: ${order_request.limit_price})",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "symbol": order_request.symbol,
                "side": "sell",
                "quantity": order_request.quantity,
                "order_type": "stop_limit",
                "stop_price": order_request.stop_price,
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place stop-limit sell order for {order_request.symbol}: {e!s}",
            },
        ) from e


# ==================== SET 6: OPTIONS TRADING ENDPOINTS ====================


class OptionLimitOrderRequest(BaseModel):
    """Schema for option limit order requests."""

    instrument_id: str = Field(..., description="Option instrument ID")
    quantity: int = Field(..., gt=0, description="Number of option contracts")
    limit_price: float = Field(..., gt=0, description="Limit price per contract")
    account_id: str | None = Field(None, description="Optional account ID")


class OptionSpreadOrderRequest(BaseModel):
    """Schema for option spread order requests."""

    short_instrument_id: str = Field(..., description="Short leg option instrument ID")
    long_instrument_id: str = Field(..., description="Long leg option instrument ID")
    quantity: int = Field(..., gt=0, description="Number of spread contracts")
    price: float = Field(..., gt=0, description="Net credit/debit price per spread")
    account_id: str | None = Field(None, description="Optional account ID")


@router.post("/orders/options/buy/limit")
async def buy_option_limit(order_request: OptionLimitOrderRequest) -> dict[str, Any]:
    """
    Place a limit buy order for an option.

    Mirrors MCP tool: buy_option_limit

    Args:
        order_request: Option limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order = await service.create_order(
            OrderCreate(
                symbol=order_request.instrument_id,
                order_type=OrderType.BUY,
                quantity=int(order_request.quantity),
                price=order_request.limit_price,
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        return {
            "success": True,
            "order": order,
            "instrument_id": order_request.instrument_id,
            "side": "buy",
            "quantity": order_request.quantity,
            "order_type": "limit",
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Limit buy order placed for {order_request.quantity} option contracts of {order_request.instrument_id} at ${order_request.limit_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "instrument_id": order_request.instrument_id,
                "side": "buy",
                "quantity": order_request.quantity,
                "order_type": "limit",
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place limit buy order for option {order_request.instrument_id}: {e!s}",
            },
        ) from e


@router.post("/orders/options/sell/limit")
async def sell_option_limit(order_request: OptionLimitOrderRequest) -> dict[str, Any]:
    """
    Place a limit sell order for an option.

    Mirrors MCP tool: sell_option_limit

    Args:
        order_request: Option limit order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        order = await service.create_order(
            OrderCreate(
                symbol=order_request.instrument_id,
                order_type=OrderType.SELL,
                quantity=int(order_request.quantity),
                price=order_request.limit_price,
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        return {
            "success": True,
            "order": order,
            "instrument_id": order_request.instrument_id,
            "side": "sell",
            "quantity": order_request.quantity,
            "order_type": "limit",
            "limit_price": order_request.limit_price,
            "account_id": account_id,
            "message": f"Limit sell order placed for {order_request.quantity} option contracts of {order_request.instrument_id} at ${order_request.limit_price}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "instrument_id": order_request.instrument_id,
                "side": "sell",
                "quantity": order_request.quantity,
                "order_type": "limit",
                "limit_price": order_request.limit_price,
                "account_id": order_request.account_id,
                "message": f"Failed to place limit sell order for option {order_request.instrument_id}: {e!s}",
            },
        ) from e


@router.post("/orders/options/spreads/credit")
async def option_credit_spread(
    order_request: OptionSpreadOrderRequest,
) -> dict[str, Any]:
    """
    Place a credit spread order (sell short option, buy long option).

    Mirrors MCP tool: option_credit_spread

    Args:
        order_request: Option spread order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # Place short leg (sell) order
        short_order = await service.create_order(
            OrderCreate(
                symbol=order_request.short_instrument_id,
                order_type=OrderType.SELL,
                quantity=int(order_request.quantity),
                price=order_request.price,
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        # Place long leg (buy) order for protection
        long_order = await service.create_order(
            OrderCreate(
                symbol=order_request.long_instrument_id,
                order_type=OrderType.BUY,
                quantity=int(order_request.quantity),
                price=0.01,  # Minimal price for protection
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        return {
            "success": True,
            "short_order": short_order,
            "long_order": long_order,
            "strategy": "credit_spread",
            "short_instrument_id": order_request.short_instrument_id,
            "long_instrument_id": order_request.long_instrument_id,
            "quantity": order_request.quantity,
            "credit_price": order_request.price,
            "account_id": account_id,
            "message": f"Credit spread placed: sold {order_request.quantity} contracts of {order_request.short_instrument_id}, bought {order_request.quantity} contracts of {order_request.long_instrument_id} for ${order_request.price} credit",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "strategy": "credit_spread",
                "short_instrument_id": order_request.short_instrument_id,
                "long_instrument_id": order_request.long_instrument_id,
                "quantity": order_request.quantity,
                "credit_price": order_request.price,
                "account_id": order_request.account_id,
                "message": f"Failed to place credit spread: {e!s}",
            },
        ) from e


@router.post("/orders/options/spreads/debit")
async def option_debit_spread(
    order_request: OptionSpreadOrderRequest,
) -> dict[str, Any]:
    """
    Place a debit spread order (buy long option, sell short option).

    Mirrors MCP tool: option_debit_spread

    Args:
        order_request: Option spread order request data

    Returns:
        Dict containing order confirmation

    Raises:
        HTTPException: If order cannot be placed
    """
    try:
        account_id = validate_account_id_param(order_request.account_id)
        service = get_trading_service()

        from app.schemas.orders import OrderCondition, OrderCreate, OrderType

        # Place long leg (buy) order
        long_order = await service.create_order(
            OrderCreate(
                symbol=order_request.long_instrument_id,
                order_type=OrderType.BUY,
                quantity=int(order_request.quantity),
                price=order_request.price,
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        # Place short leg (sell) order
        short_order = await service.create_order(
            OrderCreate(
                symbol=order_request.short_instrument_id,
                order_type=OrderType.SELL,
                quantity=int(order_request.quantity),
                price=0.01,  # Minimal price for short leg
                condition=OrderCondition.LIMIT,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            )
        )

        return {
            "success": True,
            "long_order": long_order,
            "short_order": short_order,
            "strategy": "debit_spread",
            "short_instrument_id": order_request.short_instrument_id,
            "long_instrument_id": order_request.long_instrument_id,
            "quantity": order_request.quantity,
            "debit_price": order_request.price,
            "account_id": account_id,
            "message": f"Debit spread placed: bought {order_request.quantity} contracts of {order_request.long_instrument_id}, sold {order_request.quantity} contracts of {order_request.short_instrument_id} for ${order_request.price} debit",
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "strategy": "debit_spread",
                "short_instrument_id": order_request.short_instrument_id,
                "long_instrument_id": order_request.long_instrument_id,
                "quantity": order_request.quantity,
                "debit_price": order_request.price,
                "account_id": order_request.account_id,
                "message": f"Failed to place debit spread: {e!s}",
            },
        ) from e


# =============================================================================
# Order Cancellation Endpoints (4 endpoints) - Mirrors Set 7 MCP Tools
# =============================================================================


@router.delete("/orders/stocks/all")
async def cancel_all_stock_orders() -> dict[str, Any]:
    """
    Cancel all open stock orders.

    Mirrors MCP tool: cancel_all_stock_orders_tool

    Returns:
        Dict containing cancellation results

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        service = get_trading_service()
        result = await service.cancel_all_stock_orders()

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result["error"],
                    "message": f"Failed to cancel all stock orders: {result['error']}",
                },
            )

        total_cancelled = result.get("total_cancelled", 0)
        return {
            "success": True,
            "total_cancelled": total_cancelled,
            "cancelled_orders": result.get("cancelled_orders", []),
            "message": f"Successfully cancelled {total_cancelled} stock orders",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to cancel all stock orders: {e!s}",
            },
        ) from e


@router.delete("/orders/options/all")
async def cancel_all_option_orders() -> dict[str, Any]:
    """
    Cancel all open option orders.

    Mirrors MCP tool: cancel_all_option_orders_tool

    Returns:
        Dict containing cancellation results

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        service = get_trading_service()
        result = await service.cancel_all_option_orders()

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result["error"],
                    "message": f"Failed to cancel all option orders: {result['error']}",
                },
            )

        total_cancelled = result.get("total_cancelled", 0)
        return {
            "success": True,
            "total_cancelled": total_cancelled,
            "cancelled_orders": result.get("cancelled_orders", []),
            "message": f"Successfully cancelled {total_cancelled} option orders",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to cancel all option orders: {e!s}",
            },
        ) from e


@router.delete("/orders/stocks/{order_id}")
async def cancel_stock_order_by_id(order_id: str) -> dict[str, Any]:
    """
    Cancel a specific stock order by its ID.

    Mirrors MCP tool: cancel_stock_order_by_id

    Args:
        order_id: The ID of the stock order to cancel

    Returns:
        Dict containing cancellation result

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        service = get_trading_service()
        result = await service.cancel_order(order_id)

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result["error"],
                    "order_id": order_id,
                    "message": f"Failed to cancel stock order {order_id}: {result['error']}",
                },
            )

        return {
            "success": True,
            "order_id": order_id,
            "result": result,
            "message": f"Stock order {order_id} cancelled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "message": f"Failed to cancel stock order {order_id}: {e!s}",
            },
        ) from e


@router.delete("/orders/options/{order_id}")
async def cancel_option_order_by_id(order_id: str) -> dict[str, Any]:
    """
    Cancel a specific option order by its ID.

    Mirrors MCP tool: cancel_option_order_by_id

    Args:
        order_id: The ID of the option order to cancel

    Returns:
        Dict containing cancellation result

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        service = get_trading_service()
        result = await service.cancel_order(order_id)

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result["error"],
                    "order_id": order_id,
                    "message": f"Failed to cancel option order {order_id}: {result['error']}",
                },
            )

        return {
            "success": True,
            "order_id": order_id,
            "result": result,
            "message": f"Option order {order_id} cancelled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "message": f"Failed to cancel option order {order_id}: {e!s}",
            },
        ) from e


# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================


@router.post("/users", response_model=UserProfile)
async def create_user(user_data: UserCreate) -> UserProfile:
    """Create a new user profile."""
    try:
        trading_service = get_trading_service()
        user_profile = await trading_service.create_user_profile(user_data)
        return user_profile
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Invalid user data",
                "message": str(e),
            },
        ) from e
    except Exception as e:
        logger.error(f"Failed to create user: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to create user: {e!s}",
            },
        ) from e


@router.get("/users/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str) -> UserProfile:
    """Get user profile by ID."""
    try:
        trading_service = get_trading_service()
        user_profile = await trading_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": "User not found",
                    "message": f"No user found with ID: {user_id}",
                    "user_id": user_id,
                },
            )
        return user_profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user profile {user_id}: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to get user profile: {e!s}",
                "user_id": user_id,
            },
        ) from e


@router.put("/users/{user_id}", response_model=UserProfile)
async def update_user_profile(user_id: str, user_data: UserUpdate) -> UserProfile:
    """Update user profile."""
    try:
        trading_service = get_trading_service()
        user_profile = await trading_service.update_user_profile(user_id, user_data)
        if not user_profile:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": "User not found",
                    "message": f"No user found with ID: {user_id}",
                    "user_id": user_id,
                },
            )
        return user_profile
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Invalid user data",
                "message": str(e),
                "user_id": user_id,
            },
        ) from e
    except Exception as e:
        logger.error(f"Failed to update user profile {user_id}: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to update user profile: {e!s}",
                "user_id": user_id,
            },
        ) from e


@router.delete("/users/{user_id}")
async def delete_user_profile(user_id: str) -> dict[str, Any]:
    """Delete user profile."""
    try:
        trading_service = get_trading_service()
        success = await trading_service.delete_user_profile(user_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": "User not found",
                    "message": f"No user found with ID: {user_id}",
                    "user_id": user_id,
                },
            )
        return {
            "success": True,
            "message": f"User {user_id} deleted successfully",
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user profile {user_id}: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to delete user profile: {e!s}",
                "user_id": user_id,
            },
        ) from e


@router.get("/users", response_model=list[UserProfileSummary])
async def list_users(
    limit: int = Query(
        default=50, ge=1, le=1000, description="Maximum number of users to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of users to skip"),
    verified_only: bool = Query(
        default=False, description="Only return verified users"
    ),
) -> list[UserProfileSummary]:
    """List user profiles with pagination."""
    try:
        trading_service = get_trading_service()
        users = await trading_service.list_users(
            limit=limit, offset=offset, verified_only=verified_only
        )
        return users
    except Exception as e:
        logger.error(f"Failed to list users: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to list users: {e!s}",
            },
        ) from e


@router.get("/users/{user_id}/accounts", response_model=list[dict[str, Any]])
async def get_user_accounts(user_id: str) -> list[dict[str, Any]]:
    """Get all accounts for a user."""
    try:
        trading_service = get_trading_service()
        accounts = await trading_service.get_user_accounts(user_id)
        return accounts
    except Exception as e:
        logger.error(f"Failed to get user accounts for {user_id}: {e!s}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to get user accounts: {e!s}",
                "user_id": user_id,
            },
        ) from e
