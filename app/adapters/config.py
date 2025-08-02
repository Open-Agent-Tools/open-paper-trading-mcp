"""
Adapter configuration management system.
"""

import asyncio
import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import logger

from .base import AdapterConfig, AdapterRegistry, QuoteAdapter
from .cache import CachedQuoteAdapter, QuoteCache
from .synthetic_data import DevDataQuoteAdapter


@dataclass
class AdapterFactoryConfig:
    """Configuration for adapter factory."""

    # Adapter type mappings
    adapter_types: dict[str, str] = field(
        default_factory=lambda: {
            "test_data": "app.adapters.synthetic_data.DevDataQuoteAdapter",
            "test_data_db": "app.adapters.synthetic_data_db.TestDataDBQuoteAdapter",
            "robinhood": "app.adapters.robinhood.RobinhoodAdapter",
            "polygon": "app.adapters.polygon.PolygonQuoteAdapter",  # Future
            "yahoo": "app.adapters.yahoo.YahooQuoteAdapter",  # Future
            "alpha_vantage": "app.adapters.alpha_vantage.AlphaVantageQuoteAdapter",  # Future
        }
    )

    # Default adapter configurations
    default_configs: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "test_data": {
                "enabled": True,
                "priority": 999,  # Lowest priority (fallback)
                "timeout": 5.0,
                "cache_ttl": 3600.0,  # 1 hour for test data
                "config": {"current_date": "${TEST_DATE}"},
            },
            "test_data_db": {
                "enabled": True,
                "priority": 998,  # Slightly higher priority than CSV test data
                "timeout": 5.0,
                "cache_ttl": 3600.0,  # 1 hour for test data
                "config": {"current_date": "${TEST_DATE}", "scenario": "${TEST_SCENARIO}"},
            },
            "robinhood": {
                "enabled": True,  # Requires credentials
                "priority": 1,  # Highest priority for live trading
                "timeout": 30.0,
                "cache_ttl": 300.0,  # 5 minutes for live data
                "config": {
                    "username": "${ROBINHOOD_USERNAME}",
                    "password": "${ROBINHOOD_PASSWORD}",
                    "token_path": "${ROBINHOOD_TOKEN_PATH}",
                },
            },
            "polygon": {
                "enabled": False,  # Requires API key
                "priority": 10,  # High priority for production
                "timeout": 10.0,
                "cache_ttl": 60.0,  # 1 minute for live data
                "config": {
                    "api_key": "${POLYGON_API_KEY}",
                    "base_url": "https://api.polygon.io",
                },
            },
            "yahoo": {
                "enabled": False,
                "priority": 50,  # Medium priority
                "timeout": 15.0,
                "cache_ttl": 300.0,  # 5 minutes
                "config": {"base_url": "https://query1.finance.yahoo.com"},
            },
        }
    )

    # Global caching settings
    cache_config: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "default_ttl": 60.0,
            "max_size": 10000,
            "cleanup_interval": 300.0,  # 5 minutes
        }
    )

    # Cache warming configuration
    cache_warming_config: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "warm_on_startup": True,
            "warm_interval": 300.0,  # 5 minutes
            "popular_symbols": [
                "AAPL",
                "GOOGL",
                "MSFT",
                "TSLA",
                "AMZN",
                "NVDA",
                "META",
                "NFLX",
                "SPY",
                "QQQ",
            ],
            "max_concurrent_requests": 5,
            "timeout_per_request": 10.0,
            "retry_failed_symbols": True,
            "log_cache_stats": True,
        }
    )


class AdapterFactory:
    """
    Factory for creating and configuring quote adapters.
    """

    def __init__(self, config: AdapterFactoryConfig | None = None):
        """
        Initialize adapter factory.

        Args:
            config: Factory configuration, creates default if None
        """
        self.config = config or AdapterFactoryConfig()
        self._adapter_cache: dict[str, type[QuoteAdapter]] = {}
        self._cache_warming_task: asyncio.Task[None] | None = None
        self._cache_warming_enabled = self.config.cache_warming_config.get(
            "enabled", False
        )

    def create_adapter(
        self, adapter_type: str, adapter_config: AdapterConfig | None = None
    ) -> QuoteAdapter | None:
        """
        Create an adapter instance.

        Args:
            adapter_type: Type of adapter to create (test_data, polygon, etc.)
            adapter_config: Adapter configuration, uses default if None

        Returns:
            Configured adapter instance or None if creation failed
        """
        # Get adapter class
        adapter_class = self._get_adapter_class(adapter_type)
        if adapter_class is None:
            return None

        # Get configuration
        if adapter_config is None:
            adapter_config = self._create_default_config(adapter_type)

        # Expand environment variables in config
        expanded_config = self._expand_config(adapter_config)

        try:
            # Create adapter instance
            if adapter_type == "test_data":
                # DevDataQuoteAdapter has special constructor
                current_date = expanded_config.config.get("current_date", "2017-03-24")
                adapter = adapter_class(
                    current_date=current_date, config=expanded_config
                )
            elif adapter_type == "test_data_db":
                # TestDataDBQuoteAdapter has special constructor
                current_date = expanded_config.config.get("current_date", "2017-03-24")
                scenario = expanded_config.config.get("scenario", "default")
                adapter = adapter_class(
                    current_date=current_date,
                    scenario=scenario,
                    config=expanded_config,
                )
            elif adapter_type == "robinhood":
                # RobinhoodAdapter has its own config class
                from .robinhood import RobinhoodConfig

                robinhood_config = RobinhoodConfig(
                    name="robinhood",
                    priority=expanded_config.priority,
                    cache_ttl=expanded_config.cache_ttl,
                )
                adapter = adapter_class(config=robinhood_config)
            else:
                # Standard constructor
                adapter = adapter_class(config=expanded_config)

            return adapter  # type: ignore[no-any-return]

        except Exception as e:
            print(f"Failed to create adapter {adapter_type}: {e}")
            return None

    def create_cached_adapter(
        self,
        adapter_type: str,
        adapter_config: AdapterConfig | None = None,
        cache: QuoteCache | None = None,
    ) -> CachedQuoteAdapter | None:
        """
        Create a cached adapter instance.

        Args:
            adapter_type: Type of adapter to create
            adapter_config: Adapter configuration
            cache: Cache instance, creates new one if None

        Returns:
            Cached adapter wrapper or None if creation failed
        """
        base_adapter = self.create_adapter(adapter_type, adapter_config)
        if base_adapter is None:
            return None

        if cache is None:
            cache_config = self.config.cache_config
            cache = QuoteCache(
                default_ttl=cache_config["default_ttl"],
                max_size=cache_config["max_size"],
            )

        return CachedQuoteAdapter(base_adapter, cache)

    def configure_registry(
        self,
        registry: AdapterRegistry,
        enabled_adapters: list[str] | None = None,
    ) -> None:
        """
        Configure an adapter registry with default adapters.

        Args:
            registry: Registry to configure
            enabled_adapters: List of adapter types to enable, enables all
                available if None
        """
        if enabled_adapters is None:
            enabled_adapters = self._get_available_adapters()

        cache_enabled = self.config.cache_config.get("enabled", True)
        shared_cache = None

        if cache_enabled:
            cache_config = self.config.cache_config
            shared_cache = QuoteCache(
                default_ttl=cache_config["default_ttl"],
                max_size=cache_config["max_size"],
            )

        for adapter_type in enabled_adapters:
            # Check if adapter should be enabled
            default_config = self.config.default_configs.get(adapter_type, {})
            if not default_config.get("enabled", False):
                continue

            try:
                adapter: QuoteAdapter | CachedQuoteAdapter | None
                if cache_enabled:
                    adapter = self.create_cached_adapter(
                        adapter_type, cache=shared_cache
                    )
                else:
                    adapter = self.create_adapter(adapter_type)

                if adapter is not None:
                    registry.register(adapter_type, adapter)
                    print(f"Registered adapter: {adapter_type}")

            except Exception as e:
                print(f"Failed to register adapter {adapter_type}: {e}")

    def _get_adapter_class(self, adapter_type: str) -> type[Any] | None:
        """Get adapter class by type."""
        if adapter_type in self._adapter_cache:
            return self._adapter_cache[adapter_type]

        class_path = self.config.adapter_types.get(adapter_type)
        if class_path is None:
            return None

        try:
            # Import the class dynamically
            module_path, class_name = class_path.rsplit(".", 1)

            adapter_class: type[Any]
            if adapter_type == "test_data":
                # Import from current package
                from .synthetic_data import DevDataQuoteAdapter

                adapter_class = DevDataQuoteAdapter
            elif adapter_type == "test_data_db":
                # Import from current package
                from .synthetic_data_db import (
                    TestDataDBQuoteAdapter as TestDataDBQuoteAdapter,
                )

                adapter_class = TestDataDBQuoteAdapter
            elif adapter_type == "robinhood":
                # Import from current package
                from .robinhood import RobinhoodAdapter

                adapter_class = RobinhoodAdapter
            else:
                # For future adapters, use dynamic import
                import importlib

                module = importlib.import_module(module_path)
                adapter_class = getattr(module, class_name)

            self._adapter_cache[adapter_type] = adapter_class
            return adapter_class

        except (ImportError, AttributeError) as e:
            print(f"Failed to import adapter class {class_path}: {e}")
            return None

    def _create_default_config(self, adapter_type: str) -> AdapterConfig:
        """Create default configuration for adapter type."""
        defaults = self.config.default_configs.get(adapter_type, {})

        return AdapterConfig(
            name=adapter_type,
            enabled=defaults.get("enabled", True),
            priority=defaults.get("priority", 100),
            timeout=defaults.get("timeout", 5.0),
            cache_ttl=defaults.get("cache_ttl", 60.0),
            config=defaults.get("config", {}).copy(),
        )

    def _expand_config(self, config: AdapterConfig) -> AdapterConfig:
        """Expand environment variables in configuration."""
        expanded_config = {}

        for key, value in config.config.items():
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                # Environment variable
                env_var = value[2:-1]
                expanded_value = os.getenv(env_var)
                if expanded_value is None:
                    print(f"Warning: Environment variable {env_var} not set")
                expanded_config[key] = expanded_value
            else:
                expanded_config[key] = value

        # Return new config with expanded values
        return AdapterConfig(
            name=config.name,
            enabled=config.enabled,
            priority=config.priority,
            timeout=config.timeout,
            cache_ttl=config.cache_ttl,
            config=expanded_config,
        )

    def _get_available_adapters(self) -> list[str]:
        """Get list of available adapter types."""
        return list(self.config.adapter_types.keys())

    def load_config_file(self, config_path: Path) -> None:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path) as f:
                config_data = json.load(f)

            # Update configuration
            if "adapter_types" in config_data:
                self.config.adapter_types.update(config_data["adapter_types"])

            if "default_configs" in config_data:
                self.config.default_configs.update(config_data["default_configs"])

            if "cache_config" in config_data:
                self.config.cache_config.update(config_data["cache_config"])

        except Exception as e:
            print(f"Failed to load config file {config_path}: {e}")

    def save_config_file(self, config_path: Path) -> None:
        """
        Save current configuration to JSON file.

        Args:
            config_path: Path to save configuration
        """
        try:
            config_data = asdict(self.config)

            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            print(f"Failed to save config file {config_path}: {e}")

    async def warm_cache(
        self, adapter: QuoteAdapter, symbols: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Warm cache by pre-loading quotes for popular symbols.

        Args:
            adapter: Quote adapter to use for warming
            symbols: List of symbols to warm, uses popular symbols if None

        Returns:
            Dictionary with warming statistics
        """
        if not self._cache_warming_enabled:
            return {"enabled": False, "message": "Cache warming is disabled"}

        symbols = symbols or self.config.cache_warming_config.get("popular_symbols", [])
        max_concurrent = self.config.cache_warming_config.get(
            "max_concurrent_requests", 5
        )
        timeout_per_request = self.config.cache_warming_config.get(
            "timeout_per_request", 10.0
        )
        retry_failed = self.config.cache_warming_config.get(
            "retry_failed_symbols", True
        )

        logger.info(f"Starting cache warming for {len(symbols)} symbols")

        start_time = asyncio.get_event_loop().time()
        successful_symbols = []
        failed_symbols = []

        # Process symbols in batches to avoid overwhelming the API
        semaphore = asyncio.Semaphore(max_concurrent)

        async def warm_single_symbol(symbol: str) -> bool:
            async with semaphore:
                try:
                    # Create stock asset for the symbol
                    from app.models.assets import Stock

                    asset = Stock(symbol=symbol, name=f"{symbol} Stock")

                    # Get quote with timeout
                    quote = await asyncio.wait_for(
                        adapter.get_quote(asset), timeout=timeout_per_request
                    )

                    if quote is not None:
                        successful_symbols.append(symbol)
                        return True
                    else:
                        failed_symbols.append(symbol)
                        return False

                except TimeoutError:
                    logger.warning(f"Timeout warming cache for symbol: {symbol}")
                    failed_symbols.append(symbol)
                    return False
                except Exception as e:
                    logger.warning(f"Error warming cache for symbol {symbol}: {e}")
                    failed_symbols.append(symbol)
                    return False

        # Start warming tasks for all symbols
        tasks = [warm_single_symbol(symbol) for symbol in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Retry failed symbols if configured
        if retry_failed and failed_symbols:
            logger.info(f"Retrying {len(failed_symbols)} failed symbols")
            retry_tasks = [
                warm_single_symbol(symbol) for symbol in failed_symbols.copy()
            ]
            await asyncio.gather(*retry_tasks, return_exceptions=True)

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        stats = {
            "enabled": True,
            "total_symbols": len(symbols),
            "successful": len(successful_symbols),
            "failed": len(failed_symbols),
            "success_rate": (len(successful_symbols) / len(symbols) if symbols else 0),
            "duration_seconds": duration,
            "successful_symbols": successful_symbols,
            "failed_symbols": failed_symbols,
        }

        if self.config.cache_warming_config.get("log_cache_stats", True):
            logger.info(
                f"Cache warming completed: {stats['successful']}/"
                f"{stats['total_symbols']} "
                f"symbols ({stats['success_rate']:.1%}) in {duration:.2f}s"
            )

        return stats

    async def start_cache_warming(self, adapter: QuoteAdapter) -> None:
        """
        Start periodic cache warming task.

        Args:
            adapter: Quote adapter to use for warming
        """
        if not self._cache_warming_enabled:
            return

        warm_interval = self.config.cache_warming_config.get("warm_interval", 300.0)
        warm_on_startup = self.config.cache_warming_config.get("warm_on_startup", True)

        async def warming_loop() -> None:
            # Warm cache on startup if configured
            if warm_on_startup:
                try:
                    await self.warm_cache(adapter)
                except Exception as e:
                    logger.error(f"Error during startup cache warming: {e}")

            # Start periodic warming loop
            while True:
                try:
                    await asyncio.sleep(warm_interval)
                    await self.warm_cache(adapter)
                except asyncio.CancelledError:
                    logger.info("Cache warming task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error during periodic cache warming: {e}")
                    # Continue the loop even if warming fails

        # Start the warming task
        self._cache_warming_task = asyncio.create_task(warming_loop())
        logger.info(f"Started cache warming task with {warm_interval}s interval")

    async def stop_cache_warming(self) -> None:
        """Stop the cache warming task."""
        if self._cache_warming_task and not self._cache_warming_task.done():
            self._cache_warming_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cache_warming_task
            logger.info("Cache warming task stopped")

    def get_cache_warming_status(self) -> dict[str, Any]:
        """Get current cache warming status."""
        return {
            "enabled": self._cache_warming_enabled,
            "task_running": self._cache_warming_task is not None
            and not self._cache_warming_task.done(),
            "config": self.config.cache_warming_config,
        }


# Global factory instance
_global_factory = AdapterFactory()


def get_adapter_factory() -> AdapterFactory:
    """Get the global adapter factory."""
    return _global_factory


def configure_default_registry() -> AdapterRegistry:
    """
    Create and configure a registry with default adapters.

    Returns:
        Configured adapter registry
    """
    from .base import adapter_registry

    factory = get_adapter_factory()
    factory.configure_registry(adapter_registry)

    return adapter_registry


def create_test_adapter(
    date: str = "2017-03-24",
) -> DevDataQuoteAdapter | None:
    """
    Create a test data adapter with caching.

    Args:
        date: Test data date

    Returns:
        Configured test adapter
    """
    factory = get_adapter_factory()
    config = AdapterConfig(
        name="test_data",
        enabled=True,
        priority=999,
        cache_ttl=3600.0,
        config={"current_date": date},
    )

    adapter = factory.create_adapter("test_data", config)
    return adapter if isinstance(adapter, DevDataQuoteAdapter) else None
