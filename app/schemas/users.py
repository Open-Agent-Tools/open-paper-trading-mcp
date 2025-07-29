"""
User profile schemas for API validation and serialization.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileSettings(BaseModel):
    """User profile settings schema."""

    theme: str = Field(default="light", description="UI theme preference")
    language: str = Field(default="en", description="Language preference")
    timezone: str = Field(default="UTC", description="Timezone preference")
    notifications_enabled: bool = Field(
        default=True, description="Email notifications enabled"
    )
    two_factor_enabled: bool = Field(
        default=False, description="Two-factor authentication enabled"
    )
    trading_experience: str = Field(
        default="beginner", description="Trading experience level"
    )


class UserPreferences(BaseModel):
    """User trading and display preferences."""

    default_order_size: float = Field(default=100.0, description="Default order size")
    risk_tolerance: str = Field(default="moderate", description="Risk tolerance level")
    auto_refresh_portfolio: bool = Field(
        default=True, description="Auto-refresh portfolio data"
    )
    chart_type_preference: str = Field(
        default="candlestick", description="Preferred chart type"
    )
    show_advanced_options: bool = Field(
        default=False, description="Show advanced trading options"
    )


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    username: str = Field(
        ..., min_length=3, max_length=100, description="Unique username"
    )
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    phone: str | None = Field(None, max_length=20, description="Phone number")
    date_of_birth: date | None = Field(None, description="Date of birth")

    profile_settings: UserProfileSettings = Field(default_factory=UserProfileSettings)
    preferences: UserPreferences = Field(default_factory=UserPreferences)


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    email: EmailStr | None = Field(None, description="User email address")
    first_name: str | None = Field(
        None, min_length=1, max_length=100, description="First name"
    )
    last_name: str | None = Field(
        None, min_length=1, max_length=100, description="Last name"
    )
    phone: str | None = Field(None, max_length=20, description="Phone number")
    date_of_birth: date | None = Field(None, description="Date of birth")

    profile_settings: UserProfileSettings | None = Field(
        None, description="Profile settings"
    )
    preferences: UserPreferences | None = Field(None, description="User preferences")


class UserProfile(BaseModel):
    """Complete user profile schema."""

    model_config = ConfigDict(from_attributes=True)

    # Basic info
    id: str = Field(..., description="User ID (UUID)")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    phone: str | None = Field(None, description="Phone number")
    date_of_birth: date | None = Field(None, description="Date of birth")

    # Account metadata
    is_verified: bool = Field(..., description="Account verification status")
    verification_status: str = Field(..., description="Verification status")
    account_tier: str = Field(..., description="Account tier")

    # Settings and preferences
    profile_settings: dict[str, Any] = Field(
        default_factory=dict, description="Profile settings"
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="User preferences"
    )

    # Timestamps
    created_at: datetime = Field(..., description="Account creation date")
    updated_at: datetime = Field(..., description="Last update date")
    last_login_at: datetime | None = Field(None, description="Last login date")

    # Computed fields - these will be set by the service layer
    full_name: str = Field(..., description="Full name")
    account_age_days: int = Field(..., description="Account age in days")


class UserProfileSummary(BaseModel):
    """Minimal user profile for listings."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    is_verified: bool = Field(..., description="Verification status")
    account_tier: str = Field(..., description="Account tier")
    created_at: datetime = Field(..., description="Creation date")
    last_login_at: datetime | None = Field(None, description="Last login date")


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
