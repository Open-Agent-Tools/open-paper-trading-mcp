"""
Comprehensive tests for health check endpoints.

Tests for:
- GET /health (basic health check)
- GET /health/live (liveness probe)
- GET /health/ready (readiness probe)
- GET /health/detailed (comprehensive health check)
- GET /health/metrics (Prometheus metrics)
- GET /health/dependencies (dependency listing)

All tests use proper async patterns with comprehensive mocking of database and dependencies.
"""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.config import AdapterFactory
from app.core.config import settings
from app.services.trading_service import TradingService


class TestHealthEndpoints:
    """Test health check endpoints with comprehensive coverage."""

    # GET /health endpoint tests
    @pytest.mark.asyncio
    async def test_health_check_basic_success(self, client):
        """Test basic health check endpoint returns ok status."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["service"] == "open-paper-trading-mcp"
        assert "version" in data

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_health_check_version_fallback(self, client):
        """Test health check uses version fallback when settings.VERSION is not available."""
        with patch.object(settings, "VERSION", None, create=True):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["version"] == "1.0.0"  # Fallback version

    # GET /health/live endpoint tests
    @pytest.mark.asyncio
    async def test_liveness_check_success(self, client):
        """Test liveness probe endpoint."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    # GET /health/ready endpoint tests
    @pytest.mark.asyncio
    async def test_readiness_check_database_healthy(self, client):
        """Test readiness probe when database is healthy."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock database operations to succeed
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.endpoints.health.get_async_db", return_value=mock_db):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_readiness_check_database_unhealthy(self, client):
        """Test readiness probe when database is unhealthy."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock database operations to fail
        mock_db.execute.side_effect = Exception("Connection failed")

        with patch("app.api.v1.endpoints.health.get_async_db", return_value=mock_db):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/ready")

        assert (
            response.status_code == status.HTTP_200_OK
        )  # Readiness still returns 200, but different status
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["reason"] == "Database unavailable"
        assert "timestamp" in data

    # Database health check tests
    @pytest.mark.asyncio
    async def test_check_database_health_success(self):
        """Test database health check function when database is healthy."""
        from app.api.v1.endpoints.health import HealthStatus, check_database_health

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await check_database_health(mock_db)

        assert result["status"] == HealthStatus.HEALTHY
        assert "response_time_ms" in result
        assert result["message"] == "Database is operational"
        assert isinstance(result["response_time_ms"], float)

    @pytest.mark.asyncio
    async def test_check_database_health_connection_failure(self):
        """Test database health check when connection fails."""
        from app.api.v1.endpoints.health import HealthStatus, check_database_health

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = Exception("Connection timeout")

        result = await check_database_health(mock_db)

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "response_time_ms" in result
        assert "Connection timeout" in result["message"]

    @pytest.mark.asyncio
    async def test_check_database_health_table_access_failure(self):
        """Test database health check when table access fails."""
        from app.api.v1.endpoints.health import HealthStatus, check_database_health

        mock_db = AsyncMock(spec=AsyncSession)

        # First query (SELECT 1) succeeds, second query (accounts table) fails
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.side_effect = [mock_result, Exception("Table not found")]

        result = await check_database_health(mock_db)

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Table not found" in result["message"]

    # Quote adapter health check tests
    @pytest.mark.asyncio
    async def test_check_quote_adapter_health_success(self):
        """Test quote adapter health check when adapter is healthy."""
        from app.api.v1.endpoints.health import HealthStatus, check_quote_adapter_health
        from app.models.quotes import StockQuote

        mock_quote = StockQuote(symbol="AAPL", price=150.0, timestamp=datetime.utcnow())

        mock_adapter = AsyncMock()
        mock_adapter.get_quote.return_value = mock_quote
        mock_adapter.adapter_type = "test_data"

        mock_factory = MagicMock(spec=AdapterFactory)
        mock_factory.create_adapter.return_value = mock_adapter

        with patch(
            "app.api.v1.endpoints.health.get_adapter_factory", return_value=mock_factory
        ):
            result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.HEALTHY
        assert result["adapter_type"] == "test_data"
        assert "response_time_ms" in result
        assert result["message"] == "Quote adapter is operational"
        assert "sample_quote" in result
        assert result["sample_quote"]["symbol"] == "AAPL"
        assert result["sample_quote"]["price"] == 150.0

    @pytest.mark.asyncio
    async def test_check_quote_adapter_health_adapter_creation_failure(self):
        """Test quote adapter health check when adapter creation fails."""
        from app.api.v1.endpoints.health import HealthStatus, check_quote_adapter_health

        mock_factory = MagicMock(spec=AdapterFactory)
        mock_factory.create_adapter.return_value = None

        with patch(
            "app.api.v1.endpoints.health.get_adapter_factory", return_value=mock_factory
        ):
            result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.UNHEALTHY
        assert result["adapter_type"] == "test_data"
        assert result["message"] == "Failed to create quote adapter"

    @pytest.mark.asyncio
    async def test_check_quote_adapter_health_invalid_quote_data(self):
        """Test quote adapter health check when adapter returns invalid data."""
        from app.api.v1.endpoints.health import HealthStatus, check_quote_adapter_health
        from app.models.quotes import StockQuote

        mock_quote = StockQuote(symbol="AAPL", price=0.0)  # Invalid price

        mock_adapter = AsyncMock()
        mock_adapter.get_quote.return_value = mock_quote
        mock_adapter.adapter_type = "test_data"

        mock_factory = MagicMock(spec=AdapterFactory)
        mock_factory.create_adapter.return_value = mock_adapter

        with patch(
            "app.api.v1.endpoints.health.get_adapter_factory", return_value=mock_factory
        ):
            result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.DEGRADED
        assert result["message"] == "Quote adapter returned invalid data"

    @pytest.mark.asyncio
    async def test_check_quote_adapter_health_exception(self):
        """Test quote adapter health check when adapter throws exception."""
        from app.api.v1.endpoints.health import HealthStatus, check_quote_adapter_health

        mock_adapter = AsyncMock()
        mock_adapter.get_quote.side_effect = Exception("Network error")
        mock_adapter.adapter_type = "test_data"

        mock_factory = MagicMock(spec=AdapterFactory)
        mock_factory.create_adapter.return_value = mock_adapter

        with patch(
            "app.api.v1.endpoints.health.get_adapter_factory", return_value=mock_factory
        ):
            result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Network error" in result["message"]

    # Trading service health check tests
    @pytest.mark.asyncio
    async def test_check_trading_service_health_success(self):
        """Test trading service health check when service is healthy."""
        from app.api.v1.endpoints.health import (
            HealthStatus,
            check_trading_service_health,
        )
        from app.schemas.positions import Portfolio

        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            market_value=10000.0,
            total_value=10000.0,
        )

        mock_service = AsyncMock(spec=TradingService)
        mock_service._ensure_account_exists = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio

        mock_db = AsyncMock(spec=AsyncSession)

        with patch(
            "app.api.v1.endpoints.health.TradingService", return_value=mock_service
        ):
            result = await check_trading_service_health(mock_db)

        assert result["status"] == HealthStatus.HEALTHY
        assert "response_time_ms" in result
        assert result["message"] == "Trading service is operational"
        assert "portfolio_check" in result
        assert result["portfolio_check"]["cash_balance"] == 10000.0
        assert result["portfolio_check"]["positions_count"] == 0

    @pytest.mark.asyncio
    async def test_check_trading_service_health_failure(self):
        """Test trading service health check when service fails."""
        from app.api.v1.endpoints.health import (
            HealthStatus,
            check_trading_service_health,
        )

        mock_service = AsyncMock(spec=TradingService)
        mock_service._ensure_account_exists.side_effect = Exception("Database error")

        mock_db = AsyncMock(spec=AsyncSession)

        with patch(
            "app.api.v1.endpoints.health.TradingService", return_value=mock_service
        ):
            result = await check_trading_service_health(mock_db)

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Database error" in result["message"]

    # GET /health/detailed endpoint tests
    @pytest.mark.asyncio
    async def test_detailed_health_check_all_healthy(self, client):
        """Test detailed health check when all components are healthy."""
        from app.api.v1.endpoints.health import HealthStatus

        # Mock all health checks to return healthy status
        mock_db_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }

        mock_quote_health = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }

        mock_service_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
            "portfolio_check": {"cash_balance": 10000.0, "positions_count": 0},
        }

        with (
            patch(
                "app.api.v1.endpoints.health.check_database_health",
                return_value=mock_db_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_quote_adapter_health",
                return_value=mock_quote_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_trading_service_health",
                return_value=mock_service_health,
            ),
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == HealthStatus.HEALTHY
        assert "timestamp" in data
        assert "total_check_time_ms" in data
        assert "components" in data
        assert data["components"]["database"]["status"] == HealthStatus.HEALTHY
        assert data["components"]["quote_adapter"]["status"] == HealthStatus.HEALTHY
        assert data["components"]["trading_service"]["status"] == HealthStatus.HEALTHY
        assert "system_info" in data

    @pytest.mark.asyncio
    async def test_detailed_health_check_some_unhealthy(self, client):
        """Test detailed health check when some components are unhealthy."""
        from app.api.v1.endpoints.health import HealthStatus

        mock_db_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }

        mock_quote_health = {
            "status": HealthStatus.UNHEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 1000.0,
            "message": "Quote adapter error: Network timeout",
        }

        mock_service_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        with (
            patch(
                "app.api.v1.endpoints.health.check_database_health",
                return_value=mock_db_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_quote_adapter_health",
                return_value=mock_quote_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_trading_service_health",
                return_value=mock_service_health,
            ),
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Overall status should be unhealthy if any component is unhealthy
        assert data["status"] == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_detailed_health_check_some_degraded(self, client):
        """Test detailed health check when some components are degraded."""
        from app.api.v1.endpoints.health import HealthStatus

        mock_db_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }

        mock_quote_health = {
            "status": HealthStatus.DEGRADED,
            "adapter_type": "test_data",
            "response_time_ms": 500.0,
            "message": "Quote adapter returned invalid data",
        }

        mock_service_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        with (
            patch(
                "app.api.v1.endpoints.health.check_database_health",
                return_value=mock_db_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_quote_adapter_health",
                return_value=mock_quote_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_trading_service_health",
                return_value=mock_service_health,
            ),
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Overall status should be degraded if no unhealthy but some degraded
        assert data["status"] == HealthStatus.DEGRADED

    # GET /health/metrics endpoint tests
    @pytest.mark.asyncio
    async def test_health_metrics_success(self, client):
        """Test health metrics endpoint returns Prometheus-style metrics."""
        from app.api.v1.endpoints.health import HealthStatus

        mock_db_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }

        mock_quote_health = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }

        mock_service_health = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        with (
            patch(
                "app.api.v1.endpoints.health.check_database_health",
                return_value=mock_db_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_quote_adapter_health",
                return_value=mock_quote_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_trading_service_health",
                return_value=mock_service_health,
            ),
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "metrics" in data
        assert "timestamp" in data

        metrics_lines = data["metrics"].split("\n")
        assert any("health_database_up" in line for line in metrics_lines)
        assert any("health_quote_adapter_up" in line for line in metrics_lines)
        assert any("health_trading_service_up" in line for line in metrics_lines)
        assert any("health_overall_up" in line for line in metrics_lines)

    @pytest.mark.asyncio
    async def test_health_metrics_unhealthy_components(self, client):
        """Test health metrics with unhealthy components."""
        from app.api.v1.endpoints.health import HealthStatus

        mock_db_health = {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": 1000.0,
            "message": "Database connection failed",
        }

        mock_quote_health = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "robinhood",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }

        mock_service_health = {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": 500.0,
            "message": "Trading service error",
        }

        with (
            patch(
                "app.api.v1.endpoints.health.check_database_health",
                return_value=mock_db_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_quote_adapter_health",
                return_value=mock_quote_health,
            ),
            patch(
                "app.api.v1.endpoints.health.check_trading_service_health",
                return_value=mock_service_health,
            ),
        ):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        metrics_lines = data["metrics"].split("\n")

        # Find specific metric lines and verify values
        db_metric = next(
            (line for line in metrics_lines if "health_database_up" in line), ""
        )
        assert "0" in db_metric  # 0 for unhealthy

        quote_metric = next(
            (line for line in metrics_lines if "health_quote_adapter_up" in line), ""
        )
        assert "1" in quote_metric  # 1 for healthy
        assert "robinhood" in quote_metric

        service_metric = next(
            (line for line in metrics_lines if "health_trading_service_up" in line), ""
        )
        assert "0" in service_metric  # 0 for unhealthy

        overall_metric = next(
            (line for line in metrics_lines if "health_overall_up" in line), ""
        )
        assert "0" in overall_metric  # 0 because some components are unhealthy

    # GET /health/dependencies endpoint tests
    @pytest.mark.asyncio
    async def test_dependency_health_check_basic(self, client):
        """Test dependencies health check returns expected dependencies."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health/dependencies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "dependencies" in data
        assert "timestamp" in data
        assert isinstance(data["dependencies"], list)

        # Should always have PostgreSQL and Quote Provider
        dep_names = [dep["name"] for dep in data["dependencies"]]
        assert "PostgreSQL" in dep_names
        assert any("Quote Provider" in name for name in dep_names)

    @pytest.mark.asyncio
    async def test_dependency_health_check_with_redis(self, client):
        """Test dependencies health check includes Redis when configured."""
        with patch.object(settings, "REDIS_URL", "redis://localhost:6379", create=True):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/dependencies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        dep_names = [dep["name"] for dep in data["dependencies"]]
        assert "Redis" in dep_names

    @pytest.mark.asyncio
    async def test_dependency_health_check_quote_adapter_types(self, client):
        """Test dependencies shows correct quote adapter type."""
        with patch.object(settings, "QUOTE_ADAPTER_TYPE", "robinhood", create=True):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/dependencies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        quote_dep = next(
            (dep for dep in data["dependencies"] if "Quote Provider" in dep["name"]),
            None,
        )
        assert quote_dep is not None
        assert "robinhood" in quote_dep["name"]

    # Edge cases and error conditions
    @pytest.mark.asyncio
    async def test_health_endpoints_with_database_timeout(self, client):
        """Test health endpoints handle database timeouts gracefully."""

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = TimeoutError("Query timeout")

        with patch("app.api.v1.endpoints.health.get_async_db", return_value=mock_db):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["reason"] == "Database unavailable"

    @pytest.mark.asyncio
    async def test_health_status_constants(self):
        """Test health status constants are properly defined."""
        from app.api.v1.endpoints.health import HealthStatus

        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_response_times_measured(self):
        """Test that response times are properly measured in health checks."""
        from app.api.v1.endpoints.health import check_database_health

        mock_db = AsyncMock(spec=AsyncSession)

        # Add delay to simulate slow database
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            return mock_result

        mock_db.execute.side_effect = slow_execute

        start_time = time.time()
        result = await check_database_health(mock_db)
        actual_time = (time.time() - start_time) * 1000

        assert "response_time_ms" in result
        # Response time should be at least the delay time we added (within tolerance)
        assert result["response_time_ms"] >= 90  # Allow some tolerance
        assert (
            result["response_time_ms"] <= actual_time + 50
        )  # Upper bound with tolerance
