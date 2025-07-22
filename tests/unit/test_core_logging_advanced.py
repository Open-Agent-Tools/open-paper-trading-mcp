"""Advanced comprehensive tests for app.core.logging module.

Tests logging setup, configuration patterns, structured logging,
log levels, file handling, and logging infrastructure used in the platform.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.logging import get_default_log_dir, setup_logging


class TestDefaultLogDirectoryResolution:
    """Test default log directory resolution across different platforms."""

    @patch("platform.system")
    def test_macos_log_directory(self, mock_platform):
        """Test macOS log directory resolution."""
        mock_platform.return_value = "Darwin"

        expected_path = Path.home() / "Library" / "Logs" / "open-paper-trading-mcp"
        result = get_default_log_dir()

        assert result == expected_path
        mock_platform.assert_called_once()

    @patch("platform.system")
    @patch("os.geteuid")
    def test_linux_root_log_directory(self, mock_geteuid, mock_platform):
        """Test Linux log directory for root user."""
        mock_platform.return_value = "Linux"
        mock_geteuid.return_value = 0  # root user

        expected_path = Path("/var/log/open-paper-trading-mcp")
        result = get_default_log_dir()

        assert result == expected_path
        mock_platform.assert_called_once()
        mock_geteuid.assert_called_once()

    @patch("platform.system")
    @patch("os.geteuid")
    def test_linux_non_root_log_directory(self, mock_geteuid, mock_platform):
        """Test Linux log directory for non-root user."""
        mock_platform.return_value = "Linux"
        mock_geteuid.return_value = 1000  # non-root user

        expected_path = (
            Path.home() / ".local" / "state" / "open-paper-trading-mcp" / "logs"
        )
        result = get_default_log_dir()

        assert result == expected_path
        mock_platform.assert_called_once()
        mock_geteuid.assert_called_once()

    @patch("platform.system")
    def test_windows_log_directory(self, mock_platform):
        """Test Windows log directory resolution."""
        mock_platform.return_value = "Windows"

        expected_path = (
            Path.home() / "AppData" / "Local" / "open-paper-trading-mcp" / "logs"
        )
        result = get_default_log_dir()

        assert result == expected_path
        mock_platform.assert_called_once()

    @patch("platform.system")
    def test_unknown_platform_log_directory(self, mock_platform):
        """Test unknown platform fallback log directory."""
        mock_platform.return_value = "Unknown"

        expected_path = Path.home() / ".open-paper-trading-mcp" / "logs"
        result = get_default_log_dir()

        assert result == expected_path
        mock_platform.assert_called_once()

    def test_log_directory_case_insensitive_platform(self):
        """Test that platform detection is case insensitive."""
        with patch("platform.system", return_value="darwin"):  # lowercase
            result = get_default_log_dir()
            expected_path = Path.home() / "Library" / "Logs" / "open-paper-trading-mcp"
            assert result == expected_path


class TestLoggingSetupConfiguration:
    """Test logging setup and configuration patterns."""

    def test_valid_log_levels(self):
        """Test that all valid log levels are properly configured."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.LOG_LEVEL = level

                with (
                    patch("logging.basicConfig") as mock_basic_config,
                    patch("pathlib.Path.mkdir"),
                    patch("logging.handlers.RotatingFileHandler"),
                    patch("logging.getLogger") as mock_get_logger,
                ):
                    mock_logger = MagicMock()
                    mock_get_logger.return_value = mock_logger

                    setup_logging()

                    # Verify that basicConfig was called with correct level
                    expected_level = getattr(logging, level)
                    call_args = mock_basic_config.call_args
                    assert call_args[1]["level"] == expected_level

    def test_invalid_log_level_fallback(self):
        """Test fallback to INFO level for invalid log levels."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.LOG_LEVEL = "INVALID_LEVEL"

            with (
                patch("logging.basicConfig") as mock_basic_config,
                patch("pathlib.Path.mkdir"),
                patch("logging.handlers.RotatingFileHandler"),
                patch("logging.getLogger") as mock_get_logger,
            ):
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                setup_logging()

                # Should fallback to INFO level
                call_args = mock_basic_config.call_args
                assert call_args[1]["level"] == logging.INFO

    def test_case_insensitive_log_level(self):
        """Test that log level configuration is case insensitive."""
        test_levels = ["debug", "Debug", "DEBUG", "info", "Info", "INFO"]

        for level in test_levels:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.LOG_LEVEL = level

                with (
                    patch("logging.basicConfig") as mock_basic_config,
                    patch("pathlib.Path.mkdir"),
                    patch("logging.handlers.RotatingFileHandler"),
                    patch("logging.getLogger") as mock_get_logger,
                ):
                    mock_logger = MagicMock()
                    mock_get_logger.return_value = mock_logger

                    setup_logging()

                    # Should convert to uppercase and use appropriate level
                    expected_level = getattr(logging, level.upper())
                    call_args = mock_basic_config.call_args
                    assert call_args[1]["level"] == expected_level


class TestLoggingHandlerConfiguration:
    """Test logging handler setup and configuration."""

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_file_handler_configuration(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test file handler configuration parameters."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_handler_instance = MagicMock()
        mock_rotating_handler.return_value = mock_handler_instance

        setup_logging()

        # Verify RotatingFileHandler was called with correct parameters
        mock_rotating_handler.assert_called_once()
        call_args = mock_rotating_handler.call_args

        # Check maxBytes parameter
        assert call_args[1]["maxBytes"] == 10_000_000
        # Check backupCount parameter
        assert call_args[1]["backupCount"] == 5
        # Check encoding parameter
        assert call_args[1]["encoding"] == "utf-8"

    @patch("logging.getLogger")
    @patch("logging.StreamHandler")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_stderr_handler_configuration(
        self,
        mock_settings,
        mock_mkdir,
        mock_rotating_handler,
        mock_stream_handler,
        mock_get_logger,
    ):
        """Test stderr handler configuration."""
        mock_settings.LOG_LEVEL = "DEBUG"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_stderr_handler = MagicMock()
        mock_stream_handler.return_value = mock_stderr_handler

        setup_logging()

        # Verify StreamHandler was called with sys.stderr
        mock_stream_handler.assert_called_once_with(sys.stderr)

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_handler_level_setting(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test that handlers are set to the correct log level."""
        mock_settings.LOG_LEVEL = "WARNING"

        mock_root_logger = MagicMock()
        mock_project_logger = MagicMock()

        def get_logger_side_effect(name=""):
            if name == "open_paper_trading_mcp":
                return mock_project_logger
            return mock_root_logger

        mock_get_logger.side_effect = get_logger_side_effect

        mock_file_handler = MagicMock()
        mock_rotating_handler.return_value = mock_file_handler

        with patch("logging.StreamHandler") as mock_stream_handler:
            mock_stderr_handler = MagicMock()
            mock_stream_handler.return_value = mock_stderr_handler

            setup_logging()

            # Verify handlers are set to WARNING level
            mock_file_handler.setLevel.assert_called_with(logging.WARNING)
            mock_stderr_handler.setLevel.assert_called_with(logging.WARNING)

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_formatter_configuration(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test logging formatter configuration."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_file_handler = MagicMock()
        mock_rotating_handler.return_value = mock_file_handler

        with (
            patch("logging.StreamHandler") as mock_stream_handler,
            patch("logging.Formatter") as mock_formatter,
        ):
            mock_stderr_handler = MagicMock()
            mock_stream_handler.return_value = mock_stderr_handler

            mock_formatter_instance = MagicMock()
            mock_formatter.return_value = mock_formatter_instance

            setup_logging()

            # Verify Formatter was called with correct format string
            expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            mock_formatter.assert_called_with(expected_format)

            # Verify formatter was set on handlers
            mock_file_handler.setFormatter.assert_called_with(mock_formatter_instance)
            mock_stderr_handler.setFormatter.assert_called_with(mock_formatter_instance)


class TestLoggerCleanupAndInitialization:
    """Test logger cleanup and initialization patterns."""

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_existing_handlers_removed(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test that existing handlers are properly removed during setup."""
        mock_settings.LOG_LEVEL = "INFO"

        # Create mock handlers to simulate existing handlers
        mock_existing_handler1 = MagicMock()
        mock_existing_handler2 = MagicMock()

        mock_root_logger = MagicMock()
        mock_project_logger = MagicMock()

        # Set up existing handlers
        mock_root_logger.handlers = [mock_existing_handler1, mock_existing_handler2]
        mock_project_logger.handlers = []

        def get_logger_side_effect(name=""):
            if name == "open_paper_trading_mcp":
                return mock_project_logger
            return mock_root_logger

        mock_get_logger.side_effect = get_logger_side_effect

        with patch("logging.StreamHandler"):
            setup_logging()

            # Verify existing handlers were removed
            mock_root_logger.removeHandler.assert_any_call(mock_existing_handler1)
            mock_root_logger.removeHandler.assert_any_call(mock_existing_handler2)

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_project_logger_configuration(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test project logger specific configuration."""
        mock_settings.LOG_LEVEL = "DEBUG"

        mock_root_logger = MagicMock()
        mock_project_logger = MagicMock()

        def get_logger_side_effect(name=""):
            if name == "open_paper_trading_mcp":
                return mock_project_logger
            return mock_root_logger

        mock_get_logger.side_effect = get_logger_side_effect

        with patch("logging.StreamHandler"):
            setup_logging()

            # Verify project logger configuration
            mock_project_logger.setLevel.assert_called_with(logging.DEBUG)
            assert mock_project_logger.propagate is True


class TestLogDirectoryCreation:
    """Test log directory creation patterns."""

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("app.core.config.settings")
    def test_log_directory_created(
        self, mock_settings, mock_rotating_handler, mock_get_logger
    ):
        """Test that log directory is created with correct permissions."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        with patch("pathlib.Path.mkdir") as mock_mkdir, patch("logging.StreamHandler"):
            setup_logging()

            # Verify mkdir was called with correct parameters
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_log_file_path_resolution(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test log file path resolution."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        with (
            patch("logging.StreamHandler"),
            patch("app.core.logging.get_default_log_dir") as mock_get_log_dir,
        ):
            mock_log_dir = MagicMock()
            mock_log_file = MagicMock()
            mock_log_dir.__truediv__.return_value = mock_log_file
            mock_get_log_dir.return_value = mock_log_dir

            setup_logging()

            # Verify log directory path was used
            mock_get_log_dir.assert_called_once()
            mock_log_dir.__truediv__.assert_called_once_with(
                "open-paper-trading-mcp.log"
            )

            # Verify RotatingFileHandler was called with the log file path
            mock_rotating_handler.assert_called_once()
            call_args = mock_rotating_handler.call_args
            assert call_args[0][0] == mock_log_file


class TestLoggingIntegration:
    """Test logging integration patterns and functionality."""

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_log_messages_during_setup(
        self, mock_settings, mock_mkdir, mock_rotating_handler, mock_get_logger
    ):
        """Test that setup logging produces appropriate log messages."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_root_logger = MagicMock()
        mock_project_logger = MagicMock()

        def get_logger_side_effect(name=""):
            if name == "open_paper_trading_mcp":
                return mock_project_logger
            return mock_root_logger

        mock_get_logger.side_effect = get_logger_side_effect

        with (
            patch("logging.StreamHandler"),
            patch("app.core.logging.get_default_log_dir") as mock_get_log_dir,
        ):
            mock_log_dir = Path("/test/log/dir")
            mock_get_log_dir.return_value = mock_log_dir

            setup_logging()

            # Verify info messages were logged
            assert mock_project_logger.info.call_count >= 2

            # Check that log file and log level messages were logged
            calls = [call.args[0] for call in mock_project_logger.info.call_args_list]
            assert any("Log File:" in call for call in calls)
            assert any("Log Level:" in call for call in calls)

    def test_module_logger_export(self):
        """Test that module logger is properly exported."""
        from app.core.logging import logger

        assert logger.name == "open_paper_trading_mcp"
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "critical")

    def test_logger_usage_patterns(self):
        """Test common logger usage patterns."""
        from app.core.logging import logger

        # Test that logger methods are callable without errors
        try:
            logger.info("Test info message")
            logger.debug("Test debug message")
            logger.warning("Test warning message")
            logger.error("Test error message")
            logger.critical("Test critical message")
        except Exception as e:
            pytest.fail(f"Logger methods should not raise exceptions: {e}")


class TestLoggingErrorHandling:
    """Test logging setup error handling and edge cases."""

    @patch("logging.getLogger")
    @patch("pathlib.Path.mkdir")
    @patch("app.core.config.settings")
    def test_handler_creation_failure_handling(
        self, mock_settings, mock_mkdir, mock_get_logger
    ):
        """Test handling of handler creation failures."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Mock RotatingFileHandler to raise an exception
        with (
            patch(
                "logging.handlers.RotatingFileHandler",
                side_effect=OSError("Permission denied"),
            ),
            patch("logging.StreamHandler") as mock_stream_handler,
        ):
            mock_stderr_handler = MagicMock()
            mock_stream_handler.return_value = mock_stderr_handler

            # setup_logging should not raise an exception even if file handler fails
            try:
                setup_logging()
            except OSError:
                pytest.fail(
                    "setup_logging should handle file handler creation failures gracefully"
                )

    @patch("logging.getLogger")
    @patch("logging.handlers.RotatingFileHandler")
    @patch("app.core.config.settings")
    def test_directory_creation_failure_handling(
        self, mock_settings, mock_rotating_handler, mock_get_logger
    ):
        """Test handling of directory creation failures."""
        mock_settings.LOG_LEVEL = "INFO"

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Mock mkdir to raise an exception
        with (
            patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")),
            patch("logging.StreamHandler"),
        ):
            # setup_logging should handle directory creation failures
            try:
                setup_logging()
            except OSError:
                pytest.fail(
                    "setup_logging should handle directory creation failures gracefully"
                )


class TestLoggingConfigurationInheritance:
    """Test logging configuration inheritance and propagation."""

    def test_settings_import_in_logging_module(self):
        """Test that settings are properly imported and accessible."""
        from app.core.config import Settings
        from app.core.logging import settings

        assert isinstance(settings, Settings)
        assert hasattr(settings, "LOG_LEVEL")

    @patch("app.core.config.settings")
    def test_settings_dependency_in_setup(self, mock_settings):
        """Test that setup_logging properly uses settings dependency."""
        mock_settings.LOG_LEVEL = "ERROR"

        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("pathlib.Path.mkdir"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify that settings.LOG_LEVEL was accessed
            assert mock_settings.LOG_LEVEL == "ERROR"

            # Verify basicConfig was called with ERROR level
            call_args = mock_basic_config.call_args
            assert call_args[1]["level"] == logging.ERROR


class TestLoggingStructuredPatterns:
    """Test structured logging patterns and best practices."""

    def test_logging_format_structure(self):
        """Test that logging format follows structured patterns."""
        expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        with (
            patch("logging.Formatter") as mock_formatter,
            patch("logging.getLogger"),
            patch("logging.handlers.RotatingFileHandler"),
            patch("pathlib.Path.mkdir"),
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.LOG_LEVEL = "INFO"

            setup_logging()

            # Verify structured format is used
            mock_formatter.assert_called_with(expected_format)

    def test_logger_naming_conventions(self):
        """Test logger naming conventions."""
        from app.core.logging import logger

        # Project logger should use consistent naming
        assert logger.name == "open_paper_trading_mcp"

        # Naming should be hierarchical and descriptive
        assert "paper" in logger.name
        assert "trading" in logger.name
        assert "mcp" in logger.name

    def test_log_level_hierarchy(self):
        """Test log level hierarchy understanding."""
        levels = [
            ("DEBUG", logging.DEBUG, 10),
            ("INFO", logging.INFO, 20),
            ("WARNING", logging.WARNING, 30),
            ("ERROR", logging.ERROR, 40),
            ("CRITICAL", logging.CRITICAL, 50),
        ]

        for level_name, level_constant, level_value in levels:
            assert level_constant == level_value
            assert logging.getLevelName(level_constant) == level_name
