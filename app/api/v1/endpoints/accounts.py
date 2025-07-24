from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_trading_service
from app.schemas.accounts import Account
from app.services.trading_service import TradingService

router = APIRouter()


@router.get("/", response_model=list[Account])
async def get_all_accounts(
    trading_service: Annotated[TradingService, Depends(get_trading_service)],
) -> list[Account]:
    """
    Retrieve all accounts.
    """
    from app.adapters.accounts import DatabaseAccountAdapter

    adapter = DatabaseAccountAdapter()
    return await adapter.get_all_accounts()
