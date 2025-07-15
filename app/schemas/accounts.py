"""
Pydantic schemas for Account data.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

from app.models.trading import Position


class Account(BaseModel):
    """
    Represents a trading account.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique account identifier")
    cash_balance: float = Field(..., description="Available cash balance")
    positions: List[Position] = Field(default_factory=list, description="Current positions held in the account")
    # In a real system, you'd have owner_id, account_type, etc.

    class Config:
        orm_mode = True
