"""
Account-related API schemas.

This module contains all Pydantic models for account management:
- Account schemas with positions and balance tracking
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.positions import Position


class Account(BaseModel):
    """
    Represents a trading account.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique account identifier")
    cash_balance: float = Field(..., description="Available cash balance")
    positions: List[Position] = Field(
        default_factory=list, description="Current positions held in the account"
    )
    name: Optional[str] = Field(None, description="Account name")
    owner: Optional[str] = Field(None, description="Account owner")

    # Alias for backward compatibility
    @property
    def cash(self) -> float:
        return self.cash_balance
