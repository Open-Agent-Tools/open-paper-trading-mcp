"""Comprehensive tests for app/core/config.py and app/core/exceptions.py"""

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.config import Settings, settings
from app.core.exceptions import (
    ConflictError,
    CustomException,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class TestSettings:
    """Test the Settings configuration class."""

    def test_default_values(self):
        """Test default configuration values."""
        # Use explicit environment clearing for this test
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db",
                "SECRET_KEY": "your-secret-key-change-this-in-production",
                "ENVIRONMENT": "development",
                "DEBUG": "True",
                "LOG_LEVEL": "INFO",
                "MCP_SERVER_PORT": "2081",
                "MCP_SERVER_HOST": "localhost",
                "QUOTE_ADAPTER_TYPE": "test",
                "TEST_SCENARIO": "default",
                "TEST_DATE": "2017-03-24",
                "ROBINHOOD_USERNAME": "",
                "ROBINHOOD_PASSWORD": "",
                "ROBINHOOD_TOKEN_PATH": "/app/.tokens",
            },
            clear=True,
        ):
            default_settings = Settings()

            assert default_settings.PROJECT_NAME == "Open Paper Trading MCP"
            assert default_settings.API_V1_STR == "/api/v1"
            assert default_settings.BACKEND_CORS_ORIGINS == [
                "http://localhost:3000",
                "http://localhost:2080",
            ]
            assert default_settings.REDIS_URL == "redis://localhost:6379"
            assert default_settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
            assert default_settings.MCP_SERVER_PORT == 2081
            assert default_settings.MCP_SERVER_HOST == "localhost"
            assert default_settings.MCP_SERVER_NAME == "Open Paper Trading MCP"
            assert default_settings.QUOTE_ADAPTER_TYPE == "test"
            assert default_settings.TEST_SCENARIO == "default"
            assert default_settings.TEST_DATE == "2017-03-24"
            assert default_settings.ROBINHOOD_USERNAME == ""
            assert default_settings.ROBINHOOD_PASSWORD == ""
            assert default_settings.ROBINHOOD_TOKEN_PATH == "/app/.tokens"

    def test_default_database_url_from_code(self):
        """Test default database URL directly from os.getenv default."""
        # This tests the actual logic in config.py which uses os.getenv with a default
        with patch("os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: (
                default if key == "DATABASE_URL" else os.getenv(key, default)
            )
            test_settings = Settings()
            expected_url = (
                "postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db"
            )
            assert expected_url == test_settings.DATABASE_URL

    @patch.dict(
        os.environ, {"DATABASE_URL": "postgresql://custom:db@host:5433/custom_db"}
    )
    def test_custom_database_url(self):
        """Test custom database URL from environment."""
        test_settings = Settings()
        assert (
            test_settings.DATABASE_URL == "postgresql://custom:db@host:5433/custom_db"
        )

    @patch.dict(os.environ, {"SECRET_KEY": "custom-secret-key"})
    def test_custom_secret_key(self):
        """Test custom secret key from environment."""
        test_settings = Settings()
        assert test_settings.SECRET_KEY == "custom-secret-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_default_secret_key(self):
        """Test default secret key when not set in environment."""
        test_settings = Settings()
        assert test_settings.SECRET_KEY == "your-secret-key-change-this-in-production"

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_custom_environment(self):
        """Test custom environment from environment variable."""
        test_settings = Settings()
        assert test_settings.ENVIRONMENT == "production"

    @patch.dict(os.environ, {"DEBUG": "false"})
    def test_debug_false(self):
        """Test DEBUG setting as false."""
        test_settings = Settings()
        assert test_settings.DEBUG is False

    @patch.dict(os.environ, {"DEBUG": "True"})
    def test_debug_true(self):
        """Test DEBUG setting as true."""
        test_settings = Settings()
        assert test_settings.DEBUG is True

    @patch.dict(os.environ, {"DEBUG": "FALSE"})
    def test_debug_false_case_insensitive(self):
        """Test DEBUG setting case insensitive false."""
        test_settings = Settings()
        assert test_settings.DEBUG is False

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_custom_log_level(self):
        """Test custom log level from environment."""
        test_settings = Settings()
        assert test_settings.LOG_LEVEL == "ERROR"

    @patch.dict(os.environ, {"MCP_SERVER_PORT": "3000"})
    def test_custom_mcp_port(self):
        """Test custom MCP server port from environment."""
        test_settings = Settings()
        assert test_settings.MCP_SERVER_PORT == 3000

    @patch.dict(os.environ, {"MCP_SERVER_HOST": "0.0.0.0"})
    def test_custom_mcp_host(self):
        """Test custom MCP server host from environment."""
        test_settings = Settings()
        assert test_settings.MCP_SERVER_HOST == "0.0.0.0"

    @patch.dict(os.environ, {"QUOTE_ADAPTER_TYPE": "robinhood"})
    def test_quote_adapter_robinhood(self):
        """Test Robinhood quote adapter type."""
        test_settings = Settings()
        assert test_settings.QUOTE_ADAPTER_TYPE == "robinhood"

    @patch.dict(os.environ, {"TEST_SCENARIO": "volatile"})
    def test_custom_test_scenario(self):
        """Test custom test scenario from environment."""
        test_settings = Settings()
        assert test_settings.TEST_SCENARIO == "volatile"

    @patch.dict(os.environ, {"TEST_DATE": "2020-01-01"})
    def test_custom_test_date(self):
        """Test custom test date from environment."""
        test_settings = Settings()
        assert test_settings.TEST_DATE == "2020-01-01"

    @patch.dict(
        os.environ,
        {
            "ROBINHOOD_USERNAME": "test_user",
            "ROBINHOOD_PASSWORD": "test_pass",
            "ROBINHOOD_TOKEN_PATH": "/custom/tokens",
        },
    )
    def test_robinhood_credentials(self):
        """Test Robinhood credentials from environment."""
        test_settings = Settings()
        assert test_settings.ROBINHOOD_USERNAME == "test_user"
        assert test_settings.ROBINHOOD_PASSWORD == "test_pass"
        assert test_settings.ROBINHOOD_TOKEN_PATH == "/custom/tokens"

    def test_cors_origins_string_parsing(self):
        """Test CORS origins parsing from string."""
        test_settings = Settings()

        # Test with string input (comma-separated)
        result = test_settings.assemble_cors_origins(
            "http://localhost:3000,http://localhost:8080"
        )
        assert result == ["http://localhost:3000", "http://localhost:8080"]

    def test_cors_origins_string_with_spaces(self):
        """Test CORS origins parsing with spaces."""
        test_settings = Settings()

        result = test_settings.assemble_cors_origins(
            "http://localhost:3000, http://localhost:8080"
        )
        assert result == ["http://localhost:3000", "http://localhost:8080"]

    def test_cors_origins_list_passthrough(self):
        """Test CORS origins when already a list."""
        test_settings = Settings()

        input_list = ["http://localhost:3000", "http://localhost:8080"]
        result = test_settings.assemble_cors_origins(input_list)
        assert result == input_list

    def test_cors_origins_json_array_string(self):
        """Test CORS origins with JSON array string."""
        test_settings = Settings()

        # JSON array strings should pass through unchanged
        json_string = '["http://localhost:3000", "http://localhost:8080"]'
        result = test_settings.assemble_cors_origins(json_string)
        assert result == json_string

    def test_cors_origins_invalid_type(self):
        """Test CORS origins with invalid type raises ValueError."""
        test_settings = Settings()

        with pytest.raises(ValueError):
            test_settings.assemble_cors_origins(123)

    def test_settings_singleton_instance(self):
        """Test that the global settings instance is properly configured."""
        # Test that the global settings instance exists and has expected values
        assert settings.PROJECT_NAME == "Open Paper Trading MCP"
        assert settings.API_V1_STR == "/api/v1"
        assert isinstance(settings.BACKEND_CORS_ORIGINS, list)

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("development", "development"),
            ("production", "production"),
            ("testing", "testing"),
            ("", ""),
        ],
    )
    def test_environment_values(self, env_value, expected):
        """Test various environment values."""
        with patch.dict(os.environ, {"ENVIRONMENT": env_value}):
            test_settings = Settings()
            assert expected == test_settings.ENVIRONMENT

    @pytest.mark.parametrize(
        "debug_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ],
    )
    def test_debug_boolean_parsing(self, debug_value, expected):
        """Test DEBUG boolean parsing with various values."""
        with patch.dict(os.environ, {"DEBUG": debug_value}):
            test_settings = Settings()
            assert test_settings.DEBUG is expected

    def test_debug_invalid_values(self):
        """Test DEBUG with invalid values raises ValidationError."""
        with patch.dict(os.environ, {"DEBUG": "invalid"}):
            with pytest.raises(Exception):  # Pydantic ValidationError
                Settings()

    def test_debug_empty_string_fails(self):
        """Test DEBUG with empty string fails validation."""
        with patch.dict(os.environ, {"DEBUG": ""}):
            with pytest.raises(Exception):  # Pydantic ValidationError
                Settings()

    def test_model_config_attributes(self):
        """Test model configuration attributes."""
        test_settings = Settings()

        # Test that model_config is properly set
        config = test_settings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("case_sensitive") is True
        assert config.get("extra") == "ignore"


class TestCustomException:
    """Test the CustomException base class."""

    def test_custom_exception_inheritance(self):
        """Test that CustomException inherits from HTTPException."""
        assert issubclass(CustomException, HTTPException)

    def test_custom_exception_basic_creation(self):
        """Test basic CustomException creation."""
        exc = CustomException(status_code=500, detail="Test error")

        assert exc.status_code == 500
        assert exc.detail == "Test error"
        assert exc.headers is None

    def test_custom_exception_with_headers(self):
        """Test CustomException with headers."""
        headers = {"X-Custom": "value"}
        exc = CustomException(status_code=400, detail="Bad request", headers=headers)

        assert exc.status_code == 400
        assert exc.detail == "Bad request"
        assert exc.headers == headers

    def test_custom_exception_none_detail(self):
        """Test CustomException with explicit None detail."""
        # FastAPI HTTPException automatically sets detail for status codes
        # Test that we can override this by explicitly setting None
        exc = CustomException(status_code=500, detail=None)

        assert exc.status_code == 500
        # HTTPException will set a default message even with detail=None
        # So we test that it behaves as expected with this constraint
        assert exc.detail == "Internal Server Error"  # Default for 500
        assert exc.headers is None

    def test_custom_exception_complex_detail(self):
        """Test CustomException with complex detail object."""
        detail = {"error": "validation_failed", "fields": ["name", "email"]}
        exc = CustomException(status_code=422, detail=detail)

        assert exc.status_code == 422
        assert exc.detail == detail


class TestValidationError:
    """Test the ValidationError exception class."""

    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from CustomException."""
        assert issubclass(ValidationError, CustomException)

    def test_validation_error_default(self):
        """Test ValidationError with default message."""
        exc = ValidationError()

        assert exc.status_code == 422
        assert exc.detail == "Validation error"

    def test_validation_error_custom_detail(self):
        """Test ValidationError with custom detail."""
        exc = ValidationError(detail="Invalid input format")

        assert exc.status_code == 422
        assert exc.detail == "Invalid input format"

    def test_validation_error_is_http_exception(self):
        """Test that ValidationError is an HTTPException."""
        exc = ValidationError()
        assert isinstance(exc, HTTPException)


class TestNotFoundError:
    """Test the NotFoundError exception class."""

    def test_not_found_error_inheritance(self):
        """Test that NotFoundError inherits from CustomException."""
        assert issubclass(NotFoundError, CustomException)

    def test_not_found_error_default(self):
        """Test NotFoundError with default message."""
        exc = NotFoundError()

        assert exc.status_code == 404
        assert exc.detail == "Resource not found"

    def test_not_found_error_custom_detail(self):
        """Test NotFoundError with custom detail."""
        exc = NotFoundError(detail="User not found")

        assert exc.status_code == 404
        assert exc.detail == "User not found"


class TestUnauthorizedError:
    """Test the UnauthorizedError exception class."""

    def test_unauthorized_error_inheritance(self):
        """Test that UnauthorizedError inherits from CustomException."""
        assert issubclass(UnauthorizedError, CustomException)

    def test_unauthorized_error_default(self):
        """Test UnauthorizedError with default message."""
        exc = UnauthorizedError()

        assert exc.status_code == 401
        assert exc.detail == "Unauthorized"

    def test_unauthorized_error_custom_detail(self):
        """Test UnauthorizedError with custom detail."""
        exc = UnauthorizedError(detail="Invalid token")

        assert exc.status_code == 401
        assert exc.detail == "Invalid token"


class TestForbiddenError:
    """Test the ForbiddenError exception class."""

    def test_forbidden_error_inheritance(self):
        """Test that ForbiddenError inherits from CustomException."""
        assert issubclass(ForbiddenError, CustomException)

    def test_forbidden_error_default(self):
        """Test ForbiddenError with default message."""
        exc = ForbiddenError()

        assert exc.status_code == 403
        assert exc.detail == "Forbidden"

    def test_forbidden_error_custom_detail(self):
        """Test ForbiddenError with custom detail."""
        exc = ForbiddenError(detail="Access denied")

        assert exc.status_code == 403
        assert exc.detail == "Access denied"


class TestConflictError:
    """Test the ConflictError exception class."""

    def test_conflict_error_inheritance(self):
        """Test that ConflictError inherits from CustomException."""
        assert issubclass(ConflictError, CustomException)

    def test_conflict_error_default(self):
        """Test ConflictError with default message."""
        exc = ConflictError()

        assert exc.status_code == 409
        assert exc.detail == "Conflict"

    def test_conflict_error_custom_detail(self):
        """Test ConflictError with custom detail."""
        exc = ConflictError(detail="Resource already exists")

        assert exc.status_code == 409
        assert exc.detail == "Resource already exists"


class TestExceptionRaising:
    """Test raising and catching custom exceptions."""

    def test_raise_validation_error(self):
        """Test raising and catching ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Test validation error")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "Test validation error"

    def test_raise_not_found_error(self):
        """Test raising and catching NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError("Test not found error")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Test not found error"

    def test_catch_as_http_exception(self):
        """Test catching custom exceptions as HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            raise UnauthorizedError("Test unauthorized")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Test unauthorized"

    def test_catch_as_custom_exception(self):
        """Test catching custom exceptions as CustomException."""
        with pytest.raises(CustomException) as exc_info:
            raise ForbiddenError("Test forbidden")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Test forbidden"

    @pytest.mark.parametrize(
        "exception_class,expected_status,default_message",
        [
            (ValidationError, 422, "Validation error"),
            (NotFoundError, 404, "Resource not found"),
            (UnauthorizedError, 401, "Unauthorized"),
            (ForbiddenError, 403, "Forbidden"),
            (ConflictError, 409, "Conflict"),
        ],
    )
    def test_exception_defaults(
        self, exception_class, expected_status, default_message
    ):
        """Test default values for all exception classes."""
        exc = exception_class()
        assert exc.status_code == expected_status
        assert exc.detail == default_message


class TestIntegrationScenarios:
    """Test integration scenarios combining config and exceptions."""

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "DEBUG": "false"})
    def test_production_config_with_exceptions(self):
        """Test production configuration doesn't affect exception behavior."""
        test_settings = Settings()
        assert test_settings.ENVIRONMENT == "production"
        assert test_settings.DEBUG is False

        # Exceptions should work the same regardless of config
        exc = ValidationError("Production validation error")
        assert exc.status_code == 422
        assert exc.detail == "Production validation error"

    def test_exception_serialization(self):
        """Test that exceptions can be properly serialized for API responses."""
        exc = NotFoundError("Resource not found")

        # Test that the exception has the required attributes for FastAPI
        assert hasattr(exc, "status_code")
        assert hasattr(exc, "detail")
        assert hasattr(exc, "headers")

        # Test values
        assert exc.status_code == 404
        assert exc.detail == "Resource not found"
        assert exc.headers is None
