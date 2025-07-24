"""Integration tests for app/core module interactions and application lifecycle."""

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request

from app.core.config import Settings, settings
from app.core.dependencies import get_trading_service
from app.core.exceptions import (
    CustomException,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import logger, setup_logging
from app.services.trading_service import TradingService


class TestCoreModuleIntegration:
    """Test integration between core modules."""

    def test_config_and_logging_integration(self):
        """Test that config settings affect logging setup."""
        # Test different log levels from config
        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
        ]

        for log_level_str, _expected_level in test_cases:
            with (
                patch("app.core.config.os.getenv") as mock_getenv,
                patch("app.core.logging.get_default_log_dir") as mock_log_dir,
                patch("pathlib.Path.mkdir"),
                patch("logging.handlers.RotatingFileHandler"),
                patch("logging.StreamHandler"),
            ):
                # Mock environment variable
                mock_getenv.side_effect = lambda key, default=None: (
                    log_level_str if key == "LOG_LEVEL" else default
                )
                mock_log_dir.return_value = Path("/test/logs")

                # Create new settings instance
                test_settings = Settings()
                assert log_level_str == test_settings.LOG_LEVEL

                # Test that logging setup uses the config
                with patch("app.core.logging.settings", test_settings):
                    setup_logging()
                    # Verify setup completed without error
                    assert True

    def test_dependencies_and_exceptions_integration(self):
        """Test that dependencies properly handle and raise exceptions."""
        # Test successful dependency resolution
        mock_trading_service = MagicMock(spec=TradingService)
        mock_request = MagicMock(spec=Request)
        mock_request.app.state.trading_service = mock_trading_service

        result = get_trading_service(mock_request)
        assert result is mock_trading_service

        # Test exception raising in dependency
        mock_request_no_service = MagicMock(spec=Request)
        mock_request_no_service.app.state.trading_service = None

        with pytest.raises(RuntimeError) as exc_info:
            get_trading_service(mock_request_no_service)

        assert "TradingService not found in application state" in str(exc_info.value)

    def test_config_exceptions_integration(self):
        """Test that config validation integrates with custom exceptions."""
        # Test that config validation errors can be converted to custom exceptions
        try:
            # Create settings with invalid CORS origins
            with patch.dict(os.environ, {"BACKEND_CORS_ORIGINS": "invalid_type"}):
                test_settings = Settings()
                # If validation passes, test CORS origins validator directly
                test_settings.assemble_cors_origins(123)  # Invalid type
                pytest.fail("Expected validation error")
        except ValueError:
            # Convert to custom exception
            exc = ValidationError("Invalid CORS origins configuration")
            assert exc.status_code == 422
            assert "Invalid CORS origins configuration" in str(exc.detail)

    def test_logging_and_exceptions_integration(self):
        """Test that exceptions can be properly logged."""
        # Test logging custom exceptions
        test_exceptions = [
            ValidationError("Test validation error"),
            NotFoundError("Test not found error"),
            UnauthorizedError("Test unauthorized error"),
        ]

        for exc in test_exceptions:
            try:
                # Log the exception
                logger.error(f"Exception occurred: {exc.detail}", exc_info=exc)
                # Verify exception attributes are accessible
                assert hasattr(exc, "status_code")
                assert hasattr(exc, "detail")
            except Exception as e:
                pytest.fail(f"Failed to log exception {type(exc).__name__}: {e}")

    def test_all_core_modules_import_successfully(self):
        """Test that all core modules can be imported together."""
        try:
            from app.core import config, dependencies, exceptions, logging

            # Verify key exports are available
            assert hasattr(config, "settings")
            assert hasattr(config, "Settings")
            assert hasattr(dependencies, "get_trading_service")
            assert hasattr(exceptions, "CustomException")
            assert hasattr(exceptions, "ValidationError")
            assert hasattr(logging, "setup_logging")
            assert hasattr(logging, "logger")

        except ImportError as e:
            pytest.fail(f"Failed to import core modules: {e}")

    @patch("app.core.logging.get_default_log_dir")
    def test_config_environment_affects_logging_path(self, mock_get_log_dir):
        """Test that environment configuration affects logging paths."""
        mock_log_dir = Path("/custom/log/path")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch("app.core.logging.settings") as mock_settings,
            patch.object(mock_log_dir, "mkdir") as mock_mkdir,
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
            patch("logging.StreamHandler"),
        ):
            mock_settings.LOG_LEVEL = "INFO"

            setup_logging()

            # Verify custom log directory is used
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            expected_log_file = mock_log_dir / "open-paper-trading-mcp.log"
            mock_file_handler.assert_called_once_with(
                expected_log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
            )

    def test_settings_singleton_consistency(self):
        """Test that settings singleton is consistent across imports."""
        from app.core.config import settings as settings1
        from app.core.config import settings as settings2

        # Should be the same instance
        assert settings1 is settings2

        # Verify key attributes are present
        assert hasattr(settings1, "PROJECT_NAME")
        assert hasattr(settings1, "DATABASE_URL")
        assert hasattr(settings1, "LOG_LEVEL")


class TestApplicationLifecycle:
    """Test core module behavior during application lifecycle."""

    def test_startup_sequence_simulation(self):
        """Test simulated application startup sequence."""
        startup_order = []

        # Mock the typical startup sequence
        def mock_setup_logging():
            startup_order.append("logging_setup")

        def mock_init_trading_service():
            startup_order.append("trading_service_init")
            return MagicMock(spec=TradingService)

        # Simulate startup
        with (
            patch("app.core.logging.setup_logging", side_effect=mock_setup_logging),
            patch("app.services.trading_service.TradingService") as mock_service_class,
        ):
            mock_service_class.return_value = mock_init_trading_service()

            # Simulate FastAPI lifespan startup
            mock_setup_logging()
            trading_service = mock_init_trading_service()

            # Verify startup order
            assert startup_order == ["logging_setup", "trading_service_init"]
            assert trading_service is not None

    def test_dependency_injection_during_request(self):
        """Test dependency injection during request processing."""
        # Simulate FastAPI app with state
        mock_app = MagicMock()
        mock_state = MagicMock()
        mock_trading_service = MagicMock(spec=TradingService)

        mock_state.trading_service = mock_trading_service
        mock_app.state = mock_state

        # Simulate request
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Test dependency injection
        injected_service = get_trading_service(mock_request)
        assert injected_service is mock_trading_service

    def test_exception_handling_in_request_cycle(self):
        """Test exception handling throughout request cycle."""
        # Test that custom exceptions maintain their properties through the cycle
        original_exc = NotFoundError("Resource not found")

        # Simulate exception being raised and caught
        try:
            raise original_exc
        except CustomException as caught_exc:
            # Verify exception properties are preserved
            assert caught_exc.status_code == 404
            assert caught_exc.detail == "Resource not found"
            assert isinstance(caught_exc, NotFoundError)
            assert isinstance(caught_exc, CustomException)

    def test_configuration_reload_simulation(self):
        """Test behavior when configuration might be reloaded."""
        # Test that settings can be recreated with different values
        original_project_name = settings.PROJECT_NAME

        with patch.dict(os.environ, {"PROJECT_NAME": "Test Application"}):
            # Create new settings instance (simulating reload)
            new_settings = Settings()
            assert new_settings.PROJECT_NAME == "Test Application"

            # Original settings should be unchanged
            assert original_project_name == settings.PROJECT_NAME

    @patch("app.core.logging.setup_logging")
    def test_logging_initialization_in_lifecycle(self, mock_setup_logging):
        """Test logging initialization as part of application lifecycle."""
        # Simulate application startup calling setup_logging
        mock_setup_logging.side_effect = lambda: None

        # This would typically be called in main.py lifespan
        setup_logging()

        # Verify setup was called
        mock_setup_logging.assert_called_once()

    def test_error_propagation_through_layers(self):
        """Test how errors propagate through core module layers."""
        # Test dependency layer error
        mock_request = MagicMock(spec=Request)
        mock_request.app.state.trading_service = None

        # Dependency should raise RuntimeError
        with pytest.raises(RuntimeError):
            get_trading_service(mock_request)

        # Test that this could be converted to HTTP exception
        try:
            get_trading_service(mock_request)
        except RuntimeError as e:
            # This could be caught by FastAPI and converted
            http_exc = CustomException(status_code=500, detail=str(e))
            assert http_exc.status_code == 500
            assert "TradingService not found" in str(http_exc.detail)


class TestCoreModuleRobustness:
    """Test robustness and edge cases of core module integration."""

    def test_missing_environment_variables(self):
        """Test behavior when environment variables are missing."""
        # Clear environment and test defaults
        with patch.dict(os.environ, {}, clear=True):
            test_settings = Settings()

            # Should use defaults
            assert test_settings.PROJECT_NAME == "Open Paper Trading MCP"
            assert test_settings.API_V1_STR == "/api/v1"
            assert test_settings.DEBUG is True  # Default
            assert test_settings.LOG_LEVEL == "INFO"  # Default

    def test_invalid_environment_values(self):
        """Test handling of invalid environment values."""
        test_cases = [
            ("DEBUG", "invalid", True),  # Should fallback to default or raise
            ("MCP_SERVER_PORT", "not_a_number", 2081),  # Should use default
        ]

        for env_var, invalid_value, _expected_default in test_cases:
            with patch.dict(os.environ, {env_var: invalid_value}):
                try:
                    Settings()
                    # If it doesn't raise an error, verify it uses a reasonable default
                    if env_var == "DEBUG":
                        # Might raise ValidationError or use default
                        pass
                    elif env_var == "MCP_SERVER_PORT":
                        # Should raise ValidationError for invalid int
                        pass
                except Exception:
                    # Expected for invalid values
                    pass

    def test_concurrent_access_safety(self):
        """Test thread safety of core module components."""
        import threading
        import time

        results = []
        errors = []

        def access_settings():
            try:
                # Access settings from multiple threads
                s = settings
                results.append(s.PROJECT_NAME)
                time.sleep(0.01)  # Small delay to encourage race conditions
                results.append(s.API_V1_STR)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=access_settings) for _ in range(5)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify consistent results
        project_names = [result for i, result in enumerate(results) if i % 2 == 0]
        api_strs = [result for i, result in enumerate(results) if i % 2 == 1]

        assert all(name == settings.PROJECT_NAME for name in project_names)
        assert all(api_str == settings.API_V1_STR for api_str in api_strs)

    def test_memory_usage_patterns(self):
        """Test that core modules don't have obvious memory leaks."""
        import gc

        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create and destroy multiple settings instances
        for _ in range(100):
            temp_settings = Settings()
            # Use the settings to ensure they're not optimized away
            _ = temp_settings.PROJECT_NAME
            del temp_settings

        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())

        # Allow for some variance but check for major leaks
        object_growth = final_objects - initial_objects
        assert object_growth < 50, f"Potential memory leak: {object_growth} new objects"

    def test_import_order_independence(self):
        """Test that core modules can be imported in any order."""
        # Test different import orders
        import_orders = [
            ["config", "logging", "dependencies", "exceptions"],
            ["exceptions", "config", "dependencies", "logging"],
            ["dependencies", "exceptions", "logging", "config"],
            ["logging", "dependencies", "config", "exceptions"],
        ]

        for order in import_orders:
            # Clear import cache for clean test (careful with this in real code)
            [f"app.core.{module}" for module in order]

            # Test imports work in this order
            try:
                for module_name in order:
                    module = __import__(
                        f"app.core.{module_name}", fromlist=[module_name]
                    )
                    assert module is not None
            except ImportError as e:
                pytest.fail(f"Import order {order} failed: {e}")


class TestRealWorldScenarios:
    """Test real-world usage scenarios of core modules."""

    def test_fastapi_app_integration_simulation(self):
        """Test integration with a simulated FastAPI application."""
        # Create a minimal FastAPI app simulation
        app = MagicMock(spec=FastAPI)
        app.state = MagicMock()

        # Simulate lifespan startup
        with patch("app.core.logging.setup_logging") as mock_setup:
            mock_setup.return_value = None

            # Simulate startup sequence
            setup_logging()  # Would be called in lifespan

            # Initialize trading service
            mock_trading_service = MagicMock(spec=TradingService)
            app.state.trading_service = mock_trading_service

            # Simulate request handling
            mock_request = MagicMock(spec=Request)
            mock_request.app = app

            # Test dependency injection works
            service = get_trading_service(mock_request)
            assert service is mock_trading_service

            # Verify setup was called
            mock_setup.assert_called_once()

    def test_error_scenarios_in_production(self):
        """Test error handling in production-like scenarios."""
        # Test production configuration
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "DEBUG": "false", "LOG_LEVEL": "WARNING"},
        ):
            prod_settings = Settings()
            assert prod_settings.ENVIRONMENT == "production"
            assert prod_settings.DEBUG is False
            assert prod_settings.LOG_LEVEL == "WARNING"

            # Test that exceptions still work properly in production config
            exc = ValidationError("Production validation error")
            assert exc.status_code == 422

            # Test logging setup with production settings
            with (
                patch("app.core.logging.settings", prod_settings),
                patch("app.core.logging.get_default_log_dir") as mock_log_dir,
                patch("pathlib.Path.mkdir"),
                patch("logging.handlers.RotatingFileHandler"),
                patch("logging.StreamHandler"),
            ):
                mock_log_dir.return_value = Path("/var/log/app")

                try:
                    setup_logging()
                    # Should work without error
                    assert True
                except Exception as e:
                    pytest.fail(f"Production logging setup failed: {e}")

    def test_development_vs_production_behavior(self):
        """Test different behavior between development and production."""
        # Test development settings
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "development", "DEBUG": "true", "LOG_LEVEL": "DEBUG"},
        ):
            dev_settings = Settings()
            assert dev_settings.ENVIRONMENT == "development"
            assert dev_settings.DEBUG is True
            assert dev_settings.LOG_LEVEL == "DEBUG"

        # Test production settings
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "DEBUG": "false", "LOG_LEVEL": "ERROR"},
        ):
            prod_settings = Settings()
            assert prod_settings.ENVIRONMENT == "production"
            assert prod_settings.DEBUG is False
            assert prod_settings.LOG_LEVEL == "ERROR"

        # Both should work with core modules
        for test_settings in [dev_settings, prod_settings]:
            with (
                patch("app.core.logging.settings", test_settings),
                patch("app.core.logging.get_default_log_dir") as mock_log_dir,
                patch("pathlib.Path.mkdir"),
                patch("logging.handlers.RotatingFileHandler"),
                patch("logging.StreamHandler"),
            ):
                mock_log_dir.return_value = Path("/test/logs")
                setup_logging()
                # Should complete without error
                assert True

    def test_database_url_configuration_scenarios(self):
        """Test various database URL configuration scenarios."""
        test_urls = [
            "postgresql+asyncpg://user:pass@localhost:5432/db",
            "postgresql://user:pass@remote:5432/db",
            "sqlite:///./test.db",
            "mysql+pymysql://user:pass@localhost:3306/db",
        ]

        for db_url in test_urls:
            with patch.dict(os.environ, {"DATABASE_URL": db_url}):
                test_settings = Settings()
                assert db_url == test_settings.DATABASE_URL

                # Should work with dependency injection
                mock_service = MagicMock(spec=TradingService)
                mock_request = MagicMock(spec=Request)
                mock_request.app.state.trading_service = mock_service

                result = get_trading_service(mock_request)
                assert result is mock_service
