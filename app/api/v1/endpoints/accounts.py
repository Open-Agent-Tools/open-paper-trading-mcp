from fastapi import APIRouter, Depends
from app.schemas.accounts import Account
from app.services.trading_service import TradingService
from app.core.dependencies import get_trading_service

router = APIRouter()

@router.get("/", response_model=list[Account])
async def get_all_accounts(
    trading_service: TradingService = Depends(get_trading_service),
) -> list[Account]:
    """
    Retrieve all accounts.
    """
    return await trading_service.get_all_accounts()
