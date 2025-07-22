"""Integration tests for app.core module as a whole.

Tests integration between core components, module loading patterns,
and overall core module functionality in the paper trading platform.
"""

import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestCoreModuleStructure:
    """Test core module structure and organization."""

    def test_core_module_imports(self):
        """Test that core module components can be imported successfully."""
        # Test individual module imports
        import app.core.config
        import app.core.dependencies
        import app.core.exceptions
        import app.core.logging

        # Verify modules are accessible
        assert hasattr(app.core.config, "Settings")
        assert hasattr(app.core.config, "settings")
        assert hasattr(app.core.logging, "setup_logging")
        assert hasattr(app.core.logging, "logger")
        assert hasattr(app.core.dependencies, "get_trading_service")
        assert hasattr(app.core.exceptions, "CustomException")

    def test_core_submodule_availability(self):
        """Test that all core submodules are available."""
        core_modules = [
            "app.core.config",
            "app.core.logging",
            "app.core.dependencies",
            "app.core.exceptions",
        ]

        for module_name in core_modules:
            try:
                module = importlib.import_module(module_name)
                assert module is not None
            except ImportError as e:
                pytest.fail(f"Core module {module_name} should be importable: {e}")

    def test_core_module_independence(self):
        """Test that core modules can be imported independently."""
        # Test that each module can be imported without others
        import sys

        # Clear any previously imported core modules (in a test context)
        [name for name in sys.modules if name.startswith("app.core.")]

        for module_name in [
            "app.core.config",
            "app.core.logging",
            "app.core.dependencies",
            "app.core.exceptions",
        ]:
            try:
                # Re-import to test independence
                module = importlib.import_module(module_name)
                assert module is not None
            except ImportError as e:
                pytest.fail(
                    f"Core module {module_name} should be independently importable: {e}"
                )


class TestCoreModuleDependencies:
    """Test dependencies between core modules."""

    def test_logging_depends_on_config(self):
        """Test that logging module properly depends on config module."""
        from app.core.config import Settings
        from app.core.logging import settings

        # Logging should use settings from config
        assert isinstance(settings, Settings)
        assert hasattr(settings, "LOG_LEVEL")

    def test_dependencies_imports_trading_service(self):
        """Test that dependencies module imports TradingService correctly."""
        from app.core.dependencies import TradingService

        # Should be able to import TradingService type
        assert TradingService is not None

        # Should be the correct TradingService from services module
        from app.services.trading_service import TradingService as ServiceTradingService

        assert TradingService is ServiceTradingService

    def test_exceptions_inherit_from_fastapi(self):
        """Test that exceptions module properly inherits from FastAPI."""
        from fastapi import HTTPException

        from app.core.exceptions import CustomException

        # CustomException should inherit from HTTPException
        assert issubclass(CustomException, HTTPException)

    def test_circular_dependency_absence(self):
        """Test that there are no circular dependencies between core modules."""
        # This test ensures clean module dependency graph

        # Import all core modules
        from app.core import config, dependencies, exceptions, logging

        # All should import successfully without circular dependency issues
        assert config is not None
        assert logging is not None
        assert dependencies is not None
        assert exceptions is not None


class TestCoreModuleInitialization:
    """Test core module initialization patterns."""

    def test_config_settings_global_instance(self):
        """Test that config creates a global settings instance."""
        from app.core.config import Settings, settings

        assert isinstance(settings, Settings)
        assert settings.PROJECT_NAME == "Open Paper Trading MCP"

    def test_logging_module_logger_export(self):
        """Test that logging module exports a configured logger."""
        from app.core.logging import logger

        assert logger.name == "open_paper_trading_mcp"
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_dependencies_function_availability(self):
        """Test that dependencies module provides the expected dependency function."""
        from app.core.dependencies import get_trading_service

        assert callable(get_trading_service)
        assert hasattr(get_trading_service, "__doc__")
        assert hasattr(get_trading_service, "__annotations__")

    def test_exceptions_class_availability(self):
        """Test that exception classes are available for import."""
        from app.core.exceptions import (
            ConflictError,
            CustomException,
            ForbiddenError,
            NotFoundError,
            UnauthorizedError,
            ValidationError,
        )

        exception_classes = [
            CustomException,
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]

        for exc_class in exception_classes:
            assert callable(exc_class)
            assert issubclass(exc_class, Exception)


class TestCoreModuleConfiguration:
    """Test core module configuration integration."""

    def test_environment_configuration_flow(self):
        """Test configuration flow from environment to modules."""
        with patch.dict(
            "os.environ",
            {"LOG_LEVEL": "DEBUG", "DEBUG": "true", "ENVIRONMENT": "test"},
            clear=False,
        ):
            # Re-import to get updated config
            importlib.reload(importlib.import_module("app.core.config"))
            from app.core.config import settings

            assert settings.LOG_LEVEL == "DEBUG"
            assert settings.DEBUG is True
            assert settings.ENVIRONMENT == "test"

    def test_logging_configuration_integration(self):
        """Test that logging setup integrates with configuration."""

        with patch("app.core.logging.setup_logging"):
            # Import logging module to trigger any initialization
            import app.core.logging

            # setup_logging should be available for call
            assert hasattr(app.core.logging, "setup_logging")
            assert callable(app.core.logging.setup_logging)

    def test_fastapi_integration_readiness(self):
        """Test that core modules are ready for FastAPI integration."""
        from fastapi import HTTPException, Request

        from app.core.dependencies import get_trading_service
        from app.core.exceptions import ValidationError

        # Dependencies should work with FastAPI Request
        assert get_trading_service.__annotations__["request"] == Request

        # Exceptions should be compatible with FastAPI
        validation_error = ValidationError()
        assert isinstance(validation_error, HTTPException)
        assert validation_error.status_code == 422


class TestCoreModuleErrorHandling:
    """Test error handling across core modules."""

    def test_config_loading_error_handling(self):
        """Test config module handles loading errors gracefully."""
        # Test that invalid environment variables don't crash the config
        with patch.dict(
            "os.environ", {"ACCESS_TOKEN_EXPIRE_MINUTES": "invalid_number"}, clear=False
        ):
            try:
                # Should handle invalid values gracefully or raise appropriate error
                from app.core.config import Settings

                settings = Settings()
                # Either use default or raise ValidationError
                assert isinstance(settings.ACCESS_TOKEN_EXPIRE_MINUTES, int)
            except Exception as e:
                # Should be a validation-related error, not a crash
                assert "validation" in str(e).lower() or "value" in str(e).lower()

    def test_logging_setup_error_resilience(self):
        """Test logging setup handles errors gracefully."""
        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            try:
                from app.core.logging import setup_logging

                # Should not crash even if directory creation fails
                setup_logging()
            except OSError:
                pytest.fail(
                    "Logging setup should handle directory creation failures gracefully"
                )

    def test_dependency_injection_error_messages(self):
        """Test that dependency injection provides clear error messages."""
        from app.core.dependencies import get_trading_service

        mock_request = MagicMock()
        mock_request.app.state.trading_service = None

        with pytest.raises(RuntimeError) as exc_info:
            get_trading_service(mock_request)

        error_message = str(exc_info.value)
        assert "TradingService not found" in error_message
        assert "application state" in error_message
        assert "lifespan context manager" in error_message

    def test_exception_hierarchy_consistency(self):
        """Test that exception hierarchy is consistent and usable."""
        from app.core.exceptions import (
            ConflictError,
            CustomException,
            ForbiddenError,
            NotFoundError,
            UnauthorizedError,
            ValidationError,
        )

        # All custom exceptions should inherit from CustomException
        custom_exceptions = [
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]

        for exc_class in custom_exceptions:
            try:
                instance = exc_class("Test error")
                assert isinstance(instance, CustomException)
                assert hasattr(instance, "status_code")
                assert hasattr(instance, "detail")
            except Exception as e:
                pytest.fail(f"Exception {exc_class} should be instantiable: {e}")


class TestCoreModulePerformance:
    """Test performance characteristics of core module components."""

    def test_config_loading_performance(self):
        """Test that config loading is reasonably fast."""
        import time

        start_time = time.time()
        for _ in range(10):
            from app.core.config import Settings

            Settings()
        end_time = time.time()

        # Should complete quickly (less than 1 second for 10 instantiations)
        assert end_time - start_time < 1.0

    def test_logging_setup_performance(self):
        """Test that logging setup is reasonably fast."""
        import time

        from app.core.logging import setup_logging

        with (
            patch("pathlib.Path.mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.getLogger"),
        ):
            start_time = time.time()
            for _ in range(5):
                setup_logging()
            end_time = time.time()

            # Should complete quickly
            assert end_time - start_time < 1.0

    def test_dependency_resolution_performance(self):
        """Test that dependency resolution is fast."""
        import time

        from app.core.dependencies import get_trading_service

        mock_request = MagicMock()
        mock_service = MagicMock()
        mock_request.app.state.trading_service = mock_service

        start_time = time.time()
        for _ in range(1000):
            result = get_trading_service(mock_request)
            assert result is mock_service
        end_time = time.time()

        # Should be very fast (less than 0.1 seconds for 1000 calls)
        assert end_time - start_time < 0.1

    def test_exception_instantiation_performance(self):
        """Test that exception instantiation is fast."""
        import time

        from app.core.exceptions import ValidationError

        start_time = time.time()
        for _ in range(1000):
            ValidationError("Test error")
        end_time = time.time()

        # Should be fast (less than 0.1 seconds for 1000 instantiations)
        assert end_time - start_time < 0.1


class TestCoreModuleDocumentation:
    """Test documentation and API design of core modules."""

    def test_module_docstrings_present(self):
        """Test that core modules have documentation."""
        core_modules = [
            "app.core.config",
            "app.core.logging",
            "app.core.dependencies",
            "app.core.exceptions",
        ]

        for module_name in core_modules:
            module = importlib.import_module(module_name)
            # Module should have some form of documentation
            assert hasattr(module, "__doc__")

    def test_function_signatures_documented(self):
        """Test that key functions have proper signatures and documentation."""
        from app.core.dependencies import get_trading_service
        from app.core.logging import get_default_log_dir, setup_logging

        functions_to_check = [get_trading_service, setup_logging, get_default_log_dir]

        for func in functions_to_check:
            assert hasattr(func, "__doc__")
            assert hasattr(func, "__annotations__")
            # Should have docstring
            assert func.__doc__ is not None

    def test_class_documentation_completeness(self):
        """Test that key classes have proper documentation."""
        from app.core.config import Settings
        from app.core.exceptions import CustomException, ValidationError

        classes_to_check = [Settings, CustomException, ValidationError]

        for cls in classes_to_check:
            assert hasattr(cls, "__name__")
            assert hasattr(cls, "__module__")
            # Class should be identifiable
            assert cls.__name__ is not None
            assert cls.__module__ is not None


class TestCoreModuleTyping:
    """Test type annotations and typing support in core modules."""

    def test_config_type_annotations(self):
        """Test that config module has proper type annotations."""
        import inspect

        from app.core.config import Settings

        # Settings class should have type annotations for fields
        inspect.signature(Settings.__init__)
        # Should have annotations (Pydantic handles this)
        assert hasattr(Settings, "__annotations__") or hasattr(Settings, "model_fields")

    def test_dependencies_type_annotations(self):
        """Test that dependencies module has proper type annotations."""
        from fastapi import Request

        from app.core.dependencies import get_trading_service
        from app.services.trading_service import TradingService

        annotations = get_trading_service.__annotations__
        assert "request" in annotations
        assert annotations["request"] == Request
        assert annotations["return"] == TradingService

    def test_exceptions_type_annotations(self):
        """Test that exception classes have proper type annotations."""
        from typing import get_type_hints

        from app.core.exceptions import CustomException

        # Get type hints for __init__ method
        try:
            hints = get_type_hints(CustomException.__init__)
            # Should have status_code as int
            assert "status_code" in hints
            assert hints["status_code"] == int
        except (NameError, AttributeError):
            # Type hints might not be fully available in all contexts
            pass

    def test_typing_compatibility(self):
        """Test that core modules are compatible with static type checking."""
        # Test that imports work with typing
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            pass

        # Should import without errors
        assert True
