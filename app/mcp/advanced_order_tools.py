"""
Advanced order management tools for sophisticated trading strategies.

These tools provide advanced order types and order management capabilities
beyond basic market and limit orders.
"""

from datetime import datetime, timedelta
from typing import Any

from app.mcp.response_utils import handle_tool_exception, success_response


async def create_bracket_order(
    symbol: str,
    quantity: int,
    entry_price: float,
    profit_target: float,
    stop_loss: float,
) -> dict[str, Any]:
    """
    Create a bracket order (entry + profit target + stop loss).

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares
        entry_price: Entry limit price
        profit_target: Profit target price
        stop_loss: Stop loss price
    """
    try:
        symbol = symbol.strip().upper()

        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if entry_price <= 0 or profit_target <= 0 or stop_loss <= 0:
            raise ValueError("All prices must be positive")

        # Validate bracket order logic
        is_long = profit_target > entry_price
        if is_long and stop_loss >= entry_price:
            raise ValueError("Stop loss must be below entry price for long positions")
        if not is_long and stop_loss <= entry_price:
            raise ValueError("Stop loss must be above entry price for short positions")

        # Simulate bracket order creation
        order_id = f"bracket_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create the three legs of the bracket order
        legs = [
            {
                "leg_id": f"{order_id}_entry",
                "order_type": "limit",
                "side": "buy" if is_long else "sell",
                "quantity": quantity,
                "price": entry_price,
                "status": "pending",
                "leg_type": "entry",
            },
            {
                "leg_id": f"{order_id}_profit",
                "order_type": "limit",
                "side": "sell" if is_long else "buy",
                "quantity": quantity,
                "price": profit_target,
                "status": "inactive",  # Activated when entry fills
                "leg_type": "profit_target",
            },
            {
                "leg_id": f"{order_id}_stop",
                "order_type": "stop",
                "side": "sell" if is_long else "buy",
                "quantity": quantity,
                "price": stop_loss,
                "status": "inactive",  # Activated when entry fills
                "leg_type": "stop_loss",
            },
        ]

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "order_type": "bracket",
            "strategy": "long" if is_long else "short",
            "total_quantity": quantity,
            "entry_price": entry_price,
            "profit_target": profit_target,
            "stop_loss": stop_loss,
            "legs": legs,
            "risk_reward_ratio": abs(profit_target - entry_price)
            / abs(entry_price - stop_loss),
            "max_risk": abs(entry_price - stop_loss) * quantity,
            "max_profit": abs(profit_target - entry_price) * quantity,
            "status": "submitted",
            "created_at": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_bracket_order", e)


async def create_oco_order(
    symbol: str,
    quantity: int,
    price1: float,
    order_type1: str,
    price2: float,
    order_type2: str,
) -> dict[str, Any]:
    """
    Create an OCO (One-Cancels-Other) order.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares
        price1: First order price
        order_type1: First order type ("limit" or "stop")
        price2: Second order price
        order_type2: Second order type ("limit" or "stop")
    """
    try:
        symbol = symbol.strip().upper()

        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price1 <= 0 or price2 <= 0:
            raise ValueError("All prices must be positive")
        if order_type1 not in ["limit", "stop"] or order_type2 not in ["limit", "stop"]:
            raise ValueError("Order types must be 'limit' or 'stop'")

        # Generate OCO order ID
        order_id = f"oco_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create the two legs of the OCO order
        legs = [
            {
                "leg_id": f"{order_id}_leg1",
                "order_type": order_type1,
                "side": "sell",  # Assuming exit orders
                "quantity": quantity,
                "price": price1,
                "status": "active",
                "leg_number": 1,
            },
            {
                "leg_id": f"{order_id}_leg2",
                "order_type": order_type2,
                "side": "sell",
                "quantity": quantity,
                "price": price2,
                "status": "active",
                "leg_number": 2,
            },
        ]

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "order_type": "oco",
            "total_quantity": quantity,
            "legs": legs,
            "oco_logic": "When one leg executes, the other will be automatically cancelled",
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_oco_order", e)


async def create_iceberg_order(
    symbol: str,
    total_quantity: int,
    display_quantity: int,
    limit_price: float,
    side: str,
) -> dict[str, Any]:
    """
    Create an iceberg order (large order broken into smaller visible pieces).

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        total_quantity: Total shares to trade
        display_quantity: Shares to show in order book at once
        limit_price: Limit price per share
        side: Order side ("buy" or "sell")
    """
    try:
        symbol = symbol.strip().upper()
        side = side.lower()

        if total_quantity <= 0 or display_quantity <= 0:
            raise ValueError("Quantities must be positive")
        if display_quantity >= total_quantity:
            raise ValueError("Display quantity must be less than total quantity")
        if limit_price <= 0:
            raise ValueError("Limit price must be positive")
        if side not in ["buy", "sell"]:
            raise ValueError("Side must be 'buy' or 'sell'")

        # Calculate iceberg slices
        num_slices = (total_quantity + display_quantity - 1) // display_quantity
        slices = []

        remaining_quantity = total_quantity
        for i in range(num_slices):
            slice_quantity = min(display_quantity, remaining_quantity)
            slices.append(
                {
                    "slice_id": f"slice_{i + 1}",
                    "quantity": slice_quantity,
                    "status": "active" if i == 0 else "pending",
                    "order_number": i + 1,
                }
            )
            remaining_quantity -= slice_quantity

        order_id = f"iceberg_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "order_type": "iceberg",
            "side": side,
            "total_quantity": total_quantity,
            "display_quantity": display_quantity,
            "limit_price": limit_price,
            "slices": slices,
            "total_slices": num_slices,
            "execution_strategy": "Sequential slice execution to minimize market impact",
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_iceberg_order", e)


async def create_twap_order(
    symbol: str,
    quantity: int,
    duration_minutes: int,
    start_time: str = "",
    end_time: str = "",
) -> dict[str, Any]:
    """
    Create a TWAP (Time-Weighted Average Price) order.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Total shares to trade
        duration_minutes: Duration to spread the order over
        start_time: Start time (optional, defaults to now)
        end_time: End time (optional, calculated from duration)
    """
    try:
        symbol = symbol.strip().upper()

        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if duration_minutes <= 0:
            raise ValueError("Duration must be positive")

        # Set default times
        if not start_time:
            start_dt = datetime.now()
        else:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        if not end_time:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        else:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # Calculate TWAP schedule
        interval_minutes = 5  # Execute every 5 minutes
        num_intervals = duration_minutes // interval_minutes
        shares_per_interval = quantity // num_intervals
        remaining_shares = quantity % num_intervals

        schedule = []
        current_time = start_dt

        for i in range(num_intervals):
            interval_shares = shares_per_interval
            if i == num_intervals - 1:  # Last interval gets remainder
                interval_shares += remaining_shares

            schedule.append(
                {
                    "interval": i + 1,
                    "execution_time": current_time.isoformat(),
                    "quantity": interval_shares,
                    "status": "scheduled",
                }
            )
            current_time += timedelta(minutes=interval_minutes)

        order_id = f"twap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "order_type": "twap",
            "total_quantity": quantity,
            "duration_minutes": duration_minutes,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "execution_schedule": schedule,
            "interval_minutes": interval_minutes,
            "num_intervals": num_intervals,
            "algorithm": "Time-weighted average price execution",
            "status": "scheduled",
            "created_at": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_twap_order", e)


async def create_vwap_order(
    symbol: str,
    quantity: int,
    participation_rate: float = 0.20,
    max_percentage: float = 0.50,
) -> dict[str, Any]:
    """
    Create a VWAP (Volume-Weighted Average Price) order.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Total shares to trade
        participation_rate: Target participation rate (0.0-1.0)
        max_percentage: Maximum percentage of volume per interval
    """
    try:
        symbol = symbol.strip().upper()

        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if not 0 < participation_rate <= 1:
            raise ValueError("Participation rate must be between 0 and 1")
        if not 0 < max_percentage <= 1:
            raise ValueError("Max percentage must be between 0 and 1")

        # Simulate volume profile (would use actual historical data)
        volume_profile = [
            {"time": "09:30", "volume_pct": 0.15, "shares_target": 0},
            {"time": "10:00", "volume_pct": 0.12, "shares_target": 0},
            {"time": "10:30", "volume_pct": 0.08, "shares_target": 0},
            {"time": "11:00", "volume_pct": 0.06, "shares_target": 0},
            {"time": "11:30", "volume_pct": 0.05, "shares_target": 0},
            {"time": "12:00", "volume_pct": 0.04, "shares_target": 0},
            {"time": "12:30", "volume_pct": 0.04, "shares_target": 0},
            {"time": "13:00", "volume_pct": 0.05, "shares_target": 0},
            {"time": "13:30", "volume_pct": 0.06, "shares_target": 0},
            {"time": "14:00", "volume_pct": 0.07, "shares_target": 0},
            {"time": "14:30", "volume_pct": 0.08, "shares_target": 0},
            {"time": "15:00", "volume_pct": 0.10, "shares_target": 0},
            {"time": "15:30", "volume_pct": 0.15, "shares_target": 0},
        ]

        # Calculate target shares for each interval
        for interval in volume_profile:
            target_shares = int(quantity * interval["volume_pct"] * participation_rate)
            max_shares = int(quantity * max_percentage)
            interval["shares_target"] = min(target_shares, max_shares)

        # Normalize to ensure total equals quantity
        total_allocated = sum(interval["shares_target"] for interval in volume_profile)
        if total_allocated > 0:
            adjustment_factor = quantity / total_allocated
            for interval in volume_profile:
                interval["shares_target"] = int(
                    interval["shares_target"] * adjustment_factor
                )

        order_id = f"vwap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "order_type": "vwap",
            "total_quantity": quantity,
            "participation_rate": participation_rate,
            "max_percentage": max_percentage,
            "volume_profile": volume_profile,
            "algorithm": "Volume-weighted average price execution",
            "execution_style": "Adaptive to market volume patterns",
            "status": "scheduled",
            "created_at": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("create_vwap_order", e)
