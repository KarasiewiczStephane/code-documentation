"""Tests for the HTML/MkDocs output generator."""

from pathlib import Path

import pytest
import yaml

from src.output.html import HtmlWriter
from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)


@pytest.fixture
def writer(tmp_path: Path) -> HtmlWriter:
    """Create an HtmlWriter with a temp output directory."""
    return HtmlWriter(output_dir=str(tmp_path / "site"))


def _sample_modules() -> list[ModuleInfo]:
    """Create sample modules for testing."""
    return [
        ModuleInfo(
            file_path="src/main.py",
            language=Language.PYTHON,
            docstring="Main module.",
            line_count=30,
            functions=[FunctionInfo(name="main", line_number=1, end_line_number=10)],
        ),
        ModuleInfo(
            file_path="src/utils.py",
            language=Language.PYTHON,
            docstring="Utility functions.",
            line_count=50,
            functions=[
                FunctionInfo(
                    name="helper",
                    parameters=[ParameterInfo(name="x", type_hint="int")],
                    line_number=1,
                    end_line_number=5,
                ),
            ],
            classes=[
                ClassInfo(
                    name="Config",
                    line_number=10,
                    end_line_number=20,
                ),
            ],
        ),
    ]


class TestGenerateMkdocsConfig:
    """Tests for mkdocs.yml generation."""

    def test_creates_config_file(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        path = writer.generate_mkdocs_config("My Project", modules)
        assert path.exists()
        assert path.name == "mkdocs.yml"

    def test_config_content(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        path = writer.generate_mkdocs_config("TestProject", modules)
        config = yaml.safe_load(path.read_text())
        assert config["site_name"] == "TestProject Documentation"
        assert config["theme"]["name"] == "readthedocs"

    def test_config_navigation(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        path = writer.generate_mkdocs_config("Test", modules)
        config = yaml.safe_load(path.read_text())
        nav = config["nav"]
        assert {"Home": "index.md"} in nav

    def test_custom_theme(self, writer: HtmlWriter) -> None:
        path = writer.generate_mkdocs_config("Test", [], theme="material")
        config = yaml.safe_load(path.read_text())
        assert config["theme"]["name"] == "material"

    def test_empty_modules(self, writer: HtmlWriter) -> None:
        path = writer.generate_mkdocs_config("Empty", [])
        config = yaml.safe_load(path.read_text())
        assert "nav" in config


class TestWriteDocs:
    """Tests for writing the MkDocs docs directory."""

    def test_creates_docs_dir(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        assert docs_path.exists()
        assert docs_path.is_dir()

    def test_creates_main_index(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        index = docs_path / "index.md"
        assert index.exists()
        content = index.read_text()
        assert "Welcome" in content

    def test_creates_api_directory(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        api_dir = docs_path / "api"
        assert api_dir.exists()

    def test_creates_module_files(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        api_dir = docs_path / "api"
        files = list(api_dir.glob("*.md"))
        # index.md + 2 module files
        assert len(files) >= 3

    def test_creates_api_index(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        api_index = docs_path / "api" / "index.md"
        assert api_index.exists()
        content = api_index.read_text()
        assert "src/main.py" in content

    def test_main_index_stats(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        docs_path = writer.write_docs(modules)
        content = (docs_path / "index.md").read_text()
        assert "2" in content  # 2 modules
        assert "functions" in content

    def test_empty_modules(self, writer: HtmlWriter) -> None:
        docs_path = writer.write_docs([])
        assert (docs_path / "index.md").exists()

    def test_with_generated_docs(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        generated = {"helper": "Custom docs for helper."}
        docs_path = writer.write_docs(modules, generated_docs=generated)
        # Check the utils module file contains the custom doc
        utils_file = docs_path / "api" / "src_utils.md"
        content = utils_file.read_text()
        assert "Custom docs for helper." in content


class TestBuildNavigation:
    """Tests for navigation structure building."""

    def test_basic_navigation(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        nav = writer._build_navigation(modules)
        assert {"Home": "index.md"} in nav
        assert len(nav) == 2  # Home + API Reference

    def test_empty_navigation(self, writer: HtmlWriter) -> None:
        nav = writer._build_navigation([])
        assert len(nav) == 1  # Just Home
        assert {"Home": "index.md"} in nav

    def test_module_entries(self, writer: HtmlWriter) -> None:
        modules = _sample_modules()
        nav = writer._build_navigation(modules)
        api_section = nav[1]["API Reference"]
        # Overview + 2 modules
        assert len(api_section) == 3
