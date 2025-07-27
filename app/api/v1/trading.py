"""
Trading API endpoints mirroring MCP tools functionality.

This module provides REST API endpoints that mirror the MCP tools,
allowing both AI agents (via MCP) and web clients (via REST API) 
to access the same trading functionality.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.service_factory import get_trading_service
from app.services.trading_service import TradingService

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Check the health status of the trading system.
    
    Mirrors MCP tool: health_check
    
    Returns:
        Dict containing health status message
    """
    return {"status": "healthy", "message": "Trading system is operational"}


@router.get("/account/balance")
async def get_account_balance() -> Dict[str, Any]:
    """
    Get the current account balance and basic account information.
    
    Mirrors MCP tool: get_account_balance
    
    Returns:
        Dict containing account balance information
        
    Raises:
        HTTPException: If account balance cannot be retrieved
    """
    try:
        service = get_trading_service()
        balance = await service.get_account_balance()
        
        return {
            "success": True,
            "balance": balance,
            "currency": "USD",
            "message": f"Account balance: ${balance:,.2f}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve account balance: {str(e)}"
            }
        )


@router.get("/account/info")
async def get_account_info() -> Dict[str, Any]:
    """
    Get comprehensive account information including balance and basic details.
    
    Mirrors MCP tool: get_account_info
    
    Returns:
        Dict containing comprehensive account information
        
    Raises:
        HTTPException: If account information cannot be retrieved
    """
    try:
        service = get_trading_service()
        
        # Get account details
        account = await service._get_account()
        balance = await service.get_account_balance()
        
        return {
            "success": True,
            "account": {
                "id": account.id,
                "owner": account.owner,
                "cash_balance": balance,
                "currency": "USD",
                "created_at": account.created_at.isoformat() if account.created_at else None,
                "updated_at": account.updated_at.isoformat() if account.updated_at else None
            },
            "message": f"Account {account.id} retrieved successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve account information: {str(e)}"
            }
        )


@router.get("/portfolio")
async def get_portfolio() -> Dict[str, Any]:
    """
    Get comprehensive portfolio information including positions and performance.
    
    Mirrors MCP tool: get_portfolio
    
    Returns:
        Dict containing portfolio information with all positions
        
    Raises:
        HTTPException: If portfolio cannot be retrieved
    """
    try:
        service = get_trading_service()
        portfolio = await service.get_portfolio()
        
        # Convert positions to serializable format
        positions_data = []
        for position in portfolio.positions:
            positions_data.append({
                "symbol": position.symbol,
                "quantity": position.quantity,
                "average_cost": position.average_cost,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pnl,
                "asset_type": position.asset_type,
                "side": position.side
            })
        
        return {
            "success": True,
            "portfolio": {
                "cash_balance": portfolio.cash_balance,
                "total_value": portfolio.total_value,
                "daily_pnl": portfolio.daily_pnl,
                "total_pnl": portfolio.total_pnl,
                "positions_count": len(portfolio.positions),
                "positions": positions_data
            },
            "message": f"Portfolio retrieved with {len(portfolio.positions)} positions"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve portfolio: {str(e)}"
            }
        )


@router.get("/portfolio/summary")
async def get_portfolio_summary() -> Dict[str, Any]:
    """
    Get portfolio summary with key performance metrics.
    
    Mirrors MCP tool: get_portfolio_summary
    
    Returns:
        Dict containing portfolio performance summary
        
    Raises:
        HTTPException: If portfolio summary cannot be retrieved
    """
    try:
        service = get_trading_service()
        summary = await service.get_portfolio_summary()
        
        return {
            "success": True,
            "summary": {
                "total_value": summary.total_value,
                "cash_balance": summary.cash_balance,
                "invested_value": summary.invested_value,
                "daily_pnl": summary.daily_pnl,
                "daily_pnl_percent": summary.daily_pnl_percent,
                "total_pnl": summary.total_pnl,
                "total_pnl_percent": summary.total_pnl_percent
            },
            "message": f"Portfolio value: ${summary.total_value:,.2f}, Daily P&L: ${summary.daily_pnl:,.2f} ({summary.daily_pnl_percent:.2f}%)"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve portfolio summary: {str(e)}"
            }
        )


@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """
    List all available API endpoints with their descriptions.
    
    Mirrors MCP tool: list_tools
    
    Returns:
        Dict containing list of available API endpoints
    """
    tools_list = [
        {
            "name": "get_account_balance",
            "endpoint": "/api/v1/trading/account/balance",
            "method": "GET",
            "description": "Get the current account balance and basic account information"
        },
        {
            "name": "get_account_info", 
            "endpoint": "/api/v1/trading/account/info",
            "method": "GET",
            "description": "Get comprehensive account information including balance and basic details"
        },
        {
            "name": "get_portfolio",
            "endpoint": "/api/v1/trading/portfolio", 
            "method": "GET",
            "description": "Get comprehensive portfolio information including positions and performance"
        },
        {
            "name": "get_portfolio_summary",
            "endpoint": "/api/v1/trading/portfolio/summary",
            "method": "GET", 
            "description": "Get portfolio summary with key performance metrics"
        },
        {
            "name": "health_check",
            "endpoint": "/api/v1/trading/health",
            "method": "GET",
            "description": "Check the health status of the trading system"
        },
        {
            "name": "list_tools",
            "endpoint": "/api/v1/trading/tools",
            "method": "GET",
            "description": "List all available API endpoints with their descriptions"
        }
    ]
    
    # Sort alphabetically by name
    tools_list.sort(key=lambda x: x["name"])
    
    return {
        "success": True,
        "tools": tools_list,
        "count": len(tools_list),
        "message": f"Found {len(tools_list)} available API endpoints"
    }