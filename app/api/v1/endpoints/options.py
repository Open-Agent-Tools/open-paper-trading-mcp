"""
Enhanced REST API endpoints for options trading.

Provides comprehensive options trading functionality including:
- Options chains with Greeks
- Multi-leg order creation
- Strategy analysis
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.dependencies import get_trading_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.quotes import GreeksResponse, OptionsChainResponse
from app.schemas.orders import Order
from app.services.trading_service import TradingService

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


class MultiLegOrderRequest(BaseModel):
    """Request model for multi-leg orders."""

    legs: list[dict[str, Any]] = Field(..., description="Order legs")
    order_type: str = Field("limit", description="Order type")
    net_price: float | None = Field(None, description="Net price for order")


class GreeksRequest(BaseModel):
    """Request model for Greeks calculation."""

    underlying_price: float | None = Field(
        None, description="Override underlying price"
    )
    volatility: float | None = Field(None, description="Override implied volatility")


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


class ExpirationSimulationRequest(BaseModel):
    """Request model for expiration simulation."""

    processing_date: str | None = Field(
        None, description="Processing date (YYYY-MM-DD)"
    )
    dry_run: bool = Field(True, description="Dry run mode")
    include_details: bool = Field(True, description="Include detailed results")


# Options Chain Endpoints
@router.get("/{symbol}/chain", response_model=OptionsChainResponse)
async def get_options_chain(
    symbol: str,
    expiration_date: str | None = Query(
        None, description="Expiration date filter (YYYY-MM-DD)"
    ),
    min_strike: float | None = Query(None, description="Minimum strike price"),
    max_strike: float | None = Query(None, description="Maximum strike price"),
    include_greeks: bool = Query(True, description="Include Greeks in response"),
) -> OptionsChainResponse:
    """
    Get options chain for an underlying symbol.

    Supports filtering by expiration date and strike price range.
    Includes Greeks data when available.
    """
    service: TradingService = get_trading_service()
    try:
        expiration = None
        if expiration_date:
            expiration = datetime.strptime(expiration_date, "%Y-%m-%d").date()

        chain_data = await service.get_formatted_options_chain(
            symbol, expiration, min_strike, max_strike, include_greeks
        )
        return OptionsChainResponse(
            **chain_data, data_source="trading_service", cached=False
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e!s}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving options chain: {e!s}"
        )


@router.get("/{symbol}/expirations", response_model=dict[str, Any])
async def get_expiration_dates(
    symbol: str,
) -> dict[str, Any]:
    """
    Get available expiration dates for an underlying symbol.

    Returns sorted list of expiration dates with metadata.
    """
    service: TradingService = get_trading_service()
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
            status_code=500, detail=f"Error retrieving expiration dates: {e!s}"
        )


# Multi-leg Order Endpoints
@router.post("/orders/multi-leg", response_model=Order)
async def create_multi_leg_order(
    request: MultiLegOrderRequest,
) -> Order:
    """
    Create a multi-leg options order.

    Supports complex strategies like spreads, straddles, and condors.
    """
    service: TradingService = get_trading_service()
    try:
        order = await service.create_multi_leg_order_from_request(
            request.legs, request.order_type, request.net_price
        )
        return order

    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating multi-leg order: {e!s}"
        )


# Greeks Calculation Endpoints
@router.get("/{option_symbol}/greeks", response_model=GreeksResponse)
async def calculate_option_greeks(
    option_symbol: str,
    underlying_price: float | None = Query(
        None, description="Override underlying price"
    ),
    volatility: float | None = Query(None, description="Override implied volatility"),
) -> GreeksResponse:
    """
    Calculate Greeks for a specific option symbol.

    Supports parameter overrides for scenario analysis.
    """
    service: TradingService = get_trading_service()
    try:
        greeks_data = await service.get_option_greeks_response(
            option_symbol, underlying_price
        )
        return GreeksResponse(**greeks_data)

    except (NotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating Greeks: {e!s}")


# Strategy Analysis Endpoints
@router.post("/strategies/analyze", response_model=dict[str, Any])
async def analyze_portfolio_strategies(
    request: StrategyAnalysisRequest,
) -> dict[str, Any]:
    """
    Perform comprehensive strategy analysis for current portfolio.

    Includes P&L analysis, Greeks aggregation, and optimization recommendations.
    """
    service: TradingService = get_trading_service()
    try:
        analysis_result = await service.analyze_portfolio_strategies(
            include_greeks=request.include_greeks,
            include_pnl=request.include_pnl,
            include_complex_strategies=request.include_complex_strategies,
            include_recommendations=request.include_recommendations,
        )
        return analysis_result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in strategy analysis: {e!s}"
        )


# Unified Options Data Endpoints
@router.get("/{symbol}/search", response_model=dict[str, Any])
async def find_tradable_options_endpoint(
    symbol: str,
    expiration_date: str | None = Query(
        None, description="Expiration date filter (YYYY-MM-DD)"
    ),
    option_type: str | None = Query(
        None, description="Option type filter: 'call' or 'put'"
    ),
) -> dict[str, Any]:
    """
    Find tradable options for a symbol with optional filtering.

    This endpoint provides unified access to options discovery
    that works with both test data and live market data.
    """
    service: TradingService = get_trading_service()
    try:
        result = await service.find_tradable_options(
            symbol, expiration_date, option_type
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error finding tradable options: {e!s}"
        )


@router.get("/market-data/{option_id}", response_model=dict[str, Any])
async def get_option_market_data_endpoint(
    option_id: str,
) -> dict[str, Any]:
    """
    Get comprehensive market data for a specific option contract.

    Provides pricing, Greeks, volume, and other market data
    through the unified TradingService interface.
    """
    service: TradingService = get_trading_service()
    try:
        result = await service.get_option_market_data(option_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting option market data: {e!s}"
        )
