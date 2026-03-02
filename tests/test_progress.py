"""Tests for the progress reporting module."""

from src.cli.progress import (
    FileProgress,
    ProgressReporter,
    ProgressSummary,
    _format_duration,
    _truncate_path,
)


class TestFileProgress:
    """Tests for the FileProgress dataclass."""

    def test_defaults(self):
        """Test default values."""
        fp = FileProgress(file_path="test.py")
        assert fp.file_path == "test.py"
        assert fp.input_tokens == 0
        assert fp.output_tokens == 0
        assert fp.duration_seconds == 0.0
        assert fp.items_generated == 0

    def test_custom_values(self):
        """Test custom initialization."""
        fp = FileProgress(
            file_path="src/main.py",
            input_tokens=500,
            output_tokens=200,
            duration_seconds=1.5,
            items_generated=3,
        )
        assert fp.input_tokens == 500
        assert fp.items_generated == 3


class TestProgressSummary:
    """Tests for the ProgressSummary dataclass."""

    def test_defaults(self):
        """Test default values."""
        summary = ProgressSummary()
        assert summary.total_files == 0
        assert summary.total_tokens == 0
        assert summary.avg_time_per_file == 0.0

    def test_avg_time_per_file(self):
        """Test average time calculation."""
        summary = ProgressSummary(total_files=4, total_duration_seconds=8.0)
        assert summary.avg_time_per_file == 2.0

    def test_total_tokens(self):
        """Test total token calculation."""
        summary = ProgressSummary(total_input_tokens=1000, total_output_tokens=500)
        assert summary.total_tokens == 1500


class TestProgressReporter:
    """Tests for the ProgressReporter class."""

    def test_init(self):
        """Test reporter initialization."""
        reporter = ProgressReporter(total_files=10)
        assert reporter.total_files == 10
        assert reporter.verbose is False

    def test_start(self):
        """Test start records time."""
        reporter = ProgressReporter(total_files=5)
        reporter.start()
        assert reporter._start_time is not None
        assert reporter._start_time > 0

    def test_update_tracks_progress(self):
        """Test that update increments counters."""
        reporter = ProgressReporter(total_files=3)
        reporter.start()

        progress = FileProgress(
            file_path="test.py",
            input_tokens=100,
            output_tokens=50,
            duration_seconds=1.0,
            items_generated=2,
        )
        reporter.update(progress)

        assert reporter._processed == 1
        assert reporter._summary.total_input_tokens == 100
        assert reporter._summary.total_output_tokens == 50
        assert reporter._summary.total_items_generated == 2

    def test_update_multiple_files(self):
        """Test tracking multiple file updates."""
        reporter = ProgressReporter(total_files=2)
        reporter.start()

        reporter.update(
            FileProgress("a.py", input_tokens=100, output_tokens=50, items_generated=1)
        )
        reporter.update(
            FileProgress("b.py", input_tokens=200, output_tokens=100, items_generated=3)
        )

        assert reporter._processed == 2
        assert reporter._summary.total_input_tokens == 300
        assert reporter._summary.total_output_tokens == 150
        assert reporter._summary.total_items_generated == 4

    def test_update_verbose(self):
        """Test verbose output shows per-file progress."""
        reporter = ProgressReporter(total_files=2, verbose=True)
        reporter.start()

        reporter.update(
            FileProgress(
                "test.py",
                input_tokens=100,
                output_tokens=50,
                duration_seconds=0.5,
                items_generated=2,
            )
        )
        assert reporter._processed == 1

    def test_finish_returns_summary(self):
        """Test finish returns a complete summary."""
        reporter = ProgressReporter(total_files=1)
        reporter.start()

        reporter.update(
            FileProgress(
                "test.py",
                input_tokens=1000,
                output_tokens=500,
                duration_seconds=2.0,
                items_generated=5,
            )
        )

        summary = reporter.finish()
        assert isinstance(summary, ProgressSummary)
        assert summary.total_files == 1
        assert summary.total_input_tokens == 1000
        assert summary.total_output_tokens == 500
        assert summary.total_items_generated == 5

    def test_finish_without_start(self):
        """Test finish works even without explicit start."""
        reporter = ProgressReporter(total_files=0)
        summary = reporter.finish()
        assert summary.total_files == 0

    def test_estimate_remaining(self):
        """Test remaining time estimation."""
        reporter = ProgressReporter(total_files=4)
        reporter._processed = 2
        reporter._summary.total_duration_seconds = 4.0
        # avg = 2s/file, remaining = 2 files -> 4s
        assert reporter._estimate_remaining() == 4.0

    def test_estimate_remaining_no_progress(self):
        """Test remaining estimation with zero progress."""
        reporter = ProgressReporter(total_files=4)
        assert reporter._estimate_remaining() == 0.0

    def test_estimate_cost(self):
        """Test cost estimation."""
        reporter = ProgressReporter(total_files=1)
        reporter._summary.total_input_tokens = 1_000_000
        reporter._summary.total_output_tokens = 100_000
        cost = reporter._estimate_cost()
        # 1M input * $3/M + 0.1M output * $15/M = $3 + $1.5 = $4.5
        assert abs(cost - 4.5) < 0.01


class TestTruncatePath:
    """Tests for the _truncate_path helper."""

    def test_short_path(self):
        """Test short path is not truncated."""
        assert _truncate_path("src/main.py", max_len=50) == "src/main.py"

    def test_long_path(self):
        """Test long path is truncated with ellipsis."""
        long_path = "a/" * 30 + "file.py"
        result = _truncate_path(long_path, max_len=20)
        assert len(result) == 20
        assert result.startswith("...")

    def test_exact_length(self):
        """Test path at exact max length."""
        path = "x" * 50
        assert _truncate_path(path, max_len=50) == path


class TestFormatDuration:
    """Tests for the _format_duration helper."""

    def test_subsecond(self):
        """Test sub-second formatting."""
        assert _format_duration(0.5) == "0.5s"

    def test_seconds(self):
        """Test seconds formatting."""
        assert _format_duration(30.0) == "30.0s"

    def test_minutes(self):
        """Test minutes formatting."""
        result = _format_duration(90.0)
        assert "1m" in result
        assert "30s" in result

    def test_zero(self):
        """Test zero duration."""
        assert _format_duration(0.0) == "0.0s"
