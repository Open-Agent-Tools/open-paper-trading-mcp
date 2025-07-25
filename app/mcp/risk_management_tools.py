"""
Risk management tools for portfolio and position risk analysis.

These tools provide risk calculation, position sizing, and risk limit monitoring
capabilities for sophisticated risk management.
"""

from datetime import datetime
from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def calculate_position_sizing(
    symbol: str,
    account_risk_percent: float,
    stop_loss_price: float,
    entry_price: float
) -> dict[str, Any]:
    """
    Calculate optimal position size based on risk parameters.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        account_risk_percent: Percentage of account to risk (e.g., 0.02 for 2%)
        stop_loss_price: Stop loss price
        entry_price: Entry price
    """
    try:
        symbol = symbol.strip().upper()
        
        if not 0 < account_risk_percent <= 1:
            raise ValueError("Account risk percent must be between 0 and 1")
        if entry_price <= 0 or stop_loss_price <= 0:
            raise ValueError("Prices must be positive")
        
        # Get account information
        service = get_trading_service()
        account = await service._get_account()
        account_value = account.cash_balance + 50000  # Simulate total account value
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss_price)
        
        # Calculate maximum dollar risk
        max_dollar_risk = account_value * account_risk_percent
        
        # Calculate position size
        shares = int(max_dollar_risk / risk_per_share) if risk_per_share > 0 else 0
        
        # Calculate actual dollar amounts
        position_value = shares * entry_price
        actual_risk = shares * risk_per_share
        actual_risk_percent = (actual_risk / account_value) * 100
        
        # Position sizing validation
        warnings = []
        if position_value > account_value * 0.50:
            warnings.append("Position size exceeds 50% of account value")
        if actual_risk_percent > 5:
            warnings.append("Risk per trade exceeds recommended 5% maximum")
        if shares < 1:
            warnings.append("Calculated position size is less than 1 share")
        
        data = {
            "symbol": symbol,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "account_value": account_value,
            "max_dollar_risk": max_dollar_risk,
            "risk_per_share": risk_per_share,
            "recommended_shares": shares,
            "position_value": position_value,
            "actual_dollar_risk": actual_risk,
            "actual_risk_percent": round(actual_risk_percent, 2),
            "target_risk_percent": round(account_risk_percent * 100, 2),
            "warnings": warnings,
            "risk_reward_analysis": {
                "max_loss": actual_risk,
                "break_even": entry_price,
                "position_leverage": round(position_value / account_value, 2)
            },
            "calculation_date": datetime.now().isoformat()
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("calculate_position_sizing", e)


async def check_risk_limits() -> dict[str, Any]:
    """
    Check current portfolio against predefined risk limits.
    """
    try:
        # Get portfolio information
        service = get_trading_service()
        portfolio = await service.get_portfolio()
        account = await service._get_account()
        
        # Simulate account total value
        total_account_value = account.cash_balance + portfolio.total_value
        
        # Define risk limits
        risk_limits = {
            "max_position_size_percent": 25.0,  # No single position > 25% of portfolio
            "max_sector_allocation_percent": 40.0,  # No sector > 40% of portfolio
            "max_portfolio_var_percent": 5.0,  # Daily VaR < 5% of portfolio
            "min_cash_reserve_percent": 10.0,  # Keep at least 10% in cash
            "max_leverage_ratio": 2.0,  # Maximum 2:1 leverage
            "max_correlation_threshold": 0.80  # No positions with correlation > 0.80
        }
        
        # Check each limit
        limit_violations = []
        limit_warnings = []
        
        # Check position size limits
        for position in portfolio.positions:
            position_percent = (position.total_value / total_account_value) * 100
            if position_percent > risk_limits["max_position_size_percent"]:
                limit_violations.append({
                    "type": "position_size",
                    "symbol": position.symbol,
                    "current_percent": round(position_percent, 2),
                    "limit_percent": risk_limits["max_position_size_percent"],
                    "severity": "high"
                })
            elif position_percent > risk_limits["max_position_size_percent"] * 0.8:
                limit_warnings.append({
                    "type": "position_size_warning",
                    "symbol": position.symbol,
                    "current_percent": round(position_percent, 2),
                    "limit_percent": risk_limits["max_position_size_percent"]
                })
        
        # Check cash reserve
        cash_percent = (account.cash_balance / total_account_value) * 100
        if cash_percent < risk_limits["min_cash_reserve_percent"]:
            limit_violations.append({
                "type": "cash_reserve",
                "current_percent": round(cash_percent, 2),
                "limit_percent": risk_limits["min_cash_reserve_percent"],
                "severity": "medium"
            })
        
        # Simulate sector allocation check
        sector_allocations = {
            "Technology": 35.0,
            "Healthcare": 15.0,
            "Financial": 25.0,
            "Energy": 10.0,
            "Other": 15.0
        }
        
        for sector, allocation in sector_allocations.items():
            if allocation > risk_limits["max_sector_allocation_percent"]:
                limit_violations.append({
                    "type": "sector_allocation",
                    "sector": sector,
                    "current_percent": allocation,
                    "limit_percent": risk_limits["max_sector_allocation_percent"],
                    "severity": "medium"
                })
        
        # Overall risk assessment
        total_violations = len(limit_violations)
        risk_score = total_violations * 10 + len(limit_warnings) * 5
        
        if risk_score >= 30:
            risk_level = "high"
        elif risk_score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        data = {
            "account_value": total_account_value,
            "risk_limits": risk_limits,
            "limit_violations": limit_violations,
            "limit_warnings": limit_warnings,
            "risk_assessment": {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "total_violations": total_violations,
                "total_warnings": len(limit_warnings)
            },
            "compliance_status": "non_compliant" if limit_violations else "compliant",
            "recommendations": [
                "Reduce position sizes that exceed limits",
                "Increase cash reserves if below minimum",
                "Diversify sector allocations",
                "Monitor correlation between positions"
            ] if limit_violations else ["Portfolio within risk limits"],
            "check_date": datetime.now().isoformat()
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("check_risk_limits", e)


async def get_margin_requirements(symbol: str, quantity: int, order_type: str) -> dict[str, Any]:
    """
    Calculate margin requirements for a potential trade.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares
        order_type: Order type ("buy" or "sell")
    """
    try:
        symbol = symbol.strip().upper()
        order_type = order_type.lower()
        
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if order_type not in ["buy", "sell"]:
            raise ValueError("Order type must be 'buy' or 'sell'")
        
        # Simulate margin requirements calculation
        # In reality, this would use actual margin rates and account information
        
        # Get current stock price (simulated)
        current_price = 180.00  # Simulated current price
        position_value = quantity * current_price
        
        # Margin requirements (simplified)
        if order_type == "buy":
            # Buying on margin
            reg_t_requirement = position_value * 0.50  # 50% initial margin
            house_requirement = position_value * 0.30   # 30% house minimum
            maintenance_margin = position_value * 0.25  # 25% maintenance
            
            buying_power_required = reg_t_requirement
            
        else:  # sell (short selling)
            # Short selling requirements
            reg_t_requirement = position_value * 0.50  # 50% initial margin
            sma_requirement = position_value * 1.50    # 150% of short value
            maintenance_margin = position_value * 0.30  # 30% maintenance
            
            buying_power_required = sma_requirement
        
        # Additional requirements
        day_trading_buying_power = position_value * 0.25  # PDT rules
        overnight_buying_power = reg_t_requirement
        
        # Account impact simulation
        service = get_trading_service()
        account = await service._get_account()
        current_buying_power = account.cash_balance  # Simplified
        
        remaining_buying_power = current_buying_power - buying_power_required
        
        data = {
            "symbol": symbol,
            "quantity": quantity,
            "order_type": order_type,
            "position_value": position_value,
            "current_price": current_price,
            "margin_requirements": {
                "reg_t_initial": reg_t_requirement,
                "house_minimum": house_requirement if order_type == "buy" else sma_requirement,
                "maintenance_margin": maintenance_margin,
                "buying_power_required": buying_power_required
            },
            "buying_power_analysis": {
                "current_buying_power": current_buying_power,
                "required_buying_power": buying_power_required,
                "remaining_buying_power": remaining_buying_power,
                "sufficient_funds": remaining_buying_power >= 0
            },
            "special_requirements": {
                "day_trading_bp": day_trading_buying_power,
                "overnight_bp": overnight_buying_power,
                "is_marginable": True,  # Assume stock is marginable
                "hard_to_borrow": False  # Assume not hard to borrow
            },
            "warnings": [
                "Insufficient buying power" if remaining_buying_power < 0 else None,
                "Pattern day trader rules apply" if day_trading_buying_power < buying_power_required else None
            ],
            "calculation_date": datetime.now().isoformat()
        }
        
        # Remove None warnings
        data["warnings"] = [w for w in data["warnings"] if w is not None]
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_margin_requirements", e)


async def calculate_drawdown() -> dict[str, Any]:
    """
    Calculate portfolio drawdown metrics.
    """
    try:
        # Get portfolio information
        service = get_trading_service()
        portfolio = await service.get_portfolio()
        
        # Simulate drawdown calculation
        # In reality, this would use historical portfolio values
        
        current_value = portfolio.total_value
        peak_value = current_value * 1.15  # Simulate previous peak
        
        # Calculate drawdown metrics
        current_drawdown = (peak_value - current_value) / peak_value
        max_drawdown = 0.18  # Simulate historical max drawdown
        avg_drawdown = 0.08  # Average drawdown over time
        
        # Drawdown duration analysis
        days_in_drawdown = 45  # Days since peak
        max_drawdown_duration = 120  # Longest drawdown period
        
        # Recovery analysis
        recovery_time_estimate = days_in_drawdown * 0.8  # Estimated recovery time
        recovery_percentage = (current_value / peak_value) * 100
        
        # Simulate drawdown history
        drawdown_history = [
            {"date": "2024-01-15", "drawdown_percent": 5.2},
            {"date": "2024-01-30", "drawdown_percent": 8.7},
            {"date": "2024-02-14", "drawdown_percent": 12.3},
            {"date": "2024-02-28", "drawdown_percent": 15.1},
            {"date": "2024-03-15", "drawdown_percent": 11.8},
            {"date": "2024-03-30", "drawdown_percent": 8.4}
        ]
        
        data = {
            "current_portfolio_value": current_value,
            "peak_portfolio_value": peak_value,
            "drawdown_metrics": {
                "current_drawdown_percent": round(current_drawdown * 100, 2),
                "max_drawdown_percent": round(max_drawdown * 100, 2),
                "average_drawdown_percent": round(avg_drawdown * 100, 2)
            },
            "duration_analysis": {
                "days_in_current_drawdown": days_in_drawdown,
                "max_drawdown_duration_days": max_drawdown_duration,
                "recovery_time_estimate_days": int(recovery_time_estimate)
            },
            "recovery_analysis": {
                "recovery_percentage": round(recovery_percentage, 2),
                "amount_to_recover": peak_value - current_value,
                "recovery_rate_required": round((peak_value / current_value - 1) * 100, 2)
            },
            "drawdown_history": drawdown_history,
            "risk_assessment": {
                "drawdown_risk": "high" if current_drawdown > 0.15 else "medium" if current_drawdown > 0.08 else "low",
                "recovery_outlook": "challenging" if days_in_drawdown > 90 else "moderate",
                "action_recommended": current_drawdown > 0.20
            },
            "calculation_date": datetime.now().isoformat()
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("calculate_drawdown", e)