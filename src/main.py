"""Entry point for the Code Documentation Generator.

Initializes configuration and logging, then delegates to the CLI.
"""

import logging

from src.utils.config import load_config
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize the application and launch the CLI."""
    config = load_config()
    setup_logging(
        level=config.logging.level,
        log_format=config.logging.format,
        log_file=config.logging.file,
    )
    logger.info("Code Documentation Generator v0.1.0 starting")

    # CLI entrypoint will be wired in Task 12
    logger.info("Ready. Use 'doc --help' for available commands.")


if __name__ == "__main__":
    main()
