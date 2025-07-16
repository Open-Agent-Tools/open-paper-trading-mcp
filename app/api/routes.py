from fastapi import APIRouter

from app.api.v1.endpoints import trading, portfolio, auth, options, market_data

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(options.router, prefix="/options", tags=["options"])
api_router.include_router(market_data.router, prefix="/market", tags=["market_data"])
