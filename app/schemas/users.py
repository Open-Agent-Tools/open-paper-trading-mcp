"""
User profile schemas for API validation and serialization.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Simplified user schemas for simulation platform - no complex profile settings needed


class UserCreate(BaseModel):
    """Schema for creating a new user - simplified for simulation platform."""

    username: str = Field(
        ..., min_length=3, max_length=100, description="Unique username"
    )
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")


class UserUpdate(BaseModel):
    """Schema for updating user information - simplified for simulation platform."""

    first_name: str | None = Field(
        None, min_length=1, max_length=100, description="First name"
    )
    last_name: str | None = Field(
        None, min_length=1, max_length=100, description="Last name"
    )


class UserProfile(BaseModel):
    """Complete user profile schema - simplified for simulation platform."""

    model_config = ConfigDict(from_attributes=True)

    # Basic info
    id: str = Field(..., description="User ID (UUID)")
    username: str = Field(..., description="Username")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")

    # Timestamps
    created_at: datetime = Field(..., description="Account creation date")
    updated_at: datetime = Field(..., description="Last update date")

    # Computed fields
    full_name: str = Field(..., description="Full name")
    account_age_days: int = Field(..., description="Account age in days")


class UserProfileSummary(BaseModel):
    """Minimal user profile for listings - simplified for simulation platform."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    created_at: datetime = Field(..., description="Creation date")


class AccountProfileData(BaseModel):
    """Account profile data combining financial and metadata."""

    # Financial details
    buying_power: float = Field(..., description="Available buying power")
    cash: float = Field(..., description="Cash balance (same as portfolio_cash)")
    portfolio_cash: float = Field(..., description="Portfolio cash (same as cash)")

    # Account metadata
    account_number: str = Field(..., description="Account identifier")
    account_id: str = Field(..., description="Internal account ID")
    owner: str = Field(..., description="Account owner")
    starting_balance: float = Field(..., description="Initial balance")
    total_value: float = Field(..., description="Total account value")

    # Performance metrics
    total_gain_loss: float = Field(..., description="Total gain/loss")
    total_gain_loss_percent: float = Field(
        ..., description="Total gain/loss percentage"
    )

    # Timestamps
    created_at: datetime = Field(..., description="Account creation date")
    updated_at: datetime = Field(..., description="Last update date")


class PortfolioProfileData(BaseModel):
    """Portfolio profile data with current positions."""

    # Current positions
    market_value: float = Field(..., description="Total market value")
    equity: float = Field(..., description="Total equity value")
    cash_balance: float = Field(..., description="Available cash")
    invested_value: float = Field(..., description="Value of invested positions")

    # Portfolio metrics
    positions_count: int = Field(..., description="Number of positions")
    daily_pnl: float = Field(..., description="Daily profit/loss")
    total_pnl: float = Field(..., description="Total profit/loss")

    # Ratios
    cash_ratio: float = Field(..., description="Cash percentage of portfolio")
    invested_ratio: float = Field(..., description="Invested percentage of portfolio")
