from pydantic import BaseModel, Field
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.services.trading_service import trading_service
from app.schemas.orders import (
    OrderCreate,
    OrderType,
    OrderCondition,
)
from app.models.assets import asset_factory, Option


class GetQuoteArgs(BaseModel):
    symbol: str = Field(
        ..., description="Stock symbol to get quote for (e.g., AAPL, GOOGL)"
    )


class CreateOrderArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    order_type: OrderType = Field(..., description="Order type: buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares to trade")
    price: float = Field(..., gt=0, description="Price per share")


class GetOrderArgs(BaseModel):
    order_id: str = Field(..., description="Order ID to retrieve")


class CancelOrderArgs(BaseModel):
    order_id: str = Field(..., description="Order ID to cancel")


class GetPositionArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol to get position for")


def get_stock_quote(args: GetQuoteArgs) -> str:
    """[DEPRECATED] Get current stock quote for a symbol."""
    try:
        quote = trading_service.get_quote(args.symbol)
        return json.dumps(
            {
                "symbol": quote.symbol,
                "price": quote.price,
                "change": quote.change,
                "change_percent": quote.change_percent,
                "volume": quote.volume,
                "last_updated": quote.last_updated.isoformat(),
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting quote: {str(e)}"


async def create_buy_order(args: CreateOrderArgs) -> str:
    """Create a buy order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.BUY,
            quantity=args.quantity,
            price=args.price,
            condition=OrderCondition.MARKET,
        )
        order = await trading_service.create_order(order_data)
        return json.dumps(
            {
                "id": order.id,
                "symbol": order.symbol,
                "order_type": order.order_type,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status,
                "created_at": (
                    order.created_at.isoformat() if order.created_at else None
                ),
            },
            indent=2,
        )
    except Exception as e:
        return f"Error creating buy order: {str(e)}"


async def create_sell_order(args: CreateOrderArgs) -> str:
    """Create a sell order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.SELL,
            quantity=args.quantity,
            price=args.price,
            condition=OrderCondition.MARKET,
        )
        order = await trading_service.create_order(order_data)
        return json.dumps(
            {
                "id": order.id,
                "symbol": order.symbol,
                "order_type": order.order_type,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status,
                "created_at": (
                    order.created_at.isoformat() if order.created_at else None
                ),
            },
            indent=2,
        )
    except Exception as e:
        return f"Error creating sell order: {str(e)}"


async def get_all_orders() -> str:
    """Get all trading orders."""
    try:
        orders = await trading_service.get_orders()
        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "order_type": order.order_type,
                    "quantity": order.quantity,
                    "price": order.price,
                    "status": order.status,
                    "created_at": (
                        order.created_at.isoformat() if order.created_at else None
                    ),
                    "filled_at": (
                        order.filled_at.isoformat() if order.filled_at else None
                    ),
                }
            )
        return json.dumps(orders_data, indent=2)
    except Exception as e:
        return f"Error getting orders: {str(e)}"


async def get_order(args: GetOrderArgs) -> str:
    """Get a specific order by ID."""
    try:
        order = await trading_service.get_order(args.order_id)
        return json.dumps(
            {
                "id": order.id,
                "symbol": order.symbol,
                "order_type": order.order_type,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status,
                "created_at": (
                    order.created_at.isoformat() if order.created_at else None
                ),
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting order: {str(e)}"


def cancel_order(args: CancelOrderArgs) -> str:
    """Cancel a specific order."""
    try:
        result = trading_service.cancel_order(args.order_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error cancelling order: {str(e)}"


async def get_portfolio() -> str:
    """Get complete portfolio information."""
    try:
        portfolio = await trading_service.get_portfolio()
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

        return json.dumps(
            {
                "cash_balance": portfolio.cash_balance,
                "total_value": portfolio.total_value,
                "positions": positions_data,
                "daily_pnl": portfolio.daily_pnl,
                "total_pnl": portfolio.total_pnl,
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting portfolio: {str(e)}"


async def get_portfolio_summary() -> str:
    """Get portfolio summary with key metrics."""
    try:
        summary = await trading_service.get_portfolio_summary()
        return json.dumps(
            {
                "total_value": summary.total_value,
                "cash_balance": summary.cash_balance,
                "invested_value": summary.invested_value,
                "daily_pnl": summary.daily_pnl,
                "daily_pnl_percent": summary.daily_pnl_percent,
                "total_pnl": summary.total_pnl,
                "total_pnl_percent": summary.total_pnl_percent,
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting portfolio summary: {str(e)}"


async def get_all_positions() -> str:
    """Get all portfolio positions."""
    try:
        positions = await trading_service.get_positions()
        positions_data = []
        for pos in positions:
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
        return json.dumps(positions_data, indent=2)
    except Exception as e:
        return f"Error getting positions: {str(e)}"


async def get_position(args: GetPositionArgs) -> str:
    """Get a specific position by symbol."""
    try:
        position = await trading_service.get_position(args.symbol)
        return json.dumps(
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting position: {str(e)}"


# ============================================================================
# PHASE 4: OPTIONS-SPECIFIC MCP TOOLS
# ============================================================================


class GetOptionsChainArgs(BaseModel):
    symbol: str = Field(..., description="Underlying symbol (e.g., AAPL)")
    expiration_date: Optional[str] = Field(
        None, description="Expiration date (YYYY-MM-DD), None for all"
    )
    min_strike: Optional[float] = Field(None, description="Minimum strike price filter")
    max_strike: Optional[float] = Field(None, description="Maximum strike price filter")


class GetExpirationDatesArgs(BaseModel):
    symbol: str = Field(..., description="Underlying symbol (e.g., AAPL)")


class CreateMultiLegOrderArgs(BaseModel):
    legs: List[Dict[str, Any]] = Field(
        ..., description="Order legs with symbol, quantity, order_type, price"
    )
    order_type: str = Field("limit", description="Order type (limit, market)")


class CalculateGreeksArgs(BaseModel):
    option_symbol: str = Field(
        ..., description="Option symbol (e.g., AAPL240119C00195000)"
    )
    underlying_price: Optional[float] = Field(
        None, description="Underlying price override"
    )


class GetStrategyAnalysisArgs(BaseModel):
    include_greeks: bool = Field(True, description="Include Greeks aggregation")
    include_pnl: bool = Field(True, description="Include P&L analysis")
    include_recommendations: bool = Field(
        True, description="Include optimization recommendations"
    )


class SimulateExpirationArgs(BaseModel):
    processing_date: Optional[str] = Field(
        None, description="Expiration processing date (YYYY-MM-DD)"
    )
    dry_run: bool = Field(True, description="Dry run mode (don't modify account)")


def get_options_chain(args: GetOptionsChainArgs) -> str:
    """Get options chain for an underlying symbol with filtering capabilities."""
    try:
        # Parse expiration date if provided
        expiration = None
        if args.expiration_date:
            expiration = datetime.strptime(args.expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain_data = trading_service.get_formatted_options_chain(
            args.symbol,
            expiration_date=expiration,
            min_strike=args.min_strike,
            max_strike=args.max_strike,
        )

        return json.dumps(chain_data, indent=2)

    except Exception as e:
        return f"Error getting options chain: {str(e)}"


def get_expiration_dates(args: GetExpirationDatesArgs) -> str:
    """Get available expiration dates for an underlying symbol."""
    try:
        dates = trading_service.get_expiration_dates(args.symbol)
        dates_data = [d.isoformat() for d in dates]

        return json.dumps(
            {
                "underlying_symbol": args.symbol,
                "expiration_dates": dates_data,
                "count": len(dates_data),
            },
            indent=2,
        )

    except Exception as e:
        return f"Error getting expiration dates: {str(e)}"


def create_multi_leg_order(args: CreateMultiLegOrderArgs) -> str:
    """Create a multi-leg options order (spreads, straddles, etc.)."""
    try:
        order = trading_service.create_multi_leg_order_from_request(
            args.legs, args.order_type
        )

        # Convert legs for response
        legs_data = []
        for leg in order.legs:
            legs_data.append(
                {
                    "symbol": leg.asset.symbol,
                    "quantity": leg.quantity,
                    "order_type": leg.order_type,
                    "price": leg.price,
                }
            )

        return json.dumps(
            {
                "id": order.id,
                "legs": legs_data,
                "net_price": order.net_price,
                "status": order.status,
                "created_at": (
                    order.created_at.isoformat() if order.created_at else None
                ),
            },
            indent=2,
        )

    except Exception as e:
        return f"Error creating multi-leg order: {str(e)}"


def calculate_option_greeks(args: CalculateGreeksArgs) -> str:
    """Calculate Greeks for an option symbol."""
    try:
        greeks = trading_service.calculate_greeks(
            args.option_symbol, underlying_price=args.underlying_price
        )

        # Add option details
        asset = asset_factory(args.option_symbol)
        result: Dict[str, Any] = dict(greeks)  # Copy the greeks dict
        if isinstance(asset, Option):
            result.update(
                {
                    "option_symbol": args.option_symbol,
                    "underlying_symbol": asset.underlying.symbol,
                    "strike": asset.strike,
                    "expiration_date": asset.expiration_date.isoformat(),
                    "option_type": asset.option_type.lower(),
                    "days_to_expiration": asset.get_days_to_expiration(),
                }
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error calculating Greeks: {str(e)}"


def get_strategy_analysis(args: GetStrategyAnalysisArgs) -> str:
    """Get comprehensive strategy analysis for current portfolio."""
    try:
        analysis_result = trading_service.analyze_portfolio_strategies(
            include_greeks=args.include_greeks,
            include_pnl=args.include_pnl,
            include_complex_strategies=True,  # Not available in args, default to True
            include_recommendations=args.include_recommendations,
        )
        return json.dumps(analysis_result, indent=2)

    except Exception as e:
        return f"Error in strategy analysis: {str(e)}"


def simulate_option_expiration(args: SimulateExpirationArgs) -> str:
    """Simulate option expiration processing for current portfolio."""
    try:
        result = trading_service.simulate_expiration(
            processing_date=args.processing_date,
            dry_run=args.dry_run,
        )
        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error simulating option expiration: {str(e)}"


class FindTradableOptionsArgs(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    expiration_date: Optional[str] = Field(
        None, description="Expiration date in YYYY-MM-DD format"
    )
    option_type: Optional[str] = Field(None, description="Option type: 'call' or 'put'")


class GetOptionMarketDataArgs(BaseModel):
    option_id: str = Field(..., description="Option symbol or ID")


def find_tradable_options(args: FindTradableOptionsArgs) -> str:
    """
    Find tradable options for a symbol with optional filtering.

    This function provides a unified interface for options discovery
    that works with both test data and live market data.
    """
    try:
        result = trading_service.find_tradable_options(
            args.symbol, args.expiration_date, args.option_type
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error finding tradable options: {str(e)}"


def get_option_market_data(args: GetOptionMarketDataArgs) -> str:
    """
    Get market data for a specific option contract.

    Provides comprehensive option market data including Greeks,
    pricing, and volume information.
    """
    try:
        result = trading_service.get_option_market_data(args.option_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error getting option market data: {str(e)}"
