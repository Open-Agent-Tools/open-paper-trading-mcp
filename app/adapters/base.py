"""Base adapter classes for the paperbroker pattern."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.accounts import Account
from app.models.orders import Order
from app.models.quotes import Quote
from app.models.assets import Asset


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
    def get_quote(self, asset: Asset) -> Optional[Quote]:
        """Get a single quote for an asset."""
        pass

    @abstractmethod
    def get_quotes(self, assets: List[Asset]) -> Dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        pass

    @abstractmethod
    def get_chain(
        self, underlying: str, expiration_date: Optional[datetime] = None
    ) -> List[Asset]:
        """Get option chain for an underlying."""
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        pass

    @abstractmethod
    def get_market_hours(self) -> Dict[str, Any]:
        """Get market hours information."""
        pass
