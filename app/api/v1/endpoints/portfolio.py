from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from app.models.trading import Position, Portfolio, PortfolioSummary
from app.services.trading_service import trading_service
from app.services.strategies import (
    analyze_strategy_portfolio,
    aggregate_portfolio_greeks,
)
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.get("/", response_model=Portfolio)
async def get_portfolio():
    return trading_service.get_portfolio()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    return trading_service.get_portfolio_summary()


@router.get("/positions", response_model=List[Position])
async def get_positions():
    return trading_service.get_positions()


@router.get("/position/{symbol}", response_model=Position)
async def get_position(symbol: str):
    try:
        return trading_service.get_position(symbol)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/position/{symbol}/greeks")
async def get_position_greeks(symbol: str):
    """Get Greeks for a specific position."""
    try:
        position = trading_service.get_position(symbol)

        # Get current quote for Greeks
        quote = trading_service.get_enhanced_quote(symbol)

        if not hasattr(quote, "delta"):
            raise HTTPException(
                status_code=400, detail="Position is not an options position"
            )

        return {
            "symbol": symbol,
            "position_quantity": position.quantity,
            "multiplier": getattr(position, "multiplier", 100),
            "greeks": {
                "delta": quote.delta,
                "gamma": quote.gamma,
                "theta": quote.theta,
                "vega": quote.vega,
                "rho": quote.rho,
                "iv": getattr(quote, "iv", None),
            },
            "position_greeks": {
                "delta": quote.delta
                * position.quantity
                * getattr(position, "multiplier", 100),
                "gamma": quote.gamma
                * position.quantity
                * getattr(position, "multiplier", 100),
                "theta": quote.theta
                * position.quantity
                * getattr(position, "multiplier", 100),
                "vega": quote.vega
                * position.quantity
                * getattr(position, "multiplier", 100),
                "rho": quote.rho
                * position.quantity
                * getattr(position, "multiplier", 100),
            },
            "underlying_price": getattr(quote, "underlying_price", None),
            "quote_time": quote.quote_date.isoformat(),
        }

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/greeks")
async def get_portfolio_greeks():
    """Get aggregated Greeks for entire portfolio."""
    try:
        positions = trading_service.get_positions()

        # Get quotes for all positions
        current_quotes = {}
        for position in positions:
            try:
                quote = trading_service.get_enhanced_quote(position.symbol)
                current_quotes[position.symbol] = quote
            except Exception:
                continue

        # Aggregate Greeks
        portfolio_greeks = aggregate_portfolio_greeks(positions, current_quotes)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(positions),
            "options_positions": len(
                [
                    p
                    for p in positions
                    if p.symbol in current_quotes
                    and hasattr(current_quotes[p.symbol], "delta")
                ]
            ),
            "portfolio_greeks": {
                "delta": portfolio_greeks.delta,
                "gamma": portfolio_greeks.gamma,
                "theta": portfolio_greeks.theta,
                "vega": portfolio_greeks.vega,
                "rho": portfolio_greeks.rho,
                "delta_normalized": portfolio_greeks.delta_normalized,
                "gamma_normalized": portfolio_greeks.gamma_normalized,
                "theta_normalized": portfolio_greeks.theta_normalized,
                "vega_normalized": portfolio_greeks.vega_normalized,
                "delta_dollars": portfolio_greeks.delta_dollars,
                "gamma_dollars": portfolio_greeks.gamma_dollars,
                "theta_dollars": portfolio_greeks.theta_dollars,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating portfolio Greeks: {str(e)}"
        )


@router.get("/strategies")
async def get_portfolio_strategies():
    """Get strategy analysis for portfolio."""
    try:
        positions = trading_service.get_positions()

        # Analyze strategies
        analysis = analyze_strategy_portfolio(positions)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_positions": analysis["total_positions"],
            "total_strategies": analysis["total_strategies"],
            "strategies": [
                {
                    "strategy_type": strategy.strategy_type,
                    "quantity": strategy.quantity,
                    "asset_symbol": (
                        getattr(strategy, "asset", {}).get("symbol", "unknown")
                        if hasattr(strategy, "asset")
                        else "unknown"
                    ),
                }
                for strategy in analysis["strategies"]
            ],
            "summary": analysis["summary"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing strategies: {str(e)}"
        )


@router.get("/risk")
async def get_portfolio_risk():
    """Get portfolio risk analysis."""
    try:
        positions = trading_service.get_positions()

        # Get current quotes
        current_quotes = {}
        for position in positions:
            try:
                quote = trading_service.get_enhanced_quote(position.symbol)
                current_quotes[position.symbol] = quote
            except Exception:
                continue

        # Calculate basic risk metrics
        total_value = 0.0
        options_value = 0.0
        short_positions = 0
        days_to_nearest_expiration = None

        for position in positions:
            quote = current_quotes.get(position.symbol)
            if quote:
                position_value = abs(position.quantity) * quote.price
                if hasattr(position, "multiplier"):
                    position_value *= position.multiplier

                total_value += position_value

                if hasattr(quote, "delta"):
                    options_value += position_value

                    # Check for short positions
                    if position.quantity < 0:
                        short_positions += 1

                    # Check expiration
                    if (hasattr(position, "asset") 
                        and position.asset is not None
                        and hasattr(position.asset, "expiration_date")):
                        days_to_exp = (
                            position.asset.expiration_date - datetime.now().date()
                        ).days
                        if (
                            days_to_nearest_expiration is None
                            or days_to_exp < days_to_nearest_expiration
                        ):
                            days_to_nearest_expiration = days_to_exp

        # Get portfolio Greeks
        portfolio_greeks = aggregate_portfolio_greeks(positions, current_quotes)

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_value": total_value,
            "options_exposure": options_value,
            "options_percentage": (
                (options_value / total_value * 100) if total_value > 0 else 0
            ),
            "short_positions_count": short_positions,
            "days_to_nearest_expiration": days_to_nearest_expiration,
            "risk_metrics": {
                "delta_exposure": abs(portfolio_greeks.delta),
                "gamma_exposure": abs(portfolio_greeks.gamma),
                "theta_decay_daily": portfolio_greeks.theta,
                "vega_exposure": abs(portfolio_greeks.vega),
                "delta_risk_level": (
                    "high"
                    if abs(portfolio_greeks.delta) > 1000
                    else "medium"
                    if abs(portfolio_greeks.delta) > 500
                    else "low"
                ),
                "theta_risk_level": (
                    "high"
                    if portfolio_greeks.theta < -100
                    else "medium"
                    if portfolio_greeks.theta < -50
                    else "low"
                ),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating portfolio risk: {str(e)}"
        )
