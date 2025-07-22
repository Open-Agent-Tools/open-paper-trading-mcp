"""Base adapter classes for the reference implementation pattern."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.assets import Asset
from app.models.quotes import OptionsChain, Quote
from app.schemas.accounts import Account
from app.schemas.orders import Order


class AdapterConfig(BaseModel):
    """Base configuration for adapters."""

    enabled: bool = True
    api_key: str | None = None
    api_secret: str | None = None
    base_url: str | None = None
    name: str | None = None
    priority: int = 0
    timeout: float = 30.0
    cache_ttl: float = 60.0
    config: dict[str, Any] = Field(default_factory=dict)


class AdapterRegistry:
    """Registry for managing and accessing adapters."""

    def __init__(self) -> None:
        self.adapters: dict[str, Any] = {}

    def register(self, name: str, adapter_instance: Any) -> None:
        self.adapters[name] = adapter_instance

    def get(self, name: str) -> Any | None:
        return self.adapters.get(name)


# Global registry instance
adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    return adapter_registry


class AccountAdapter(ABC):
    """Abstract base class for account storage adapters."""

    @abstractmethod
    def get_account(self, account_id: str) -> Account | None:
        """Retrieve an account by ID."""
        pass

    @abstractmethod
    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        pass

    @abstractmethod
    def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        pass

    @abstractmethod
    def account_exists(self, account_id: str) -> bool:
        """Check if an account exists."""
        pass

    @abstractmethod
    def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        pass


class MarketAdapter(ABC):
    """Abstract base class for market simulation adapters."""

    def __init__(self, quote_adapter: "QuoteAdapter"):
        self.quote_adapter = quote_adapter
        self.pending_orders: list[Order] = []

    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """Submit an order to the market."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass

    @abstractmethod
    def get_pending_orders(self, account_id: str | None = None) -> list[Order]:
        """Get pending orders, optionally filtered by account."""
        pass

    @abstractmethod
    async def simulate_order(self, order: Order) -> dict[str, Any]:
        """Simulate order execution without actually executing."""
        pass

    @abstractmethod
    async def process_pending_orders(self) -> list[Order]:
        """Process all pending orders and return filled orders."""
        pass


class QuoteAdapter(ABC):
    """Abstract base class for market data adapters."""

    @abstractmethod
    async def get_quote(self, asset: Asset) -> Quote | None:
        """Get a single quote for an asset."""
        pass

    @abstractmethod
    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        pass

    @abstractmethod
    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        """Get option chain for an underlying."""
        pass

    @abstractmethod
    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> Optional["OptionsChain"]:
        """Get complete options chain for an underlying."""
        pass

    @abstractmethod
    async def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        pass

    @abstractmethod
    async def get_market_hours(self) -> dict[str, Any]:
        """Get market hours information."""
        pass

    @abstractmethod
    def get_sample_data_info(self) -> dict[str, Any]:
        """Get information about sample data."""
        pass

    @abstractmethod
    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get available expiration dates for an underlying symbol."""
        pass

    @abstractmethod
    def get_test_scenarios(self) -> dict[str, Any]:
        """Get available test scenarios."""
        pass

    @abstractmethod
    def set_date(self, date: str) -> None:
        """Set the current date for test data."""
        pass

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """Get list of available symbols."""
        pass
