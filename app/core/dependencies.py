"""
FastAPI dependencies for dependency injection.

This module provides shared dependencies that can be used across
all API endpoints, following FastAPI best practices.
"""

from typing import cast

from fastapi import Request

from app.services.trading_service import TradingService


def get_trading_service(request: Request) -> TradingService:
    """
    Dependency to get the TradingService instance from application state.

    This replaces the global service instance with proper FastAPI dependency injection.

    Args:
        request: FastAPI Request object containing application state

    Returns:
        TradingService instance from application state

    Raises:
        RuntimeError: If TradingService is not found in application state
    """
    trading_service = getattr(request.app.state, "trading_service", None)
    if trading_service is None:
        raise RuntimeError(
            "TradingService not found in application state. "
            "Ensure the service is initialized in the lifespan context manager."
        )
    return cast(TradingService, trading_service)
