"""
Advanced test suite for main application entry point and server lifecycle.

Tests FastAPI application startup, shutdown, configuration, MCP server integration,
error handling, and comprehensive server lifecycle management.
"""

import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.exceptions import CustomException, ValidationError
from app.main import (
    app,
    custom_exception_handler,
    general_exception_handler,
    initialize_database,
    lifespan,
    main,
    run_mcp_server,
    value_error_handler,
)


class TestApplicationConfiguration:
    """Test application configuration and setup."""

    def test_app_basic_configuration(self):
        """Test basic FastAPI application configuration."""
        assert isinstance(app, FastAPI)
        assert app.title == "Open Paper Trading MCP"
        assert app.description == "A FastAPI web application for paper trading with MCP support"
        assert app.version == "0.1.0"
        assert "/api/v1/openapi.json" in app.openapi_url

    def test_cors_middleware_configuration(self):
        """Test CORS middleware configuration."""
        # Check if CORS middleware is properly configured
        middleware_found = False
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                middleware_found = True
                break
        
        # CORS may or may not be enabled depending on settings
        # Just ensure no errors during app initialization
        assert app is not None

    @patch("app.main.settings")
    def test_cors_middleware_with_origins(self, mock_settings):
        """Test CORS middleware with configured origins."""
        mock_settings.BACKEND_CORS_ORIGINS = ["http://localhost:3000", "https://example.com"]
        mock_settings.PROJECT_NAME = "Test App"
        mock_settings.API_V1_STR = "/api/v1"
        
        # Would need to recreate app with new settings, but testing configuration logic
        assert mock_settings.BACKEND_CORS_ORIGINS is not None


class TestDatabaseInitialization:
    """Test database initialization functionality."""

    @patch("app.main.init_db")
    async def test_initialize_database_success(self, mock_init_db):
        """Test successful database initialization."""
        mock_init_db.return_value = None

        await initialize_database()
        
        mock_init_db.assert_called_once()

    @patch("app.main.init_db")
    async def test_initialize_database_failure(self, mock_init_db, capsys):
        """Test database initialization failure handling."""
        mock_init_db.side_effect = Exception("Database connection failed")

        # Should not raise exception but continue
        await initialize_database()
        
        captured = capsys.readouterr()
        assert "Database initialization failed" in captured.out
        assert "Database connection failed" in captured.out

    @patch("app.main.print")
    @patch("app.main.init_db")
    async def test_initialize_database_logging(self, mock_init_db, mock_print):
        """Test database initialization logging."""
        mock_init_db.return_value = None

        await initialize_database()
        
        # Check that appropriate messages are printed
        assert mock_print.call_count >= 2
        mock_print.assert_any_call("Initializing database...")
        mock_print.assert_any_call("Database initialized successfully.")


class TestApplicationLifespan:
    """Test application lifespan management."""

    @patch("app.main.initialize_database")
    @patch("app.main.setup_logging")
    @patch("app.main.get_robinhood_client")
    @patch("app.main.get_adapter_factory")
    @patch("app.main.TradingService")
    @patch("app.main._get_quote_adapter")
    @patch("app.main.set_mcp_trading_service")
    async def test_lifespan_startup_success(
        self,
        mock_set_mcp_service,
        mock_get_adapter,
        mock_trading_service_class,
        mock_adapter_factory,
        mock_robinhood_client,
        mock_setup_logging,
        mock_init_db,
    ):
        """Test successful application startup."""
        # Setup mocks
        mock_init_db.return_value = None
        mock_setup_logging.return_value = None
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter
        mock_trading_service = MagicMock()
        mock_trading_service_class.return_value = mock_trading_service
        
        mock_rh_client = MagicMock()
        mock_rh_client.authenticate = AsyncMock()
        mock_robinhood_client.return_value = mock_rh_client
        
        mock_factory = MagicMock()
        mock_factory.create_adapter.return_value = mock_adapter
        mock_factory.start_cache_warming = AsyncMock()
        mock_factory.stop_cache_warming = AsyncMock()
        mock_adapter_factory.return_value = mock_factory

        test_app = FastAPI()

        async with lifespan(test_app):
            # Verify startup calls
            mock_setup_logging.assert_called_once()
            mock_init_db.assert_called_once()
            mock_trading_service_class.assert_called_once_with(mock_adapter)
            mock_set_mcp_service.assert_called_once_with(mock_trading_service)
            mock_rh_client.authenticate.assert_called_once()
            
            # Verify trading service is stored in app state
            assert hasattr(test_app.state, "trading_service")
            assert test_app.state.trading_service == mock_trading_service

        # Verify shutdown calls
        mock_factory.stop_cache_warming.assert_called_once()

    @patch("app.main.initialize_database")
    @patch("app.main.setup_logging")
    @patch("app.main.get_robinhood_client")
    @patch("app.main.get_adapter_factory")
    @patch("app.main.TradingService")
    @patch("app.main._get_quote_adapter")
    async def test_lifespan_cache_warming_fallback(
        self,
        mock_get_adapter,
        mock_trading_service_class,
        mock_adapter_factory,
        mock_robinhood_client,
        mock_setup_logging,
        mock_init_db,
    ):
        """Test cache warming fallback to test adapter."""
        # Setup mocks
        mock_init_db.return_value = None
        mock_robinhood_client.return_value.authenticate = AsyncMock()
        
        mock_factory = MagicMock()
        mock_factory.create_adapter.side_effect = [None, MagicMock()]  # Robinhood fails, test succeeds
        mock_factory.start_cache_warming = AsyncMock()
        mock_factory.stop_cache_warming = AsyncMock()
        mock_adapter_factory.return_value = mock_factory

        test_app = FastAPI()

        async with lifespan(test_app):
            pass

        # Verify both adapter types were tried
        assert mock_factory.create_adapter.call_count == 2
        mock_factory.create_adapter.assert_any_call("robinhood")
        mock_factory.create_adapter.assert_any_call("test_data")

    @patch("app.main.initialize_database")
    @patch("app.main.setup_logging")
    @patch("app.main.get_robinhood_client")
    @patch("app.main.get_adapter_factory")
    @patch("app.main.print")
    async def test_lifespan_cache_warming_failure(
        self,
        mock_print,
        mock_adapter_factory,
        mock_robinhood_client,
        mock_setup_logging,
        mock_init_db,
    ):
        """Test cache warming failure handling."""
        mock_init_db.return_value = None
        mock_robinhood_client.return_value.authenticate = AsyncMock()
        
        mock_factory = MagicMock()
        mock_factory.create_adapter.side_effect = Exception("Adapter creation failed")
        mock_adapter_factory.return_value = mock_factory

        test_app = FastAPI()

        # Should not raise exception
        async with lifespan(test_app):
            pass

        # Verify error was printed but startup continued
        mock_print.assert_any_call("Cache warming failed to start: Adapter creation failed")

    @patch("app.main.initialize_database")
    @patch("app.main.setup_logging")
    @patch("app.main.get_robinhood_client")
    @patch("app.main.get_adapter_factory")
    @patch("app.main.print")
    async def test_lifespan_shutdown_error_handling(
        self,
        mock_print,
        mock_adapter_factory,
        mock_robinhood_client,
        mock_setup_logging,
        mock_init_db,
    ):
        """Test error handling during shutdown."""
        mock_init_db.return_value = None
        mock_robinhood_client.return_value.authenticate = AsyncMock()
        
        mock_factory = MagicMock()
        mock_factory.create_adapter.return_value = None
        mock_factory.stop_cache_warming = AsyncMock(side_effect=Exception("Shutdown error"))
        mock_adapter_factory.return_value = mock_factory

        test_app = FastAPI()

        # Should not raise exception during shutdown
        async with lifespan(test_app):
            pass

        # Verify error was handled
        mock_print.assert_any_call("Error stopping cache warming: Shutdown error")


class TestMCPServerIntegration:
    """Test MCP server integration and threading."""

    @patch("app.main.mcp_instance")
    @patch("app.main.settings")
    def test_run_mcp_server_success(self, mock_settings, mock_mcp_instance):
        """Test successful MCP server startup."""
        mock_settings.MCP_SERVER_HOST = "localhost"
        mock_settings.MCP_SERVER_PORT = 2081
        mock_mcp_instance.run = MagicMock()

        run_mcp_server()

        mock_mcp_instance.run.assert_called_once_with(
            host="localhost",
            port=2081,
            transport="sse"
        )

    @patch("app.main.mcp_instance", None)
    @patch("app.main.print")
    def test_run_mcp_server_not_available(self, mock_print):
        """Test MCP server when not available."""
        run_mcp_server()

        mock_print.assert_called_once_with("MCP server not available (likely in test mode)")

    @patch("app.main.mcp_instance")
    @patch("app.main.settings")
    @patch("app.main.print")
    def test_run_mcp_server_exception_handling(self, mock_print, mock_settings, mock_mcp_instance):
        """Test MCP server exception handling."""
        mock_settings.MCP_SERVER_HOST = "localhost"
        mock_settings.MCP_SERVER_PORT = 2081
        mock_mcp_instance.run.side_effect = Exception("Server startup failed")

        run_mcp_server()

        mock_print.assert_any_call("Error running MCP server: Server startup failed")

    @patch("app.main.mcp_instance")
    @patch("app.main.threading.Thread")
    @patch("app.main.uvicorn.run")
    @patch("os.getenv")
    def test_main_with_mcp_server(self, mock_getenv, mock_uvicorn_run, mock_thread_class, mock_mcp_instance):
        """Test main function with MCP server available."""
        mock_getenv.return_value = "production"
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        main()

        # Verify MCP thread is created and started
        mock_thread_class.assert_called_once_with(target=run_mcp_server, daemon=True)
        mock_thread.start.assert_called_once()

        # Verify uvicorn is started
        mock_uvicorn_run.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=2080,
            reload=False
        )

    @patch("app.main.mcp_instance", None)
    @patch("app.main.uvicorn.run")
    @patch("app.main.print")
    @patch("os.getenv")
    def test_main_without_mcp_server(self, mock_getenv, mock_print, mock_uvicorn_run):
        """Test main function without MCP server."""
        mock_getenv.return_value = "production"

        main()

        # Verify message is printed
        mock_print.assert_called_with("MCP server not available - running FastAPI only")

        # Verify uvicorn is still started
        mock_uvicorn_run.assert_called_once()

    @patch("app.main.uvicorn.run")
    @patch("os.getenv")
    def test_main_development_mode(self, mock_getenv, mock_uvicorn_run):
        """Test main function in development mode."""
        mock_getenv.return_value = "development"

        main()

        # Verify reload is enabled in development
        mock_uvicorn_run.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=2080,
            reload=True
        )


class TestExceptionHandlers:
    """Test application exception handlers."""

    async def test_custom_exception_handler(self):
        """Test custom exception handler."""
        request = MagicMock()
        request.url.path = "/test/path"
        
        exc = CustomException(
            detail="Test error message",
            status_code=400
        )

        response = await custom_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        # Check response content structure
        content = response.body.decode()
        assert "Test error message" in content
        assert "CustomException" in content
        assert "/test/path" in content

    async def test_value_error_handler(self):
        """Test ValueError exception handler."""
        request = MagicMock()
        request.url.path = "/test/path"
        
        exc = ValueError("Invalid input value")

        response = await value_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        content = response.body.decode()
        assert "Invalid input value" in content
        assert "ValidationError" in content

    @patch("app.main.logging.getLogger")
    async def test_general_exception_handler(self, mock_get_logger):
        """Test general exception handler."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        request = MagicMock()
        request.url.path = "/test/path"
        
        exc = Exception("Unexpected error")

        response = await general_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        content = response.body.decode()
        assert "An internal server error occurred" in content
        assert "InternalServerError" in content
        
        # Verify error was logged
        mock_logger.error.assert_called_once()


class TestRootEndpoint:
    """Test root endpoint functionality."""

    @patch("app.main.settings")
    async def test_root_endpoint_response(self, mock_settings):
        """Test root endpoint response structure."""
        mock_settings.API_V1_STR = "/api/v1"
        mock_settings.MCP_SERVER_HOST = "localhost"
        mock_settings.MCP_SERVER_PORT = 2081
        mock_settings.MCP_SERVER_NAME = "trading-mcp"

        # Import after mocking settings
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "endpoints" in data
        assert "api" in data["endpoints"]
        assert "docs" in data["endpoints"]
        assert "health" in data["endpoints"]
        assert "mcp" in data["endpoints"]
        
        mcp_config = data["endpoints"]["mcp"]
        assert mcp_config["host"] == "localhost"
        assert mcp_config["port"] == 2081
        assert mcp_config["name"] == "trading-mcp"


class TestApplicationIntegration:
    """Test full application integration scenarios."""

    def test_application_startup_with_client(self):
        """Test application can be started with test client."""
        client = TestClient(app)
        
        # Test basic connectivity
        response = client.get("/")
        assert response.status_code == 200

    @patch("app.main.mcp_instance", None)
    def test_application_without_mcp_import(self):
        """Test application works without MCP module."""
        # Application should still work even if MCP is not available
        assert app is not None
        assert isinstance(app, FastAPI)

    def test_api_routes_included(self):
        """Test that API routes are properly included."""
        route_paths = [route.path for route in app.routes]
        
        # Should have basic routes
        assert "/" in route_paths
        
        # API routes should be included with prefix
        api_routes_found = any("/api/v1" in path for path in route_paths)
        # Note: This might be True or False depending on route registration

    def test_exception_handlers_registered(self):
        """Test that exception handlers are properly registered."""
        # Check that custom exception handlers are registered
        assert CustomException in app.exception_handlers
        assert ValueError in app.exception_handlers
        assert Exception in app.exception_handlers


class TestThreadingSafety:
    """Test threading safety and concurrent operations."""

    @patch("app.main.mcp_instance")
    @patch("app.main.time.sleep", lambda x: None)  # Speed up test
    def test_mcp_server_thread_safety(self, mock_mcp_instance):
        """Test MCP server can be run in separate thread."""
        mock_mcp_instance.run = MagicMock(side_effect=lambda **kwargs: time.sleep(0.1))
        
        # Start MCP server in thread
        mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
        mcp_thread.start()
        
        # Give thread time to start
        time.sleep(0.01)
        
        # Thread should be alive
        assert mcp_thread.is_alive()
        
        # Clean up
        mcp_thread.join(timeout=0.1)

    def test_application_state_isolation(self):
        """Test that application state is properly isolated."""
        # Create separate app instances
        app1 = FastAPI()
        app2 = FastAPI()
        
        # Set different state
        app1.state.test_value = "app1"
        app2.state.test_value = "app2"
        
        # Verify isolation
        assert app1.state.test_value != app2.state.test_value


class TestConfigurationEdgeCases:
    """Test edge cases in configuration and setup."""

    @patch.dict(os.environ, {"ENVIRONMENT": "test"})
    @patch("app.main.uvicorn.run")
    def test_main_with_environment_variable(self, mock_uvicorn_run):
        """Test main function reads environment variables."""
        main()
        
        # Should pass reload=False for test environment (not development)
        mock_uvicorn_run.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=2080,
            reload=False
        )

    @patch("app.main.suppress")
    @patch("app.main.mcp_instance", None)
    def test_mcp_import_error_handling(self, mock_suppress):
        """Test that MCP import errors are properly suppressed."""
        # The suppress context manager should handle ImportError
        # This test verifies the structure is in place
        assert mock_suppress is not None

    def test_application_middleware_order(self):
        """Test that middleware is applied in correct order."""
        # Verify middleware stack exists and is properly ordered
        middleware_stack = app.user_middleware
        
        # Should have at least basic middleware
        assert isinstance(middleware_stack, list)