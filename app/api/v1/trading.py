"""
Trading API endpoints mirroring MCP tools functionality.

This module provides REST API endpoints that mirror the MCP tools,
allowing both AI agents (via MCP) and web clients (via REST API)
to access the same trading functionality.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.id_utils import validate_optional_account_id
from app.core.service_factory import get_trading_service

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


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
    ]

    # Sort alphabetically by name
    tools_list.sort(key=lambda x: x["name"])

    return {
        "success": True,
        "tools": tools_list,
        "count": len(tools_list),
        "message": f"Found {len(tools_list)} available API endpoints",
    }
