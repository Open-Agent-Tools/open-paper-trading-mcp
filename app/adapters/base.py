"""Base adapter classes for the reference implementation pattern."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field

from app.schemas.accounts import Account
from app.schemas.orders import Order
from app.models.quotes import Quote, OptionsChain
from app.models.assets import Asset


class AdapterConfig(BaseModel):
    """Base configuration for adapters."""

    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    name: Optional[str] = None
    priority: int = 0
    timeout: float = 30.0
    cache_ttl: float = 60.0
    config: Dict[str, Any] = Field(default_factory=dict)


class AdapterRegistry:
    """Registry for managing and accessing adapters."""

    def __init__(self) -> None:
        self.adapters: Dict[str, Any] = {}

    def register(self, name: str, adapter_instance: Any) -> None:
        self.adapters[name] = adapter_instance

    def get(self, name: str) -> Optional[Any]:
        return self.adapters.get(name)


# Global registry instance
adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    return adapter_registry


class AccountAdapter(ABC):
    """Abstract base class for account storage adapters."""

    @abstractmethod
    def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve an account by ID."""
        pass

    @abstractmethod
    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        pass

    @abstractmethod
    def get_account_ids(self) -> List[str]:
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
        self.pending_orders: List[Order] = []

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """Submit an order to the market."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass

    @abstractmethod
    def get_pending_orders(self, account_id: Optional[str] = None) -> List[Order]:
        """Get pending orders, optionally filtered by account."""
        pass

    @abstractmethod
    def simulate_order(self, order: Order) -> Dict[str, Any]:
        """Simulate order execution without actually executing."""
        pass

    @abstractmethod
    def process_pending_orders(self) -> List[Order]:
        """Process all pending orders and return filled orders."""
        pass


class QuoteAdapter(ABC):
    """Abstract base class for market data adapters."""

    @abstractmethod
    async def get_quote(self, asset: Asset) -> Optional[Quote]:
        """Get a single quote for an asset."""
        pass

    @abstractmethod
    async def get_quotes(self, assets: List[Asset]) -> Dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        pass

    @abstractmethod
    async def get_chain(
        self, underlying: str, expiration_date: Optional[datetime] = None
    ) -> List[Asset]:
        """Get option chain for an underlying."""
        pass

    @abstractmethod
    async def get_options_chain(
        self, underlying: str, expiration_date: Optional[datetime] = None
    ) -> Optional["OptionsChain"]:
        """Get complete options chain for an underlying."""
        pass

    @abstractmethod
    async def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        pass

    @abstractmethod
    async def get_market_hours(self) -> Dict[str, Any]:
        """Get market hours information."""
        pass

    @abstractmethod
    def get_sample_data_info(self) -> Dict[str, Any]:
        """Get information about sample data."""
        pass

    @abstractmethod
    def get_expiration_dates(self, underlying: str) -> List[date]:
        """Get available expiration dates for an underlying symbol."""
        pass

    @abstractmethod
    def get_test_scenarios(self) -> Dict[str, Any]:
        """Get available test scenarios."""
        pass

    @abstractmethod
    def set_date(self, date: str) -> None:
        """Set the current date for test data."""
        pass

    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols."""
        pass
