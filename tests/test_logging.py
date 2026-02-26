"""Tests for structured logging setup."""

import logging
from pathlib import Path

from src.utils.logging import setup_logging


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_returns_logger(self) -> None:
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "code_doc_gen"

    def test_default_level_is_info(self) -> None:
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_custom_level(self) -> None:
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_console_handler_present(self) -> None:
        logger = setup_logging()
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_file_handler_when_path_given(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.log")
        logger = setup_logging(log_file=log_file)
        handler_types = [type(h) for h in logger.handlers]
        assert logging.FileHandler in handler_types

    def test_no_file_handler_by_default(self) -> None:
        logger = setup_logging()
        handler_types = [type(h) for h in logger.handlers]
        assert logging.FileHandler not in handler_types

    def test_clears_existing_handlers(self) -> None:
        logger = setup_logging()
        initial_count = len(logger.handlers)
        logger = setup_logging()
        assert len(logger.handlers) == initial_count

    def test_file_handler_writes(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = setup_logging(level="INFO", log_file=str(log_file))
        logger.info("test message")
        # Flush handlers
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text()
        assert "test message" in content
