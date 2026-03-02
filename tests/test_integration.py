"""End-to-end integration tests for the documentation generation pipeline.

Tests complete workflows from parsing through output generation,
CLI command execution, and error handling scenarios.
"""

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.analysis.call_graph import CallGraphAnalyzer
from src.analysis.complexity import ComplexityAnalyzer
from src.analysis.graph_viz import DependencyVisualizer
from src.cli.commands import doc
from src.generators.llm_client import GenerationResult, TokenUsage
from src.generators.module_gen import ModuleDocGenerator
from src.output.html import HtmlWriter
from src.output.injector import DocstringInjector
from src.output.markdown import MarkdownWriter
from src.parsers.python_parser import PythonParser
from src.parsers.structure import DependencyGraph


@pytest.fixture
def sample_project(tmp_path):
    """Create a realistic sample Python project for integration tests."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "__init__.py").write_text('"""Sample project package."""\n')
    (src / "main.py").write_text(
        textwrap.dedent('''\
            """Main entry point for the application."""

            from src.utils import helper

            def main():
                """Run the application."""
                result = helper()
                return result

            def process_data(items: list[str]) -> dict:
                count = len(items)
                if count > 10:
                    return {"status": "large", "count": count}
                return {"status": "small", "count": count}

            if __name__ == "__main__":
                main()
        ''')
    )

    utils = src / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text('"""Utility functions."""\n')
    (utils / "helpers.py").write_text(
        textwrap.dedent('''\
            """Helper utilities module."""

            import os
            from pathlib import Path

            def helper() -> str:
                """Return a helper string."""
                return "help"

            def format_output(data: dict, verbose: bool = False) -> str:
                lines = []
                for key, value in data.items():
                    if verbose:
                        lines.append(f"{key}: {value}")
                    else:
                        lines.append(str(value))
                return "\\n".join(lines)

            class DataStore:
                """Simple in-memory data store."""

                def __init__(self):
                    self.data = {}

                def set(self, key: str, value: str) -> None:
                    self.data[key] = value

                def get(self, key: str) -> str:
                    return self.data.get(key, "")
        ''')
    )

    (tmp_path / "requirements.txt").write_text("click>=8.0\njinja2>=3.1\npyyaml>=6.0\n")

    return tmp_path


@pytest.fixture
def mixed_project(tmp_path):
    """Create a mixed Python/JS project."""
    (tmp_path / "app.py").write_text("def main(): pass\n")
    (tmp_path / "index.js").write_text("function init() { console.log('hello'); }\n")
    pkg = {"name": "test", "dependencies": {"express": "^4.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    (tmp_path / "requirements.txt").write_text("flask>=2.0\n")
    return tmp_path


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    client = MagicMock()
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    result = MagicMock()
    result.content = "Generated documentation."
    result.usage = usage
    result.model = "test-model"
    result.stop_reason = "end_turn"

    client.generate.return_value = result
    return client


class TestParseAnalyzeGeneratePipeline:
    """Tests for the full parse -> analyze -> generate -> output pipeline."""

    def test_parse_then_markdown_output(self, sample_project):
        """Test parsing files and writing Markdown output."""
        parser = PythonParser()
        modules = []

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                module = parser.parse_file(str(py_file))
                module.file_path = str(py_file.relative_to(sample_project))
                modules.append(module)
            except SyntaxError:
                pass

        assert len(modules) >= 3

        # Write Markdown
        out_dir = str(sample_project / "docs" / "api")
        writer = MarkdownWriter(output_dir=out_dir)
        for module in modules:
            writer.write_module_doc(module)
        index_path = writer.write_index(modules)

        assert index_path.exists()
        content = index_path.read_text()
        assert "API Reference" in content

    def test_parse_then_html_output(self, sample_project):
        """Test parsing files and writing HTML/MkDocs output."""
        parser = PythonParser()
        modules = []

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                module = parser.parse_file(str(py_file))
                module.file_path = str(py_file.relative_to(sample_project))
                modules.append(module)
            except SyntaxError:
                pass

        out_dir = str(sample_project / "site_docs")
        writer = HtmlWriter(output_dir=out_dir)
        config_path = writer.generate_mkdocs_config("test-project", modules)
        docs_path = writer.write_docs(modules)

        assert config_path.exists()
        assert docs_path.exists()
        assert (docs_path / "index.md").exists()

    def test_parse_analyze_complexity(self, sample_project):
        """Test parsing then running complexity analysis."""
        analyzer = ComplexityAnalyzer()

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                report = analyzer.analyze_file(str(py_file))
                assert report.total_functions >= 0
            except (SyntaxError, FileNotFoundError):
                pass

    def test_parse_build_call_graph(self, sample_project):
        """Test parsing then building a call graph."""
        parser = PythonParser()
        modules = []

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                module = parser.parse_file(str(py_file))
                module.file_path = str(py_file)
                modules.append(module)
            except SyntaxError:
                pass

        cg_analyzer = CallGraphAnalyzer()
        graph = cg_analyzer.analyze_modules(modules)

        assert isinstance(graph, DependencyGraph)
        assert len(graph.call_edges) > 0

    def test_parse_build_dependency_graph(self, sample_project):
        """Test building import dependency graph from parsed modules."""
        parser = PythonParser()
        graph = DependencyGraph()

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                module = parser.parse_file(str(py_file))
                module.file_path = str(py_file.relative_to(sample_project))
                graph.add_module(module)

                for imp in module.imports:
                    graph.add_import_edge(module.file_path, imp.module)
            except SyntaxError:
                pass

        assert len(graph.modules) >= 3
        assert len(graph.import_edges) > 0

    def test_dependency_graph_visualization(self, sample_project):
        """Test full pipeline from parse to Mermaid visualization."""
        parser = PythonParser()
        graph = DependencyGraph()

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                module = parser.parse_file(str(py_file))
                module.file_path = str(py_file.relative_to(sample_project))
                graph.add_module(module)
                for imp in module.imports:
                    graph.add_import_edge(module.file_path, imp.module)
            except SyntaxError:
                pass

        viz = DependencyVisualizer(graph)
        markdown = viz.to_markdown()

        assert "```mermaid" in markdown or "No dependency" in markdown


class TestDocstringInjectionWorkflow:
    """Tests for the docstring injection workflow."""

    def test_inject_into_real_file(self, sample_project):
        """Test injecting docstrings into a real Python file."""
        target = sample_project / "src" / "main.py"
        parser = PythonParser()
        module = parser.parse_file(str(target))

        # Find functions without docstrings
        missing = [f.name for f in module.functions if not f.docstring]

        if missing:
            injector = DocstringInjector(backup=False)
            docstrings = {name: f"Documentation for {name}." for name in missing}
            result = injector.inject(str(target), docstrings)

            assert result.modified or result.injected_count == 0
            # Verify the file is still valid Python
            content = target.read_text()
            compile(content, str(target), "exec")

    def test_dry_run_no_modification(self, sample_project):
        """Test dry-run does not change files."""
        target = sample_project / "src" / "main.py"
        original = target.read_text()

        injector = DocstringInjector(backup=False)
        injector.inject(str(target), {"main": "Docs."}, dry_run=True)

        assert target.read_text() == original


class TestModuleDocGeneratorWorkflow:
    """Tests for the module doc generator workflow."""

    def test_generate_docs_for_module(self, mock_llm, sample_project):
        """Test generating docs for a parsed module."""
        parser = PythonParser()
        module = parser.parse_file(str(sample_project / "src" / "utils" / "helpers.py"))

        gen = ModuleDocGenerator(mock_llm)
        result = gen.generate(module, skip_existing=True)

        assert result.file_path == str(sample_project / "src" / "utils" / "helpers.py")
        assert result.module_doc is not None

    def test_batch_generate_docs(self, mock_llm, sample_project):
        """Test batch generating docs for multiple modules."""
        parser = PythonParser()
        modules = []

        for py_file in sorted(sample_project.rglob("*.py")):
            try:
                modules.append(parser.parse_file(str(py_file)))
            except SyntaxError:
                pass

        gen = ModuleDocGenerator(mock_llm)
        results = gen.generate_batch(modules, skip_existing=True)

        assert len(results) == len(modules)


class TestCLIEndToEnd:
    """Tests for CLI commands in end-to-end scenarios."""

    def test_generate_dry_run(self, runner, sample_project):
        """Test CLI generate --dry-run."""
        result = runner.invoke(doc, ["generate", str(sample_project), "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run complete" in result.output
        assert "source files" in result.output

    def test_generate_markdown_output(self, runner, sample_project):
        """Test CLI generate produces Markdown files."""
        out_dir = str(sample_project / "docs" / "out")
        result = runner.invoke(
            doc,
            [
                "generate",
                str(sample_project),
                "--format",
                "md",
                "--output-dir",
                out_dir,
            ],
        )

        assert result.exit_code == 0
        assert Path(out_dir).exists()

    def test_generate_html_output(self, runner, sample_project):
        """Test CLI generate produces HTML/MkDocs files."""
        out_dir = str(sample_project / "site_docs")
        result = runner.invoke(
            doc,
            [
                "generate",
                str(sample_project),
                "--format",
                "html",
                "--output-dir",
                out_dir,
            ],
        )

        assert result.exit_code == 0
        assert Path(out_dir).exists()

    def test_complexity_report(self, runner, sample_project):
        """Test CLI complexity command."""
        result = runner.invoke(doc, ["complexity", str(sample_project)])

        assert result.exit_code == 0
        assert "functions analyzed" in result.output

    def test_estimate_cost(self, runner, sample_project):
        """Test CLI estimate command."""
        result = runner.invoke(doc, ["estimate", str(sample_project)])

        assert result.exit_code == 0
        assert "USD" in result.output

    def test_docstrings_dry_run(self, runner, sample_project):
        """Test CLI docstrings --dry-run."""
        result = runner.invoke(doc, ["docstrings", str(sample_project), "--dry-run"])

        assert result.exit_code == 0
        assert "without docstrings" in result.output

    @patch("src.cli.commands.LLMClient")
    def test_readme_generation(self, mock_cls, runner, sample_project):
        """Test CLI readme command end-to-end."""
        mock_client = MagicMock()
        mock_client.generate.return_value = GenerationResult(
            content="# Test Project\n\nA sample project.",
            usage=TokenUsage(input_tokens=100, output_tokens=200),
            model="test",
        )
        mock_cls.return_value = mock_client

        output = str(sample_project / "README_TEST.md")
        result = runner.invoke(
            doc,
            ["readme", str(sample_project), "--output", output],
        )

        assert result.exit_code == 0
        assert Path(output).exists()

    def test_incremental_mode_full_cycle(self, runner, sample_project):
        """Test incremental mode: first run saves state, second skips."""
        out_dir = str(sample_project / "docs" / "inc")

        # First run
        result1 = runner.invoke(
            doc,
            [
                "generate",
                str(sample_project),
                "--incremental",
                "--format",
                "md",
                "--output-dir",
                out_dir,
            ],
        )
        assert result1.exit_code == 0

        # State file should exist
        state_file = sample_project / ".codedoc-state.json"
        assert state_file.exists()

        # Second run should skip all files
        result2 = runner.invoke(
            doc,
            [
                "generate",
                str(sample_project),
                "--incremental",
                "--dry-run",
            ],
        )
        assert result2.exit_code == 0
        assert "0 changed files" in result2.output


class TestMultiLanguageProject:
    """Tests for mixed-language project workflows."""

    def test_analyze_mixed_project(self, mixed_project):
        """Test analysis of a mixed Python/JS project."""
        from src.generators.readme_gen import ReadmeGenerator

        gen = ReadmeGenerator(llm_client=MagicMock())
        info = gen.analyze_project(str(mixed_project))

        assert "Python" in info.languages
        assert "JavaScript/TypeScript" in info.languages
        assert len(info.dependencies) >= 1
        assert len(info.js_dependencies) >= 1

    def test_cli_generate_mixed_project(self, runner, mixed_project):
        """Test CLI generate on mixed-language project."""
        result = runner.invoke(doc, ["generate", str(mixed_project), "--dry-run"])

        assert result.exit_code == 0
        assert "source files" in result.output


class TestErrorRecovery:
    """Tests for error handling and recovery scenarios."""

    def test_parser_survives_bad_files(self, tmp_path):
        """Test that parser skips bad files and continues."""
        (tmp_path / "good.py").write_text("def good(): pass\n")
        (tmp_path / "bad.py").write_text("def broken(:\n")
        (tmp_path / "also_good.py").write_text("def also_good(): pass\n")

        parser = PythonParser()
        modules = []
        for py_file in sorted(tmp_path.rglob("*.py")):
            try:
                modules.append(parser.parse_file(str(py_file)))
            except SyntaxError:
                pass

        assert len(modules) == 2

    def test_cli_handles_single_file(self, runner, tmp_path):
        """Test CLI can process a single file."""
        (tmp_path / "single.py").write_text(
            "def hello(): pass\ndef world(): return 42\n"
        )

        result = runner.invoke(doc, ["complexity", str(tmp_path / "single.py")])
        assert result.exit_code == 0

    def test_markdown_writer_creates_directories(self, tmp_path):
        """Test Markdown writer creates output dirs as needed."""
        out_dir = str(tmp_path / "deep" / "nested" / "docs")
        writer = MarkdownWriter(output_dir=out_dir)

        from src.parsers.structure import Language, ModuleInfo

        module = ModuleInfo(
            file_path="test.py",
            language=Language.PYTHON,
            line_count=10,
        )
        path = writer.write_module_doc(module)
        assert path.exists()
