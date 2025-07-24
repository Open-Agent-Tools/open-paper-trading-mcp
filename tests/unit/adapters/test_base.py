"""
Comprehensive tests for base adapter classes and registry.
"""

from datetime import date, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from app.adapters.base import (
    AccountAdapter,
    AdapterConfig,
    AdapterRegistry,
    MarketAdapter,
    QuoteAdapter,
    adapter_registry,
    get_adapter_registry,
)
from app.models.assets import Asset, Stock
from app.models.quotes import OptionsChain, Quote
from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType


class TestAdapterConfig:
    """Test suite for AdapterConfig."""

    def test_adapter_config_defaults(self):
        """Test AdapterConfig default values."""
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

    def test_adapter_config_custom_values(self):
        """Test AdapterConfig with custom values."""
        config = AdapterConfig(
            enabled=False,
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://api.example.com",
            name="test_adapter",
            priority=10,
            timeout=15.0,
            cache_ttl=120.0,
            config={"param1": "value1", "param2": 42},
        )

        assert config.enabled is False
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.base_url == "https://api.example.com"
        assert config.name == "test_adapter"
        assert config.priority == 10
        assert config.timeout == 15.0
        assert config.cache_ttl == 120.0
        assert config.config == {"param1": "value1", "param2": 42}

    def test_adapter_config_validation(self):
        """Test AdapterConfig validation."""
        # Test negative timeout
        config = AdapterConfig(timeout=-1.0)
        assert config.timeout == -1.0  # No validation in base model

        # Test negative cache_ttl
        config = AdapterConfig(cache_ttl=-10.0)
        assert config.cache_ttl == -10.0  # No validation in base model


class TestAdapterRegistry:
    """Test suite for AdapterRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return AdapterRegistry()

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert registry.adapters == {}

    def test_register_adapter(self, registry):
        """Test registering an adapter."""
        mock_adapter = Mock()
        registry.register("test_adapter", mock_adapter)

        assert "test_adapter" in registry.adapters
        assert registry.adapters["test_adapter"] is mock_adapter

    def test_get_adapter(self, registry):
        """Test getting an adapter."""
        mock_adapter = Mock()
        registry.register("test_adapter", mock_adapter)

        retrieved = registry.get("test_adapter")
        assert retrieved is mock_adapter

    def test_get_nonexistent_adapter(self, registry):
        """Test getting non-existent adapter."""
        retrieved = registry.get("nonexistent")
        assert retrieved is None

    def test_overwrite_adapter(self, registry):
        """Test overwriting an adapter."""
        mock_adapter1 = Mock()
        mock_adapter2 = Mock()

        registry.register("test_adapter", mock_adapter1)
        registry.register("test_adapter", mock_adapter2)

        retrieved = registry.get("test_adapter")
        assert retrieved is mock_adapter2

    def test_global_registry(self):
        """Test global registry access."""
        global_reg = get_adapter_registry()
        assert global_reg is adapter_registry
        assert isinstance(global_reg, AdapterRegistry)


class MockAccountAdapter(AccountAdapter):
    """Mock implementation of AccountAdapter for testing."""

    def __init__(self):
        self.accounts = {}

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def put_account(self, account: Account) -> None:
        self.accounts[account.id] = account

    def get_account_ids(self) -> list[str]:
        return list(self.accounts.keys())

    def account_exists(self, account_id: str) -> bool:
        return account_id in self.accounts

    def delete_account(self, account_id: str) -> bool:
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False


class TestAccountAdapter:
    """Test suite for AccountAdapter abstract base class."""

    @pytest.fixture
    def adapter(self):
        """Create mock account adapter."""
        return MockAccountAdapter()

    @pytest.fixture
    def sample_account(self):
        """Create a sample account."""
        return Account(
            id="test-123",
            cash_balance=10000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )

    def test_put_and_get_account(self, adapter, sample_account):
        """Test storing and retrieving account."""
        adapter.put_account(sample_account)

        retrieved = adapter.get_account("test-123")
        assert retrieved is not None
        assert retrieved.id == "test-123"
        assert retrieved.cash_balance == 10000.0
        assert retrieved.name == "Test Account"

    def test_get_nonexistent_account(self, adapter):
        """Test getting non-existent account."""
        account = adapter.get_account("nonexistent")
        assert account is None

    def test_account_exists(self, adapter, sample_account):
        """Test account existence check."""
        assert not adapter.account_exists("test-123")

        adapter.put_account(sample_account)
        assert adapter.account_exists("test-123")

    def test_get_account_ids(self, adapter, sample_account):
        """Test getting account IDs."""
        assert adapter.get_account_ids() == []

        adapter.put_account(sample_account)
        account_ids = adapter.get_account_ids()
        assert len(account_ids) == 1
        assert "test-123" in account_ids

    def test_delete_account(self, adapter, sample_account):
        """Test deleting account."""
        adapter.put_account(sample_account)
        assert adapter.account_exists("test-123")

        result = adapter.delete_account("test-123")
        assert result is True
        assert not adapter.account_exists("test-123")

    def test_delete_nonexistent_account(self, adapter):
        """Test deleting non-existent account."""
        result = adapter.delete_account("nonexistent")
        assert result is False

    def test_update_account(self, adapter, sample_account):
        """Test updating existing account."""
        adapter.put_account(sample_account)

        # Update the account
        sample_account.cash_balance = 15000.0
        adapter.put_account(sample_account)

        retrieved = adapter.get_account("test-123")
        assert retrieved.cash_balance == 15000.0


class MockQuoteAdapter(QuoteAdapter):
    """Mock implementation of QuoteAdapter for testing."""

    def __init__(self):
        self.quotes = {}
        self.market_open = True

    async def get_quote(self, asset: Asset) -> Quote | None:
        return self.quotes.get(asset.symbol)

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        results = {}
        for asset in assets:
            quote = await self.get_quote(asset)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        return []

    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> OptionsChain | None:
        return None

    async def is_market_open(self) -> bool:
        return self.market_open

    async def get_market_hours(self) -> dict[str, Any]:
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self) -> dict[str, Any]:
        return {"type": "mock", "quotes": len(self.quotes)}

    def get_expiration_dates(self, underlying: str) -> list[date]:
        return []

    def get_test_scenarios(self) -> dict[str, Any]:
        return {"scenarios": ["default"]}

    def set_date(self, date: str) -> None:
        pass

    def get_available_symbols(self) -> list[str]:
        return list(self.quotes.keys())


class TestQuoteAdapter:
    """Test suite for QuoteAdapter abstract base class."""

    @pytest.fixture
    def adapter(self):
        """Create mock quote adapter."""
        return MockQuoteAdapter()

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock asset."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def sample_quote(self, sample_stock):
        """Create sample quote."""
        return Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, adapter, sample_stock):
        """Test getting non-existent quote."""
        quote = await adapter.get_quote(sample_stock)
        assert quote is None

    @pytest.mark.asyncio
    async def test_get_quotes_empty(self, adapter):
        """Test getting quotes for empty list."""
        quotes = await adapter.get_quotes([])
        assert quotes == {}

    @pytest.mark.asyncio
    async def test_get_quotes_none_found(self, adapter, sample_stock):
        """Test getting quotes when none exist."""
        quotes = await adapter.get_quotes([sample_stock])
        assert quotes == {}

    @pytest.mark.asyncio
    async def test_is_market_open(self, adapter):
        """Test market open status."""
        is_open = await adapter.is_market_open()
        assert is_open is True

    @pytest.mark.asyncio
    async def test_get_market_hours(self, adapter):
        """Test getting market hours."""
        hours = await adapter.get_market_hours()
        assert isinstance(hours, dict)
        assert "open" in hours
        assert "close" in hours

    def test_get_sample_data_info(self, adapter):
        """Test getting sample data info."""
        info = adapter.get_sample_data_info()
        assert isinstance(info, dict)
        assert "type" in info

    def test_get_expiration_dates(self, adapter):
        """Test getting expiration dates."""
        dates = adapter.get_expiration_dates("AAPL")
        assert isinstance(dates, list)

    def test_get_test_scenarios(self, adapter):
        """Test getting test scenarios."""
        scenarios = adapter.get_test_scenarios()
        assert isinstance(scenarios, dict)

    def test_get_available_symbols(self, adapter):
        """Test getting available symbols."""
        symbols = adapter.get_available_symbols()
        assert isinstance(symbols, list)


class MockMarketAdapter(MarketAdapter):
    """Mock implementation of MarketAdapter for testing."""

    def __init__(self, quote_adapter: QuoteAdapter):
        super().__init__(quote_adapter)
        self.filled_orders = []

    async def submit_order(self, order: Order) -> Order:
        if not order.id:
            order.id = f"order-{len(self.pending_orders) + 1}"
        order.status = OrderStatus.PENDING
        self.pending_orders.append(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        for i, order in enumerate(self.pending_orders):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def get_pending_orders(self, account_id: str | None = None) -> list[Order]:
        return self.pending_orders.copy()

    async def simulate_order(self, order: Order) -> dict[str, Any]:
        return {
            "success": True,
            "would_fill": True,
            "estimated_price": 150.0,
            "estimated_cost": order.quantity * 150.0,
        }

    async def process_pending_orders(self) -> list[Order]:
        filled = []
        remaining = []

        for order in self.pending_orders:
            if order.condition == OrderCondition.MARKET:
                order.status = OrderStatus.FILLED
                filled.append(order)
            else:
                remaining.append(order)

        self.pending_orders = remaining
        self.filled_orders.extend(filled)
        return filled


class TestMarketAdapter:
    """Test suite for MarketAdapter abstract base class."""

    @pytest.fixture
    def quote_adapter(self):
        """Create mock quote adapter."""
        return MockQuoteAdapter()

    @pytest.fixture
    def market_adapter(self, quote_adapter):
        """Create mock market adapter."""
        return MockMarketAdapter(quote_adapter)

    @pytest.fixture
    def sample_order(self):
        """Create sample order."""
        return Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            price=None,
        )

    def test_market_adapter_initialization(self, market_adapter, quote_adapter):
        """Test market adapter initialization."""
        assert market_adapter.quote_adapter is quote_adapter
        assert market_adapter.pending_orders == []
        assert market_adapter.filled_orders == []

    @pytest.mark.asyncio
    async def test_submit_order(self, market_adapter, sample_order):
        """Test submitting an order."""
        submitted = await market_adapter.submit_order(sample_order)

        assert submitted.id is not None
        assert submitted.status == OrderStatus.PENDING
        assert len(market_adapter.pending_orders) == 1

    def test_cancel_order(self, market_adapter, sample_order):
        """Test canceling an order."""
        # First submit an order
        import asyncio

        submitted = asyncio.run(market_adapter.submit_order(sample_order))
        order_id = submitted.id

        # Then cancel it
        result = market_adapter.cancel_order(order_id)
        assert result is True
        assert len(market_adapter.pending_orders) == 0

    def test_cancel_nonexistent_order(self, market_adapter):
        """Test canceling non-existent order."""
        result = market_adapter.cancel_order("nonexistent")
        assert result is False

    def test_get_pending_orders(self, market_adapter, sample_order):
        """Test getting pending orders."""
        import asyncio

        asyncio.run(market_adapter.submit_order(sample_order))

        pending = market_adapter.get_pending_orders()
        assert len(pending) == 1
        assert pending[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_simulate_order(self, market_adapter, sample_order):
        """Test simulating an order."""
        simulation = await market_adapter.simulate_order(sample_order)

        assert isinstance(simulation, dict)
        assert "success" in simulation
        assert simulation["success"] is True

    @pytest.mark.asyncio
    async def test_process_pending_orders(self, market_adapter, sample_order):
        """Test processing pending orders."""
        # Submit a market order
        await market_adapter.submit_order(sample_order)

        # Process orders
        filled = await market_adapter.process_pending_orders()

        assert len(filled) == 1
        assert filled[0].status == OrderStatus.FILLED
        assert len(market_adapter.pending_orders) == 0

    @pytest.mark.asyncio
    async def test_process_pending_orders_mixed(self, market_adapter):
        """Test processing mixed order types."""
        # Submit market order
        market_order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
        )
        await market_adapter.submit_order(market_order)

        # Submit limit order
        limit_order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            price=150.0,
        )
        await market_adapter.submit_order(limit_order)

        # Process orders
        filled = await market_adapter.process_pending_orders()

        assert len(filled) == 1  # Only market order filled
        assert len(market_adapter.pending_orders) == 1  # Limit order remains
        assert market_adapter.pending_orders[0].condition == OrderCondition.LIMIT


class TestAdapterErrorHandling:
    """Test error handling in adapter implementations."""

    def test_adapter_config_with_none_values(self):
        """Test AdapterConfig with None values."""
        config = AdapterConfig(api_key=None, base_url=None, config=None)

        assert config.api_key is None
        assert config.base_url is None
        # config field has default_factory so should not be None
        assert config.config == {}

    def test_registry_type_safety(self):
        """Test registry accepts any type."""
        registry = AdapterRegistry()

        # Should accept any object type
        registry.register("string", "test")
        registry.register("int", 42)
        registry.register("dict", {"key": "value"})

        assert registry.get("string") == "test"
        assert registry.get("int") == 42
        assert registry.get("dict") == {"key": "value"}


class TestAdapterIntegration:
    """Integration tests for adapter components."""

    @pytest.mark.asyncio
    async def test_market_adapter_with_quote_adapter(self):
        """Test market adapter integration with quote adapter."""
        quote_adapter = MockQuoteAdapter()
        market_adapter = MockMarketAdapter(quote_adapter)

        # Add a quote to the quote adapter
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Create and submit order
        order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
        )

        # Simulate the order
        simulation = await market_adapter.simulate_order(order)
        assert simulation["success"] is True

        # Submit and process the order
        await market_adapter.submit_order(order)
        filled_orders = await market_adapter.process_pending_orders()

        assert len(filled_orders) == 1
        assert filled_orders[0].symbol == "AAPL"

    def test_adapter_registry_integration(self):
        """Test adapter registry with multiple adapter types."""
        registry = AdapterRegistry()

        quote_adapter = MockQuoteAdapter()
        account_adapter = MockAccountAdapter()

        registry.register("quote", quote_adapter)
        registry.register("account", account_adapter)

        assert registry.get("quote") is quote_adapter
        assert registry.get("account") is account_adapter

        # Test that adapters maintain their independence
        quote_adapter.quotes["TEST"] = Mock()
        account = Account(
            id="test", cash_balance=1000.0, positions=[], name="Test", owner="user"
        )
        account_adapter.put_account(account)

        assert len(quote_adapter.quotes) == 1
        assert len(account_adapter.accounts) == 1


@pytest.mark.asyncio
async def test_abstract_methods_enforcement():
    """Test that abstract methods are properly enforced."""

    # These should raise TypeError if instantiated directly
    with pytest.raises(TypeError):
        AccountAdapter()

    with pytest.raises(TypeError):
        QuoteAdapter()

    with pytest.raises(TypeError):
        MarketAdapter(Mock())


class TestAdapterPerformance:
    """Performance-related tests for adapters."""

    def test_registry_performance(self):
        """Test registry performance with many adapters."""
        registry = AdapterRegistry()

        # Register many adapters
        for i in range(1000):
            adapter_name = f"adapter_{i}"
            adapter = Mock()
            registry.register(adapter_name, adapter)

        # Test retrieval performance
        import time

        start_time = time.time()

        for i in range(1000):
            adapter_name = f"adapter_{i}"
            retrieved = registry.get(adapter_name)
            assert retrieved is not None

        end_time = time.time()

        # Should complete quickly (less than 1 second)
        assert (end_time - start_time) < 1.0

    @pytest.mark.asyncio
    async def test_quote_adapter_batch_performance(self):
        """Test quote adapter batch operations."""
        adapter = MockQuoteAdapter()

        # Create many assets
        assets = []
        for i in range(100):
            stock = Stock(symbol=f"STOCK{i}", name=f"Stock {i}")
            assets.append(stock)

            # Add quote to adapter
            quote = Quote(
                asset=stock,
                quote_date=datetime.now(),
                price=100.0 + i,
                bid=99.5 + i,
                ask=100.5 + i,
                bid_size=100,
                ask_size=100,
                volume=1000,
            )
            adapter.quotes[stock.symbol] = quote

        # Test batch retrieval
        import time

        start_time = time.time()

        quotes = await adapter.get_quotes(assets)

        end_time = time.time()

        assert len(quotes) == 100
        # Should complete quickly
        assert (end_time - start_time) < 1.0
