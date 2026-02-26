"""Structured logging setup for the code documentation generator.

Provides a centralized logging configuration with console and optional
file handlers. Log level and format are driven by config.yaml.
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure the root logger with console and optional file output.

    Sets up structured logging for the entire application. Clears any
    existing handlers to prevent duplicate log entries across calls.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Format string for log messages.
        log_file: Optional file path for log output. If None, logs only
            to the console.

    Returns:
        The configured root logger instance.
    """
    root_logger = logging.getLogger("code_doc_gen")
    root_logger.handlers.clear()

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger.debug("Logging initialized at level %s", level)
    return root_logger
