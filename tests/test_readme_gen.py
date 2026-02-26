"""Tests for the README generator."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.generators.llm_client import GenerationResult, LLMClient, TokenUsage
from src.generators.readme_gen import ProjectInfo, ReadmeGenerator


def _mock_llm_client() -> MagicMock:
    """Create a mocked LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.generate.return_value = GenerationResult(
        content="# My Project\n\nGenerated README content.",
        usage=TokenUsage(input_tokens=100, output_tokens=200),
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    )
    return client


@pytest.fixture
def generator() -> ReadmeGenerator:
    """Create a ReadmeGenerator with a mocked LLM client."""
    return ReadmeGenerator(llm_client=_mock_llm_client())


class TestProjectInfo:
    """Tests for ProjectInfo dataclass."""

    def test_defaults(self) -> None:
        info = ProjectInfo(name="test")
        assert info.name == "test"
        assert info.modules == []
        assert info.dependencies == []

    def test_with_all_fields(self) -> None:
        info = ProjectInfo(
            name="my-project",
            description="A test project",
            root_path="/tmp/project",
            entry_points=["main.py"],
            dependencies=["click", "jinja2"],
            structure="src/\n  main.py",
        )
        assert info.description == "A test project"
        assert len(info.dependencies) == 2


class TestAnalyzeProject:
    """Tests for project analysis."""

    def test_analyze_simple_project(
        self, generator: ReadmeGenerator, tmp_path: Path
    ) -> None:
        # Create a minimal project
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text('"""Package."""\n')
        (src_dir / "main.py").write_text(
            textwrap.dedent('''\
                """Main module."""

                def main():
                    """Entry point."""
                    pass
            ''')
        )
        (tmp_path / "requirements.txt").write_text("click>=8.0\njinja2>=3.1\n")

        info = generator.analyze_project(str(tmp_path))
        assert info.name == tmp_path.name
        assert len(info.modules) >= 2
        assert len(info.dependencies) == 2
        assert any("main" in ep for ep in info.entry_points)

    def test_project_not_found(self, generator: ReadmeGenerator) -> None:
        with pytest.raises(FileNotFoundError):
            generator.analyze_project("/nonexistent/project")

    def test_skips_excluded_dirs(
        self, generator: ReadmeGenerator, tmp_path: Path
    ) -> None:
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        (venv_dir / "module.py").write_text("def func(): pass\n")
        (tmp_path / "app.py").write_text("def app(): pass\n")

        info = generator.analyze_project(str(tmp_path))
        paths = [m.file_path for m in info.modules]
        assert not any("venv" in p for p in paths)
        assert "app.py" in paths

    def test_handles_syntax_errors(
        self, generator: ReadmeGenerator, tmp_path: Path
    ) -> None:
        (tmp_path / "bad.py").write_text("def broken(:\n")
        (tmp_path / "good.py").write_text("def good(): pass\n")

        info = generator.analyze_project(str(tmp_path))
        paths = [m.file_path for m in info.modules]
        assert "good.py" in paths
        # bad.py should be skipped without crashing

    def test_empty_project(self, generator: ReadmeGenerator, tmp_path: Path) -> None:
        info = generator.analyze_project(str(tmp_path))
        assert info.modules == []
        assert info.dependencies == []


class TestReadDependencies:
    """Tests for dependency reading."""

    def test_no_requirements_file(
        self, generator: ReadmeGenerator, tmp_path: Path
    ) -> None:
        deps = generator._read_dependencies(tmp_path)
        assert deps == []

    def test_with_requirements(
        self, generator: ReadmeGenerator, tmp_path: Path
    ) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("# Core deps\nclick>=8.0\njinja2>=3.1\n\n# Dev\npytest\n")
        deps = generator._read_dependencies(tmp_path)
        assert "click>=8.0" in deps
        assert "jinja2>=3.1" in deps
        assert "pytest" in deps
        # Comments and blank lines should be excluded
        assert not any(d.startswith("#") for d in deps)


class TestBuildTree:
    """Tests for directory tree generation."""

    def test_simple_tree(self, generator: ReadmeGenerator, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("")
        (tmp_path / "README.md").write_text("")

        tree = generator._build_tree(tmp_path)
        assert tmp_path.name in tree
        assert "src" in tree
        assert "main.py" in tree

    def test_max_depth(self, generator: ReadmeGenerator, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "file.py").write_text("")

        tree = generator._build_tree(tmp_path, max_depth=2)
        # Should not go deeper than 2 levels
        assert "file.py" not in tree


class TestGenerateReadme:
    """Tests for README generation via LLM."""

    def test_generates_readme_content(self, generator: ReadmeGenerator) -> None:
        info = ProjectInfo(
            name="my-project",
            description="A test project",
            dependencies=["click", "jinja2"],
        )
        readme = generator.generate_readme(info)
        assert "My Project" in readme
        assert "Generated README content" in readme

    def test_llm_called_with_prompt(self, generator: ReadmeGenerator) -> None:
        info = ProjectInfo(name="test")
        generator.generate_readme(info)
        generator.llm.generate.assert_called_once()
        call_args = generator.llm.generate.call_args
        assert "test" in call_args[0][0]  # prompt contains project name
