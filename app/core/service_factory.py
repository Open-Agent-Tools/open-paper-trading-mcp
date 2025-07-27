"""
Service factory for creating and configuring service instances.

This module provides centralized service creation logic and handles
the complexity of service dependencies and configuration.
"""

from typing import TYPE_CHECKING

from app.adapters.base import QuoteAdapter
from app.core.container import container

if TYPE_CHECKING:
    from app.services.trading_service import TradingService


def create_trading_service(account_owner: str = "default") -> "TradingService":
    """Create and configure a TradingService instance.

    Args:
        account_owner: The account owner identifier

    Returns:
        Configured TradingService instance
    """
    from app.services.trading_service import TradingService

    quote_adapter = _get_quote_adapter()
    return TradingService(quote_adapter=quote_adapter, account_owner=account_owner)


def _get_quote_adapter() -> QuoteAdapter:
    """Get the appropriate quote adapter based on environment configuration.

    Returns:
        Configured QuoteAdapter instance
    """
    from app.adapters.config import get_adapter_factory
    from app.core.config import settings

    # Use adapter factory to create quote adapter based on configuration
    factory = get_adapter_factory()

    # Try to get the configured adapter type
    quote_adapter = factory.create_adapter(settings.QUOTE_ADAPTER_TYPE)

    if quote_adapter is None:
        # Fall back to database test data adapter
        quote_adapter = factory.create_adapter("synthetic_data_db")

    if quote_adapter is None:
        # Final fallback to dev data adapter
        from app.adapters.synthetic_data import DevDataQuoteAdapter

        quote_adapter = DevDataQuoteAdapter()

    return quote_adapter


def register_services() -> None:
    """Register all core services in the container.

    This function should be called during application startup to
    populate the service container with all necessary services.
    """
    from app.services.trading_service import TradingService

    # Create and register TradingService
    trading_service = create_trading_service()
    container.register(TradingService, trading_service)


def get_trading_service() -> "TradingService":
    """Get the TradingService from the container.

    Returns:
        The registered TradingService instance

    Raises:
        RuntimeError: If TradingService is not registered
    """
    from app.services.trading_service import TradingService

    return container.get(TradingService)
