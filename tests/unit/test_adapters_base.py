"""Tests for base adapter classes and patterns."""

import pytest
from unittest.mock import MagicMock, Mock
from datetime import datetime, date
from typing import Any, Optional

from app.adapters.base import (
    AdapterConfig,
    AdapterRegistry,
    QuoteAdapter,
    AccountAdapter,
    MarketAdapter,
    get_adapter_registry,
)
from app.models.assets import Asset, Stock, Option
from app.models.quotes import Quote, OptionsChain
from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderType, OrderStatus, OrderCondition


class TestAdapterConfig:
    """Test adapter configuration class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdapterConfig()
        
        assert config.enabled is True
        assert config.api_key is None
        assert config.api_secret is None
        assert config.base_url is None
        assert config.name is None
        assert config.priority == 0
        assert config.timeout == 30.0
        assert config.cache_ttl == 60.0
        assert config.config == {}

    def test_custom_config(self):
        """Test custom configuration values."""
        custom_config = {
            "api_key": "test-key",
            "base_url": "https://api.example.com",
            "enabled": False,
            "priority": 10,
            "timeout": 45.0,
            "cache_ttl": 120.0,
            "name": "test-adapter",
            "config": {"param1": "value1", "param2": 42}
        }
        
        config = AdapterConfig(**custom_config)
        
        assert config.enabled is False
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.example.com"
        assert config.name == "test-adapter"
        assert config.priority == 10
        assert config.timeout == 45.0
        assert config.cache_ttl == 120.0
        assert config.config == {"param1": "value1", "param2": 42}

    def test_config_validation(self):
        """Test configuration validation."""
        # Test negative timeout
        with pytest.raises((ValueError, TypeError)):
            AdapterConfig(timeout=-1.0)
        
        # Test negative cache_ttl
        with pytest.raises((ValueError, TypeError)):
            AdapterConfig(cache_ttl=-5.0)


class TestAdapterRegistry:
    """Test adapter registry functionality."""

    def test_empty_registry(self):
        """Test empty registry initialization."""
        registry = AdapterRegistry()
        assert len(registry.adapters) == 0
        assert registry.get("nonexistent") is None

    def test_register_adapter(self):
        """Test registering adapters."""
        registry = AdapterRegistry()
        mock_adapter = MagicMock()
        
        registry.register("test_adapter", mock_adapter)
        
        assert "test_adapter" in registry.adapters
        assert registry.get("test_adapter") is mock_adapter

    def test_register_multiple_adapters(self):
        """Test registering multiple adapters."""
        registry = AdapterRegistry()
        adapter1 = MagicMock()
        adapter2 = MagicMock()
        
        registry.register("adapter1", adapter1)
        registry.register("adapter2", adapter2)
        
        assert len(registry.adapters) == 2
        assert registry.get("adapter1") is adapter1
        assert registry.get("adapter2") is adapter2

    def test_overwrite_adapter(self):
        """Test overwriting an existing adapter."""
        registry = AdapterRegistry()
        old_adapter = MagicMock()
        new_adapter = MagicMock()
        
        registry.register("test_adapter", old_adapter)
        registry.register("test_adapter", new_adapter)
        
        assert registry.get("test_adapter") is new_adapter
        assert registry.get("test_adapter") is not old_adapter

    def test_get_nonexistent_adapter(self):
        """Test getting a non-existent adapter."""
        registry = AdapterRegistry()
        adapter = MagicMock()
        registry.register("existing_adapter", adapter)
        
        assert registry.get("nonexistent_adapter") is None

    def test_global_registry(self):
        """Test global registry instance."""
        registry1 = get_adapter_registry()
        registry2 = get_adapter_registry()
        
        # Should return the same instance
        assert registry1 is registry2


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing."""

    def __init__(self):
        self.quotes = {}
        self.market_open = True
        self.sample_data_info = {"test": "data"}
        self.available_symbols = ["AAPL", "GOOGL", "MSFT"]
        self.test_scenarios = {"default": "test scenario"}

    async def get_quote(self, asset: Asset) -> Quote | None:
        """Get a single quote."""
        if asset.symbol in self.quotes:
            return self.quotes[asset.symbol]
        return None

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """Get multiple quotes."""
        results = {}
        for asset in assets:
            quote = await self.get_quote(asset)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(self, underlying: str, expiration_date: datetime | None = None) -> list[Asset]:
        """Get option chain assets."""
        return []

    async def get_options_chain(self, underlying: str, expiration_date: datetime | None = None) -> Optional[OptionsChain]:
        """Get options chain."""
        return None

    async def is_market_open(self) -> bool:
        """Check if market is open."""
        return self.market_open

    async def get_market_hours(self) -> dict[str, Any]:
        """Get market hours."""
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self) -> dict[str, Any]:
        """Get sample data info."""
        return self.sample_data_info

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get expiration dates."""
        return [date.today()]

    def get_test_scenarios(self) -> dict[str, Any]:
        """Get test scenarios."""
        return self.test_scenarios

    def set_date(self, date: str) -> None:
        """Set current date."""
        pass

    def get_available_symbols(self) -> list[str]:
        """Get available symbols."""
        return self.available_symbols


class TestQuoteAdapter:
    """Test quote adapter abstract class behavior."""

    def test_quote_adapter_instantiation(self):
        """Test that concrete quote adapter can be instantiated."""
        adapter = MockQuoteAdapter()
        assert isinstance(adapter, QuoteAdapter)

    @pytest.mark.asyncio
    async def test_get_quote(self):
        """Test getting a single quote."""
        adapter = MockQuoteAdapter()
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.98,
            ask=150.02,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )
        adapter.quotes["AAPL"] = quote

        result = await adapter.get_quote(stock)
        assert result is quote

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self):
        """Test getting a quote that doesn't exist."""
        adapter = MockQuoteAdapter()
        stock = Stock(symbol="NONEXISTENT", name="Non-existent")

        result = await adapter.get_quote(stock)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_multiple_quotes(self):
        """Test getting multiple quotes."""
        adapter = MockQuoteAdapter()
        
        # Setup test data
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        stock3 = Stock(symbol="NONEXISTENT", name="Non-existent")
        
        quote1 = Quote(
            asset=stock1, quote_date=datetime.now(), price=150.0,
            bid=149.98, ask=150.02, bid_size=100, ask_size=100, volume=1000000
        )
        quote2 = Quote(
            asset=stock2, quote_date=datetime.now(), price=2500.0,
            bid=2499.50, ask=2500.50, bid_size=100, ask_size=100, volume=500000
        )
        
        adapter.quotes["AAPL"] = quote1
        adapter.quotes["GOOGL"] = quote2

        # Test getting multiple quotes
        assets = [stock1, stock2, stock3]
        results = await adapter.get_quotes(assets)
        
        assert len(results) == 2  # Only 2 found
        assert stock1 in results
        assert stock2 in results
        assert stock3 not in results
        assert results[stock1] is quote1
        assert results[stock2] is quote2

    @pytest.mark.asyncio
    async def test_market_status_methods(self):
        """Test market status related methods."""
        adapter = MockQuoteAdapter()
        
        # Test market open
        assert await adapter.is_market_open() is True
        
        # Test market closed
        adapter.market_open = False
        assert await adapter.is_market_open() is False
        
        # Test market hours
        hours = await adapter.get_market_hours()
        assert "open" in hours
        assert "close" in hours

    def test_data_info_methods(self):
        """Test data information methods."""
        adapter = MockQuoteAdapter()
        
        # Test sample data info
        sample_info = adapter.get_sample_data_info()
        assert sample_info == {"test": "data"}
        
        # Test available symbols
        symbols = adapter.get_available_symbols()
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "MSFT" in symbols
        
        # Test test scenarios
        scenarios = adapter.get_test_scenarios()
        assert "default" in scenarios
        
        # Test expiration dates
        dates = adapter.get_expiration_dates("AAPL")
        assert len(dates) > 0
        assert isinstance(dates[0], date)

    def test_date_setting(self):
        """Test date setting method."""
        adapter = MockQuoteAdapter()
        
        # Should not raise exception
        adapter.set_date("2023-01-01")


class MockAccountAdapter(AccountAdapter):
    """Mock account adapter for testing."""

    def __init__(self):
        self.accounts = {}

    def get_account(self, account_id: str) -> Account | None:
        """Get account by ID."""
        return self.accounts.get(account_id)

    def put_account(self, account: Account) -> None:
        """Store account."""
        self.accounts[account.id] = account

    def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        return list(self.accounts.keys())

    def account_exists(self, account_id: str) -> bool:
        """Check if account exists."""
        return account_id in self.accounts

    def delete_account(self, account_id: str) -> bool:
        """Delete account."""
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False


class TestAccountAdapter:
    """Test account adapter abstract class behavior."""

    def test_account_adapter_instantiation(self):
        """Test that concrete account adapter can be instantiated."""
        adapter = MockAccountAdapter()
        assert isinstance(adapter, AccountAdapter)

    def test_account_crud_operations(self):
        """Test basic CRUD operations on accounts."""
        adapter = MockAccountAdapter()
        
        # Test empty state
        assert len(adapter.get_account_ids()) == 0
        assert not adapter.account_exists("test-id")
        assert adapter.get_account("test-id") is None
        
        # Create account
        account = Account(
            id="test-id",
            cash_balance=100000.0,
            positions=[],
            name="Test Account",
            owner="test-user"
        )
        
        # Test put/create
        adapter.put_account(account)
        assert adapter.account_exists("test-id")
        assert "test-id" in adapter.get_account_ids()
        
        # Test get
        retrieved = adapter.get_account("test-id")
        assert retrieved is not None
        assert retrieved.id == "test-id"
        assert retrieved.cash_balance == 100000.0
        assert retrieved.name == "Test Account"
        
        # Test update
        account.cash_balance = 95000.0
        adapter.put_account(account)
        updated = adapter.get_account("test-id")
        assert updated.cash_balance == 95000.0
        
        # Test delete
        assert adapter.delete_account("test-id") is True
        assert not adapter.account_exists("test-id")
        assert adapter.get_account("test-id") is None
        assert len(adapter.get_account_ids()) == 0
        
        # Test delete non-existent
        assert adapter.delete_account("nonexistent") is False

    def test_multiple_accounts(self):
        """Test handling multiple accounts."""
        adapter = MockAccountAdapter()
        
        # Create multiple accounts
        account1 = Account(id="acc1", cash_balance=10000.0, positions=[], name="Account 1", owner="user1")
        account2 = Account(id="acc2", cash_balance=20000.0, positions=[], name="Account 2", owner="user2")
        account3 = Account(id="acc3", cash_balance=30000.0, positions=[], name="Account 3", owner="user3")
        
        adapter.put_account(account1)
        adapter.put_account(account2)
        adapter.put_account(account3)
        
        # Test getting all IDs
        ids = adapter.get_account_ids()
        assert len(ids) == 3
        assert "acc1" in ids
        assert "acc2" in ids
        assert "acc3" in ids
        
        # Test individual retrieval
        for account_id in ids:
            account = adapter.get_account(account_id)
            assert account is not None
            assert account.id == account_id


class MockMarketAdapter(MarketAdapter):
    """Mock market adapter for testing."""

    def __init__(self, quote_adapter: QuoteAdapter):
        super().__init__(quote_adapter)
        self.submitted_orders = []
        self.order_counter = 1

    async def submit_order(self, order: Order) -> Order:
        """Submit order to market."""
        if not order.id:
            order.id = f"order-{self.order_counter}"
            self.order_counter += 1
        
        order.status = OrderStatus.PENDING
        order.created_at = datetime.utcnow()
        self.pending_orders.append(order)
        self.submitted_orders.append(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        for i, order in enumerate(self.pending_orders):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def get_pending_orders(self, account_id: str | None = None) -> list[Order]:
        """Get pending orders."""
        return self.pending_orders.copy()

    async def simulate_order(self, order: Order) -> dict[str, Any]:
        """Simulate order execution."""
        return {
            "success": True,
            "would_fill": True,
            "estimated_price": 100.0,
            "estimated_cost": order.quantity * 100.0
        }

    async def process_pending_orders(self) -> list[Order]:
        """Process pending orders."""
        filled_orders = []
        remaining_orders = []
        
        for order in self.pending_orders:
            # Simple fill logic - fill all market orders
            if order.condition == OrderCondition.MARKET:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.utcnow()
                filled_orders.append(order)
            else:
                remaining_orders.append(order)
        
        self.pending_orders = remaining_orders
        return filled_orders


class TestMarketAdapter:
    """Test market adapter abstract class behavior."""

    @pytest.mark.asyncio
    async def test_market_adapter_instantiation(self):
        """Test that concrete market adapter can be instantiated."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        assert isinstance(adapter, MarketAdapter)
        assert adapter.quote_adapter is quote_adapter
        assert len(adapter.pending_orders) == 0

    @pytest.mark.asyncio
    async def test_submit_order(self):
        """Test order submission."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            price=None
        )
        
        submitted = await adapter.submit_order(order)
        
        assert submitted.id is not None
        assert submitted.status == OrderStatus.PENDING
        assert submitted.created_at is not None
        assert len(adapter.pending_orders) == 1
        assert len(adapter.submitted_orders) == 1

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        """Test order cancellation."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.0
        )
        
        submitted = await adapter.submit_order(order)
        assert len(adapter.pending_orders) == 1
        
        # Test successful cancellation
        cancelled = adapter.cancel_order(submitted.id)
        assert cancelled is True
        assert len(adapter.pending_orders) == 0
        assert submitted.status == OrderStatus.CANCELLED
        
        # Test cancellation of non-existent order
        not_cancelled = adapter.cancel_order("nonexistent-id")
        assert not_cancelled is False

    @pytest.mark.asyncio
    async def test_get_pending_orders(self):
        """Test getting pending orders."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        # Test empty
        pending = adapter.get_pending_orders()
        assert len(pending) == 0
        
        # Add some orders
        order1 = Order(symbol="AAPL", order_type=OrderType.BUY, condition=OrderCondition.MARKET, quantity=100)
        order2 = Order(symbol="GOOGL", order_type=OrderType.SELL, condition=OrderCondition.LIMIT, quantity=50, price=2500.0)
        
        await adapter.submit_order(order1)
        await adapter.submit_order(order2)
        
        pending = adapter.get_pending_orders()
        assert len(pending) == 2
        
        # Test that it returns a copy (modification doesn't affect original)
        pending.clear()
        assert len(adapter.get_pending_orders()) == 2

    @pytest.mark.asyncio
    async def test_simulate_order(self):
        """Test order simulation."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100
        )
        
        simulation = await adapter.simulate_order(order)
        
        assert simulation["success"] is True
        assert "would_fill" in simulation
        assert "estimated_price" in simulation
        assert "estimated_cost" in simulation

    @pytest.mark.asyncio
    async def test_process_pending_orders(self):
        """Test processing pending orders."""
        quote_adapter = MockQuoteAdapter()
        adapter = MockMarketAdapter(quote_adapter)
        
        # Add market and limit orders
        market_order = Order(symbol="AAPL", order_type=OrderType.BUY, condition=OrderCondition.MARKET, quantity=100)
        limit_order = Order(symbol="GOOGL", order_type=OrderType.SELL, condition=OrderCondition.LIMIT, quantity=50, price=2500.0)
        
        await adapter.submit_order(market_order)
        await adapter.submit_order(limit_order)
        
        assert len(adapter.pending_orders) == 2
        
        # Process orders - market orders should fill
        filled = await adapter.process_pending_orders()
        
        assert len(filled) == 1  # Only market order filled
        assert filled[0].symbol == "AAPL"
        assert filled[0].status == OrderStatus.FILLED
        assert filled[0].filled_at is not None
        
        # Limit order should still be pending
        assert len(adapter.pending_orders) == 1
        assert adapter.pending_orders[0].symbol == "GOOGL"
        assert adapter.pending_orders[0].status == OrderStatus.PENDING
