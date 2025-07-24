"""
Health check endpoints for system monitoring.

Provides comprehensive health status for all system components including
database connectivity, quote adapter status, and overall system health.
"""

import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.config import get_adapter_factory
from app.core.config import settings
from app.services.trading_service import TradingService
from app.storage.database import get_async_db

router = APIRouter()


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


async def check_database_health(db: AsyncSession) -> dict[str, Any]:
    """Check database connectivity and performance."""
    start_time = time.time()

    try:
        # Test basic connectivity
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        # Test table access
        await db.execute(text("SELECT COUNT(*) FROM accounts"))

        response_time = (time.time() - start_time) * 1000  # ms

        return {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": round(response_time, 2),
            "message": "Database is operational",
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "message": f"Database error: {e!s}",
        }


async def check_quote_adapter_health() -> dict[str, Any]:
    """Check quote adapter connectivity and performance."""
    start_time = time.time()

    try:
        adapter_factory = get_adapter_factory()
        adapter = adapter_factory.create_adapter(
            "test_data"
        )  # Use test adapter for health checks

        if not adapter:
            return {
                "status": HealthStatus.UNHEALTHY,
                "adapter_type": "test_data",
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "message": "Failed to create quote adapter",
            }

        # Test quote retrieval for a common symbol
        from app.models.assets import Stock

        asset = Stock(symbol="AAPL", name="Apple Inc.")
        quote = await adapter.get_quote(asset)

        if quote and quote.price is not None and quote.price > 0:
            response_time = (time.time() - start_time) * 1000  # ms

            return {
                "status": HealthStatus.HEALTHY,
                "adapter_type": getattr(adapter, "name", "unknown"),
                "response_time_ms": round(response_time, 2),
                "message": "Quote adapter is operational",
                "sample_quote": {
                    "symbol": quote.asset.symbol,
                    "price": quote.price,
                    "timestamp": (
                        quote.quote_date.isoformat() if quote.quote_date else None
                    ),
                },
            }
        else:
            return {
                "status": HealthStatus.DEGRADED,
                "adapter_type": getattr(adapter, "name", "unknown"),
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "message": "Quote adapter returned invalid data",
            }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "message": f"Quote adapter error: {e!s}",
        }


async def check_trading_service_health(db: AsyncSession) -> dict[str, Any]:
    """Check trading service functionality."""
    start_time = time.time()

    try:
        # Create a test trading service instance
        service = TradingService(account_owner="health_check_user")

        # Test basic operations
        await service._ensure_account_exists()

        # Test portfolio calculation
        portfolio = await service.get_portfolio()

        response_time = (time.time() - start_time) * 1000  # ms

        return {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": round(response_time, 2),
            "message": "Trading service is operational",
            "portfolio_check": {
                "cash_balance": portfolio.cash_balance,
                "positions_count": len(portfolio.positions),
            },
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "message": f"Trading service error: {e!s}",
        }


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "open-paper-trading-mcp",
        "version": settings.VERSION if hasattr(settings, "VERSION") else "1.0.0",
    }


@router.get("/health/live", response_model=dict[str, Any])
async def liveness_check() -> dict[str, Any]:
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/ready", response_model=dict[str, Any])
async def readiness_check(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict[str, Any]:
    """Kubernetes readiness probe endpoint."""
    # Check database connectivity
    db_health = await check_database_health(db)

    if db_health["status"] == HealthStatus.UNHEALTHY:
        return {
            "status": "not_ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "reason": "Database unavailable",
        }

    return {"status": "ready", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/detailed", response_model=dict[str, Any])
async def detailed_health_check(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict[str, Any]:
    """Detailed health check of all system components."""
    start_time = time.time()

    # Check all components
    db_health = await check_database_health(db)
    quote_health = await check_quote_adapter_health()
    service_health = await check_trading_service_health(db)

    # Determine overall status
    statuses = [db_health["status"], quote_health["status"], service_health["status"]]

    if all(s == HealthStatus.HEALTHY for s in statuses):
        overall_status = HealthStatus.HEALTHY
    elif any(s == HealthStatus.UNHEALTHY for s in statuses):
        overall_status = HealthStatus.UNHEALTHY
    else:
        overall_status = HealthStatus.DEGRADED

    total_time = (time.time() - start_time) * 1000  # ms

    return {
        "status": overall_status,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_check_time_ms": round(total_time, 2),
        "components": {
            "database": db_health,
            "quote_adapter": quote_health,
            "trading_service": service_health,
        },
        "system_info": {
            "service": "open-paper-trading-mcp",
            "version": settings.VERSION if hasattr(settings, "VERSION") else "1.0.0",
            "environment": (
                settings.ENVIRONMENT
                if hasattr(settings, "ENVIRONMENT")
                else "production"
            ),
        },
    }


@router.get("/health/metrics", response_model=dict[str, Any])
async def health_metrics(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict[str, Any]:
    """Return health metrics in Prometheus format."""
    # Collect metrics
    db_health = await check_database_health(db)
    quote_health = await check_quote_adapter_health()
    service_health = await check_trading_service_health(db)

    # Convert to Prometheus-style metrics
    metrics = []

    # Database metrics
    db_status = 1 if db_health["status"] == HealthStatus.HEALTHY else 0
    metrics.append(f'health_database_up{{service="open-paper-trading"}} {db_status}')
    metrics.append(
        f'health_database_response_ms{{service="open-paper-trading"}} {db_health["response_time_ms"]}'
    )

    # Quote adapter metrics
    quote_status = 1 if quote_health["status"] == HealthStatus.HEALTHY else 0
    metrics.append(
        f'health_quote_adapter_up{{service="open-paper-trading",adapter="{quote_health["adapter_type"]}"}} {quote_status}'
    )
    metrics.append(
        f'health_quote_adapter_response_ms{{service="open-paper-trading"}} {quote_health["response_time_ms"]}'
    )

    # Trading service metrics
    service_status = 1 if service_health["status"] == HealthStatus.HEALTHY else 0
    metrics.append(
        f'health_trading_service_up{{service="open-paper-trading"}} {service_status}'
    )
    metrics.append(
        f'health_trading_service_response_ms{{service="open-paper-trading"}} {service_health["response_time_ms"]}'
    )

    # Overall health
    overall_health = min(db_status, quote_status, service_status)
    metrics.append(
        f'health_overall_up{{service="open-paper-trading"}} {overall_health}'
    )

    return {"metrics": "\n".join(metrics), "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/dependencies", response_model=dict[str, Any])
async def dependency_health_check() -> dict[str, Any]:
    """Check health of external dependencies."""
    dependencies = []

    # PostgreSQL Database
    dependencies.append(
        {
            "name": "PostgreSQL",
            "type": "database",
            "required": True,
            "description": "Primary data store for trading state",
        }
    )

    # Quote Provider (Robinhood/Test)
    adapter_type = (
        settings.QUOTE_ADAPTER_TYPE
        if hasattr(settings, "QUOTE_ADAPTER_TYPE")
        else "test"
    )
    dependencies.append(
        {
            "name": f"Quote Provider ({adapter_type})",
            "type": "external_api",
            "required": True,
            "description": "Market data provider for real-time quotes",
        }
    )

    # Redis (if caching is enabled)
    if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
        dependencies.append(
            {
                "name": "Redis",
                "type": "cache",
                "required": False,
                "description": "Optional caching layer for performance",
            }
        )

    return {"dependencies": dependencies, "timestamp": datetime.now(UTC).isoformat()}
