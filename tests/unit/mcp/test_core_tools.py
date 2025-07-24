"""
Comprehensive unit tests for MCP core tools.

Tests the core system tools: list_tools, health_check, market_hours,
stock_ratings, stock_events, and stock_level2_data.

Includes testing patterns for async MCP tools, service integration,
error handling, and system monitoring.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.mcp.core_tools import (
    get_mcp_trading_service,
    health_check,
    list_tools,
    market_hours,
    set_mcp_trading_service,
    stock_events,
    stock_level2_data,
    stock_ratings,
)


class TestCoreToolsServiceManagement:
    """Test trading service dependency management for core tools."""

    def test_set_and_get_mcp_trading_service(self):
        """Test setting and getting trading service."""
        mock_service = Mock()
        set_mcp_trading_service(mock_service)

        service = get_mcp_trading_service()
        assert service is mock_service

    def test_get_mcp_trading_service_not_initialized(self):
        """Test getting service when not initialized raises error."""
        # Clear any existing service
        from app.mcp import core_tools

        core_tools._trading_service = None

        with pytest.raises(RuntimeError, match="TradingService not initialized"):
            get_mcp_trading_service()


class TestListToolsTool:
    """Test the list_tools MCP tool."""

    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        """Test list_tools returns correct structure."""
        result = await list_tools()

        # Check response structure
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]
        assert result["result"]["status"] == "success"

        # Check data structure
        data = result["result"]["data"]
        assert "total_tools" in data
        assert "version" in data
        assert "categories" in data
        assert "description" in data
        assert "implementation_status" in data

        # Check specific values
        assert data["total_tools"] == 60
        assert data["version"] == "v0.5.0"
        assert isinstance(data["categories"], dict)
        assert isinstance(data["implementation_status"], dict)

    @pytest.mark.asyncio
    async def test_list_tools_categories_structure(self):
        """Test list_tools categories are correctly structured."""
        result = await list_tools()
        data = result["result"]["data"]
        categories = data["categories"]

        # Check all expected categories exist
        expected_categories = [
            "core_system",
            "account_portfolio",
            "market_data",
            "order_management",
            "options_trading",
            "stock_trading",
            "options_orders",
            "order_cancellation",
            "legacy_tools",
        ]

        for category in expected_categories:
            assert category in categories
            assert isinstance(categories[category], list)
            assert len(categories[category]) > 0

        # Check core system tools
        assert "list_tools" in categories["core_system"]
        assert "health_check" in categories["core_system"]

    @pytest.mark.asyncio
    async def test_list_tools_return_type(self):
        """Test list_tools returns dict[str, Any]."""
        result = await list_tools()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())

    @pytest.mark.asyncio
    async def test_list_tools_exception_handling(self):
        """Test list_tools handles exceptions properly."""
        with patch(
            "app.mcp.core_tools.success_response",
            side_effect=Exception("Test error"),
        ):
            result = await list_tools()

            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]
            assert "list_tools" in result["result"]["error"]


class TestHealthCheckTool:
    """Test the health_check MCP tool."""

    @pytest.fixture
    def mock_trading_service(self):
        """Mock trading service for health check tests."""
        mock_service = Mock()
        mock_service.quote_adapter = Mock()
        set_mcp_trading_service(mock_service)
        return mock_service

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_trading_service):
        """Test health_check returns correct structure."""
        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
            patch("time.time", return_value=1000),
        ):
            # Mock database session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute = AsyncMock(return_value=Mock())

            # Mock system metrics
            mock_memory.return_value.used = 268435456  # 256 MB
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            result = await health_check()

            # Check response structure
            assert "result" in result
            assert "status" in result["result"]
            assert "data" in result["result"]
            assert result["result"]["status"] == "success"

            # Check data structure
            data = result["result"]["data"]
            assert "status" in data
            assert "timestamp" in data
            assert "version" in data
            assert "components" in data
            assert "system_metrics" in data
            assert "mcp_server" in data

            # Check component statuses
            components = data["components"]
            assert "trading_service" in components
            assert "database" in components
            assert "market_data" in components

            # Check system metrics
            metrics = data["system_metrics"]
            assert "uptime_seconds" in metrics
            assert "memory_usage_mb" in metrics
            assert "cpu_percent" in metrics

    @pytest.mark.asyncio
    async def test_health_check_degraded_status(self, mock_trading_service):
        """Test health_check detects degraded services."""
        # Remove quote_adapter to simulate degraded service
        mock_trading_service.quote_adapter = None

        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
        ):
            # Mock database session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute = AsyncMock(return_value=Mock())

            # Mock system metrics
            mock_memory.return_value.used = 268435456
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            result = await health_check()
            data = result["result"]["data"]

            # Should be degraded due to missing quote_adapter
            assert data["status"] == "degraded"
            assert data["components"]["trading_service"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self):
        """Test health_check detects unhealthy services."""
        # Clear trading service to simulate failure
        from app.mcp import core_tools

        core_tools._trading_service = None

        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
        ):
            # Mock database failure
            mock_session.side_effect = Exception("Database error")

            # Mock system metrics
            mock_memory.return_value.used = 268435456
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            result = await health_check()
            data = result["result"]["data"]

            # Should be unhealthy due to multiple failures
            assert data["status"] == "unhealthy"
            assert data["components"]["trading_service"] == "down"
            assert data["components"]["database"] == "down"

    @pytest.mark.asyncio
    async def test_health_check_test_data_adapter(self, mock_trading_service):
        """Test health_check identifies test data adapter."""
        # Mock test data adapter
        mock_trading_service.quote_adapter.__class__.__name__ = "TestDataQuoteAdapter"

        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
        ):
            # Mock database session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute = AsyncMock(return_value=Mock())

            # Mock system metrics
            mock_memory.return_value.used = 268435456
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            result = await health_check()
            data = result["result"]["data"]

            assert data["components"]["market_data"] == "operational (test)"

    @pytest.mark.asyncio
    async def test_health_check_return_type(self, mock_trading_service):
        """Test health_check returns dict[str, Any]."""
        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
        ):
            # Mock database session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute = AsyncMock(return_value=Mock())

            # Mock system metrics
            mock_memory.return_value.used = 268435456
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            result = await health_check()
            assert isinstance(result, dict)
            assert all(isinstance(k, str) for k in result.keys())

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self):
        """Test health_check handles system metric collection failures gracefully."""
        # Test with psutil failures - should still return success but with default values
        with (
            patch("psutil.virtual_memory", side_effect=Exception("System error")),
            patch("psutil.cpu_percent", side_effect=Exception("System error")),
            patch("psutil.Process", side_effect=Exception("System error")),
        ):
            mock_service = Mock()
            mock_service.quote_adapter = Mock()
            set_mcp_trading_service(mock_service)

            with patch("app.storage.database.get_async_session") as mock_session:
                # Mock database session
                mock_session_instance = AsyncMock()
                mock_session.return_value.__aenter__.return_value = (
                    mock_session_instance
                )
                mock_session_instance.execute = AsyncMock(return_value=Mock())

                result = await health_check()

                # Should still return success but with default metric values
                assert "result" in result
                assert result["result"]["status"] == "success"
                assert "data" in result["result"]

                # Check that system metrics are present with default values
                data = result["result"]["data"]
                assert data["system_metrics"]["memory_usage_mb"] == 0
                assert data["system_metrics"]["cpu_percent"] == 0
                assert data["system_metrics"]["uptime_seconds"] == 0


class TestMarketHoursTool:
    """Test the market_hours MCP tool."""

    @pytest.fixture
    def mock_trading_service(self):
        """Mock trading service for market hours tests."""
        mock_service = AsyncMock()
        set_mcp_trading_service(mock_service)
        return mock_service

    @pytest.mark.asyncio
    async def test_market_hours_success(self, mock_trading_service):
        """Test market_hours returns correct structure."""
        expected_data = {
            "is_open": True,
            "next_open": "2024-07-23T14:30:00Z",
            "next_close": "2024-07-23T21:00:00Z",
            "timezone": "US/Eastern",
        }
        mock_trading_service.get_market_hours.return_value = expected_data

        result = await market_hours()

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == expected_data

        # Verify service call
        mock_trading_service.get_market_hours.assert_called_once()

    @pytest.mark.asyncio
    async def test_market_hours_exception_handling(self, mock_trading_service):
        """Test market_hours handles exceptions properly."""
        mock_trading_service.get_market_hours.side_effect = Exception("Service error")

        result = await market_hours()

        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "market_hours" in result["result"]["error"]


class TestStockRatingsTool:
    """Test the stock_ratings MCP tool."""

    @pytest.fixture
    def mock_trading_service(self):
        """Mock trading service for stock ratings tests."""
        mock_service = AsyncMock()
        set_mcp_trading_service(mock_service)
        return mock_service

    @pytest.mark.asyncio
    async def test_stock_ratings_success(self, mock_trading_service):
        """Test stock_ratings returns correct structure."""
        expected_data = {
            "symbol": "AAPL",
            "average_rating": 4.2,
            "buy_count": 8,
            "hold_count": 3,
            "sell_count": 1,
        }
        mock_trading_service.get_stock_ratings.return_value = expected_data

        result = await stock_ratings("aapl")

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == expected_data

        # Verify service call with normalized symbol
        mock_trading_service.get_stock_ratings.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stock_ratings_symbol_normalization(self, mock_trading_service):
        """Test stock_ratings normalizes symbols properly."""
        mock_trading_service.get_stock_ratings.return_value = {}

        await stock_ratings("  tsla  ")
        mock_trading_service.get_stock_ratings.assert_called_once_with("TSLA")

    @pytest.mark.asyncio
    async def test_stock_ratings_exception_handling(self, mock_trading_service):
        """Test stock_ratings handles exceptions properly."""
        mock_trading_service.get_stock_ratings.side_effect = Exception("Service error")

        result = await stock_ratings("AAPL")

        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "stock_ratings" in result["result"]["error"]


class TestStockEventsTool:
    """Test the stock_events MCP tool."""

    @pytest.fixture
    def mock_trading_service(self):
        """Mock trading service for stock events tests."""
        mock_service = AsyncMock()
        set_mcp_trading_service(mock_service)
        return mock_service

    @pytest.mark.asyncio
    async def test_stock_events_success(self, mock_trading_service):
        """Test stock_events returns correct structure."""
        expected_data = {
            "symbol": "AAPL",
            "events": [{"type": "dividend", "date": "2024-08-15", "amount": 0.24}],
        }
        mock_trading_service.get_stock_events.return_value = expected_data

        result = await stock_events("aapl")

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == expected_data

        # Verify service call with normalized symbol
        mock_trading_service.get_stock_events.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stock_events_exception_handling(self, mock_trading_service):
        """Test stock_events handles exceptions properly."""
        mock_trading_service.get_stock_events.side_effect = Exception("Service error")

        result = await stock_events("AAPL")

        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "stock_events" in result["result"]["error"]


class TestStockLevel2DataTool:
    """Test the stock_level2_data MCP tool."""

    @pytest.fixture
    def mock_trading_service(self):
        """Mock trading service for level2 data tests."""
        mock_service = AsyncMock()
        set_mcp_trading_service(mock_service)
        return mock_service

    @pytest.mark.asyncio
    async def test_stock_level2_data_success(self, mock_trading_service):
        """Test stock_level2_data returns correct structure."""
        expected_data = {
            "symbol": "AAPL",
            "bids": [{"price": 150.00, "size": 100}],
            "asks": [{"price": 150.05, "size": 200}],
        }
        mock_trading_service.get_stock_level2_data.return_value = expected_data

        result = await stock_level2_data("aapl")

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == expected_data

        # Verify service call with normalized symbol
        mock_trading_service.get_stock_level2_data.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stock_level2_data_exception_handling(self, mock_trading_service):
        """Test stock_level2_data handles exceptions properly."""
        mock_trading_service.get_stock_level2_data.side_effect = Exception(
            "Service error"
        )

        result = await stock_level2_data("AAPL")

        assert "result" in result
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "stock_level2_data" in result["result"]["error"]


class TestCoreToolsIntegration:
    """Integration tests for core tools."""

    @pytest.mark.asyncio
    async def test_all_tools_follow_response_format(self):
        """Test all core tools follow standardized response format."""
        mock_service = AsyncMock()
        mock_service.get_market_hours.return_value = {}
        mock_service.get_stock_ratings.return_value = {}
        mock_service.get_stock_events.return_value = {}
        mock_service.get_stock_level2_data.return_value = {}
        set_mcp_trading_service(mock_service)

        # Test all tools return proper response format
        tools_to_test = [
            (list_tools, []),
            (market_hours, []),
            (stock_ratings, ["AAPL"]),
            (stock_events, ["AAPL"]),
            (stock_level2_data, ["AAPL"]),
        ]

        with (
            patch("app.storage.database.get_async_session") as mock_session,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.Process") as mock_process,
        ):
            # Mock for health_check
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute = AsyncMock(return_value=Mock())
            mock_memory.return_value.used = 268435456
            mock_cpu.return_value = 15.5
            mock_process.return_value.create_time.return_value = 500

            tools_to_test.append((health_check, []))

            for tool_func, args in tools_to_test:
                result = await tool_func(*args)

                # Check standardized response format
                assert isinstance(result, dict)
                assert "result" in result
                assert "status" in result["result"]
                assert result["result"]["status"] in ["success", "error"]

                if result["result"]["status"] == "success":
                    assert "data" in result["result"]
                else:
                    assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_all_tools_have_correct_signatures(self):
        """Test all core tools have correct function signatures."""
        # Tools that take no parameters
        no_param_tools = [list_tools, health_check, market_hours]

        # Tools that take symbol parameter
        symbol_param_tools = [stock_ratings, stock_events, stock_level2_data]

        # Verify no-param tools can be called without arguments
        for tool in no_param_tools:
            # Should not raise TypeError
            try:
                await tool()
            except Exception as e:
                # Other exceptions are ok, but not TypeError from wrong signature
                assert not isinstance(e, TypeError)

        # Verify symbol-param tools require symbol
        for tool in symbol_param_tools:
            # Should raise TypeError if no symbol provided
            with pytest.raises(TypeError):
                await tool()

    @pytest.mark.asyncio
    async def test_all_tools_are_async(self):
        """Test all core tools are async functions."""
        tools = [
            list_tools,
            health_check,
            market_hours,
            stock_ratings,
            stock_events,
            stock_level2_data,
        ]

        for tool in tools:
            assert asyncio.iscoroutinefunction(tool)


class TestCoreToolsErrorHandling:
    """Test error handling patterns across core tools."""

    @pytest.mark.asyncio
    async def test_service_not_initialized_error(self):
        """Test tools handle service not initialized error."""
        from app.mcp import core_tools

        # Clear service to simulate not initialized
        core_tools._trading_service = None

        tools_that_need_service = [
            (market_hours, []),
            (stock_ratings, ["AAPL"]),
            (stock_events, ["AAPL"]),
            (stock_level2_data, ["AAPL"]),
        ]

        for tool_func, args in tools_that_need_service:
            result = await tool_func(*args)

            assert result["result"]["status"] == "error"
            assert "TradingService not initialized" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_consistent_error_response_format(self):
        """Test all tools return consistent error response format."""
        mock_service = AsyncMock()
        mock_service.get_market_hours.side_effect = Exception("Test error")
        mock_service.get_stock_ratings.side_effect = Exception("Test error")
        mock_service.get_stock_events.side_effect = Exception("Test error")
        mock_service.get_stock_level2_data.side_effect = Exception("Test error")
        set_mcp_trading_service(mock_service)

        error_tools = [
            (market_hours, []),
            (stock_ratings, ["AAPL"]),
            (stock_events, ["AAPL"]),
            (stock_level2_data, ["AAPL"]),
        ]

        for tool_func, args in error_tools:
            result = await tool_func(*args)

            # Check error response format
            assert isinstance(result, dict)
            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]
            assert isinstance(result["result"]["error"], str)
            assert tool_func.__name__ in result["result"]["error"]


class TestCoreToolsCoverage:
    """Test coverage requirements for core tools."""

    @pytest.mark.asyncio
    async def test_module_exports(self):
        """Test module exports all expected functions."""
        from app.mcp import core_tools

        expected_functions = [
            "list_tools",
            "health_check",
            "market_hours",
            "stock_ratings",
            "stock_events",
            "stock_level2_data",
            "get_mcp_trading_service",
            "set_mcp_trading_service",
        ]

        for func_name in expected_functions:
            assert hasattr(core_tools, func_name)
            assert callable(getattr(core_tools, func_name))

    @pytest.mark.asyncio
    async def test_response_utils_integration(self):
        """Test integration with response utils."""
        from app.mcp.response_utils import error_response, success_response

        # Test successful response integration
        test_data = {"test": "data"}
        success_result = success_response(test_data)
        assert success_result["result"]["status"] == "success"
        assert success_result["result"]["data"] == test_data

        # Test error response integration
        error_msg = "Test error"
        error_result = error_response(error_msg)
        assert error_result["result"]["status"] == "error"
        assert error_result["result"]["error"] == error_msg

    @pytest.mark.asyncio
    async def test_service_dependency_management(self):
        """Test service dependency management works correctly."""
        from app.mcp import core_tools

        # Test setting service
        mock_service = Mock()
        core_tools.set_mcp_trading_service(mock_service)
        assert core_tools._trading_service is mock_service

        # Test getting service
        retrieved_service = core_tools.get_mcp_trading_service()
        assert retrieved_service is mock_service

        # Test clearing service
        core_tools._trading_service = None
        with pytest.raises(RuntimeError):
            core_tools.get_mcp_trading_service()
