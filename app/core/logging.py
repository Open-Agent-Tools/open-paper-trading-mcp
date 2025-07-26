"""Logging configuration for Open Paper Trading MCP."""

import logging
import logging.handlers
import os
import platform
import sys
from pathlib import Path

from app.core.config import settings


def get_default_log_dir() -> Path:
    """Get the default log directory based on OS standards"""
    system = platform.system().lower()

    if system == "darwin":  # macOS
        return Path.home() / "Library" / "Logs" / "open-paper-trading-mcp"
    elif system == "linux":
        if os.geteuid() == 0:
            return Path("/var/log/open-paper-trading-mcp")
        else:
            return Path.home() / ".local" / "state" / "open-paper-trading-mcp" / "logs"
    elif system == "windows":
        return Path.home() / "AppData" / "Local" / "open-paper-trading-mcp" / "logs"
    else:
        return Path.home() / ".open-paper-trading-mcp" / "logs"


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = settings.LOG_LEVEL.upper()

    valid_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    effective_level = valid_levels.get(log_level, logging.INFO)

    logging.basicConfig(
        level=effective_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[],
    )

    project_logger = logging.getLogger("open_paper_trading_mcp")
    root_logger = logging.getLogger()

    for logger in [project_logger, root_logger]:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(effective_level)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    log_path = get_default_log_dir()
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "open-paper-trading-mcp.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    project_logger.setLevel(effective_level)
    project_logger.propagate = True

    project_logger.info(f"Log File: {log_file}")
    project_logger.info(f"Log Level: {log_level}")


# Export the logger for use in other modules
logger = logging.getLogger("open_paper_trading_mcp")
