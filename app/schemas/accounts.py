"""
Account-related API schemas.

This module contains all Pydantic models for account management:
- Account schemas with positions and balance tracking
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.positions import Position
from app.schemas.validation import AccountValidationMixin


class Account(BaseModel, AccountValidationMixin):
    """
    Represents a trading account.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(
        ..., description="Unique 10-character alphanumeric account identifier"
    )
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


class AccountSummary(BaseModel):
    """
    Summary information for a trading account.
    Includes ID, creation date, starting balance, and current balance.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(
        ..., description="Unique 10-character alphanumeric account identifier"
    )
    created_at: datetime = Field(
        ..., description="Date and time when account was created"
    )
    starting_balance: float = Field(
        ..., description="Initial cash balance when account was created"
    )
    current_balance: float = Field(..., description="Current available cash balance")
    owner: str = Field(..., description="Account owner")


class AccountSummaryList(BaseModel):
    """
    List of account summaries with metadata.
    """

    model_config = ConfigDict(from_attributes=True)

    accounts: list[AccountSummary] = Field(..., description="List of account summaries")
    total_count: int = Field(..., description="Total number of accounts")
    total_starting_balance: float = Field(
        ..., description="Sum of all starting balances"
    )
    total_current_balance: float = Field(..., description="Sum of all current balances")
