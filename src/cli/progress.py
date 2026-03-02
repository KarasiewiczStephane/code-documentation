"""Progress reporting utilities for CLI operations.

Provides a ProgressReporter class that tracks file processing progress,
token usage, estimated costs, and timing information for large codebase
documentation runs.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import click

logger = logging.getLogger(__name__)


@dataclass
class FileProgress:
    """Progress data for a single file processing operation.

    Attributes:
        file_path: Path to the processed file.
        input_tokens: Input tokens used.
        output_tokens: Output tokens used.
        duration_seconds: Time taken to process.
        items_generated: Number of items documented.
    """

    file_path: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    items_generated: int = 0


@dataclass
class ProgressSummary:
    """Summary statistics for a documentation run.

    Attributes:
        total_files: Total number of files processed.
        total_input_tokens: Sum of all input tokens.
        total_output_tokens: Sum of all output tokens.
        total_duration_seconds: Total wall clock time.
        total_items_generated: Total documentation items generated.
        files: Per-file progress records.
    """

    total_files: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_seconds: float = 0.0
    total_items_generated: int = 0
    files: list[FileProgress] = field(default_factory=list)

    @property
    def avg_time_per_file(self) -> float:
        """Average processing time per file in seconds."""
        if self.total_files == 0:
            return 0.0
        return self.total_duration_seconds / self.total_files

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.total_input_tokens + self.total_output_tokens


class ProgressReporter:
    """Reports progress during documentation generation.

    Tracks processing status, token usage, timing, and provides
    a formatted summary table at completion.
    """

    # Pricing per million tokens (approximate)
    _PRICING = {
        "input": 3.0,
        "output": 15.0,
    }

    def __init__(self, total_files: int, verbose: bool = False) -> None:
        """Initialize the progress reporter.

        Args:
            total_files: Total number of files to process.
            verbose: Whether to show detailed per-file progress.
        """
        self.total_files = total_files
        self.verbose = verbose
        self._summary = ProgressSummary()
        self._start_time: Optional[float] = None
        self._processed = 0

    def start(self) -> None:
        """Mark the start of the documentation run."""
        self._start_time = time.monotonic()
        click.echo(f"Processing {self.total_files} files...")

    def update(self, progress: FileProgress) -> None:
        """Record progress for a completed file.

        Args:
            progress: Progress data for the processed file.
        """
        self._processed += 1
        self._summary.files.append(progress)
        self._summary.total_files = self._processed
        self._summary.total_input_tokens += progress.input_tokens
        self._summary.total_output_tokens += progress.output_tokens
        self._summary.total_duration_seconds += progress.duration_seconds
        self._summary.total_items_generated += progress.items_generated

        if self.verbose:
            truncated = _truncate_path(progress.file_path, max_len=50)
            eta = self._estimate_remaining()
            eta_str = f" (ETA: {_format_duration(eta)})" if eta > 0 else ""
            click.echo(
                f"  [{self._processed}/{self.total_files}] "
                f"{truncated} — {progress.items_generated} items, "
                f"{progress.input_tokens + progress.output_tokens} tokens"
                f"{eta_str}"
            )

    def finish(self) -> ProgressSummary:
        """Finalize and print the summary report.

        Returns:
            The completed ProgressSummary with all statistics.
        """
        if self._start_time:
            wall_time = time.monotonic() - self._start_time
        else:
            wall_time = self._summary.total_duration_seconds

        click.echo("")
        click.echo("=" * 60)
        click.echo("Documentation Generation Summary")
        click.echo("=" * 60)
        click.echo(f"  Files processed:     {self._summary.total_files}")
        click.echo(f"  Items generated:     {self._summary.total_items_generated}")
        click.echo(f"  Input tokens:        {self._summary.total_input_tokens:,}")
        click.echo(f"  Output tokens:       {self._summary.total_output_tokens:,}")
        click.echo(f"  Total tokens:        {self._summary.total_tokens:,}")
        click.echo(f"  Estimated cost:      ${self._estimate_cost():.4f} USD")
        click.echo(f"  Wall clock time:     {_format_duration(wall_time)}")
        click.echo(
            f"  Avg time per file:   {_format_duration(self._summary.avg_time_per_file)}"
        )
        click.echo("=" * 60)

        return self._summary

    def _estimate_remaining(self) -> float:
        """Estimate remaining time based on average processing time.

        Returns:
            Estimated seconds remaining.
        """
        if self._processed == 0:
            return 0.0
        avg = self._summary.total_duration_seconds / self._processed
        remaining_files = self.total_files - self._processed
        return avg * remaining_files

    def _estimate_cost(self) -> float:
        """Estimate the API cost based on token usage.

        Returns:
            Estimated cost in USD.
        """
        input_cost = (self._summary.total_input_tokens / 1_000_000) * self._PRICING[
            "input"
        ]
        output_cost = (self._summary.total_output_tokens / 1_000_000) * self._PRICING[
            "output"
        ]
        return input_cost + output_cost


def _truncate_path(path: str, max_len: int = 50) -> str:
    """Truncate a file path for display.

    Args:
        path: File path to truncate.
        max_len: Maximum display length.

    Returns:
        Truncated path string.
    """
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., '1m 23s' or '0.5s').
    """
    if seconds < 1:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"
