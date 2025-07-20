"""
Account-related API schemas.

This module contains all Pydantic models for account management:
- Account schemas with positions and balance tracking
"""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.positions import Position
from app.schemas.validation import AccountValidationMixin


class Account(BaseModel, AccountValidationMixin):
    """
    Represents a trading account.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique account identifier")
    cash_balance: float = Field(..., description="Available cash balance")
    positions: list[Position] = Field(
        default_factory=list, description="Current positions held in the account"
    )
    name: str | None = Field(None, description="Account name")
    owner: str | None = Field(None, description="Account owner")

    # Alias for backward compatibility
    @property
    def cash(self) -> float:
        return self.cash_balance
