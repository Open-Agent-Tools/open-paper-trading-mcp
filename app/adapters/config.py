"""
Adapter configuration management system.
"""

import os
import json
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from dataclasses import dataclass, asdict, field

from .base import QuoteAdapter, AdapterConfig, AdapterRegistry
from .test_data import TestDataQuoteAdapter
from .cache import CachedQuoteAdapter, QuoteCache


@dataclass
class AdapterFactoryConfig:
    """Configuration for adapter factory."""

    # Adapter type mappings
    adapter_types: Dict[str, str] = field(
        default_factory=lambda: {
            "test_data": "app.adapters.test_data.TestDataQuoteAdapter",
            "polygon": "app.adapters.polygon.PolygonQuoteAdapter",  # Future
            "yahoo": "app.adapters.yahoo.YahooQuoteAdapter",  # Future
            "alpha_vantage": "app.adapters.alpha_vantage.AlphaVantageQuoteAdapter",  # Future
        }
    )

    # Default adapter configurations
    default_configs: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "test_data": {
                "enabled": True,
                "priority": 999,  # Lowest priority (fallback)
                "timeout": 5.0,
                "cache_ttl": 3600.0,  # 1 hour for test data
                "config": {"current_date": "2017-03-24"},
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
    cache_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "default_ttl": 60.0,
            "max_size": 10000,
            "cleanup_interval": 300.0,  # 5 minutes
        }
    )


class AdapterFactory:
    """
    Factory for creating and configuring quote adapters.
    """

    def __init__(self, config: Optional[AdapterFactoryConfig] = None):
        """
        Initialize adapter factory.

        Args:
            config: Factory configuration, creates default if None
        """
        self.config = config or AdapterFactoryConfig()
        self._adapter_cache: Dict[str, Type[QuoteAdapter]] = {}

    def create_adapter(
        self, adapter_type: str, adapter_config: Optional[AdapterConfig] = None
    ) -> Optional[QuoteAdapter]:
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
                # TestDataQuoteAdapter has special constructor
                current_date = expanded_config.config.get("current_date", "2017-03-24")
                adapter = adapter_class(
                    current_date=current_date, config=expanded_config
                )
            else:
                # Standard constructor
                adapter = adapter_class(config=expanded_config)

            return adapter

        except Exception as e:
            print(f"Failed to create adapter {adapter_type}: {e}")
            return None

    def create_cached_adapter(
        self,
        adapter_type: str,
        adapter_config: Optional[AdapterConfig] = None,
        cache: Optional[QuoteCache] = None,
    ) -> Optional[CachedQuoteAdapter]:
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
        self, registry: AdapterRegistry, enabled_adapters: Optional[List[str]] = None
    ) -> None:
        """
        Configure an adapter registry with default adapters.

        Args:
            registry: Registry to configure
            enabled_adapters: List of adapter types to enable, enables all available if None
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

    def _get_adapter_class(self, adapter_type: str) -> Optional[Type[Any]]:
        """Get adapter class by type."""
        if adapter_type in self._adapter_cache:
            return self._adapter_cache[adapter_type]

        class_path = self.config.adapter_types.get(adapter_type)
        if class_path is None:
            return None

        try:
            # Import the class dynamically
            module_path, class_name = class_path.rsplit(".", 1)

            if adapter_type == "test_data":
                # Import from current package
                from .test_data import TestDataQuoteAdapter

                adapter_class = TestDataQuoteAdapter
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

    def _get_available_adapters(self) -> List[str]:
        """Get list of available adapter types."""
        return list(self.config.adapter_types.keys())

    def load_config_file(self, config_path: Path) -> None:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path, "r") as f:
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


def create_test_adapter(date: str = "2017-03-24") -> TestDataQuoteAdapter:
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

    return factory.create_adapter("test_data", config)
