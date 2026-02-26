"""Entry point for the Code Documentation Generator.

Delegates to the Click CLI command group.
"""

from src.cli.commands import doc


def main() -> None:
    """Launch the CLI."""
    doc()


if __name__ == "__main__":
    main()
