"""
Quote adapters package for market data integration.

This package provides a pluggable framework for accessing market data from
different sources with caching, fallback support, and configuration management.
"""

from .base import (AdapterConfig, AdapterRegistry, QuoteAdapter,
                   adapter_registry, get_adapter_registry)
from .cache import (CachedQuoteAdapter, CacheEntry, QuoteCache, cached_adapter,
                    get_global_cache)
from .config import (AdapterFactory, AdapterFactoryConfig,
                     configure_default_registry, create_test_adapter,
                     get_adapter_factory)
from .test_data import DevDataQuoteAdapter, TestDataError, get_test_adapter

__all__ = [
    "AdapterConfig",
    # Configuration
    "AdapterFactory",
    "AdapterFactoryConfig",
    "AdapterRegistry",
    "CacheEntry",
    "CachedQuoteAdapter",
    # Test data
    "DevDataQuoteAdapter",
    # Base classes
    "QuoteAdapter",
    # Caching
    "QuoteCache",
    "TestDataError",
    "adapter_registry",
    "cached_adapter",
    "configure_default_registry",
    "create_test_adapter",
    "get_adapter_factory",
    "get_adapter_registry",
    "get_global_cache",
    "get_test_adapter",
]


def initialize_adapters() -> None:
    """
    Initialize the adapter system with default configuration.

    This function sets up the global adapter registry with available
    adapters and caching enabled.
    """
    configure_default_registry()


# Auto-initialize when package is imported
initialize_adapters()
