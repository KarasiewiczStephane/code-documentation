"""Tests for the CLI commands using Click's CliRunner."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli.commands import doc


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample Python project for CLI testing."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    (src / "main.py").write_text(
        textwrap.dedent('''\
            """Main module."""

            def main():
                """Entry point."""
                pass

            def undocumented():
                x = 1
                if x > 0:
                    return True
                return False
        ''')
    )
    (tmp_path / "requirements.txt").write_text("click>=8.0\n")
    return tmp_path


class TestDocGroup:
    """Tests for the main doc command group."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["--help"])
        assert result.exit_code == 0
        assert "Code Documentation Generator" in result.output

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestGenerateCommand:
    """Tests for the 'generate' command."""

    def test_generate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate full documentation" in result.output

    def test_generate_dry_run(self, runner: CliRunner, sample_project: Path) -> None:
        result = runner.invoke(doc, ["generate", str(sample_project), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run complete" in result.output
        assert "Would process" in result.output

    def test_generate_nonexistent_path(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["generate", "/nonexistent/path"])
        assert result.exit_code != 0


class TestReadmeCommand:
    """Tests for the 'readme' command."""

    def test_readme_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["readme", "--help"])
        assert result.exit_code == 0
        assert "Generate a README" in result.output

    @patch("src.cli.commands.LLMClient")
    def test_readme_generation(
        self,
        mock_llm_cls: MagicMock,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        from src.generators.llm_client import GenerationResult, TokenUsage

        mock_client = MagicMock()
        mock_client.generate.return_value = GenerationResult(
            content="# Test README\n\nGenerated.",
            usage=TokenUsage(input_tokens=100, output_tokens=200),
            model="test",
        )
        mock_llm_cls.return_value = mock_client

        output_path = sample_project / "README_TEST.md"
        result = runner.invoke(
            doc,
            ["readme", str(sample_project), "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert output_path.exists()
        assert "README written to" in result.output


class TestDocstringsCommand:
    """Tests for the 'docstrings' command."""

    def test_docstrings_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["docstrings", "--help"])
        assert result.exit_code == 0
        assert "Generate missing docstrings" in result.output

    def test_docstrings_dry_run(self, runner: CliRunner, sample_project: Path) -> None:
        result = runner.invoke(doc, ["docstrings", str(sample_project), "--dry-run"])
        assert result.exit_code == 0
        assert "without docstrings" in result.output


class TestComplexityCommand:
    """Tests for the 'complexity' command."""

    def test_complexity_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["complexity", "--help"])
        assert result.exit_code == 0
        assert "complexity report" in result.output

    def test_complexity_report(self, runner: CliRunner, sample_project: Path) -> None:
        result = runner.invoke(doc, ["complexity", str(sample_project)])
        assert result.exit_code == 0
        assert "functions analyzed" in result.output

    def test_complexity_single_file(
        self, runner: CliRunner, sample_project: Path
    ) -> None:
        result = runner.invoke(
            doc, ["complexity", str(sample_project / "src" / "main.py")]
        )
        assert result.exit_code == 0


class TestEstimateCommand:
    """Tests for the 'estimate' command."""

    def test_estimate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(doc, ["estimate", "--help"])
        assert result.exit_code == 0
        assert "Estimate API cost" in result.output

    def test_estimate_output(self, runner: CliRunner, sample_project: Path) -> None:
        result = runner.invoke(doc, ["estimate", str(sample_project)])
        assert result.exit_code == 0
        assert "Estimated" in result.output
        assert "USD" in result.output
