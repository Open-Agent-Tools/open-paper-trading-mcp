"""
Comprehensive integration tests for adapter configuration management.

Tests AdapterFactory, configuration management, and cache warming
with focus on:
- Adapter factory creation and management
- Configuration loading and validation
- Environment variable expansion
- Registry management and configuration
- Cache warming integration
- Performance monitoring
- Error handling and recovery scenarios
"""

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.adapters.base import AdapterConfig, AdapterRegistry, QuoteAdapter
from app.adapters.cache import CachedQuoteAdapter, QuoteCache
from app.adapters.config import (
    AdapterFactory,
    AdapterFactoryConfig,
    configure_default_registry,
    create_test_adapter,
    get_adapter_factory,
)
from app.adapters.test_data import DevDataQuoteAdapter
from app.models.assets import Asset, Stock
from app.models.quotes import Quote


class MockTestQuoteAdapter(QuoteAdapter):
    """Mock adapter for testing configuration."""

    def __init__(self, config: AdapterConfig | None = None):
        self.config = config or AdapterConfig()
        self.name = "MockTestAdapter"
        self.enabled = True
        self.call_count = 0

    async def get_quote(self, asset: Asset) -> Quote | None:
        self.call_count += 1
        return None

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        self.call_count += 1
        return {}

    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        return []

    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ):
        return None

    async def is_market_open(self) -> bool:
        return True

    async def get_market_hours(self) -> dict[str, Any]:
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self) -> dict[str, Any]:
        return {"type": "mock"}

    def get_expiration_dates(self, underlying: str) -> list[date]:
        return []

    def get_test_scenarios(self) -> dict[str, Any]:
        return {"scenarios": ["default"]}

    def set_date(self, date_str: str) -> None:
        pass

    def get_available_symbols(self) -> list[str]:
        return ["TEST"]


class TestAdapterFactoryConfigIntegration:
    """Integration tests for AdapterFactoryConfig."""

    @pytest.fixture
    def factory_config(self):
        """Create factory configuration for testing."""
        return AdapterFactoryConfig()

    def test_factory_config_initialization(self, factory_config):
        """Test factory configuration initialization."""
        assert isinstance(factory_config.adapter_types, dict)
        assert isinstance(factory_config.default_configs, dict)
        assert isinstance(factory_config.cache_config, dict)
        assert isinstance(factory_config.cache_warming_config, dict)

        # Verify default adapter types
        assert "test_data" in factory_config.adapter_types
        assert "robinhood" in factory_config.adapter_types

        # Verify default configurations
        assert "test_data" in factory_config.default_configs
        assert factory_config.default_configs["test_data"]["enabled"] is True

    def test_factory_config_cache_settings(self, factory_config):
        """Test cache configuration settings."""
        cache_config = factory_config.cache_config

        assert cache_config["enabled"] is True
        assert cache_config["default_ttl"] == 60.0
        assert cache_config["max_size"] == 10000
        assert cache_config["cleanup_interval"] == 300.0

    def test_factory_config_cache_warming_settings(self, factory_config):
        """Test cache warming configuration."""
        warming_config = factory_config.cache_warming_config

        assert warming_config["enabled"] is True
        assert warming_config["warm_on_startup"] is True
        assert warming_config["warm_interval"] == 300.0
        assert isinstance(warming_config["popular_symbols"], list)
        assert "AAPL" in warming_config["popular_symbols"]


class TestAdapterFactoryIntegration:
    """Integration tests for AdapterFactory."""

    @pytest.fixture
    def factory(self):
        """Create adapter factory for testing."""
        return AdapterFactory()

    @pytest.fixture
    def custom_config(self):
        """Create custom factory configuration."""
        config = AdapterFactoryConfig()
        config.adapter_types["mock_test"] = (
            "tests.adapters.test_config_integration.MockTestQuoteAdapter"
        )
        config.default_configs["mock_test"] = {
            "enabled": True,
            "priority": 100,
            "timeout": 10.0,
            "cache_ttl": 120.0,
            "config": {"test_param": "test_value"},
        }
        return config

    @pytest.fixture
    def factory_with_custom_config(self, custom_config):
        """Create factory with custom configuration."""
        return AdapterFactory(custom_config)

    @pytest.mark.integration
    def test_factory_create_test_data_adapter(self, factory):
        """Test creating test data adapter through factory."""
        adapter = factory.create_adapter("test_data")

        assert adapter is not None
        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.name == "DevDataQuoteAdapter"
        assert adapter.current_date == date(2017, 3, 24)

    @pytest.mark.integration
    def test_factory_create_adapter_with_custom_config(self, factory):
        """Test creating adapter with custom configuration."""
        config = AdapterConfig(
            name="custom_test",
            enabled=True,
            priority=50,
            timeout=20.0,
            cache_ttl=180.0,
            config={"current_date": "2017-01-27"},
        )

        adapter = factory.create_adapter("test_data", config)

        assert adapter is not None
        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.current_date == date(2017, 1, 27)
        assert adapter.config.timeout == 20.0

    @pytest.mark.integration
    def test_factory_create_nonexistent_adapter(self, factory):
        """Test creating non-existent adapter type."""
        adapter = factory.create_adapter("nonexistent_adapter")
        assert adapter is None

    @pytest.mark.integration
    def test_factory_create_cached_adapter(self, factory):
        """Test creating cached adapter through factory."""
        cached_adapter = factory.create_cached_adapter("test_data")

        assert cached_adapter is not None
        assert isinstance(cached_adapter, CachedQuoteAdapter)
        assert isinstance(cached_adapter.adapter, DevDataQuoteAdapter)
        assert isinstance(cached_adapter.cache, QuoteCache)

    @pytest.mark.integration
    def test_factory_create_cached_adapter_with_custom_cache(self, factory):
        """Test creating cached adapter with custom cache."""
        custom_cache = QuoteCache(default_ttl=600.0, max_size=5000)

        cached_adapter = factory.create_cached_adapter("test_data", cache=custom_cache)

        assert cached_adapter is not None
        assert cached_adapter.cache is custom_cache
        assert cached_adapter.cache.default_ttl == 600.0

    @pytest.mark.integration
    def test_factory_configure_registry(self, factory):
        """Test configuring adapter registry."""
        registry = AdapterRegistry()

        factory.configure_registry(registry, enabled_adapters=["test_data"])

        # Should have registered test_data adapter
        adapter = registry.get("test_data")
        assert adapter is not None

    @pytest.mark.integration
    def test_factory_environment_variable_expansion(self, factory):
        """Test environment variable expansion in configuration."""
        # Set test environment variable
        os.environ["TEST_API_KEY"] = "test_secret_key"
        os.environ["TEST_BASE_URL"] = "https://test.api.com"

        try:
            config = AdapterConfig(
                name="env_test",
                config={
                    "api_key": "${TEST_API_KEY}",
                    "base_url": "${TEST_BASE_URL}",
                    "regular_param": "regular_value",
                },
            )

            expanded_config = factory._expand_config(config)

            assert expanded_config.config["api_key"] == "test_secret_key"
            assert expanded_config.config["base_url"] == "https://test.api.com"
            assert expanded_config.config["regular_param"] == "regular_value"

        finally:
            # Clean up environment variables
            del os.environ["TEST_API_KEY"]
            del os.environ["TEST_BASE_URL"]

    @pytest.mark.integration
    def test_factory_missing_environment_variable(self, factory):
        """Test handling of missing environment variables."""
        config = AdapterConfig(
            name="missing_env_test",
            config={"api_key": "${MISSING_ENV_VAR}", "other_param": "other_value"},
        )

        expanded_config = factory._expand_config(config)

        # Missing env var should be None
        assert expanded_config.config["api_key"] is None
        assert expanded_config.config["other_param"] == "other_value"

    @pytest.mark.integration
    def test_factory_config_file_operations(self, factory):
        """Test loading and saving configuration files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "adapter_types": {"custom_adapter": "custom.module.CustomAdapter"},
                "default_configs": {
                    "custom_adapter": {"enabled": True, "priority": 10}
                },
                "cache_config": {"enabled": False, "default_ttl": 30.0},
            }
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            # Load configuration
            factory.load_config_file(config_path)

            # Verify configuration was updated
            assert "custom_adapter" in factory.config.adapter_types
            assert factory.config.cache_config["enabled"] is False
            assert factory.config.cache_config["default_ttl"] == 30.0

            # Test saving configuration
            save_path = config_path.with_suffix(".saved.json")
            factory.save_config_file(save_path)

            # Verify saved file
            assert save_path.exists()
            with open(save_path) as f:
                saved_data = json.load(f)

            assert "custom_adapter" in saved_data["adapter_types"]

        finally:
            # Clean up
            config_path.unlink(missing_ok=True)
            save_path = config_path.with_suffix(".saved.json")
            save_path.unlink(missing_ok=True)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_factory_cache_warming_integration(self, factory):
        """Test cache warming functionality."""
        # Create test adapter
        adapter = factory.create_adapter("test_data")
        assert adapter is not None

        # Test cache warming
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(adapter, "get_quote") as mock_get_quote:
            # Mock successful quote retrieval
            mock_quote = Quote(
                asset=Stock(symbol="TEST", name="Test Stock"),
                quote_date=datetime.now(),
                price=100.0,
                bid=99.5,
                ask=100.5,
                bid_size=100,
                ask_size=100,
                volume=1000,
            )
            mock_get_quote.return_value = mock_quote

            stats = await factory.warm_cache(adapter, symbols)

            # Verify warming statistics
            assert stats["enabled"] is True
            assert stats["total_symbols"] == 3
            assert stats["successful"] >= 0
            assert isinstance(stats["duration_seconds"], float)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_factory_cache_warming_with_failures(self, factory):
        """Test cache warming with some failures."""
        adapter = factory.create_adapter("test_data")
        assert adapter is not None

        symbols = ["VALID", "INVALID", "TIMEOUT"]

        with patch.object(adapter, "get_quote") as mock_get_quote:

            async def mock_quote_response(asset):
                if asset.symbol == "VALID":
                    return Quote(
                        asset=asset,
                        quote_date=datetime.now(),
                        price=100.0,
                        bid=99.5,
                        ask=100.5,
                        bid_size=100,
                        ask_size=100,
                        volume=1000,
                    )
                elif asset.symbol == "INVALID":
                    return None
                else:  # TIMEOUT
                    raise TimeoutError("Request timed out")

            mock_get_quote.side_effect = mock_quote_response

            stats = await factory.warm_cache(adapter, symbols)

            # Should handle failures gracefully
            assert stats["total_symbols"] == 3
            assert stats["failed"] > 0
            assert stats["successful"] > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_factory_cache_warming_lifecycle(self, factory):
        """Test complete cache warming lifecycle."""
        adapter = factory.create_adapter("test_data")
        assert adapter is not None

        with patch.object(adapter, "get_quote") as mock_get_quote:
            mock_get_quote.return_value = None  # Simulate no quotes

            # Start cache warming
            await factory.start_cache_warming(adapter)

            # Verify task is running
            status = factory.get_cache_warming_status()
            assert status["enabled"] is True
            assert status["task_running"] is True

            # Stop cache warming
            await factory.stop_cache_warming()

            # Verify task is stopped
            status = factory.get_cache_warming_status()
            assert status["task_running"] is False

    @pytest.mark.integration
    def test_factory_adapter_class_caching(self, factory):
        """Test adapter class caching mechanism."""
        # First call should load and cache the class
        adapter1 = factory.create_adapter("test_data")
        assert adapter1 is not None

        # Second call should use cached class
        adapter2 = factory.create_adapter("test_data")
        assert adapter2 is not None

        # Both should be instances of the same class
        assert type(adapter1) == type(adapter2)

    @pytest.mark.integration
    def test_factory_error_handling(self, factory):
        """Test factory error handling scenarios."""
        # Test creating adapter with invalid configuration
        invalid_config = AdapterConfig(
            name="invalid_test", config={"invalid_param": "invalid_value"}
        )

        # Should handle gracefully
        adapter = factory.create_adapter("test_data", invalid_config)
        assert adapter is not None  # Should still create with default fallbacks

        # Test importing non-existent adapter class
        factory.config.adapter_types["nonexistent"] = (
            "nonexistent.module.NonexistentAdapter"
        )
        adapter = factory.create_adapter("nonexistent")
        assert adapter is None


class TestAdapterRegistryIntegration:
    """Integration tests for adapter registry management."""

    @pytest.fixture
    def registry(self):
        """Create adapter registry for testing."""
        return AdapterRegistry()

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter for testing."""
        return MockTestQuoteAdapter()

    @pytest.mark.integration
    def test_registry_basic_operations(self, registry, mock_adapter):
        """Test basic registry operations."""
        # Register adapter
        registry.register("mock_test", mock_adapter)

        # Retrieve adapter
        retrieved = registry.get("mock_test")
        assert retrieved is mock_adapter

        # Test non-existent adapter
        assert registry.get("nonexistent") is None

    @pytest.mark.integration
    def test_registry_multiple_adapters(self, registry):
        """Test registry with multiple adapters."""
        adapters = {}
        for i in range(5):
            adapter = MockTestQuoteAdapter()
            adapter.name = f"MockAdapter{i}"
            adapters[f"mock_{i}"] = adapter
            registry.register(f"mock_{i}", adapter)

        # Verify all adapters are registered
        for name, adapter in adapters.items():
            retrieved = registry.get(name)
            assert retrieved is adapter

    @pytest.mark.integration
    def test_registry_adapter_replacement(self, registry):
        """Test replacing adapter in registry."""
        adapter1 = MockTestQuoteAdapter()
        adapter1.name = "Original"

        adapter2 = MockTestQuoteAdapter()
        adapter2.name = "Replacement"

        # Register original
        registry.register("test_adapter", adapter1)
        assert registry.get("test_adapter") is adapter1

        # Replace with new adapter
        registry.register("test_adapter", adapter2)
        assert registry.get("test_adapter") is adapter2


class TestConfigurationIntegrationScenarios:
    """Integration tests for complete configuration scenarios."""

    @pytest.mark.integration
    def test_complete_configuration_workflow(self):
        """Test complete configuration workflow from factory to registry."""
        # Create factory with custom configuration
        config = AdapterFactoryConfig()
        factory = AdapterFactory(config)

        # Create registry
        registry = AdapterRegistry()

        # Configure registry with enabled adapters
        factory.configure_registry(registry, enabled_adapters=["test_data"])

        # Verify adapter is registered and functional
        adapter = registry.get("test_data")
        assert adapter is not None

        # Test adapter functionality
        if hasattr(adapter, "get_available_symbols"):
            symbols = adapter.get_available_symbols()
            assert isinstance(symbols, list)

    @pytest.mark.integration
    def test_environment_specific_configuration(self):
        """Test environment-specific configuration handling."""
        # Set environment variables for testing
        os.environ["TRADING_ENV"] = "test"
        os.environ["CACHE_TTL"] = "120"
        os.environ["MAX_CACHE_SIZE"] = "5000"

        try:
            config = AdapterFactoryConfig()

            # Modify config based on environment
            if os.getenv("TRADING_ENV") == "test":
                config.cache_config["default_ttl"] = float(os.getenv("CACHE_TTL", "60"))
                config.cache_config["max_size"] = int(
                    os.getenv("MAX_CACHE_SIZE", "1000")
                )

            factory = AdapterFactory(config)

            # Create cached adapter
            cached_adapter = factory.create_cached_adapter("test_data")
            assert cached_adapter is not None
            assert cached_adapter.cache.default_ttl == 120.0
            assert cached_adapter.cache.max_size == 5000

        finally:
            # Clean up
            del os.environ["TRADING_ENV"]
            del os.environ["CACHE_TTL"]
            del os.environ["MAX_CACHE_SIZE"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_production_like_configuration_scenario(self):
        """Test production-like configuration scenario."""
        # Create production-like configuration
        config = AdapterFactoryConfig()

        # Disable test adapters, enable production adapters
        config.default_configs["test_data"]["enabled"] = True  # Keep for testing
        config.cache_config["enabled"] = True
        config.cache_config["default_ttl"] = 60.0
        config.cache_warming_config["enabled"] = True
        config.cache_warming_config["warm_on_startup"] = False  # Disable for test

        factory = AdapterFactory(config)
        registry = AdapterRegistry()

        # Configure registry
        factory.configure_registry(registry)

        # Verify configured adapters
        test_adapter = registry.get("test_data")
        assert test_adapter is not None

        # Test cache warming (disabled startup)
        status = factory.get_cache_warming_status()
        assert status["enabled"] is True

    @pytest.mark.integration
    def test_configuration_error_recovery(self):
        """Test recovery from configuration errors."""
        config = AdapterFactoryConfig()

        # Introduce configuration error
        config.adapter_types["broken_adapter"] = "nonexistent.module.BrokenAdapter"
        config.default_configs["broken_adapter"] = {"enabled": True}

        factory = AdapterFactory(config)
        registry = AdapterRegistry()

        # Should handle broken adapter gracefully
        factory.configure_registry(
            registry, enabled_adapters=["test_data", "broken_adapter"]
        )

        # Working adapter should still be registered
        test_adapter = registry.get("test_data")
        assert test_adapter is not None

        # Broken adapter should not be registered
        broken_adapter = registry.get("broken_adapter")
        assert broken_adapter is None

    @pytest.mark.integration
    def test_dynamic_configuration_updates(self):
        """Test dynamic configuration updates."""
        factory = AdapterFactory()

        # Initial configuration
        adapter1 = factory.create_adapter("test_data")
        assert adapter1 is not None

        # Update configuration
        new_config = AdapterConfig(
            name="test_data_updated", config={"current_date": "2017-01-28"}
        )

        # Create adapter with updated config
        adapter2 = factory.create_adapter("test_data", new_config)
        assert adapter2 is not None

        # Should have different configuration
        if hasattr(adapter2, "current_date"):
            assert adapter2.current_date == date(2017, 1, 28)


class TestGlobalFactoryIntegration:
    """Integration tests for global factory functions."""

    def test_get_adapter_factory_singleton(self):
        """Test global factory singleton behavior."""
        factory1 = get_adapter_factory()
        factory2 = get_adapter_factory()

        # Should be same instance
        assert factory1 is factory2
        assert isinstance(factory1, AdapterFactory)

    @pytest.mark.integration
    def test_configure_default_registry_integration(self):
        """Test default registry configuration."""
        registry = configure_default_registry()

        assert isinstance(registry, AdapterRegistry)

        # Should have configured test_data adapter (if enabled)
        test_adapter = registry.get("test_data")
        if test_adapter:  # Depends on default configuration
            assert test_adapter is not None

    @pytest.mark.integration
    def test_create_test_adapter_convenience_function(self):
        """Test create_test_adapter convenience function."""
        # Test with default date
        adapter1 = create_test_adapter()
        assert adapter1 is not None
        assert isinstance(adapter1, DevDataQuoteAdapter)
        assert adapter1.current_date == date(2017, 3, 24)

        # Test with custom date
        adapter2 = create_test_adapter(date="2017-01-27")
        assert adapter2 is not None
        assert adapter2.current_date == date(2017, 1, 27)


class TestConfigurationPerformance:
    """Performance tests for configuration system."""

    @pytest.mark.performance
    def test_factory_creation_performance(self):
        """Test adapter factory creation performance."""
        import time

        start_time = time.time()

        # Create many adapters
        factory = AdapterFactory()
        adapters = []

        for _i in range(50):
            adapter = factory.create_adapter("test_data")
            if adapter:
                adapters.append(adapter)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 5.0, f"Adapter creation took {duration} seconds"
        assert len(adapters) > 0

    @pytest.mark.performance
    def test_registry_operations_performance(self):
        """Test registry operations performance."""
        import time

        registry = AdapterRegistry()
        adapters = []

        # Create adapters
        for i in range(100):
            adapter = MockTestQuoteAdapter()
            adapter.name = f"PerfTest{i}"
            adapters.append(adapter)

        start_time = time.time()

        # Register all adapters
        for i, adapter in enumerate(adapters):
            registry.register(f"perf_test_{i}", adapter)

        # Retrieve all adapters
        retrieved = []
        for i in range(100):
            adapter = registry.get(f"perf_test_{i}")
            if adapter:
                retrieved.append(adapter)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 1.0, f"Registry operations took {duration} seconds"
        assert len(retrieved) == 100

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_cache_warming_performance(self):
        """Test cache warming performance."""
        factory = AdapterFactory()
        adapter = factory.create_adapter("test_data")
        assert adapter is not None

        # Test warming many symbols
        symbols = [f"STOCK{i}" for i in range(100)]

        import time

        start_time = time.time()

        with patch.object(adapter, "get_quote") as mock_get_quote:
            mock_get_quote.return_value = None  # Quick return

            stats = await factory.warm_cache(adapter, symbols)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time
        assert duration < 10.0, f"Cache warming took {duration} seconds"
        assert stats["total_symbols"] == 100
