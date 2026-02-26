"""Tests for the Markdown output generator."""

from pathlib import Path

import pytest

from src.output.markdown import MarkdownWriter
from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)


@pytest.fixture
def writer(tmp_path: Path) -> MarkdownWriter:
    """Create a MarkdownWriter with a temp output directory."""
    return MarkdownWriter(output_dir=str(tmp_path / "docs"))


def _sample_module() -> ModuleInfo:
    """Create a sample module for testing."""
    return ModuleInfo(
        file_path="src/utils.py",
        language=Language.PYTHON,
        docstring="Utility functions.",
        line_count=50,
        functions=[
            FunctionInfo(
                name="helper",
                parameters=[ParameterInfo(name="x", type_hint="int")],
                return_type="str",
                docstring="A helper function.",
                line_number=5,
                end_line_number=10,
                complexity=2,
            ),
        ],
        classes=[
            ClassInfo(
                name="Config",
                base_classes=["dict"],
                docstring="Configuration class.",
                methods=[
                    FunctionInfo(
                        name="load",
                        parameters=[ParameterInfo(name="self")],
                        return_type="None",
                        line_number=15,
                        end_line_number=20,
                    ),
                ],
                line_number=12,
                end_line_number=25,
            ),
        ],
        imports=[
            ImportInfo(module="os"),
            ImportInfo(module="pathlib", names=["Path"], is_from_import=True),
        ],
    )


class TestWriteModuleDoc:
    """Tests for writing module documentation."""

    def test_creates_file(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        assert path.exists()
        assert path.suffix == ".md"

    def test_file_content(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "src/utils.py" in content
        assert "Utility functions." in content
        assert "helper" in content
        assert "Config" in content

    def test_function_signature_in_output(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "x: int" in content
        assert "-> str" in content

    def test_class_bases_in_output(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "dict" in content

    def test_imports_in_output(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "import os" in content
        assert "from pathlib import Path" in content

    def test_complexity_in_output(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "**2**" in content

    def test_generated_docs_override(self, writer: MarkdownWriter) -> None:
        module = _sample_module()
        generated = {"helper": "Custom generated docs for helper."}
        path = writer.write_module_doc(module, generated_docs=generated)
        content = path.read_text()
        assert "Custom generated docs for helper." in content

    def test_safe_filename(self, writer: MarkdownWriter) -> None:
        module = ModuleInfo(file_path="src/deep/module.py")
        path = writer.write_module_doc(module)
        assert "src_deep_module.md" == path.name

    def test_async_function(self, writer: MarkdownWriter) -> None:
        module = ModuleInfo(
            file_path="async_mod.py",
            functions=[
                FunctionInfo(
                    name="fetch",
                    is_async=True,
                    line_number=1,
                    end_line_number=5,
                ),
            ],
        )
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "async fetch" in content

    def test_decorators_in_output(self, writer: MarkdownWriter) -> None:
        module = ModuleInfo(
            file_path="deco.py",
            functions=[
                FunctionInfo(
                    name="cached",
                    decorators=["cache"],
                    line_number=1,
                    end_line_number=3,
                ),
            ],
        )
        path = writer.write_module_doc(module)
        content = path.read_text()
        assert "@cache" in content


class TestWriteIndex:
    """Tests for writing the index/table of contents."""

    def test_creates_index(self, writer: MarkdownWriter) -> None:
        modules = [_sample_module()]
        path = writer.write_index(modules)
        assert path.exists()
        assert path.name == "index.md"

    def test_index_links_modules(self, writer: MarkdownWriter) -> None:
        modules = [
            ModuleInfo(file_path="src/a.py", docstring="Module A."),
            ModuleInfo(file_path="src/b.py", docstring="Module B."),
        ]
        path = writer.write_index(modules)
        content = path.read_text()
        assert "src/a.py" in content
        assert "src/b.py" in content
        assert "src_a.md" in content
        assert "src_b.md" in content

    def test_index_includes_docstrings(self, writer: MarkdownWriter) -> None:
        modules = [
            ModuleInfo(file_path="main.py", docstring="Main module."),
        ]
        path = writer.write_index(modules)
        content = path.read_text()
        assert "Main module." in content

    def test_custom_title(self, writer: MarkdownWriter) -> None:
        path = writer.write_index([], title="Documentation")
        content = path.read_text()
        assert "# Documentation" in content

    def test_empty_modules(self, writer: MarkdownWriter) -> None:
        path = writer.write_index([])
        assert path.exists()


class TestFormatParam:
    """Tests for parameter formatting."""

    def test_simple_param(self, writer: MarkdownWriter) -> None:
        param = ParameterInfo(name="x")
        assert writer._format_param(param) == "x"

    def test_typed_param(self, writer: MarkdownWriter) -> None:
        param = ParameterInfo(name="x", type_hint="int")
        assert writer._format_param(param) == "x: int"

    def test_default_param(self, writer: MarkdownWriter) -> None:
        param = ParameterInfo(name="x", type_hint="int", default_value="0")
        assert writer._format_param(param) == "x: int = 0"

    def test_args_param(self, writer: MarkdownWriter) -> None:
        param = ParameterInfo(name="args", is_args=True)
        assert writer._format_param(param) == "*args"

    def test_kwargs_param(self, writer: MarkdownWriter) -> None:
        param = ParameterInfo(name="kwargs", is_kwargs=True)
        assert writer._format_param(param) == "**kwargs"
