"""
MCP Tools for Open Paper Trading
Trading tools for AI agents including account and portfolio management
"""

import asyncio
import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.service_factory import get_trading_service
from app.core.id_utils import validate_optional_account_id


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
def list_tools() -> Dict[str, Any]:
    """List all available MCP tools with their descriptions"""
    try:
        # Get tools from FastMCP instance
        tools_dict = run_async_safely(mcp.get_tools())
        
        # Format tools for user-friendly display
        tools_list = []
        for tool_name, tool_info in tools_dict.items():
            tools_list.append({
                "name": tool_name,
                "description": tool_info.description or "No description available"
            })
        
        # Sort alphabetically by name
        tools_list.sort(key=lambda x: x["name"])
        
        return {
            "success": True,
            "tools": tools_list,
            "count": len(tools_list),
            "message": f"Found {len(tools_list)} available tools"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to list tools: {str(e)}"
        }


@mcp.tool
def health_check() -> str:
    """Check the health status of the trading system"""
    return "MCP Server is healthy and operational"


@mcp.tool
def get_account_balance(account_id: str = None) -> Dict[str, Any]:
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
            "message": f"Account balance{account_msg}: ${balance:,.2f}"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve account balance: {str(e)}"
        }


@mcp.tool
def get_account_info(account_id: str = None) -> Dict[str, Any]:
    """Get comprehensive account information including balance and basic details
    
    Args:
        account_id: Optional 10-character account ID. If not provided, uses default account.
    """
    try:
        # Validate account_id parameter
        account_id = validate_optional_account_id(account_id)
        
        service = get_trading_service()
        
        # Use the new get_account_info method
        account_info = run_async_safely(service.get_account_info(account_id))
        
        return {
            "success": True,
            "account": {
                **account_info,
                "currency": "USD"
            },
            "message": f"Account {account_info['account_id']} retrieved successfully"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve account information: {str(e)}"
        }


@mcp.tool
def get_portfolio(account_id: str = None) -> Dict[str, Any]:
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
        
        account_msg = f" for account {account_id}" if account_id else ""
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
            "account_id": account_id,
            "message": f"Portfolio{account_msg} retrieved with {len(portfolio.positions)} positions"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve portfolio: {str(e)}"
        }


@mcp.tool
def get_portfolio_summary(account_id: str = None) -> Dict[str, Any]:
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
                "total_pnl_percent": summary.total_pnl_percent
            },
            "account_id": account_id,
            "message": f"Portfolio{account_msg} value: ${summary.total_value:,.2f}, Daily P&L: ${summary.daily_pnl:,.2f} ({summary.daily_pnl_percent:.2f}%)"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "account_id": account_id,
            "message": f"Failed to retrieve portfolio summary: {str(e)}"
        }


@mcp.tool
def get_all_accounts() -> Dict[str, Any]:
    """Get summary of all accounts with their IDs, creation dates, and balances"""
    try:
        service = get_trading_service()
        accounts_summary = run_async_safely(service.get_all_accounts_summary())
        
        # Convert to serializable format
        accounts_data = []
        for account in accounts_summary.accounts:
            accounts_data.append({
                "account_id": account.id,
                "owner": account.owner,
                "created_at": account.created_at.isoformat(),
                "starting_balance": account.starting_balance,
                "current_balance": account.current_balance,
                "change": account.current_balance - account.starting_balance,
                "change_percent": ((account.current_balance - account.starting_balance) / account.starting_balance * 100) if account.starting_balance > 0 else 0
            })
        
        return {
            "success": True,
            "accounts": accounts_data,
            "summary": {
                "total_count": accounts_summary.total_count,
                "total_starting_balance": accounts_summary.total_starting_balance,
                "total_current_balance": accounts_summary.total_current_balance,
                "total_change": accounts_summary.total_current_balance - accounts_summary.total_starting_balance,
                "total_change_percent": ((accounts_summary.total_current_balance - accounts_summary.total_starting_balance) / accounts_summary.total_starting_balance * 100) if accounts_summary.total_starting_balance > 0 else 0
            },
            "message": f"Found {accounts_summary.total_count} accounts with total value ${accounts_summary.total_current_balance:,.2f}"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve accounts: {str(e)}"
        }


# Export the MCP instance for integration with FastAPI
__all__ = ["mcp"]
