from pydantic import BaseModel, Field
import json
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from app.services.trading_service import trading_service
from app.models.trading import (
    OrderCreate,
    OrderType,
    MultiLegOrderCreate,
    OrderLegCreate,
)
from app.models.assets import asset_factory, Option
from app.services.strategies import (
    analyze_advanced_strategy_pnl,
    aggregate_portfolio_greeks,
    detect_complex_strategies,
    get_portfolio_optimization_recommendations,
)
from app.services.expiration import OptionsExpirationEngine
from app.services.pre_trade_risk import analyze_pre_trade_risk, quick_risk_check
from app.services.advanced_validation import create_default_account_limits


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


def create_buy_order(args: CreateOrderArgs) -> str:
    """Create a buy order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.BUY,
            quantity=args.quantity,
            price=args.price,
        )
        order = trading_service.create_order(order_data)
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


def create_sell_order(args: CreateOrderArgs) -> str:
    """Create a sell order for a stock."""
    try:
        order_data = OrderCreate(
            symbol=args.symbol,
            order_type=OrderType.SELL,
            quantity=args.quantity,
            price=args.price,
        )
        order = trading_service.create_order(order_data)
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


def get_all_orders() -> str:
    """Get all trading orders."""
    try:
        orders = trading_service.get_orders()
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


def get_order(args: GetOrderArgs) -> str:
    """Get a specific order by ID."""
    try:
        order = trading_service.get_order(args.order_id)
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


def get_portfolio() -> str:
    """Get complete portfolio information."""
    try:
        portfolio = trading_service.get_portfolio()
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


def get_portfolio_summary() -> str:
    """Get portfolio summary with key metrics."""
    try:
        summary = trading_service.get_portfolio_summary()
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


def get_all_positions() -> str:
    """Get all portfolio positions."""
    try:
        positions = trading_service.get_positions()
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


def get_position(args: GetPositionArgs) -> str:
    """Get a specific position by symbol."""
    try:
        position = trading_service.get_position(args.symbol)
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


class PreTradeAnalysisArgs(BaseModel):
    order_data: Dict[str, Any] = Field(..., description="Order data to analyze")
    include_scenarios: bool = Field(True, description="Include scenario stress testing")
    options_level: int = Field(2, description="Account options trading level")


def get_options_chain(args: GetOptionsChainArgs) -> str:
    """Get options chain for an underlying symbol with filtering capabilities."""
    try:
        # Parse expiration date if provided
        expiration = None
        if args.expiration_date:
            expiration = datetime.strptime(args.expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain = trading_service.get_options_chain(args.symbol)

        if chain is None:
            return json.dumps(
                {"error": f"No options chain found for {args.symbol}"}, indent=2
            )

        # Apply filters
        if args.min_strike or args.max_strike or expiration:
            chain = chain.filter_by_strike_range(args.min_strike, args.max_strike)

        # Convert to JSON-serializable format
        calls_data = []
        for call in chain.calls:
            calls_data.append(
                {
                    "symbol": call.asset.symbol,
                    "strike": call.asset.strike,
                    "expiration": call.asset.expiration_date.isoformat(),
                    "bid": call.bid,
                    "ask": call.ask,
                    "price": call.price,
                    "volume": getattr(call, "volume", None),
                    "open_interest": getattr(call, "open_interest", None),
                    "delta": getattr(call, "delta", None),
                    "gamma": getattr(call, "gamma", None),
                    "theta": getattr(call, "theta", None),
                    "vega": getattr(call, "vega", None),
                    "iv": getattr(call, "iv", None),
                }
            )

        puts_data = []
        for put in chain.puts:
            puts_data.append(
                {
                    "symbol": put.asset.symbol,
                    "strike": put.asset.strike,
                    "expiration": put.asset.expiration_date.isoformat(),
                    "bid": put.bid,
                    "ask": put.ask,
                    "price": put.price,
                    "volume": getattr(put, "volume", None),
                    "open_interest": getattr(put, "open_interest", None),
                    "delta": getattr(put, "delta", None),
                    "gamma": getattr(put, "gamma", None),
                    "theta": getattr(put, "theta", None),
                    "vega": getattr(put, "vega", None),
                    "iv": getattr(put, "iv", None),
                }
            )

        return json.dumps(
            {
                "underlying_symbol": chain.underlying_symbol,
                "underlying_price": chain.underlying_price,
                "expiration_date": (
                    chain.expiration_date.isoformat() if chain.expiration_date else None
                ),
                "quote_time": chain.quote_time.isoformat(),
                "calls": calls_data,
                "puts": puts_data,
                "summary": chain.get_summary_stats(),
            },
            indent=2,
        )

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
        # Convert legs to OrderLegCreate objects
        order_legs = []
        for leg_data in args.legs:
            asset = asset_factory(leg_data["symbol"])
            leg = OrderLegCreate(
                asset=asset,
                quantity=leg_data["quantity"],
                order_type=OrderType(leg_data["order_type"]),
                price=leg_data.get("price"),
            )
            order_legs.append(leg)

        # Create multi-leg order
        order_data = MultiLegOrderCreate(legs=order_legs, order_type=args.order_type)

        order = trading_service.create_multi_leg_order(order_data)

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
        if isinstance(asset, Option):
            greeks.update(
                {
                    "option_symbol": args.option_symbol,
                    "underlying_symbol": asset.underlying.symbol,
                    "strike": asset.strike,
                    "expiration_date": asset.expiration_date.isoformat(),
                    "option_type": asset.option_type,
                    "days_to_expiration": asset.get_days_to_expiration(),
                }
            )

        return json.dumps(greeks, indent=2)

    except Exception as e:
        return f"Error calculating Greeks: {str(e)}"


def get_strategy_analysis(args: GetStrategyAnalysisArgs) -> str:
    """Get comprehensive strategy analysis for current portfolio."""
    try:
        portfolio = trading_service.get_portfolio()
        positions = portfolio.positions

        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(positions),
        }

        # Get current quotes for analysis
        symbols = [pos.symbol for pos in positions]
        current_quotes = {}
        for symbol in symbols:
            try:
                quote = trading_service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        # Portfolio Greeks aggregation
        if args.include_greeks and current_quotes:
            try:
                portfolio_greeks = aggregate_portfolio_greeks(positions, current_quotes)
                analysis_result["portfolio_greeks"] = {
                    "delta": portfolio_greeks.delta,
                    "gamma": portfolio_greeks.gamma,
                    "theta": portfolio_greeks.theta,
                    "vega": portfolio_greeks.vega,
                    "rho": portfolio_greeks.rho,
                    "delta_normalized": portfolio_greeks.delta_normalized,
                    "delta_dollars": portfolio_greeks.delta_dollars,
                    "theta_dollars": portfolio_greeks.theta_dollars,
                }
            except Exception as e:
                analysis_result["greeks_error"] = str(e)

        # Strategy P&L analysis
        if args.include_pnl and current_quotes:
            try:
                strategy_pnls = analyze_advanced_strategy_pnl(positions, current_quotes)
                pnl_data = []
                for pnl in strategy_pnls:
                    pnl_data.append(
                        {
                            "strategy_type": pnl.strategy_type,
                            "strategy_name": pnl.strategy_name,
                            "unrealized_pnl": pnl.unrealized_pnl,
                            "realized_pnl": pnl.realized_pnl,
                            "total_pnl": pnl.total_pnl,
                            "pnl_percent": pnl.pnl_percent,
                            "cost_basis": pnl.cost_basis,
                            "market_value": pnl.market_value,
                            "days_held": pnl.days_held,
                            "annualized_return": pnl.annualized_return,
                        }
                    )
                analysis_result["strategy_pnl"] = pnl_data
            except Exception as e:
                analysis_result["pnl_error"] = str(e)

        # Complex strategy detection
        try:
            complex_strategies = detect_complex_strategies(positions)
            complex_data = []
            for strategy in complex_strategies:
                complex_data.append(
                    {
                        "complex_type": strategy.complex_type,
                        "underlying_symbol": strategy.underlying_symbol,
                        "leg_count": len(strategy.legs),
                        "net_credit": strategy.net_credit,
                        "max_profit": strategy.max_profit,
                        "max_loss": strategy.max_loss,
                    }
                )
            analysis_result["complex_strategies"] = complex_data
        except Exception as e:
            analysis_result["complex_strategies_error"] = str(e)

        # Optimization recommendations
        if args.include_recommendations and current_quotes:
            try:
                recommendations = get_portfolio_optimization_recommendations(
                    positions, current_quotes
                )
                analysis_result["recommendations"] = recommendations
            except Exception as e:
                analysis_result["recommendations_error"] = str(e)

        return json.dumps(analysis_result, indent=2)

    except Exception as e:
        return f"Error in strategy analysis: {str(e)}"


def simulate_option_expiration(args: SimulateExpirationArgs) -> str:
    """Simulate option expiration processing for current portfolio."""
    try:
        # Get current account data
        portfolio = trading_service.get_portfolio()
        account_data = {
            "cash_balance": portfolio.cash_balance,
            "positions": portfolio.positions,
        }

        # Parse processing date
        processing_date = date.today()
        if args.processing_date:
            processing_date = datetime.strptime(args.processing_date, "%Y-%m-%d").date()

        # Get quote adapter for current prices
        quote_adapter = trading_service.quote_adapter

        # Run expiration simulation
        expiration_engine = OptionsExpirationEngine()
        result = expiration_engine.process_account_expirations(
            account_data, quote_adapter, processing_date
        )

        # Convert result to JSON-serializable format
        expired_data = []
        for pos in result.expired_positions:
            expired_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                }
            )

        new_positions_data = []
        for pos in result.new_positions:
            new_positions_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                }
            )

        return json.dumps(
            {
                "processing_date": processing_date.isoformat(),
                "dry_run": args.dry_run,
                "expired_positions": expired_data,
                "new_positions": new_positions_data,
                "cash_impact": result.cash_impact,
                "assignments": result.assignments,
                "exercises": result.exercises,
                "worthless_expirations": result.worthless_expirations,
                "warnings": result.warnings,
                "errors": result.errors,
            },
            indent=2,
        )

    except Exception as e:
        return f"Error simulating option expiration: {str(e)}"


def analyze_pre_trade_risk_advanced(args: PreTradeAnalysisArgs) -> str:
    """Perform comprehensive pre-trade risk analysis for an order."""
    try:
        # Get current account data
        portfolio = trading_service.get_portfolio()
        account_data = {
            "cash_balance": portfolio.cash_balance,
            "positions": portfolio.positions,
        }

        # Create order object from data
        order_data = args.order_data
        if "legs" in order_data:
            # Multi-leg order
            legs = []
            for leg_data in order_data["legs"]:
                asset = asset_factory(leg_data["symbol"])
                leg = OrderLegCreate(
                    asset=asset,
                    quantity=leg_data["quantity"],
                    order_type=OrderType(leg_data["order_type"]),
                    price=leg_data.get("price"),
                )
                legs.append(leg)

            order = MultiLegOrderCreate(legs=legs)
        else:
            # Single order
            order = OrderCreate(
                symbol=order_data["symbol"],
                order_type=OrderType(order_data["order_type"]),
                quantity=order_data["quantity"],
                price=order_data.get("price"),
            )

        # Get current quotes
        symbols = []
        if hasattr(order, "symbol"):
            symbols = [order.symbol]
        elif hasattr(order, "legs"):
            symbols = [leg.asset.symbol for leg in order.legs]

        current_quotes = {}
        for symbol in symbols:
            try:
                quote = trading_service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        # Create account limits
        account_limits = create_default_account_limits(options_level=args.options_level)

        # Perform analysis
        analysis = analyze_pre_trade_risk(
            account_data, order, current_quotes, account_limits
        )

        # Convert to JSON-serializable format
        validation_messages = []
        for msg in analysis.validation_result.messages:
            validation_messages.append(
                {
                    "rule": msg.rule,
                    "severity": msg.severity,
                    "code": msg.code,
                    "message": msg.message,
                    "details": msg.details,
                    "suggested_action": msg.suggested_action,
                }
            )

        scenario_data = []
        for scenario in analysis.scenario_results:
            scenario_data.append(
                {
                    "scenario_type": scenario.scenario.scenario_type,
                    "description": scenario.scenario.description,
                    "portfolio_pnl": scenario.portfolio_pnl,
                    "order_pnl": scenario.order_pnl,
                    "combined_pnl": scenario.combined_pnl,
                    "max_loss": scenario.max_loss,
                    "margin_call_risk": scenario.margin_call_risk,
                }
            )

        return json.dumps(
            {
                "analysis_timestamp": datetime.now().isoformat(),
                "should_execute": analysis.should_execute,
                "execution_recommendation": analysis.execution_recommendation,
                "confidence_level": analysis.confidence_level,
                "validation": {
                    "is_valid": analysis.validation_result.is_valid,
                    "can_execute": analysis.validation_result.can_execute,
                    "risk_score": analysis.validation_result.risk_score,
                    "estimated_cost": analysis.validation_result.estimated_cost,
                    "messages": validation_messages,
                },
                "risk_metrics": {
                    "overall_risk_level": analysis.risk_metrics.overall_risk_level,
                    "risk_score": analysis.risk_metrics.risk_score,
                    "order_max_loss": analysis.risk_metrics.order_max_loss,
                    "concentration_risk": analysis.risk_metrics.concentration_risk,
                    "delta_risk": analysis.risk_metrics.delta_risk,
                    "theta_risk": analysis.risk_metrics.theta_risk,
                    "days_to_next_expiration": analysis.risk_metrics.days_to_next_expiration,
                },
                "portfolio_greeks": {
                    "current_delta": analysis.portfolio_greeks.delta,
                    "current_theta": analysis.portfolio_greeks.theta,
                    "projected_delta": analysis.projected_greeks.delta,
                    "projected_theta": analysis.projected_greeks.theta,
                    "delta_change": analysis.projected_greeks.delta
                    - analysis.portfolio_greeks.delta,
                    "theta_change": analysis.projected_greeks.theta
                    - analysis.portfolio_greeks.theta,
                },
                "scenarios": scenario_data,
                "worst_case_loss": analysis.worst_case_loss,
                "best_case_gain": analysis.best_case_gain,
                "recommendations": analysis.recommendations,
                "alternative_strategies": analysis.alternative_strategies,
            },
            indent=2,
        )

    except Exception as e:
        return f"Error in pre-trade analysis: {str(e)}"


def quick_order_risk_check(args: PreTradeAnalysisArgs) -> str:
    """Perform quick risk assessment for an order without full analysis."""
    try:
        # Create order object from data
        order_data = args.order_data
        if "legs" in order_data:
            # Multi-leg order
            legs = []
            for leg_data in order_data["legs"]:
                asset = asset_factory(leg_data["symbol"])
                leg = OrderLegCreate(
                    asset=asset,
                    quantity=leg_data["quantity"],
                    order_type=OrderType(leg_data["order_type"]),
                    price=leg_data.get("price"),
                )
                legs.append(leg)

            order = MultiLegOrderCreate(legs=legs)
        else:
            # Single order
            order = OrderCreate(
                symbol=order_data["symbol"],
                order_type=OrderType(order_data["order_type"]),
                quantity=order_data["quantity"],
                price=order_data.get("price"),
            )

        # Get current quotes
        symbols = []
        if hasattr(order, "symbol"):
            symbols = [order.symbol]
        elif hasattr(order, "legs"):
            symbols = [leg.asset.symbol for leg in order.legs]

        current_quotes = {}
        for symbol in symbols:
            try:
                quote = trading_service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        # Quick risk check
        risk_check = quick_risk_check(order, current_quotes)

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "risk_level": risk_check["risk_level"],
                "risk_score": risk_check["risk_score"],
                "can_execute": risk_check["can_execute"],
                "key_warnings": risk_check["key_warnings"],
                "recommendation": (
                    "proceed" if risk_check["can_execute"] else "review_risks"
                ),
            },
            indent=2,
        )

    except Exception as e:
        return f"Error in quick risk check: {str(e)}"


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
            args.symbol, 
            args.expiration_date, 
            args.option_type
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
