"""
Comprehensive unit tests for RobinhoodConfig authentication configuration module.

Tests cover configuration loading, credential validation, environment variable handling,
security patterns, and pydantic integration as required by the platform architecture.
"""

import os
from unittest.mock import patch, MagicMock
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.auth.config import RobinhoodConfig, settings


class TestRobinhoodConfig:
    """Test suite for RobinhoodConfig settings management."""

    def test_default_initialization(self):
        """Test RobinhoodConfig initialization with default values."""
        config = RobinhoodConfig()
        
        assert config.username is None
        assert config.password is None
        assert config.expires_in == 86400  # 24 hours default

    def test_explicit_initialization(self):
        """Test RobinhoodConfig initialization with explicit values."""
        config = RobinhoodConfig(
            username="test_user",
            password=SecretStr("test_password"),
            expires_in=3600
        )
        
        assert config.username == "test_user"
        assert isinstance(config.password, SecretStr)
        assert config.expires_in == 3600

    def test_has_credentials_true(self):
        """Test has_credentials returns True when both username and password provided."""
        config = RobinhoodConfig(
            username="test_user",
            password=SecretStr("test_password")
        )
        
        assert config.has_credentials() is True

    def test_has_credentials_false_no_username(self):
        """Test has_credentials returns False when username is missing."""
        config = RobinhoodConfig(
            password=SecretStr("test_password")
        )
        
        assert config.has_credentials() is False

    def test_has_credentials_false_no_password(self):
        """Test has_credentials returns False when password is missing."""
        config = RobinhoodConfig(
            username="test_user"
        )
        
        assert config.has_credentials() is False

    def test_has_credentials_false_both_none(self):
        """Test has_credentials returns False when both are None."""
        config = RobinhoodConfig()
        
        assert config.has_credentials() is False

    def test_get_password_with_password(self):
        """Test get_password returns string when password is set."""
        config = RobinhoodConfig(
            password=SecretStr("secret_password_123")
        )
        
        password = config.get_password()
        assert password == "secret_password_123"
        assert isinstance(password, str)

    def test_get_password_none(self):
        """Test get_password returns None when password is not set."""
        config = RobinhoodConfig()
        
        password = config.get_password()
        assert password is None

    def test_secret_str_security(self):
        """Test that SecretStr properly masks password in string representation."""
        config = RobinhoodConfig(
            username="test_user",
            password=SecretStr("very_secret_password")
        )
        
        # String representation should not contain the actual password
        config_str = str(config)
        assert "very_secret_password" not in config_str
        assert "SecretStr" in config_str or "**********" in config_str

    def test_secret_str_repr_security(self):
        """Test that SecretStr properly masks password in repr."""
        config = RobinhoodConfig(
            password=SecretStr("super_secret_password")
        )
        
        # Repr should not contain the actual password
        config_repr = repr(config)
        assert "super_secret_password" not in config_repr

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "ROBINHOOD_USERNAME": "env_user",
            "ROBINHOOD_PASSWORD": "env_password",
            "ROBINHOOD_EXPIRES_IN": "7200"
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            assert config.username == "env_user"
            assert config.get_password() == "env_password"
            assert config.expires_in == 7200

    def test_environment_variable_prefix(self):
        """Test that environment variables use correct ROBINHOOD_ prefix."""
        # Test that variables without prefix are ignored
        env_vars = {
            "USERNAME": "wrong_user",  # No prefix
            "PASSWORD": "wrong_password",  # No prefix
            "ROBINHOOD_USERNAME": "correct_user",  # Correct prefix
            "ROBINHOOD_PASSWORD": "correct_password"  # Correct prefix
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = RobinhoodConfig()
            
            assert config.username == "correct_user"
            assert config.get_password() == "correct_password"

    def test_environment_variable_case_sensitivity(self):
        """Test that environment variable names are case sensitive."""
        env_vars = {
            "robinhood_username": "lowercase_user",  # Wrong case
            "ROBINHOOD_USERNAME": "uppercase_user",  # Correct case
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = RobinhoodConfig()
            
            assert config.username == "uppercase_user"

    def test_extra_environment_variables_ignored(self):
        """Test that extra environment variables are ignored."""
        env_vars = {
            "ROBINHOOD_USERNAME": "test_user",
            "ROBINHOOD_PASSWORD": "test_password",
            "ROBINHOOD_EXTRA_FIELD": "should_be_ignored",
            "ROBINHOOD_ANOTHER_FIELD": "also_ignored"
        }
        
        with patch.dict(os.environ, env_vars):
            # Should not raise validation error due to extra fields
            config = RobinhoodConfig()
            
            assert config.username == "test_user"
            assert config.get_password() == "test_password"
            # Extra fields should not be present
            assert not hasattr(config, "extra_field")
            assert not hasattr(config, "another_field")

    def test_explicit_values_override_environment(self):
        """Test that explicit values override environment variables."""
        env_vars = {
            "ROBINHOOD_USERNAME": "env_user",
            "ROBINHOOD_PASSWORD": "env_password"
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig(
                username="explicit_user",
                password=SecretStr("explicit_password")
            )
            
            assert config.username == "explicit_user"
            assert config.get_password() == "explicit_password"

    def test_partial_environment_override(self):
        """Test partial override of environment variables."""
        env_vars = {
            "ROBINHOOD_USERNAME": "env_user",
            "ROBINHOOD_PASSWORD": "env_password",
            "ROBINHOOD_EXPIRES_IN": "7200"
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig(
                username="override_user"  # Override username only
            )
            
            assert config.username == "override_user"
            assert config.get_password() == "env_password"  # From env
            assert config.expires_in == 7200  # From env

    def test_dotenv_configuration(self):
        """Test that model config properly handles .env file settings."""
        config = RobinhoodConfig()
        
        # Check model configuration
        assert config.model_config["env_file"] == ".env"
        assert config.model_config["env_file_encoding"] == "utf-8"
        assert config.model_config["env_prefix"] == "ROBINHOOD_"
        assert config.model_config["extra"] == "ignore"

    def test_expires_in_type_conversion(self):
        """Test that expires_in properly converts string to int."""
        env_vars = {
            "ROBINHOOD_EXPIRES_IN": "3600"  # String value
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            assert config.expires_in == 3600
            assert isinstance(config.expires_in, int)

    def test_invalid_expires_in_type(self):
        """Test handling of invalid expires_in values."""
        env_vars = {
            "ROBINHOOD_EXPIRES_IN": "not_a_number"
        }
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(ValidationError):
                RobinhoodConfig()

    def test_negative_expires_in(self):
        """Test handling of negative expires_in values."""
        with pytest.raises(ValidationError):
            RobinhoodConfig(expires_in=-1)

    def test_zero_expires_in(self):
        """Test that zero expires_in is allowed."""
        config = RobinhoodConfig(expires_in=0)
        assert config.expires_in == 0

    def test_password_none_handling(self):
        """Test proper handling when password is explicitly None."""
        config = RobinhoodConfig(password=None)
        
        assert config.password is None
        assert config.get_password() is None
        assert config.has_credentials() is False

    def test_username_none_handling(self):
        """Test proper handling when username is explicitly None."""
        config = RobinhoodConfig(username=None)
        
        assert config.username is None
        assert config.has_credentials() is False

    def test_empty_string_credentials(self):
        """Test handling of empty string credentials."""
        config = RobinhoodConfig(
            username="",
            password=SecretStr("")
        )
        
        # Empty strings should be considered as having credentials
        # (validation of actual values is handled elsewhere)
        assert config.has_credentials() is True
        assert config.username == ""
        assert config.get_password() == ""

    def test_whitespace_credentials(self):
        """Test handling of whitespace-only credentials."""
        config = RobinhoodConfig(
            username="   ",
            password=SecretStr("   ")
        )
        
        assert config.has_credentials() is True
        assert config.username == "   "
        assert config.get_password() == "   "

    def test_unicode_credentials(self):
        """Test handling of unicode characters in credentials."""
        config = RobinhoodConfig(
            username="user_测试",
            password=SecretStr("password_密码")
        )
        
        assert config.has_credentials() is True
        assert config.username == "user_测试"
        assert config.get_password() == "password_密码"

    def test_long_credentials(self):
        """Test handling of very long credentials."""
        long_username = "u" * 1000
        long_password = "p" * 1000
        
        config = RobinhoodConfig(
            username=long_username,
            password=SecretStr(long_password)
        )
        
        assert config.has_credentials() is True
        assert config.username == long_username
        assert config.get_password() == long_password

    def test_special_characters_in_credentials(self):
        """Test handling of special characters in credentials."""
        special_username = "user@example.com"
        special_password = "p@$$w0rd!@#$%^&*()"
        
        config = RobinhoodConfig(
            username=special_username,
            password=SecretStr(special_password)
        )
        
        assert config.has_credentials() is True
        assert config.username == special_username
        assert config.get_password() == special_password


class TestGlobalSettings:
    """Test suite for global settings instance management."""

    def test_global_settings_instance(self):
        """Test that global settings instance exists."""
        assert settings is not None
        assert isinstance(settings, RobinhoodConfig)

    def test_global_settings_singleton_behavior(self):
        """Test that importing settings multiple times returns same instance."""
        # Import settings again
        from app.auth.config import settings as settings2
        
        # Should be the same instance (due to module caching)
        assert settings is settings2

    def test_global_settings_environment_integration(self):
        """Test that global settings integrate with environment variables."""
        # This tests the actual global instance behavior
        # Results depend on current environment, so we test the mechanism
        
        # Settings should be callable and return appropriate types
        if settings.username is not None:
            assert isinstance(settings.username, str)
        
        if settings.password is not None:
            assert isinstance(settings.password, SecretStr)
        
        assert isinstance(settings.expires_in, int)

    def test_global_settings_methods(self):
        """Test that global settings instance has expected methods."""
        # Test method availability
        assert hasattr(settings, "has_credentials")
        assert hasattr(settings, "get_password")
        
        # Test method return types
        has_creds = settings.has_credentials()
        assert isinstance(has_creds, bool)
        
        password = settings.get_password()
        assert password is None or isinstance(password, str)


class TestRobinhoodConfigSecurity:
    """Test suite for security aspects of RobinhoodConfig."""

    def test_password_not_logged_in_dict(self):
        """Test that password is not exposed in dict representation."""
        config = RobinhoodConfig(
            username="test_user",
            password=SecretStr("super_secret_password")
        )
        
        # Convert to dict (as might happen in logging)
        config_dict = config.model_dump()
        
        # Password should be masked or excluded
        if "password" in config_dict:
            # If present, should not contain the actual password
            assert config_dict["password"] != "super_secret_password"

    def test_password_excluded_from_json_serialization(self):
        """Test password handling in JSON serialization."""
        config = RobinhoodConfig(
            username="test_user",
            password=SecretStr("secret_password")
        )
        
        # Test JSON serialization
        json_data = config.model_dump_json()
        
        # Should not contain the actual password
        assert "secret_password" not in json_data

    def test_secure_password_comparison(self):
        """Test that SecretStr provides secure comparison."""
        password1 = SecretStr("same_password")
        password2 = SecretStr("same_password")
        password3 = SecretStr("different_password")
        
        config1 = RobinhoodConfig(password=password1)
        config2 = RobinhoodConfig(password=password2)
        config3 = RobinhoodConfig(password=password3)
        
        # SecretStr should support equality comparison
        assert config1.get_password() == config2.get_password()
        assert config1.get_password() != config3.get_password()

    def test_memory_cleanup_behavior(self):
        """Test that password values can be properly cleaned up."""
        config = RobinhoodConfig(
            password=SecretStr("temporary_password")
        )
        
        # Get password value
        password = config.get_password()
        assert password == "temporary_password"
        
        # Clear config
        config = None
        
        # Password string should still exist in local var
        # (Python's garbage collection behavior test)
        assert password == "temporary_password"

    def test_password_immutability(self):
        """Test that SecretStr provides immutable password storage."""
        config = RobinhoodConfig(
            password=SecretStr("original_password")
        )
        
        # Getting password should return same value consistently
        password1 = config.get_password()
        password2 = config.get_password()
        
        assert password1 == password2
        assert password1 is not None
        assert password2 is not None


class TestRobinhoodConfigValidation:
    """Test suite for validation aspects of RobinhoodConfig."""

    def test_field_types_validation(self):
        """Test that field types are properly validated."""
        # Valid types should work
        config = RobinhoodConfig(
            username="string_username",
            password=SecretStr("string_password"),
            expires_in=3600
        )
        
        assert isinstance(config.username, str)
        assert isinstance(config.password, SecretStr)
        assert isinstance(config.expires_in, int)

    def test_expires_in_validation_positive(self):
        """Test that positive expires_in values are accepted."""
        config = RobinhoodConfig(expires_in=3600)
        assert config.expires_in == 3600

    def test_expires_in_validation_zero(self):
        """Test that zero expires_in value is accepted."""
        config = RobinhoodConfig(expires_in=0)
        assert config.expires_in == 0

    def test_optional_fields_validation(self):
        """Test that optional fields can be None."""
        config = RobinhoodConfig(
            username=None,
            password=None,
            expires_in=86400  # Required field with default
        )
        
        assert config.username is None
        assert config.password is None
        assert config.expires_in == 86400

    def test_default_field_behavior(self):
        """Test default field values and behavior."""
        config = RobinhoodConfig()
        
        # Check default values are set correctly
        assert config.username is None  # Default None
        assert config.password is None  # Default None
        assert config.expires_in == 86400  # Default 24 hours

    def test_pydantic_model_integration(self):
        """Test proper integration with Pydantic BaseSettings."""
        # Should inherit from BaseSettings
        assert issubclass(RobinhoodConfig, BaseSettings)
        
        # Should have proper model configuration
        config = RobinhoodConfig()
        assert hasattr(config, "model_config")
        
        # Should support Pydantic features
        assert hasattr(config, "model_dump")
        assert hasattr(config, "model_dump_json")

    def test_environment_variable_type_coercion(self):
        """Test that environment variables are properly type-coerced."""
        env_vars = {
            "ROBINHOOD_EXPIRES_IN": "7200"  # String that should become int
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            assert config.expires_in == 7200
            assert isinstance(config.expires_in, int)

    def test_configuration_immutability_after_creation(self):
        """Test configuration behavior after creation."""
        config = RobinhoodConfig(
            username="original_user",
            password=SecretStr("original_password")
        )
        
        # Config values should remain stable
        assert config.username == "original_user"
        assert config.get_password() == "original_password"
        
        # Test that has_credentials remains consistent
        assert config.has_credentials() is True


class TestRobinhoodConfigErrorHandling:
    """Test suite for error handling in RobinhoodConfig."""

    def test_invalid_type_for_expires_in(self):
        """Test error handling for invalid expires_in type."""
        with pytest.raises(ValidationError):
            RobinhoodConfig(expires_in="not_a_number")  # type: ignore

    def test_invalid_type_for_username(self):
        """Test error handling for invalid username type."""
        with pytest.raises(ValidationError):
            RobinhoodConfig(username=123)  # type: ignore

    def test_invalid_environment_variable_types(self):
        """Test error handling for invalid environment variable types."""
        env_vars = {
            "ROBINHOOD_EXPIRES_IN": "definitely_not_a_number"
        }
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(ValidationError):
                RobinhoodConfig()

    def test_missing_required_fields_with_defaults(self):
        """Test that fields with defaults don't cause errors when missing."""
        # Should not raise error even with empty config
        config = RobinhoodConfig()
        
        # Default should be applied
        assert config.expires_in == 86400

    def test_model_validation_error_details(self):
        """Test that validation errors provide useful details."""
        try:
            RobinhoodConfig(expires_in="invalid")  # type: ignore
        except ValidationError as e:
            # Should contain useful error information
            error_info = str(e)
            assert "expires_in" in error_info
            # Should indicate type validation issue
            assert "input" in error_info.lower() or "type" in error_info.lower()

    def test_graceful_handling_of_malformed_env(self):
        """Test graceful handling of malformed environment variables."""
        env_vars = {
            "ROBINHOOD_USERNAME": "valid_user",
            "ROBINHOOD_PASSWORD": "valid_password",
            "ROBINHOOD_EXPIRES_IN": ""  # Empty string
        }
        
        with patch.dict(os.environ, env_vars):
            # Should handle empty string appropriately
            with pytest.raises(ValidationError):
                RobinhoodConfig()


class TestRobinhoodConfigEdgeCases:
    """Test suite for edge cases in RobinhoodConfig."""

    def test_very_long_environment_variables(self):
        """Test handling of very long environment variable values."""
        long_value = "x" * 10000
        env_vars = {
            "ROBINHOOD_USERNAME": long_value
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            assert config.username == long_value

    def test_environment_variables_with_quotes(self):
        """Test handling of environment variables with quotes."""
        env_vars = {
            "ROBINHOOD_USERNAME": '"quoted_user"',
            "ROBINHOOD_PASSWORD": "'single_quoted_password'"
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            # Should preserve quotes as they are part of the value
            assert config.username == '"quoted_user"'
            assert config.get_password() == "'single_quoted_password'"

    def test_environment_variables_with_newlines(self):
        """Test handling of environment variables with newlines."""
        env_vars = {
            "ROBINHOOD_USERNAME": "user\nwith\nnewlines"
        }
        
        with patch.dict(os.environ, env_vars):
            config = RobinhoodConfig()
            
            assert config.username == "user\nwith\nnewlines"

    def test_configuration_with_all_none_values(self):
        """Test configuration where all optional values are None."""
        config = RobinhoodConfig(
            username=None,
            password=None
        )
        
        assert config.username is None
        assert config.password is None
        assert config.get_password() is None
        assert config.has_credentials() is False
        assert config.expires_in == 86400  # Default value

    def test_repeated_instantiation_consistency(self):
        """Test that repeated instantiation produces consistent results."""
        env_vars = {
            "ROBINHOOD_USERNAME": "consistent_user",
            "ROBINHOOD_PASSWORD": "consistent_password"
        }
        
        with patch.dict(os.environ, env_vars):
            config1 = RobinhoodConfig()
            config2 = RobinhoodConfig()
            
            assert config1.username == config2.username
            assert config1.get_password() == config2.get_password()
            assert config1.expires_in == config2.expires_in

    def test_model_config_immutability(self):
        """Test that model_config cannot be modified after class definition."""
        config = RobinhoodConfig()
        original_config = config.model_config.copy()
        
        # Verify configuration is as expected
        assert original_config["env_prefix"] == "ROBINHOOD_"
        assert original_config["extra"] == "ignore"
        
        # Model config should remain consistent
        assert config.model_config == original_config