"""
Enhanced REST API endpoints for options trading.

Provides comprehensive options trading functionality including:
- Options chains with Greeks
- Multi-leg order creation
- Strategy analysis
- Pre-trade risk assessment
- Options expiration simulation
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional, Union
from datetime import date, datetime
from pydantic import BaseModel, Field

from app.schemas.orders import (
    MultiLegOrderCreate,
    OrderLegCreate,
    OrderType,
    OrderCreate,
    Order,
    OrderCondition,
)
from app.models.quotes import OptionsChainResponse, GreeksResponse
from app.models.assets import asset_factory, Option
from app.services.trading_service import trading_service, TradingService
from app.core.exceptions import NotFoundError, ValidationError
from app.services.strategies import (
    analyze_advanced_strategy_pnl,
    aggregate_portfolio_greeks,
    detect_complex_strategies,
    get_portfolio_optimization_recommendations,
)
from app.services.expiration import OptionsExpirationEngine
from app.services.pre_trade_risk import (
    analyze_pre_trade_risk,
    RiskAnalysis,
    quick_risk_check,
)
from app.services.advanced_validation import create_default_account_limits

router = APIRouter()

# TODO: Restore when find_tradable_options is re-implemented
# @router.get("/{symbol}/live-chain/search")
# async def find_live_tradable_options(
#     symbol: str,
#     expiration_date: Optional[str] = Query(None, description="Expiration date in YYYY-MM-DD format"),
#     option_type: Optional[str] = Query(None, description="Option type: 'call' or 'put'")
# ):
#     """
#     Find live tradable options for a symbol with optional filtering.
#     """
#     try:
#         args = FindTradableOptionsArgs(
#             symbol=symbol,
#             expiration_date=expiration_date,
#             option_type=option_type
#         )
#         result = await mcp_find_tradable_options(args)
#         if "error" in result:
#             raise HTTPException(status_code=500, detail=result["error"])
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error finding tradable options: {str(e)}")


@router.get("/market-data/{option_id}", response_model=Dict[str, Any])
async def get_live_option_market_data(option_id: str) -> Dict[str, Any]:
    """
    Get live market data for a specific option contract by ID.
    """
    try:
        from app.mcp.options_tools import (
            get_option_market_data,
            GetOptionMarketDataArgs,
        )

        args = GetOptionMarketDataArgs(option_id=option_id)
        result = await get_option_market_data(args)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting option market data: {str(e)}"
        )


class MultiLegOrderRequest(BaseModel):
    """Request model for multi-leg orders."""

    legs: List[Dict[str, Any]] = Field(..., description="Order legs")
    order_type: str = Field("limit", description="Order type")
    net_price: Optional[float] = Field(None, description="Net price for order")


class GreeksRequest(BaseModel):
    """Request model for Greeks calculation."""

    underlying_price: Optional[float] = Field(
        None, description="Override underlying price"
    )
    volatility: Optional[float] = Field(None, description="Override implied volatility")
    risk_free_rate: Optional[float] = Field(None, description="Override risk-free rate")


class StrategyAnalysisRequest(BaseModel):
    """Request model for strategy analysis."""

    include_greeks: bool = Field(True, description="Include Greeks aggregation")
    include_pnl: bool = Field(True, description="Include P&L analysis")
    include_complex_strategies: bool = Field(
        True, description="Include complex strategy detection"
    )
    include_recommendations: bool = Field(
        True, description="Include optimization recommendations"
    )


class PreTradeRiskRequest(BaseModel):
    """Request model for pre-trade risk analysis."""

    order_data: Dict[str, Any] = Field(..., description="Order data to analyze")
    include_scenarios: bool = Field(True, description="Include scenario analysis")
    options_level: int = Field(2, description="Account options level")
    include_alternatives: bool = Field(
        True, description="Include alternative strategies"
    )


class ExpirationSimulationRequest(BaseModel):
    """Request model for expiration simulation."""

    processing_date: Optional[str] = Field(
        None, description="Processing date (YYYY-MM-DD)"
    )
    dry_run: bool = Field(True, description="Dry run mode")
    include_details: bool = Field(True, description="Include detailed results")


# Options Chain Endpoints
@router.get("/{symbol}/chain", response_model=OptionsChainResponse)
async def get_options_chain(
    symbol: str,
    expiration_date: Optional[str] = Query(
        None, description="Expiration date filter (YYYY-MM-DD)"
    ),
    min_strike: Optional[float] = Query(None, description="Minimum strike price"),
    max_strike: Optional[float] = Query(None, description="Maximum strike price"),
    include_greeks: bool = Query(True, description="Include Greeks in response"),
    service: TradingService = Depends(trading_service),
) -> OptionsChainResponse:
    """
    Get options chain for an underlying symbol.

    Supports filtering by expiration date and strike price range.
    Includes Greeks data when available.
    """
    try:
        # Parse expiration date if provided
        expiration = None
        if expiration_date:
            expiration = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        # Get options chain
        chain = service.get_options_chain(symbol, expiration)

        if chain is None:
            raise NotFoundError(f"No options chain found for {symbol}")

        # Apply filters
        if min_strike or max_strike:
            chain = chain.filter_by_strike_range(min_strike, max_strike)

        # Convert to response format
        calls_data = []
        for call in chain.calls:
            asset = call.asset
            if not isinstance(asset, Option):
                continue
            call_data = {
                "symbol": asset.symbol,
                "strike": asset.strike,
                "expiration": asset.expiration_date.isoformat(),
                "bid": call.bid,
                "ask": call.ask,
                "price": call.price,
                "volume": getattr(call, "volume", None),
                "open_interest": getattr(call, "open_interest", None),
            }

            if include_greeks:
                call_data.update(
                    {
                        "delta": getattr(call, "delta", None),
                        "gamma": getattr(call, "gamma", None),
                        "theta": getattr(call, "theta", None),
                        "vega": getattr(call, "vega", None),
                        "rho": getattr(call, "rho", None),
                        "iv": getattr(call, "iv", None),
                    }
                )

            calls_data.append(call_data)

        puts_data = []
        for put in chain.puts:
            asset = put.asset
            if not isinstance(asset, Option):
                continue
            put_data = {
                "symbol": asset.symbol,
                "strike": asset.strike,
                "expiration": asset.expiration_date.isoformat(),
                "bid": put.bid,
                "ask": put.ask,
                "price": put.price,
                "volume": getattr(put, "volume", None),
                "open_interest": getattr(put, "open_interest", None),
            }

            if include_greeks:
                put_data.update(
                    {
                        "delta": getattr(put, "delta", None),
                        "gamma": getattr(put, "gamma", None),
                        "theta": getattr(put, "theta", None),
                        "vega": getattr(put, "vega", None),
                        "rho": getattr(put, "rho", None),
                        "iv": getattr(put, "iv", None),
                    }
                )

            puts_data.append(put_data)

        return OptionsChainResponse(
            underlying_symbol=chain.underlying_symbol,
            underlying_price=chain.underlying_price,
            expiration_date=(
                chain.expiration_date.isoformat() if chain.expiration_date else None
            ),
            quote_time=chain.quote_time.isoformat(),
            calls=calls_data,
            puts=puts_data,
            summary=chain.get_summary_stats(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving options chain: {str(e)}"
        )


@router.get("/{symbol}/expirations", response_model=Dict[str, Any])
async def get_expiration_dates(
    symbol: str, service: TradingService = Depends(trading_service)
) -> Dict[str, Any]:
    """
    Get available expiration dates for an underlying symbol.

    Returns sorted list of expiration dates with metadata.
    """
    try:
        dates = service.get_expiration_dates(symbol)

        return {
            "underlying_symbol": symbol,
            "expiration_dates": [d.isoformat() for d in dates],
            "count": len(dates),
            "next_expiration": dates[0].isoformat() if dates else None,
            "last_expiration": dates[-1].isoformat() if dates else None,
        }

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving expiration dates: {str(e)}"
        )


# Multi-leg Order Endpoints
@router.post("/orders/multi-leg", response_model=Order)
async def create_multi_leg_order(
    request: MultiLegOrderRequest, service: TradingService = Depends(trading_service)
) -> Order:
    """
    Create a multi-leg options order.

    Supports complex strategies like spreads, straddles, and condors.
    """
    try:
        # Convert legs to OrderLegCreate objects
        order_legs = []
        for leg_data in request.legs:
            leg = OrderLegCreate(
                symbol=leg_data["symbol"],
                quantity=leg_data["quantity"],
                side=leg_data["side"],
                price=leg_data.get("price"),
            )
            order_legs.append(leg)

        # Create multi-leg order
        order_data = MultiLegOrderCreate(
            legs=order_legs,
            limit_price=request.net_price,
            condition=OrderCondition(request.order_type),
        )

        order = service.create_multi_leg_order(order_data)

        return order

    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating multi-leg order: {str(e)}"
        )


# Greeks Calculation Endpoints
@router.get("/{option_symbol}/greeks", response_model=GreeksResponse)
async def calculate_option_greeks(
    option_symbol: str,
    underlying_price: Optional[float] = Query(
        None, description="Override underlying price"
    ),
    volatility: Optional[float] = Query(
        None, description="Override implied volatility"
    ),
    risk_free_rate: Optional[float] = Query(
        None, description="Override risk-free rate"
    ),
    service: TradingService = Depends(trading_service),
) -> GreeksResponse:
    """
    Calculate Greeks for a specific option symbol.

    Supports parameter overrides for scenario analysis.
    """
    try:
        # Calculate Greeks
        greeks = service.calculate_greeks(
            option_symbol,
            underlying_price=underlying_price,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
        )

        # Get option details
        asset = asset_factory(option_symbol)
        if not isinstance(asset, Option):
            raise HTTPException(status_code=400, detail="Symbol is not an option")

        return GreeksResponse(
            option_symbol=option_symbol,
            underlying_symbol=asset.underlying.symbol,
            strike=asset.strike,
            expiration_date=asset.expiration_date.isoformat(),
            option_type=asset.option_type.value,
            days_to_expiration=asset.get_days_to_expiration(),
            delta=greeks.delta,
            gamma=greeks.gamma,
            theta=greeks.theta,
            vega=greeks.vega,
            rho=greeks.rho,
            charm=greeks.charm,
            vanna=greeks.vanna,
            speed=greeks.speed,
            zomma=greeks.zomma,
            color=greeks.color,
        )

    except (NotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating Greeks: {str(e)}"
        )


# Strategy Analysis Endpoints
@router.post("/strategies/analyze", response_model=Dict[str, Any])
async def analyze_portfolio_strategies(
    request: StrategyAnalysisRequest, service: TradingService = Depends(trading_service)
) -> Dict[str, Any]:
    """
    Perform comprehensive strategy analysis for current portfolio.

    Includes P&L analysis, Greeks aggregation, and optimization recommendations.
    """
    try:
        portfolio = service.get_portfolio()
        positions = portfolio.positions

        # Get current quotes
        symbols = [pos.symbol for pos in positions]
        current_quotes = {}
        for symbol in symbols:
            try:
                quote = service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(positions),
            "symbols_analyzed": len(current_quotes),
        }

        # Portfolio Greeks aggregation
        if request.include_greeks and current_quotes:
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

        # Strategy P&L analysis
        if request.include_pnl and current_quotes:
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

        # Complex strategy detection
        if request.include_complex_strategies:
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
                        "breakeven_points": strategy.breakeven_points,
                    }
                )
            analysis_result["complex_strategies"] = complex_data

        # Optimization recommendations
        if request.include_recommendations and current_quotes:
            recommendations = get_portfolio_optimization_recommendations(
                positions, current_quotes
            )
            analysis_result["recommendations"] = recommendations

        return analysis_result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in strategy analysis: {str(e)}"
        )


# Pre-trade Risk Analysis Endpoints
@router.post("/risk/pre-trade", response_model=RiskAnalysis)
async def analyze_pre_trade_risk_endpoint(
    request: PreTradeRiskRequest, service: TradingService = Depends(trading_service)
) -> RiskAnalysis:
    """
    Perform comprehensive pre-trade risk analysis.

    Includes validation, scenario analysis, and recommendations.
    """
    try:
        # Get current account data
        portfolio = service.get_portfolio()
        account_data = {
            "cash_balance": portfolio.cash_balance,
            "positions": portfolio.positions,
        }

        # Create order object from request data
        order_data = request.order_data
        order: Union[OrderCreate, MultiLegOrderCreate]
        if "legs" in order_data:
            # Multi-leg order
            legs = []
            for leg_data in order_data["legs"]:
                leg = OrderLegCreate(
                    symbol=leg_data["symbol"],
                    quantity=leg_data["quantity"],
                    side=leg_data["side"],
                    price=leg_data.get("price"),
                )
                legs.append(leg)

            order = MultiLegOrderCreate(
                legs=legs,
                limit_price=order_data.get("net_price"),
                condition=OrderCondition(order_data.get("order_type", "limit")),
            )
        else:
            # Single order
            order = OrderCreate(
                symbol=order_data["symbol"],
                order_type=OrderType(order_data["order_type"]),
                quantity=order_data["quantity"],
                price=order_data.get("price"),
                condition=OrderCondition(order_data.get("condition", "limit")),
            )

        # Get current quotes
        symbols: List[str] = []
        if isinstance(order, OrderCreate):
            symbols = [order.symbol]
        elif isinstance(order, MultiLegOrderCreate):
            symbols = [leg.symbol for leg in order.legs]

        current_quotes = {}
        for symbol in symbols:
            try:
                quote = service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        # Create account limits
        account_limits = create_default_account_limits(
            options_level=request.options_level
        )

        # Perform analysis
        analysis = analyze_pre_trade_risk(
            account_data, order, current_quotes, account_limits
        )

        return analysis

    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in pre-trade analysis: {str(e)}"
        )


# Options Expiration Endpoints
@router.post("/expiration/simulate", response_model=Dict[str, Any])
async def simulate_options_expiration(
    request: ExpirationSimulationRequest,
    service: TradingService = Depends(trading_service),
) -> Dict[str, Any]:
    """
    Simulate options expiration processing.

    Supports dry-run mode and detailed reporting.
    """
    try:
        # Get current account data
        portfolio = service.get_portfolio()
        account_data = {
            "cash_balance": portfolio.cash_balance,
            "positions": portfolio.positions,
        }

        # Parse processing date
        processing_date = date.today()
        if request.processing_date:
            processing_date = datetime.strptime(
                request.processing_date, "%Y-%m-%d"
            ).date()

        # Get quote adapter
        quote_adapter = service.quote_adapter

        # Run expiration simulation
        expiration_engine = OptionsExpirationEngine()
        result = expiration_engine.process_account_expirations(
            account_data, quote_adapter, processing_date
        )

        # Convert result to response format
        expired_data = []
        for pos in result.expired_positions:
            expired_data.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "expiration_type": getattr(pos, "expiration_type", "unknown"),
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
                    "creation_reason": getattr(pos, "creation_reason", "assignment"),
                }
            )

        response = {
            "processing_date": processing_date.isoformat(),
            "dry_run": request.dry_run,
            "expired_positions": expired_data,
            "new_positions": new_positions_data,
            "cash_impact": result.cash_impact,
            "assignments": result.assignments,
            "exercises": result.exercises,
            "worthless_expirations": result.worthless_expirations,
            "warnings": result.warnings,
            "errors": result.errors,
        }

        if request.include_details:
            response["processing_summary"] = {
                "total_expired": len(result.expired_positions),
                "total_new_positions": len(result.new_positions),
                "net_cash_impact": result.cash_impact,
                "success_rate": (
                    (len(result.expired_positions) - len(result.errors))
                    / len(result.expired_positions)
                    if result.expired_positions
                    else 1.0
                ),
            }

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error simulating expiration: {str(e)}"
        )


# Quick Risk Check Endpoint
@router.post("/risk/quick-check", response_model=Dict[str, Any])
async def quick_risk_check_endpoint(
    order_data: Dict[str, Any], service: TradingService = Depends(trading_service)
) -> Dict[str, Any]:
    """
    Perform quick risk assessment for an order.

    Lightweight version of pre-trade analysis for real-time feedback.
    """
    try:
        # Create order object
        order: Union[OrderCreate, MultiLegOrderCreate]
        if "legs" in order_data:
            # Multi-leg order
            legs = []
            for leg_data in order_data["legs"]:
                leg = OrderLegCreate(
                    symbol=leg_data["symbol"],
                    quantity=leg_data["quantity"],
                    side=leg_data["side"],
                    price=leg_data.get("price"),
                )
                legs.append(leg)

            order = MultiLegOrderCreate(
                legs=legs,
                limit_price=order_data.get("net_price"),
                condition=OrderCondition(order_data.get("order_type", "limit")),
            )
        else:
            # Single order
            order = OrderCreate(
                symbol=order_data["symbol"],
                order_type=OrderType(order_data["order_type"]),
                quantity=order_data["quantity"],
                price=order_data.get("price"),
                condition=OrderCondition(order_data.get("condition", "limit")),
            )

        # Get current quotes
        symbols: List[str] = []
        if isinstance(order, OrderCreate):
            symbols = [order.symbol]
        elif isinstance(order, MultiLegOrderCreate):
            symbols = [leg.symbol for leg in order.legs]

        current_quotes = {}
        for symbol in symbols:
            try:
                quote = service.get_enhanced_quote(symbol)
                current_quotes[symbol] = quote
            except Exception:
                continue

        # Quick risk check
        risk_check = quick_risk_check(order, current_quotes)

        return {
            "timestamp": datetime.now().isoformat(),
            "risk_level": risk_check["risk_level"],
            "risk_score": risk_check["risk_score"],
            "can_execute": risk_check["can_execute"],
            "key_warnings": risk_check["key_warnings"],
            "recommendation": (
                "proceed" if risk_check["can_execute"] else "review_risks"
            ),
        }

    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in quick risk check: {str(e)}"
        )
