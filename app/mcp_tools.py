"""
MCP Tools for Open Paper Trading
Trading tools for AI agents including account and portfolio management
"""

import asyncio
import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.service_factory import get_trading_service


def run_async_safely(coro):
    """Safely run async coroutine in sync context"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(coro)

# Initialize FastMCP instance
mcp = FastMCP("Open Paper Trading MCP")


@mcp.tool
def health_check() -> str:
    """Check the health status of the trading system"""
    return "MCP Server is healthy and operational"


@mcp.tool
def get_account_balance() -> Dict[str, Any]:
    """Get the current account balance and basic account information"""
    try:
        service = get_trading_service()
        balance = run_async_safely(service.get_account_balance())
        
        return {
            "success": True,
            "balance": balance,
            "currency": "USD",
            "message": f"Account balance: ${balance:,.2f}"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve account balance: {str(e)}"
        }


@mcp.tool
def get_account_info() -> Dict[str, Any]:
    """Get comprehensive account information including balance and basic details"""
    try:
        service = get_trading_service()
        
        # Get account details
        account = run_async_safely(service._get_account())
        balance = run_async_safely(service.get_account_balance())
        
        return {
            "success": True,
            "account": {
                "id": account.id,
                "name": account.name,
                "owner": account.owner,
                "cash_balance": balance,
                "currency": "USD"
            },
            "message": f"Account {account.id} retrieved successfully"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve account information: {str(e)}"
        }


@mcp.tool
def get_portfolio() -> Dict[str, Any]:
    """Get comprehensive portfolio information including positions and performance"""
    try:
        service = get_trading_service()
        portfolio = run_async_safely(service.get_portfolio())
        
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
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve portfolio: {str(e)}"
        }


@mcp.tool
def get_portfolio_summary() -> Dict[str, Any]:
    """Get portfolio summary with key performance metrics"""
    try:
        service = get_trading_service()
        summary = run_async_safely(service.get_portfolio_summary())
        
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
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve portfolio summary: {str(e)}"
        }


# Export the MCP instance for integration with FastAPI
__all__ = ["mcp"]
