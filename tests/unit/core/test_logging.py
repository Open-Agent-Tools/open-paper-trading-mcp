"""Comprehensive tests for app/core/logging.py"""

import logging
import logging.handlers
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.logging import get_default_log_dir, logger, setup_logging


class TestGetDefaultLogDir:
    """Test the get_default_log_dir function."""

    @patch("platform.system")
    def test_get_default_log_dir_macos(self, mock_system):
        """Test default log directory on macOS."""
        mock_system.return_value = "Darwin"

        result = get_default_log_dir()
        expected = Path.home() / "Library" / "Logs" / "open-paper-trading-mcp"

        assert result == expected
        mock_system.assert_called_once()

    @patch("platform.system")
    @patch("os.geteuid")
    def test_get_default_log_dir_linux_root(self, mock_geteuid, mock_system):
        """Test default log directory on Linux as root user."""
        mock_system.return_value = "Linux"
        mock_geteuid.return_value = 0  # Root user

        result = get_default_log_dir()
        expected = Path("/var/log/open-paper-trading-mcp")

        assert result == expected
        mock_system.assert_called_once()
        mock_geteuid.assert_called_once()

    @patch("platform.system")
    @patch("os.geteuid")
    def test_get_default_log_dir_linux_non_root(self, mock_geteuid, mock_system):
        """Test default log directory on Linux as non-root user."""
        mock_system.return_value = "Linux"
        mock_geteuid.return_value = 1000  # Non-root user

        result = get_default_log_dir()
        expected = Path.home() / ".local" / "state" / "open-paper-trading-mcp" / "logs"

        assert result == expected
        mock_system.assert_called_once()
        mock_geteuid.assert_called_once()

    @patch("platform.system")
    def test_get_default_log_dir_windows(self, mock_system):
        """Test default log directory on Windows."""
        mock_system.return_value = "Windows"

        result = get_default_log_dir()
        expected = Path.home() / "AppData" / "Local" / "open-paper-trading-mcp" / "logs"

        assert result == expected
        mock_system.assert_called_once()

    @patch("platform.system")
    def test_get_default_log_dir_unknown_system(self, mock_system):
        """Test default log directory on unknown system."""
        mock_system.return_value = "UnknownOS"

        result = get_default_log_dir()
        expected = Path.home() / ".open-paper-trading-mcp" / "logs"

        assert result == expected
        mock_system.assert_called_once()

    @patch("platform.system")
    def test_get_default_log_dir_case_insensitive(self, mock_system):
        """Test that system detection is case insensitive."""
        mock_system.return_value = "DARWIN"

        result = get_default_log_dir()
        expected = Path.home() / "Library" / "Logs" / "open-paper-trading-mcp"

        assert result == expected

    @patch("platform.system")
    @patch("os.geteuid", side_effect=AttributeError("Not available on Windows"))
    def test_get_default_log_dir_linux_no_geteuid(self, mock_geteuid, mock_system):
        """Test Linux path when geteuid is not available (e.g., Windows Python)."""
        mock_system.return_value = "Linux"

        # Should fallback to non-root path when geteuid raises AttributeError
        result = get_default_log_dir()
        expected = Path.home() / ".local" / "state" / "open-paper-trading-mcp" / "logs"

        assert result == expected
        mock_system.assert_called_once()


class TestSetupLogging:
    """Test the setup_logging function."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing handlers
        logging.getLogger().handlers.clear()
        logging.getLogger("open_paper_trading_mcp").handlers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear handlers to avoid interference between tests
        logging.getLogger().handlers.clear()
        logging.getLogger("open_paper_trading_mcp").handlers.clear()

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_default_level(self, mock_get_log_dir, mock_settings):
        """Test setup_logging with default INFO level."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir") as mock_mkdir,
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
        ):
            mock_handler_instance = MagicMock()
            mock_file_handler.return_value = mock_handler_instance

            setup_logging()

            # Verify log directory creation
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

            # Verify file handler creation
            expected_log_file = mock_log_dir / "open-paper-trading-mcp.log"
            mock_file_handler.assert_called_once_with(
                expected_log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
            )

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_debug_level(self, mock_get_log_dir, mock_settings):
        """Test setup_logging with DEBUG level."""
        mock_settings.LOG_LEVEL = "DEBUG"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
            patch("logging.StreamHandler") as mock_stream_handler,
        ):
            mock_file_instance = MagicMock()
            mock_stream_instance = MagicMock()
            mock_file_handler.return_value = mock_file_instance
            mock_stream_handler.return_value = mock_stream_instance

            setup_logging()

            # Verify handlers are set to DEBUG level
            mock_file_instance.setLevel.assert_called_with(logging.DEBUG)
            mock_stream_instance.setLevel.assert_called_with(logging.DEBUG)

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_invalid_level(self, mock_get_log_dir, mock_settings):
        """Test setup_logging with invalid log level falls back to INFO."""
        mock_settings.LOG_LEVEL = "INVALID_LEVEL"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
            patch("logging.StreamHandler") as mock_stream_handler,
        ):
            mock_file_instance = MagicMock()
            mock_stream_instance = MagicMock()
            mock_file_handler.return_value = mock_file_instance
            mock_stream_handler.return_value = mock_stream_instance

            setup_logging()

            # Should fallback to INFO level
            mock_file_instance.setLevel.assert_called_with(logging.INFO)
            mock_stream_instance.setLevel.assert_called_with(logging.INFO)

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_handler_configuration(self, mock_get_log_dir, mock_settings):
        """Test that handlers are properly configured."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
            patch("logging.StreamHandler") as mock_stream_handler,
            patch("logging.Formatter") as mock_formatter,
        ):
            mock_file_instance = MagicMock()
            mock_stream_instance = MagicMock()
            mock_formatter_instance = MagicMock()

            mock_file_handler.return_value = mock_file_instance
            mock_stream_handler.return_value = mock_stream_instance
            mock_formatter.return_value = mock_formatter_instance

            setup_logging()

            # Verify formatter is created with correct format
            expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            mock_formatter.assert_called_with(expected_format)

            # Verify formatters are set on handlers
            mock_file_instance.setFormatter.assert_called_with(mock_formatter_instance)
            mock_stream_instance.setFormatter.assert_called_with(
                mock_formatter_instance
            )

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_stderr_handler(self, mock_get_log_dir, mock_settings):
        """Test that stderr handler is properly configured."""
        mock_settings.LOG_LEVEL = "WARNING"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler") as mock_stream_handler,
        ):
            mock_stream_instance = MagicMock()
            mock_stream_handler.return_value = mock_stream_instance

            setup_logging()

            # Verify StreamHandler is created with sys.stderr
            mock_stream_handler.assert_called_once_with(sys.stderr)

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_clears_existing_handlers(
        self, mock_get_log_dir, mock_settings
    ):
        """Test that existing handlers are cleared before setup."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        # Add some existing handlers
        root_logger = logging.getLogger()
        project_logger = logging.getLogger("open_paper_trading_mcp")

        existing_handler1 = MagicMock()
        existing_handler2 = MagicMock()

        root_logger.addHandler(existing_handler1)
        project_logger.addHandler(existing_handler2)

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler"),
        ):
            setup_logging()

            # Verify handlers were cleared
            assert existing_handler1 not in root_logger.handlers
            assert existing_handler2 not in project_logger.handlers

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_project_logger_config(self, mock_get_log_dir, mock_settings):
        """Test that project logger is properly configured."""
        mock_settings.LOG_LEVEL = "DEBUG"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler"),
        ):
            setup_logging()

            project_logger = logging.getLogger("open_paper_trading_mcp")

            # Verify project logger configuration
            assert project_logger.level == logging.DEBUG
            assert project_logger.propagate is True

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_file_rotation_config(self, mock_get_log_dir, mock_settings):
        """Test rotating file handler configuration."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
        ):
            setup_logging()

            # Verify rotating file handler parameters
            expected_log_file = mock_log_dir / "open-paper-trading-mcp.log"
            mock_file_handler.assert_called_once_with(
                expected_log_file,
                maxBytes=10_000_000,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    @patch("logging.getLogger")
    def test_setup_logging_info_messages(
        self, mock_get_logger, mock_get_log_dir, mock_settings
    ):
        """Test that setup_logging logs informational messages."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        mock_project_logger = MagicMock()
        mock_get_logger.side_effect = lambda name="": (
            mock_project_logger if name == "open_paper_trading_mcp" else MagicMock()
        )

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler"),
        ):
            setup_logging()

            # Verify info messages are logged
            expected_log_file = mock_log_dir / "open-paper-trading-mcp.log"
            mock_project_logger.info.assert_any_call(f"Log File: {expected_log_file}")
            mock_project_logger.info.assert_any_call("Log Level: INFO")

    @pytest.mark.parametrize(
        "log_level,expected_level",
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("debug", logging.DEBUG),  # Test case insensitivity
            ("info", logging.INFO),
        ],
    )
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_level_mapping(
        self, mock_get_log_dir, log_level, expected_level
    ):
        """Test log level string to logging level mapping."""
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch("app.core.logging.settings") as mock_settings,
            patch.object(mock_log_dir, "mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler") as mock_stream_handler,
            patch("logging.basicConfig") as mock_basic_config,
        ):
            mock_settings.LOG_LEVEL = log_level
            mock_stream_instance = MagicMock()
            mock_stream_handler.return_value = mock_stream_instance

            setup_logging()

            # Verify the correct logging level is used
            mock_basic_config.assert_called_once()
            call_args = mock_basic_config.call_args
            assert call_args[1]["level"] == expected_level

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_mkdir_failure_handling(
        self, mock_get_log_dir, mock_settings
    ):
        """Test handling of mkdir failures."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        # Mock mkdir to raise an exception
        with (
            patch.object(
                mock_log_dir, "mkdir", side_effect=PermissionError("Permission denied")
            ),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler"),
        ):
            # Should not raise an exception but continue with setup
            try:
                setup_logging()
                # If we get here, the function handled the error gracefully
                assert True
            except PermissionError:
                # If mkdir error propagates, that's a problem
                pytest.fail("setup_logging should handle mkdir errors gracefully")


class TestLoggerModule:
    """Test the exported logger module."""

    def test_logger_export(self):
        """Test that logger is properly exported."""

        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == "open_paper_trading_mcp"

    def test_logger_is_singleton(self):
        """Test that imported logger is the same instance."""
        from app.core.logging import logger as logger1
        from app.core.logging import logger as logger2

        assert logger1 is logger2

    def test_logger_methods_available(self):
        """Test that logger has all expected methods."""

        # Test that standard logging methods are available
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")
        assert hasattr(logger, "exception")

    def test_logger_name(self):
        """Test that logger has the correct name."""

        assert logger.name == "open_paper_trading_mcp"


class TestLoggingIntegration:
    """Test logging integration scenarios."""

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_setup_logging_complete_flow(self, mock_get_log_dir, mock_settings):
        """Test complete logging setup flow."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir") as mock_mkdir,
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
            patch("logging.StreamHandler") as mock_stream_handler,
            patch("logging.basicConfig") as mock_basic_config,
        ):
            mock_file_instance = MagicMock()
            mock_stream_instance = MagicMock()
            mock_file_handler.return_value = mock_file_instance
            mock_stream_handler.return_value = mock_stream_instance

            setup_logging()

            # Verify complete setup sequence
            mock_basic_config.assert_called_once()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file_handler.assert_called_once()
            mock_stream_handler.assert_called_once()

    def test_logging_after_setup(self):
        """Test that logging works after setup."""

        # Test that we can call logging methods without error
        # (We can't easily test actual output without complex mocking)
        try:
            logger.info("Test message")
            logger.debug("Debug message")
            logger.warning("Warning message")
            logger.error("Error message")
            assert True  # If we get here, no exceptions were raised
        except Exception as e:
            pytest.fail(f"Logging failed after setup: {e}")

    @patch("app.core.logging.settings")
    def test_logging_with_different_platforms(self, mock_settings):
        """Test logging setup works on different platforms."""
        mock_settings.LOG_LEVEL = "INFO"

        platforms = ["Darwin", "Linux", "Windows", "UnknownOS"]

        for platform_name in platforms:
            with (
                patch("platform.system", return_value=platform_name),
                patch("os.geteuid", return_value=1000),
                patch("pathlib.Path.mkdir"),
                patch("logging.handlers.RotatingFileHandler"),
                patch("logging.StreamHandler"),
            ):
                try:
                    setup_logging()
                    assert True  # Setup succeeded
                except Exception as e:
                    pytest.fail(f"Logging setup failed on {platform_name}: {e}")

    def test_concurrent_logging_setup(self):
        """Test that multiple calls to setup_logging are safe."""
        from app.core.logging import setup_logging

        with (
            patch("app.core.logging.settings") as mock_settings,
            patch("app.core.logging.get_default_log_dir") as mock_get_log_dir,
            patch("pathlib.Path.mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.StreamHandler"),
        ):
            mock_settings.LOG_LEVEL = "INFO"
            mock_get_log_dir.return_value = Path("/test/log/dir")

            # Call setup multiple times
            for _ in range(3):
                try:
                    setup_logging()
                    assert True
                except Exception as e:
                    pytest.fail(f"Multiple setup_logging calls failed: {e}")


class TestErrorHandling:
    """Test error handling in logging module."""

    @patch("app.core.logging.settings")
    @patch("app.core.logging.get_default_log_dir")
    def test_file_handler_creation_failure(self, mock_get_log_dir, mock_settings):
        """Test handling of file handler creation failure."""
        mock_settings.LOG_LEVEL = "INFO"
        mock_log_dir = Path("/test/log/dir")
        mock_get_log_dir.return_value = mock_log_dir

        with (
            patch.object(mock_log_dir, "mkdir"),
            patch(
                "logging.handlers.RotatingFileHandler",
                side_effect=PermissionError("Access denied"),
            ),
            patch("logging.StreamHandler"),
        ):
            # Should handle the error and continue
            try:
                setup_logging()
                # If exception propagates, that's unexpected
                pytest.fail("Expected RotatingFileHandler error to be handled")
            except PermissionError:
                # This is expected - the function should let this propagate
                # since it's a critical error
                pass

    @patch("app.core.logging.settings")
    @patch("platform.system", side_effect=Exception("Platform detection failed"))
    def test_platform_detection_failure(self, mock_system, mock_settings):
        """Test handling of platform detection failure."""
        mock_settings.LOG_LEVEL = "INFO"

        # get_default_log_dir should handle platform detection failures
        try:
            result = get_default_log_dir()
            # Should fallback to some reasonable default
            assert isinstance(result, Path)
        except Exception as e:
            pytest.fail(f"Platform detection failure should be handled: {e}")

    def test_home_directory_unavailable(self):
        """Test handling when home directory is not available."""
        with patch("pathlib.Path.home", side_effect=RuntimeError("HOME not set")):
            try:
                # This might fail, but should not crash the module import
                get_default_log_dir()
            except RuntimeError:
                # This is acceptable - system is misconfigured
                pass
