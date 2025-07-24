"""
Base module for MCP tools providing shared service access.

This module eliminates the need for duplicated global state across
MCP tool modules by providing centralized service access through
the dependency injection container.
"""

from typing import TYPE_CHECKING

from app.core.container import container

if TYPE_CHECKING:
    from app.services.trading_service import TradingService


def get_trading_service() -> "TradingService":
    """Get the TradingService instance from the container.

    Returns:
        The registered TradingService instance

    Raises:
        RuntimeError: If TradingService is not registered in container
    """
    from app.services.trading_service import TradingService

    return container.get(TradingService)


def is_trading_service_available() -> bool:
    """Check if TradingService is available in the container.

    Returns:
        True if TradingService is registered, False otherwise
    """
    from app.services.trading_service import TradingService

    return container.is_registered(TradingService)
