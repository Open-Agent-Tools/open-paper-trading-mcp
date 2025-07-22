"""
End-to-end tests for health check endpoints.

Tests all health check endpoints to ensure system monitoring capabilities
are working correctly.
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self, test_client: AsyncClient):
        """Test basic health check endpoint."""
        response = await test_client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["service"] == "open-paper-trading-mcp"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_liveness_check(self, test_client: AsyncClient):
        """Test Kubernetes liveness probe endpoint."""
        response = await test_client.get("/api/v1/health/live")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, test_client: AsyncClient):
        """Test Kubernetes readiness probe endpoint."""
        response = await test_client.get("/api/v1/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, test_client: AsyncClient):
        """Test detailed health check of all components."""
        response = await test_client.get("/api/v1/health/detailed")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "total_check_time_ms" in data
        assert data["total_check_time_ms"] > 0

        # Check components
        assert "components" in data
        components = data["components"]

        # Database component
        assert "database" in components
        db_health = components["database"]
        assert "status" in db_health
        assert "response_time_ms" in db_health
        assert "message" in db_health
        assert db_health["response_time_ms"] >= 0

        # Quote adapter component
        assert "quote_adapter" in components
        quote_health = components["quote_adapter"]
        assert "status" in quote_health
        assert "adapter_type" in quote_health
        assert "response_time_ms" in quote_health
        assert "message" in quote_health

        # Trading service component
        assert "trading_service" in components
        service_health = components["trading_service"]
        assert "status" in service_health
        assert "response_time_ms" in service_health
        assert "message" in service_health

        # System info
        assert "system_info" in data
        sys_info = data["system_info"]
        assert sys_info["service"] == "open-paper-trading-mcp"
        assert "version" in sys_info
        assert "environment" in sys_info

    @pytest.mark.asyncio
    async def test_health_metrics_endpoint(self, test_client: AsyncClient):
        """Test Prometheus-style metrics endpoint."""
        response = await test_client.get("/api/v1/health/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "metrics" in data
        assert "timestamp" in data

        metrics = data["metrics"]
        assert isinstance(metrics, str)

        # Check for expected metric patterns
        expected_metrics = [
            'health_database_up{service="open-paper-trading"}',
            'health_database_response_ms{service="open-paper-trading"}',
            'health_quote_adapter_up{service="open-paper-trading"',
            'health_quote_adapter_response_ms{service="open-paper-trading"}',
            'health_trading_service_up{service="open-paper-trading"}',
            'health_trading_service_response_ms{service="open-paper-trading"}',
            'health_overall_up{service="open-paper-trading"}',
        ]

        for expected in expected_metrics:
            assert expected in metrics, (
                f"Expected metric pattern '{expected}' not found"
            )

    @pytest.mark.asyncio
    async def test_dependencies_health_check(self, test_client: AsyncClient):
        """Test dependencies listing endpoint."""
        response = await test_client.get("/api/v1/health/dependencies")
        assert response.status_code == 200

        data = response.json()
        assert "dependencies" in data
        assert "timestamp" in data

        dependencies = data["dependencies"]
        assert isinstance(dependencies, list)
        assert len(dependencies) >= 2  # At least PostgreSQL and Quote Provider

        # Check each dependency has required fields
        for dep in dependencies:
            assert "name" in dep
            assert "type" in dep
            assert "required" in dep
            assert "description" in dep
            assert isinstance(dep["required"], bool)

        # Verify specific dependencies
        dep_names = {dep["name"] for dep in dependencies}
        assert "PostgreSQL" in dep_names
        assert any("Quote Provider" in name for name in dep_names)

    @pytest.mark.asyncio
    async def test_health_check_performance(self, test_client: AsyncClient):
        """Test that health checks respond quickly."""
        import time

        endpoints = ["/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"]

        for endpoint in endpoints:
            start_time = time.time()
            response = await test_client.get(endpoint)
            elapsed_time = time.time() - start_time

            assert response.status_code == 200
            # Health checks should be fast
            assert elapsed_time < 0.5, f"{endpoint} took {elapsed_time:.2f}s"

    @pytest.mark.asyncio
    async def test_health_check_consistency(self, test_client: AsyncClient):
        """Test that multiple health checks return consistent results."""
        # Get detailed health status
        detailed_response = await test_client.get("/api/v1/health/detailed")
        assert detailed_response.status_code == 200
        detailed_data = detailed_response.json()

        # If overall status is healthy, readiness should be ready
        if detailed_data["status"] == "healthy":
            ready_response = await test_client.get("/api/v1/health/ready")
            assert ready_response.status_code == 200
            assert ready_response.json()["status"] == "ready"

        # Liveness should always be alive if we can reach it
        live_response = await test_client.get("/api/v1/health/live")
        assert live_response.status_code == 200
        assert live_response.json()["status"] == "alive"

    @pytest.mark.asyncio
    async def test_health_check_with_degraded_service(self, test_client: AsyncClient):
        """Test health check behavior when services might be degraded."""
        # This test verifies the endpoint handles degraded states gracefully
        response = await test_client.get("/api/v1/health/detailed")
        assert response.status_code == 200

        data = response.json()

        # Even if service is degraded, response should be valid
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # If any component is unhealthy, overall should not be healthy
        components = data["components"]
        unhealthy_components = [
            name for name, comp in components.items() if comp["status"] == "unhealthy"
        ]

        if unhealthy_components:
            assert data["status"] != "healthy"
