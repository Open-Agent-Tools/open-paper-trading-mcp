"""
MCP tools for options data operations.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.mcp.response_utils import handle_tool_exception, success_response
from app.services.trading_service import TradingService


# Argument classes for backward compatibility with tests
class FindTradableOptionsArgs(BaseModel):
    """Arguments for find_tradable_options function."""

    symbol: str
    expiration_date: str | None = None
    option_type: str | None = None


class GetOptionMarketDataArgs(BaseModel):
    """Arguments for get_option_market_data function."""

    option_id: str


class GetOptionsChainsArgs(BaseModel):
    """Arguments for get_options_chains function."""

    symbol: str


class FindOptionsArgs(BaseModel):
    """Arguments for find_options function."""

    symbol: str
    expiration_date: str | None = None
    option_type: str | None = None


class OptionHistoricalsArgs(BaseModel):
    """Arguments for option_historicals function."""

    symbol: str
    expiration_date: str
    strike_price: float
    option_type: str
    interval: str
    span: str


class OptionMarketDataArgs(BaseModel):
    """Arguments for option_market_data function."""

    option_id: str


class OptionsChainsArgs(BaseModel):
    """Arguments for options_chains function."""

    symbol: str


# MCP tools will receive TradingService instance as dependency
_trading_service: TradingService | None = None


def set_mcp_trading_service(service: TradingService) -> None:
    """Set the trading service for MCP tools."""
    global _trading_service
    _trading_service = service


def get_mcp_trading_service() -> TradingService:
    """Get the trading service for MCP tools."""
    if _trading_service is None:
        raise RuntimeError("TradingService not initialized for MCP tools")
    return _trading_service


# New direct parameter functions (main API)
async def options_chains(symbol: str) -> dict[str, Any]:
    """
    Get complete option chains for a stock symbol.

    Args:
        symbol: Stock symbol to get option chains for (e.g., AAPL, GOOGL)

    Returns:
        Dict containing options chain data or error
    """
    try:
        # Use TradingService to get options chain
        chain_data = await get_mcp_trading_service().get_formatted_options_chain(
            symbol.strip().upper()
        )
        return success_response(chain_data)
    except Exception as e:
        return handle_tool_exception("options_chains", e)


async def find_options(
    symbol: str, expiration_date: str | None, option_type: str | None
) -> dict[str, Any]:
    """
    Find tradable options for a symbol with optional filtering.

    Args:
        symbol: Stock symbol (e.g., AAPL, GOOGL)
        expiration_date: Expiration date in YYYY-MM-DD format (optional)
        option_type: Option type: 'call' or 'put' (optional)

    Returns:
        Dict containing filtered options data or error
    """
    try:
        result = await get_mcp_trading_service().find_tradable_options(
            symbol.strip().upper(), expiration_date, option_type
        )
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("find_options", e)


async def option_market_data(option_id: str) -> dict[str, Any]:
    """
    Get market data for a specific option contract.

    Args:
        option_id: Unique option contract ID

    Returns:
        Dict containing market data or error
    """
    try:
        result = await get_mcp_trading_service().get_option_market_data(option_id)
        return success_response(result)
    except Exception as e:
        return handle_tool_exception("option_market_data", e)


async def option_historicals(
    symbol: str,
    expiration_date: str,
    strike_price: float,
    option_type: str,
    interval: str,
    span: str,
) -> dict[str, Any]:
    """
    Get historical option price data.

    Args:
        symbol: Underlying stock symbol (e.g., AAPL, GOOGL)
        expiration_date: Expiration date in YYYY-MM-DD format
        strike_price: Strike price of the option
        option_type: Option type: 'call' or 'put'
        interval: Data interval: 'minute', 'hour', 'day', 'week'
        span: Time span: 'day', 'week', 'month', 'year'

    Returns:
        Dict containing historical price data or error
    """
    try:
        import random
        from datetime import datetime, timedelta

        from app.models.assets import Option, Stock

        # Validate inputs
        if option_type.lower() not in ["call", "put"]:
            return handle_tool_exception(
                "option_historicals",
                Exception("Invalid option type. Must be 'call' or 'put'"),
            )

        if interval not in ["minute", "hour", "day", "week"]:
            return handle_tool_exception(
                "option_historicals",
                Exception(
                    "Invalid interval. Must be 'minute', 'hour', 'day', or 'week'"
                ),
            )

        if span not in ["day", "week", "month", "year"]:
            return handle_tool_exception(
                "option_historicals",
                Exception("Invalid span. Must be 'day', 'week', 'month', or 'year'"),
            )

        # Parse expiration date
        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
        except ValueError:
            return handle_tool_exception(
                "option_historicals",
                Exception("Invalid expiration date format. Use YYYY-MM-DD"),
            )

        # Create option symbol for lookup
        try:
            underlying = Stock(symbol.strip().upper())
            option = Option(
                underlying=underlying,
                expiration_date=exp_date,
                strike=strike_price,
                option_type=option_type.upper(),
            )
            option_symbol = option.symbol
        except Exception as e:
            return handle_tool_exception(
                "option_historicals", Exception(f"Invalid option parameters: {e!s}")
            )

        # Try to get historical data from adapter if available
        trading_service = get_mcp_trading_service()

        # Check if adapter has historical data capability
        if hasattr(trading_service.quote_adapter, "get_option_historicals"):
            try:
                historicals = (
                    await trading_service.quote_adapter.get_option_historicals(
                        option_symbol, interval, span
                    )
                )
                if historicals:
                    return success_response(
                        {
                            "option_symbol": option_symbol,
                            "underlying_symbol": symbol.upper(),
                            "strike_price": strike_price,
                            "expiration_date": expiration_date,
                            "option_type": option_type.lower(),
                            "interval": interval,
                            "span": span,
                            "data": historicals,
                            "data_source": "live_adapter",
                        }
                    )
            except Exception:
                # Fall through to mock data if adapter fails
                pass

        # Fallback to mock historical data generation
        # Generate mock historical data points
        current_time = datetime.now()
        data_points = []

        # Determine number of data points based on span and interval
        point_count_map = {
            ("minute", "day"): 390,  # Trading minutes in a day
            ("hour", "day"): 7,  # Trading hours in a day
            ("day", "week"): 5,  # Trading days in a week
            ("day", "month"): 22,  # Trading days in a month
            ("day", "year"): 252,  # Trading days in a year
            ("week", "month"): 4,  # Weeks in a month
            ("week", "year"): 52,  # Weeks in a year
        }

        point_count = point_count_map.get((interval, span), 30)

        # Generate base option price (rough approximation)
        try:
            current_quote = await trading_service.get_quote(symbol)
            underlying_price = current_quote.price
        except Exception:
            underlying_price = 100.0  # Fallback price

        # Simple Black-Scholes approximation for base option price
        if option_type.lower() == "call":
            intrinsic_value = max(0, underlying_price - strike_price)
        else:
            intrinsic_value = max(0, strike_price - underlying_price)

        # Rough time value estimate
        days_to_expiry = max(1, (exp_date - datetime.now().date()).days)
        time_value = max(0.01, intrinsic_value * 0.1 + days_to_expiry * 0.02)
        base_option_price = intrinsic_value + time_value

        # Generate historical points
        time_delta_map = {
            "minute": timedelta(minutes=1),
            "hour": timedelta(hours=1),
            "day": timedelta(days=1),
            "week": timedelta(weeks=1),
        }

        time_delta = time_delta_map[interval]

        for i in range(point_count):
            point_time = current_time - (time_delta * (point_count - i - 1))

            # Add some random variation to the base price
            price_variation = random.uniform(0.8, 1.2)
            price = max(0.01, base_option_price * price_variation)

            data_points.append(
                {
                    "timestamp": point_time.isoformat(),
                    "price": round(price, 2),
                    "volume": random.randint(0, 1000),
                    "open_interest": random.randint(100, 5000),
                }
            )

        return success_response(
            {
                "option_symbol": option_symbol,
                "underlying_symbol": symbol.upper(),
                "strike_price": strike_price,
                "expiration_date": expiration_date,
                "option_type": option_type.lower(),
                "interval": interval,
                "span": span,
                "data_points": len(data_points),
                "data": data_points,
                "data_source": "mock_generator",
                "note": "Historical data generated for demonstration purposes",
            }
        )

    except Exception as e:
        return handle_tool_exception("option_historicals", e)


async def aggregate_option_positions() -> dict[str, Any]:
    """
    Get aggregated view of all option positions with Greeks and risk metrics.

    Returns:
        Dict containing aggregated position data and portfolio Greeks
    """
    try:
        trading_service = get_mcp_trading_service()

        # Get all positions
        positions = await trading_service.get_positions()

        option_positions = []
        total_positions = 0
        total_value = 0.0
        total_pnl = 0.0

        # Aggregate Greeks
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0

        for position in positions:
            try:
                # Check if position is an option
                from app.models.assets import Option, asset_factory

                asset = asset_factory(position.symbol)
                if isinstance(asset, Option):
                    total_positions += 1
                    position_value = position.quantity * (position.current_price or 0)
                    total_value += position_value
                    total_pnl += position.unrealized_pnl or 0

                    # Get current option quote with Greeks
                    try:
                        option_quote = await trading_service.get_enhanced_quote(
                            position.symbol
                        )

                        # Calculate position Greeks (per contract * quantity * multiplier)
                        multiplier = 100  # Standard option multiplier
                        pos_delta = (
                            (getattr(option_quote, "delta", 0) or 0)
                            * position.quantity
                            * multiplier
                        )
                        pos_gamma = (
                            (getattr(option_quote, "gamma", 0) or 0)
                            * position.quantity
                            * multiplier
                        )
                        pos_theta = (
                            (getattr(option_quote, "theta", 0) or 0)
                            * position.quantity
                            * multiplier
                        )
                        pos_vega = (
                            (getattr(option_quote, "vega", 0) or 0)
                            * position.quantity
                            * multiplier
                        )
                        pos_rho = (
                            (getattr(option_quote, "rho", 0) or 0)
                            * position.quantity
                            * multiplier
                        )

                        total_delta += pos_delta
                        total_gamma += pos_gamma
                        total_theta += pos_theta
                        total_vega += pos_vega
                        total_rho += pos_rho

                        option_positions.append(
                            {
                                "symbol": position.symbol,
                                "underlying_symbol": asset.underlying.symbol,
                                "strike": asset.strike,
                                "expiration_date": asset.expiration_date.isoformat(),
                                "option_type": asset.option_type.lower(),
                                "quantity": position.quantity,
                                "current_price": position.current_price,
                                "market_value": position_value,
                                "unrealized_pnl": position.unrealized_pnl,
                                "greeks": {
                                    "delta": getattr(option_quote, "delta", None),
                                    "gamma": getattr(option_quote, "gamma", None),
                                    "theta": getattr(option_quote, "theta", None),
                                    "vega": getattr(option_quote, "vega", None),
                                    "rho": getattr(option_quote, "rho", None),
                                },
                                "position_greeks": {
                                    "delta": pos_delta,
                                    "gamma": pos_gamma,
                                    "theta": pos_theta,
                                    "vega": pos_vega,
                                    "rho": pos_rho,
                                },
                                "days_to_expiration": asset.get_days_to_expiration(),
                            }
                        )

                    except Exception as quote_error:
                        # Add position without Greeks if quote fails
                        option_positions.append(
                            {
                                "symbol": position.symbol,
                                "underlying_symbol": asset.underlying.symbol,
                                "strike": asset.strike,
                                "expiration_date": asset.expiration_date.isoformat(),
                                "option_type": asset.option_type.lower(),
                                "quantity": position.quantity,
                                "current_price": position.current_price,
                                "market_value": position_value,
                                "unrealized_pnl": position.unrealized_pnl,
                                "error": f"Could not get Greeks: {quote_error!s}",
                                "days_to_expiration": asset.get_days_to_expiration(),
                            }
                        )

            except Exception:
                # Skip positions that can't be processed
                continue

        return success_response(
            {
                "timestamp": datetime.now().isoformat(),
                "total_option_positions": total_positions,
                "total_market_value": round(total_value, 2),
                "total_unrealized_pnl": round(total_pnl, 2),
                "portfolio_greeks": {
                    "total_delta": round(total_delta, 4),
                    "total_gamma": round(total_gamma, 4),
                    "total_theta": round(total_theta, 4),
                    "total_vega": round(total_vega, 4),
                    "total_rho": round(total_rho, 4),
                },
                "positions": option_positions,
                "summary": {
                    "call_positions": len(
                        [p for p in option_positions if p.get("option_type") == "call"]
                    ),
                    "put_positions": len(
                        [p for p in option_positions if p.get("option_type") == "put"]
                    ),
                    "positions_with_greeks": len(
                        [p for p in option_positions if "greeks" in p]
                    ),
                    "positions_with_errors": len(
                        [p for p in option_positions if "error" in p]
                    ),
                },
            }
        )

    except Exception as e:
        return handle_tool_exception("aggregate_option_positions", e)


async def all_option_positions() -> dict[str, Any]:
    """
    Get detailed information about all option positions (open and closed).

    Returns:
        Dict containing all option positions with full details
    """
    try:
        trading_service = get_mcp_trading_service()

        # Get all positions from the portfolio
        positions = await trading_service.get_positions()

        option_positions = []

        for position in positions:
            try:
                # Check if position is an option
                from app.models.assets import Option, asset_factory

                asset = asset_factory(position.symbol)
                if isinstance(asset, Option):
                    # Get current market data
                    try:
                        option_quote = await trading_service.get_enhanced_quote(
                            position.symbol
                        )
                        underlying_quote = await trading_service.get_enhanced_quote(
                            asset.underlying.symbol
                        )

                        # Calculate intrinsic value
                        if asset.option_type.upper() == "CALL":
                            intrinsic_value = max(
                                0, (underlying_quote.price or 0) - (asset.strike or 0)
                            )
                        else:
                            intrinsic_value = max(
                                0, (asset.strike or 0) - (underlying_quote.price or 0)
                            )

                        time_value = max(0, (option_quote.price or 0) - intrinsic_value)

                        position_data = {
                            "symbol": position.symbol,
                            "underlying_symbol": asset.underlying.symbol,
                            "underlying_price": underlying_quote.price,
                            "strike_price": asset.strike,
                            "expiration_date": asset.expiration_date.isoformat(),
                            "option_type": asset.option_type.lower(),
                            "quantity": position.quantity,
                            "average_cost": position.avg_price,
                            "current_price": option_quote.price,
                            "market_value": position.quantity
                            * (option_quote.price or 0)
                            * 100,
                            "total_cost": position.quantity
                            * (position.avg_price or 0)
                            * 100,
                            "unrealized_pnl": position.unrealized_pnl,
                            "unrealized_pnl_percent": (
                                (
                                    (position.unrealized_pnl or 0)
                                    / (
                                        position.quantity
                                        * (position.avg_price or 1)
                                        * 100
                                    )
                                )
                                * 100
                                if position.avg_price and position.avg_price > 0
                                else 0
                            ),
                            "bid_price": getattr(option_quote, "bid", None),
                            "ask_price": getattr(option_quote, "ask", None),
                            "bid_ask_spread": (
                                (getattr(option_quote, "ask", 0) or 0)
                                - (getattr(option_quote, "bid", 0) or 0)
                                if hasattr(option_quote, "ask")
                                and hasattr(option_quote, "bid")
                                else None
                            ),
                            "volume": getattr(option_quote, "volume", None),
                            "open_interest": getattr(
                                option_quote, "open_interest", None
                            ),
                            "implied_volatility": getattr(option_quote, "iv", None),
                            "intrinsic_value": intrinsic_value,
                            "time_value": time_value,
                            "days_to_expiration": asset.get_days_to_expiration(),
                            "greeks": {
                                "delta": getattr(option_quote, "delta", None),
                                "gamma": getattr(option_quote, "gamma", None),
                                "theta": getattr(option_quote, "theta", None),
                                "vega": getattr(option_quote, "vega", None),
                                "rho": getattr(option_quote, "rho", None),
                            },
                            "status": "open" if position.quantity != 0 else "closed",
                            "last_updated": option_quote.quote_date.isoformat(),
                        }

                        option_positions.append(position_data)

                    except Exception as quote_error:
                        # Add position with basic info if quotes fail
                        option_positions.append(
                            {
                                "symbol": position.symbol,
                                "underlying_symbol": asset.underlying.symbol,
                                "strike_price": asset.strike,
                                "expiration_date": asset.expiration_date.isoformat(),
                                "option_type": asset.option_type.lower(),
                                "quantity": position.quantity,
                                "average_cost": position.avg_price,
                                "days_to_expiration": asset.get_days_to_expiration(),
                                "status": (
                                    "open" if position.quantity != 0 else "closed"
                                ),
                                "error": f"Market data unavailable: {quote_error!s}",
                            }
                        )

            except Exception:
                # Skip positions that can't be processed
                continue

        # Sort positions by expiration date and strike
        option_positions.sort(
            key=lambda x: (
                x.get("expiration_date", ""),
                x.get("underlying_symbol", ""),
                x.get("strike_price", 0),
            )
        )

        # Calculate summary statistics
        total_positions = len(option_positions)
        open_positions = len([p for p in option_positions if p.get("status") == "open"])
        closed_positions = total_positions - open_positions

        total_market_value = 0.0
        total_unrealized_pnl = 0.0

        for p in option_positions:
            if p.get("status") == "open":
                market_val = p.get("market_value")
                if isinstance(market_val, int | float):
                    total_market_value += market_val

                unrealized_pnl = p.get("unrealized_pnl")
                if isinstance(unrealized_pnl, int | float):
                    total_unrealized_pnl += unrealized_pnl

        return success_response(
            {
                "timestamp": datetime.now().isoformat(),
                "total_positions": total_positions,
                "open_positions": open_positions,
                "closed_positions": closed_positions,
                "total_market_value": round(total_market_value, 2),
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "positions": option_positions,
                "summary_by_underlying": {},  # Could be populated with grouping logic
                "summary_by_expiration": {},  # Could be populated with grouping logic
            }
        )

    except Exception as e:
        return handle_tool_exception("all_option_positions", e)


async def open_option_positions() -> dict[str, Any]:
    """
    Get information about currently open option positions only.

    Returns:
        Dict containing open option positions with current market data
    """
    try:
        # Get all option positions first
        all_positions_result = await all_option_positions()

        if "error" in all_positions_result:
            return all_positions_result

        # Filter for only open positions
        open_positions = [
            pos
            for pos in all_positions_result.get("positions", [])
            if pos.get("status") == "open" and pos.get("quantity", 0) != 0
        ]

        # Calculate summary for open positions only
        total_market_value = sum(
            p.get("market_value", 0) for p in open_positions if "market_value" in p
        )

        total_unrealized_pnl = sum(
            p.get("unrealized_pnl", 0) for p in open_positions if "unrealized_pnl" in p
        )

        # Group by underlying for better organization
        positions_by_underlying: dict[str, list[dict[str, Any]]] = {}
        for position in open_positions:
            underlying = position.get("underlying_symbol", "UNKNOWN")
            if underlying not in positions_by_underlying:
                positions_by_underlying[underlying] = []
            positions_by_underlying[underlying].append(position)

        # Calculate risk metrics
        call_positions = len(
            [p for p in open_positions if p.get("option_type") == "call"]
        )
        put_positions = len(
            [p for p in open_positions if p.get("option_type") == "put"]
        )

        # Find positions near expiration (within 7 days)
        near_expiration = []

        for position in open_positions:
            days_to_exp = position.get("days_to_expiration")
            if days_to_exp is not None and days_to_exp <= 7:
                near_expiration.append(position)

        return success_response(
            {
                "timestamp": datetime.now().isoformat(),
                "total_open_positions": len(open_positions),
                "total_market_value": round(total_market_value, 2),
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "positions": open_positions,
                "positions_by_underlying": positions_by_underlying,
                "summary": {
                    "call_positions": call_positions,
                    "put_positions": put_positions,
                    "underlyings_count": len(positions_by_underlying),
                    "positions_near_expiration": len(near_expiration),
                    "positions_with_quotes": len(
                        [p for p in open_positions if "current_price" in p]
                    ),
                    "positions_with_errors": len(
                        [p for p in open_positions if "error" in p]
                    ),
                },
                "risk_alerts": {
                    "near_expiration": near_expiration,
                    "high_unrealized_loss": [
                        p
                        for p in open_positions
                        if p.get("unrealized_pnl_percent", 0)
                        < -20  # Positions down more than 20%
                    ],
                },
            }
        )

    except Exception as e:
        return handle_tool_exception("open_option_positions", e)


# Backward compatibility wrappers for tests
async def find_tradable_options(args: FindTradableOptionsArgs) -> dict[str, Any]:
    """Wrapper for find_options that accepts Pydantic args."""
    return await find_options(args.symbol, args.expiration_date, args.option_type)


async def get_option_market_data(args: GetOptionMarketDataArgs) -> dict[str, Any]:
    """Wrapper for option_market_data that accepts Pydantic args."""
    return await option_market_data(args.option_id)


async def get_options_chains(args: GetOptionsChainsArgs) -> dict[str, Any]:
    """Wrapper for options_chains that accepts Pydantic args."""
    return await options_chains(args.symbol)


async def get_options_chain(symbol: str) -> dict[str, Any]:
    """Alias for options_chains."""
    return await options_chains(symbol)
