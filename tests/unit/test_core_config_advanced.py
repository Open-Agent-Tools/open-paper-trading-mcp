"""Advanced comprehensive tests for app.core.config module.

Tests configuration loading, environment variable handling, validation,
field validators, and configuration patterns used in the paper trading platform.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


class TestSettingsConfiguration:
    """Test Settings class configuration and initialization patterns."""

    def test_default_values_loaded_correctly(self):
        """Test that default configuration values are loaded correctly."""
        test_settings = Settings()

        assert test_settings.PROJECT_NAME == "Open Paper Trading MCP"
        assert test_settings.API_V1_STR == "/api/v1"
        assert test_settings.BACKEND_CORS_ORIGINS == [
            "http://localhost:3000",
            "http://localhost:2080",
        ]
        assert test_settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert test_settings.MCP_SERVER_PORT == 2081
        assert test_settings.MCP_SERVER_HOST == "localhost"
        assert test_settings.MCP_SERVER_NAME == "Open Paper Trading MCP"

    def test_environment_variable_override_patterns(self):
        """Test that environment variables correctly override default values."""
        test_env_vars = {
            "PROJECT_NAME": "Test Trading Platform",
            "API_V1_STR": "/test/api/v1",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            "MCP_SERVER_PORT": "3000",
            "MCP_SERVER_HOST": "0.0.0.0",
            "DEBUG": "false",
            "LOG_LEVEL": "ERROR",
            "ENVIRONMENT": "production",
        }

        with patch.dict(os.environ, test_env_vars, clear=False):
            test_settings = Settings()

            assert test_settings.PROJECT_NAME == "Test Trading Platform"
            assert test_settings.API_V1_STR == "/test/api/v1"
            assert test_settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
            assert test_settings.MCP_SERVER_PORT == 3000
            assert test_settings.MCP_SERVER_HOST == "0.0.0.0"
            assert test_settings.DEBUG is False
            assert test_settings.LOG_LEVEL == "ERROR"
            assert test_settings.ENVIRONMENT == "production"

    def test_database_url_configuration(self):
        """Test database URL configuration patterns."""
        # Test default database URL
        test_settings = Settings()
        expected_default = (
            "postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db"
        )
        assert expected_default == test_settings.DATABASE_URL

        # Test custom database URL override
        custom_db_url = (
            "postgresql+asyncpg://custom_user:custom_pass@custom_host:5433/custom_db"
        )
        with patch.dict(os.environ, {"DATABASE_URL": custom_db_url}, clear=False):
            test_settings = Settings()
            assert custom_db_url == test_settings.DATABASE_URL

    def test_redis_configuration(self):
        """Test Redis configuration patterns."""
        test_settings = Settings()
        assert test_settings.REDIS_URL == "redis://localhost:6379"

        # Test Redis URL override
        custom_redis_url = "redis://custom_host:6380/1"
        with patch.dict(os.environ, {"REDIS_URL": custom_redis_url}, clear=False):
            test_settings = Settings()
            assert custom_redis_url == test_settings.REDIS_URL

    def test_security_configuration(self):
        """Test security-related configuration patterns."""
        test_settings = Settings()

        # Test default secret key (should be overridden in production)
        assert test_settings.SECRET_KEY == "your-secret-key-change-this-in-production"

        # Test custom secret key
        custom_secret = "super-secure-secret-key-for-testing"
        with patch.dict(os.environ, {"SECRET_KEY": custom_secret}, clear=False):
            test_settings = Settings()
            assert custom_secret == test_settings.SECRET_KEY

    def test_debug_flag_parsing(self):
        """Test DEBUG flag parsing from string environment variables."""
        # Test various true values
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes"]
        for value in true_values:
            with patch.dict(os.environ, {"DEBUG": value}, clear=False):
                test_settings = Settings()
                assert test_settings.DEBUG is True, f"Failed for DEBUG={value}"

        # Test various false values
        false_values = ["false", "False", "FALSE", "0", "no", "No", ""]
        for value in false_values:
            with patch.dict(os.environ, {"DEBUG": value}, clear=False):
                test_settings = Settings()
                assert test_settings.DEBUG is False, f"Failed for DEBUG={value}"

    def test_quote_adapter_configuration(self):
        """Test quote adapter configuration patterns."""
        test_settings = Settings()
        assert test_settings.QUOTE_ADAPTER_TYPE == "test"

        # Test robinhood adapter
        with patch.dict(os.environ, {"QUOTE_ADAPTER_TYPE": "robinhood"}, clear=False):
            test_settings = Settings()
            assert test_settings.QUOTE_ADAPTER_TYPE == "robinhood"

    def test_test_data_configuration(self):
        """Test test data configuration patterns."""
        test_settings = Settings()
        assert test_settings.TEST_SCENARIO == "default"
        assert test_settings.TEST_DATE == "2017-03-24"

        # Test custom test configuration
        with patch.dict(
            os.environ,
            {"TEST_SCENARIO": "volatility_spike", "TEST_DATE": "2020-03-16"},
            clear=False,
        ):
            test_settings = Settings()
            assert test_settings.TEST_SCENARIO == "volatility_spike"
            assert test_settings.TEST_DATE == "2020-03-16"

    def test_robinhood_configuration(self):
        """Test Robinhood adapter configuration patterns."""
        test_settings = Settings()
        assert test_settings.ROBINHOOD_USERNAME == ""
        assert test_settings.ROBINHOOD_PASSWORD == ""
        assert test_settings.ROBINHOOD_TOKEN_PATH == "/app/.tokens"

        # Test custom Robinhood configuration
        with patch.dict(
            os.environ,
            {
                "ROBINHOOD_USERNAME": "test_user",
                "ROBINHOOD_PASSWORD": "test_pass",
                "ROBINHOOD_TOKEN_PATH": "/custom/token/path",
            },
            clear=False,
        ):
            test_settings = Settings()
            assert test_settings.ROBINHOOD_USERNAME == "test_user"
            assert test_settings.ROBINHOOD_PASSWORD == "test_pass"
            assert test_settings.ROBINHOOD_TOKEN_PATH == "/custom/token/path"


class TestCORSOriginsValidator:
    """Test CORS origins field validator functionality."""

    def test_cors_origins_string_splitting(self):
        """Test CORS origins splitting from comma-separated string."""
        cors_string = "http://localhost:3000,http://localhost:8080,https://example.com"
        with patch.dict(os.environ, {"BACKEND_CORS_ORIGINS": cors_string}, clear=False):
            test_settings = Settings()
            expected = [
                "http://localhost:3000",
                "http://localhost:8080",
                "https://example.com",
            ]
            assert expected == test_settings.BACKEND_CORS_ORIGINS

    def test_cors_origins_with_spaces(self):
        """Test CORS origins handling with extra spaces."""
        cors_string = (
            " http://localhost:3000 , http://localhost:8080 , https://example.com "
        )
        with patch.dict(os.environ, {"BACKEND_CORS_ORIGINS": cors_string}, clear=False):
            test_settings = Settings()
            expected = [
                "http://localhost:3000",
                "http://localhost:8080",
                "https://example.com",
            ]
            assert expected == test_settings.BACKEND_CORS_ORIGINS

    def test_cors_origins_already_list(self):
        """Test CORS origins when already provided as list."""
        # This tests the direct instantiation with list
        test_settings = Settings(
            BACKEND_CORS_ORIGINS=[
                "http://localhost:3000",
                "https://production.example.com",
            ]
        )
        expected = ["http://localhost:3000", "https://production.example.com"]
        assert expected == test_settings.BACKEND_CORS_ORIGINS

    def test_cors_origins_json_array_string(self):
        """Test CORS origins when provided as JSON array string."""
        cors_json = '["http://localhost:3000", "https://example.com"]'
        with patch.dict(os.environ, {"BACKEND_CORS_ORIGINS": cors_json}, clear=False):
            test_settings = Settings()
            # JSON array strings should be returned as-is (starts with '[')
            assert cors_json == test_settings.BACKEND_CORS_ORIGINS

    def test_cors_origins_empty_string(self):
        """Test CORS origins with empty string."""
        with patch.dict(os.environ, {"BACKEND_CORS_ORIGINS": ""}, clear=False):
            test_settings = Settings()
            assert test_settings.BACKEND_CORS_ORIGINS == [""]

    def test_cors_origins_single_value(self):
        """Test CORS origins with single value."""
        with patch.dict(
            os.environ, {"BACKEND_CORS_ORIGINS": "http://localhost:3000"}, clear=False
        ):
            test_settings = Settings()
            assert test_settings.BACKEND_CORS_ORIGINS == ["http://localhost:3000"]


class TestSettingsModelConfiguration:
    """Test Pydantic model configuration settings."""

    def test_model_config_attributes(self):
        """Test that model configuration is set correctly."""
        test_settings = Settings()

        # Check that model config attributes are accessible
        assert hasattr(test_settings.model_config, "case_sensitive")
        assert hasattr(test_settings.model_config, "extra")
        assert hasattr(test_settings.model_config, "env_file")

    def test_case_sensitivity(self):
        """Test case sensitivity in environment variable names."""
        # Settings should be case sensitive
        with patch.dict(
            os.environ,
            {
                "project_name": "lowercase_should_not_work",  # lowercase
                "PROJECT_NAME": "uppercase_should_work",  # uppercase
            },
            clear=False,
        ):
            test_settings = Settings()
            # Should use uppercase version due to case_sensitive=True
            assert test_settings.PROJECT_NAME == "uppercase_should_work"

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored due to extra='ignore'."""
        # This is harder to test directly with environment variables
        # but we can test that no validation error is raised for unknown fields
        try:
            with patch.dict(
                os.environ,
                {
                    "UNKNOWN_SETTING": "should_be_ignored",
                    "ANOTHER_UNKNOWN": "also_ignored",
                },
                clear=False,
            ):
                test_settings = Settings()
                # Should not raise ValidationError due to extra="ignore"
                assert test_settings.PROJECT_NAME == "Open Paper Trading MCP"
        except ValidationError:
            pytest.fail("Settings should ignore extra/unknown fields")


class TestEnvironmentFileLoading:
    """Test .env file loading patterns."""

    def test_env_file_loading_simulation(self):
        """Test environment file loading simulation with temporary file."""
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as temp_env:
            temp_env.write("PROJECT_NAME=EnvFileProject\n")
            temp_env.write("MCP_SERVER_PORT=4000\n")
            temp_env.write("DEBUG=false\n")
            temp_env_path = temp_env.name

        try:
            # Test that Settings would load from .env file if present
            # Note: This is more of a configuration validation test
            # since we can't easily mock the Pydantic env file loading
            test_settings = Settings()

            # Verify the structure supports env file loading
            assert hasattr(test_settings.model_config, "env_file")
            assert test_settings.model_config.env_file == ".env"

        finally:
            # Clean up temporary file
            os.unlink(temp_env_path)


class TestSettingsGlobalInstance:
    """Test the global settings instance."""

    def test_global_settings_instance(self):
        """Test that global settings instance is properly initialized."""
        from app.core.config import settings as global_settings

        assert isinstance(global_settings, Settings)
        assert global_settings.PROJECT_NAME == "Open Paper Trading MCP"

    def test_global_settings_is_singleton_like(self):
        """Test that importing settings multiple times gives consistent values."""
        from app.core.config import settings as settings1
        from app.core.config import settings as settings2

        # Should be the same instance
        assert settings1 is settings2
        assert id(settings1) == id(settings2)


class TestConfigurationEdgeCases:
    """Test edge cases and error conditions in configuration."""

    def test_integer_conversion_edge_cases(self):
        """Test integer field conversion edge cases."""
        # Test valid integer strings
        with patch.dict(
            os.environ,
            {"ACCESS_TOKEN_EXPIRE_MINUTES": "45", "MCP_SERVER_PORT": "8080"},
            clear=False,
        ):
            test_settings = Settings()
            assert test_settings.ACCESS_TOKEN_EXPIRE_MINUTES == 45
            assert test_settings.MCP_SERVER_PORT == 8080

    def test_boolean_conversion_comprehensive(self):
        """Comprehensive test of boolean conversion patterns."""
        # Test all recognized true patterns
        true_patterns = ["1", "true", "True", "TRUE", "on", "On", "ON"]
        for pattern in true_patterns:
            with patch.dict(os.environ, {"DEBUG": pattern}, clear=False):
                test_settings = Settings()
                assert test_settings.DEBUG is True, (
                    f"Pattern '{pattern}' should be True"
                )

    def test_configuration_validation_patterns(self):
        """Test configuration validation patterns."""
        # Test that Settings can be instantiated with various combinations
        test_configs = [
            {},  # Empty config (all defaults)
            {"PROJECT_NAME": "Custom Name"},  # Single override
            {"DEBUG": True, "LOG_LEVEL": "DEBUG"},  # Multiple overrides
        ]

        for config in test_configs:
            test_settings = Settings(**config)
            assert isinstance(test_settings, Settings)

    def test_configuration_immutability_patterns(self):
        """Test that configuration behaves appropriately for immutability."""
        test_settings = Settings()
        original_project_name = test_settings.PROJECT_NAME

        # Pydantic models are not immutable by default, but we can test access patterns
        assert original_project_name == test_settings.PROJECT_NAME

        # Test that we can create new instances with different values
        new_settings = Settings(PROJECT_NAME="Different Name")
        assert new_settings.PROJECT_NAME == "Different Name"
        assert original_project_name == test_settings.PROJECT_NAME


class TestLoggingBasicConfigIntegration:
    """Test integration with basic logging configuration in config module."""

    def test_logging_basic_config_called(self):
        """Test that logging.basicConfig is called during config import."""
        # Since logging.basicConfig is called at module level,
        # we test that importing the module doesn't raise errors
        try:
            import app.core.config

            assert hasattr(app.core.config, "logger")
            assert app.core.config.logger.name == "app.core.config"
        except Exception as e:
            pytest.fail(f"Config module import should not raise exceptions: {e}")

    def test_config_logger_functionality(self):
        """Test that config module logger is functional."""
        from app.core.config import logger as config_logger

        assert config_logger.name == "app.core.config"

        # Test that logger methods exist and are callable
        assert hasattr(config_logger, "info")
        assert hasattr(config_logger, "debug")
        assert hasattr(config_logger, "error")
        assert hasattr(config_logger, "warning")

        # Test that logger calls don't raise exceptions
        try:
            config_logger.info("Test log message")
            config_logger.debug("Test debug message")
        except Exception as e:
            pytest.fail(f"Logger should not raise exceptions: {e}")


class TestConfigurationDependencyInjection:
    """Test configuration usage in dependency injection patterns."""

    def test_settings_can_be_injected(self):
        """Test that settings can be used in dependency injection patterns."""

        # Simulate dependency injection pattern
        def mock_dependency_function(config: Settings = settings):
            return config.PROJECT_NAME

        result = mock_dependency_function()
        assert result == "Open Paper Trading MCP"

        # Test with custom settings
        custom_settings = Settings(PROJECT_NAME="Custom Project")
        result = mock_dependency_function(custom_settings)
        assert result == "Custom Project"

    def test_configuration_serialization(self):
        """Test configuration serialization capabilities."""
        test_settings = Settings()

        # Test that settings can be converted to dict (useful for debugging/logging)
        try:
            settings_dict = test_settings.model_dump()
            assert isinstance(settings_dict, dict)
            assert "PROJECT_NAME" in settings_dict
            assert settings_dict["PROJECT_NAME"] == "Open Paper Trading MCP"
        except Exception as e:
            pytest.fail(f"Settings should be serializable: {e}")
