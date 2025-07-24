"""
Comprehensive tests for health check endpoints.

Tests all health endpoints with proper mocking:
- GET /health (basic health check)
- GET /health/live (liveness probe)
- GET /health/ready (readiness probe)
- GET /health/detailed (comprehensive health check)
- GET /health/metrics (Prometheus metrics)
- GET /health/dependencies (dependency listing)

Covers success paths, error handling, and edge cases.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.health import (
    HealthStatus,
    check_database_health,
    check_quote_adapter_health,
    check_trading_service_health,
)


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_basic_health_check(self, client: TestClient):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["service"] == "open-paper-trading-mcp"
        assert "version" in data

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    def test_liveness_check(self, client: TestClient):
        """Test liveness probe endpoint."""
        response = client.get("/api/v1/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_readiness_check_healthy(self, mock_db_health, client: TestClient):
        """Test readiness probe when database is healthy."""
        mock_db_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }

        response = client.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ready"
        assert "timestamp" in data

    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_readiness_check_unhealthy(self, mock_db_health, client: TestClient):
        """Test readiness probe when database is unhealthy."""
        mock_db_health.return_value = {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": 2000.0,
            "message": "Database connection failed",
        }

        response = client.get("/api/v1/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "not_ready"
        assert data["reason"] == "Database unavailable"
        assert "timestamp" in data

    @patch("app.api.v1.endpoints.health.check_trading_service_health")
    @patch("app.api.v1.endpoints.health.check_quote_adapter_health")
    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_detailed_health_check_all_healthy(
        self, mock_db_health, mock_quote_health, mock_service_health, client: TestClient
    ):
        """Test detailed health check when all components are healthy."""
        mock_db_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }
        mock_quote_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }
        mock_service_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        response = client.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == HealthStatus.HEALTHY
        assert "timestamp" in data
        assert "total_check_time_ms" in data
        assert "components" in data
        assert "system_info" in data

        # Verify component health
        components = data["components"]
        assert components["database"]["status"] == HealthStatus.HEALTHY
        assert components["quote_adapter"]["status"] == HealthStatus.HEALTHY
        assert components["trading_service"]["status"] == HealthStatus.HEALTHY

    @patch("app.api.v1.endpoints.health.check_trading_service_health")
    @patch("app.api.v1.endpoints.health.check_quote_adapter_health")
    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_detailed_health_check_degraded(
        self, mock_db_health, mock_quote_health, mock_service_health, client: TestClient
    ):
        """Test detailed health check when some components are degraded."""
        mock_db_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }
        mock_quote_health.return_value = {
            "status": HealthStatus.DEGRADED,
            "adapter_type": "test_data",
            "response_time_ms": 500.0,
            "message": "Quote adapter is slow",
        }
        mock_service_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        response = client.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == HealthStatus.DEGRADED

    @patch("app.api.v1.endpoints.health.check_trading_service_health")
    @patch("app.api.v1.endpoints.health.check_quote_adapter_health")
    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_detailed_health_check_unhealthy(
        self, mock_db_health, mock_quote_health, mock_service_health, client: TestClient
    ):
        """Test detailed health check when components are unhealthy."""
        mock_db_health.return_value = {
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": 5000.0,
            "message": "Database connection failed",
        }
        mock_quote_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }
        mock_service_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        response = client.get("/api/v1/health/detailed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == HealthStatus.UNHEALTHY

    @patch("app.api.v1.endpoints.health.check_trading_service_health")
    @patch("app.api.v1.endpoints.health.check_quote_adapter_health")
    @patch("app.api.v1.endpoints.health.check_database_health")
    def test_health_metrics_endpoint(
        self, mock_db_health, mock_quote_health, mock_service_health, client: TestClient
    ):
        """Test health metrics endpoint returns Prometheus format."""
        mock_db_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 5.0,
            "message": "Database is operational",
        }
        mock_quote_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "adapter_type": "test_data",
            "response_time_ms": 10.0,
            "message": "Quote adapter is operational",
        }
        mock_service_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "response_time_ms": 15.0,
            "message": "Trading service is operational",
        }

        response = client.get("/api/v1/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "metrics" in data
        assert "timestamp" in data

        metrics = data["metrics"]
        assert "health_database_up" in metrics
        assert "health_quote_adapter_up" in metrics
        assert "health_trading_service_up" in metrics
        assert "health_overall_up" in metrics

    def test_dependency_health_check(self, client: TestClient):
        """Test dependency health check endpoint."""
        response = client.get("/api/v1/health/dependencies")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "dependencies" in data
        assert "timestamp" in data

        dependencies = data["dependencies"]
        assert len(dependencies) > 0

        # Check for required dependencies
        dep_names = [dep["name"] for dep in dependencies]
        assert any("PostgreSQL" in name for name in dep_names)
        assert any("Quote Provider" in name for name in dep_names)


class TestHealthCheckFunctions:
    """Test individual health check functions."""

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, async_db_session: AsyncSession):
        """Test successful database health check."""
        result = await check_database_health(async_db_session)

        assert result["status"] == HealthStatus.HEALTHY
        assert "response_time_ms" in result
        assert result["message"] == "Database is operational"
        assert isinstance(result["response_time_ms"], int | float)

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self):
        """Test database health check failure."""
        # Create a mock session that raises an exception
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Connection failed")

        result = await check_database_health(mock_session)

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "response_time_ms" in result
        assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.get_adapter_factory")
    async def test_check_quote_adapter_health_success(self, mock_get_factory):
        """Test successful quote adapter health check."""
        # Mock adapter factory and adapter
        mock_factory = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.name = "test_data"

        # Mock quote response
        from app.schemas.trading import StockQuote

        mock_quote = StockQuote(symbol="AAPL", price=155.0, quote_date=datetime.now())
        mock_adapter.get_quote = AsyncMock(return_value=mock_quote)

        mock_factory.create_adapter.return_value = mock_adapter
        mock_get_factory.return_value = mock_factory

        result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.HEALTHY
        assert result["adapter_type"] == "test_data"
        assert "response_time_ms" in result
        assert result["message"] == "Quote adapter is operational"
        assert "sample_quote" in result

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.get_adapter_factory")
    async def test_check_quote_adapter_health_no_adapter(self, mock_get_factory):
        """Test quote adapter health check when adapter creation fails."""
        mock_factory = MagicMock()
        mock_factory.create_adapter.return_value = None
        mock_get_factory.return_value = mock_factory

        result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.UNHEALTHY
        assert result["message"] == "Failed to create quote adapter"

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.get_adapter_factory")
    async def test_check_quote_adapter_health_invalid_quote(self, mock_get_factory):
        """Test quote adapter health check with invalid quote data."""
        mock_factory = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.name = "test_data"

        # Mock invalid quote response (no price or price is 0)
        from app.schemas.trading import StockQuote

        mock_quote = StockQuote(
            symbol="AAPL",
            price=0.0,  # Invalid price
            quote_date=datetime.now(),
        )
        mock_adapter.get_quote = AsyncMock(return_value=mock_quote)

        mock_factory.create_adapter.return_value = mock_adapter
        mock_get_factory.return_value = mock_factory

        result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.DEGRADED
        assert result["message"] == "Quote adapter returned invalid data"

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.get_adapter_factory")
    async def test_check_quote_adapter_health_exception(self, mock_get_factory):
        """Test quote adapter health check with exception."""
        mock_get_factory.side_effect = Exception("Adapter factory error")

        result = await check_quote_adapter_health()

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Adapter factory error" in result["message"]

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.TradingService")
    async def test_check_trading_service_health_success(
        self, mock_service_class, async_db_session: AsyncSession
    ):
        """Test successful trading service health check."""
        # Mock trading service
        mock_service = AsyncMock()
        mock_service._ensure_account_exists = AsyncMock()

        # Mock portfolio response
        from app.schemas.positions import Portfolio

        mock_portfolio = Portfolio(
            cash_balance=10000.0, positions=[], market_value=0.0, total_value=10000.0
        )
        mock_service.get_portfolio = AsyncMock(return_value=mock_portfolio)

        mock_service_class.return_value = mock_service

        result = await check_trading_service_health(async_db_session)

        assert result["status"] == HealthStatus.HEALTHY
        assert result["message"] == "Trading service is operational"
        assert "portfolio_check" in result

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.health.TradingService")
    async def test_check_trading_service_health_failure(
        self, mock_service_class, async_db_session: AsyncSession
    ):
        """Test trading service health check failure."""
        mock_service_class.side_effect = Exception("Service initialization failed")

        result = await check_trading_service_health(async_db_session)

        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Service initialization failed" in result["message"]


class TestHealthStatusConstants:
    """Test health status constants."""

    def test_health_status_constants(self):
        """Test that health status constants are correctly defined."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
