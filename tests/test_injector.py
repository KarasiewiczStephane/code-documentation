"""Tests for the docstring injection module."""

import textwrap
from pathlib import Path

import pytest

from src.output.injector import DocstringInjector, InjectionResult


@pytest.fixture
def injector():
    """Create a DocstringInjector with backup disabled."""
    return DocstringInjector(backup=False)


@pytest.fixture
def injector_with_backup():
    """Create a DocstringInjector with backup enabled."""
    return DocstringInjector(backup=True)


@pytest.fixture
def sample_source():
    """Sample Python source code without docstrings."""
    return textwrap.dedent("""\
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        def add(a: int, b: int) -> int:
            return a + b

        class Calculator:
            def multiply(self, x: int, y: int) -> int:
                return x * y
    """)


@pytest.fixture
def source_with_existing_docstrings():
    """Sample source code with some existing docstrings."""
    return textwrap.dedent('''\
        def greet(name: str) -> str:
            """Greet a person by name."""
            return f"Hello, {name}!"

        def add(a: int, b: int) -> int:
            return a + b
    ''')


@pytest.fixture
def sample_file(tmp_path, sample_source):
    """Create a temporary Python file with sample source."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(sample_source, encoding="utf-8")
    return str(file_path)


@pytest.fixture
def file_with_existing(tmp_path, source_with_existing_docstrings):
    """Create a temporary file with some existing docstrings."""
    file_path = tmp_path / "existing.py"
    file_path.write_text(source_with_existing_docstrings, encoding="utf-8")
    return str(file_path)


class TestDocstringInjector:
    """Tests for DocstringInjector initialization."""

    def test_init_default(self):
        """Test default initialization with backup enabled."""
        injector = DocstringInjector()
        assert injector.backup is True

    def test_init_no_backup(self):
        """Test initialization with backup disabled."""
        injector = DocstringInjector(backup=False)
        assert injector.backup is False


class TestInject:
    """Tests for the inject method."""

    def test_inject_function_docstring(self, injector, sample_file):
        """Test injecting a docstring into a function."""
        docstrings = {"greet": "Greet a person by name."}
        result = injector.inject(sample_file, docstrings)

        assert result.modified is True
        assert result.injected_count >= 1
        assert result.file_path == sample_file

        # Verify the file was modified
        content = Path(sample_file).read_text(encoding="utf-8")
        assert '"""Greet a person by name."""' in content

    def test_inject_multiple_docstrings(self, injector, sample_file):
        """Test injecting docstrings into multiple items."""
        docstrings = {
            "greet": "Greet a person by name.",
            "add": "Add two numbers together.",
            "Calculator": "A simple calculator class.",
        }
        result = injector.inject(sample_file, docstrings)

        assert result.modified is True
        content = Path(sample_file).read_text(encoding="utf-8")
        assert '"""Greet a person by name."""' in content
        assert '"""Add two numbers together."""' in content
        assert '"""A simple calculator class."""' in content

    def test_inject_preserves_existing(self, injector, file_with_existing):
        """Test that existing docstrings are not overwritten."""
        docstrings = {
            "greet": "New greet docstring.",
            "add": "Add two numbers.",
        }
        injector.inject(file_with_existing, docstrings)

        content = Path(file_with_existing).read_text(encoding="utf-8")
        # Existing docstring should be preserved
        assert "Greet a person by name." in content
        # New docstring should be added
        assert '"""Add two numbers."""' in content

    def test_inject_dry_run(self, injector, sample_file):
        """Test dry-run mode does not modify the file."""
        original = Path(sample_file).read_text(encoding="utf-8")
        docstrings = {"greet": "Greet a person by name."}

        result = injector.inject(sample_file, docstrings, dry_run=True)

        # File should not be modified
        assert Path(sample_file).read_text(encoding="utf-8") == original
        # But diff should be non-empty
        assert len(result.diff) > 0

    def test_inject_with_backup(self, injector_with_backup, sample_file):
        """Test that backup file is created."""
        docstrings = {"greet": "Greet a person by name."}
        injector_with_backup.inject(sample_file, docstrings)

        backup_path = Path(f"{sample_file}.bak")
        assert backup_path.exists()

    def test_inject_file_not_found(self, injector):
        """Test injection raises error for missing file."""
        with pytest.raises(FileNotFoundError):
            injector.inject("/nonexistent/file.py", {"foo": "bar"})

    def test_inject_no_matching_names(self, injector, sample_file):
        """Test injection with names that don't match any items."""
        original = Path(sample_file).read_text(encoding="utf-8")
        docstrings = {"nonexistent_func": "Some docstring."}

        result = injector.inject(sample_file, docstrings)

        assert result.modified is False
        assert Path(sample_file).read_text(encoding="utf-8") == original

    def test_inject_multiline_docstring(self, injector, sample_file):
        """Test injecting a multi-line docstring."""
        docstrings = {
            "greet": "Greet a person by name.\n\nArgs:\n    name: The person's name.\n\nReturns:\n    A greeting string.",
        }
        result = injector.inject(sample_file, docstrings)

        assert result.modified is True
        content = Path(sample_file).read_text(encoding="utf-8")
        assert "Greet a person by name." in content
        assert "Args:" in content

    def test_inject_syntax_error(self, injector, tmp_path):
        """Test injection raises error for invalid Python."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

        with pytest.raises(SyntaxError):
            injector.inject(str(bad_file), {"broken": "docstring"})

    def test_injected_file_is_valid_python(self, injector, sample_file):
        """Test that the modified file is valid Python."""
        docstrings = {
            "greet": "Greet a person.",
            "add": "Add numbers.",
            "Calculator": "Calculator class.",
        }
        injector.inject(sample_file, docstrings)

        content = Path(sample_file).read_text(encoding="utf-8")
        # Should parse without error
        compile(content, sample_file, "exec")


class TestInjectBatch:
    """Tests for the inject_batch method."""

    def test_batch_injection(self, injector, tmp_path):
        """Test injecting into multiple files."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def foo():\n    pass\n", encoding="utf-8")

        file2 = tmp_path / "file2.py"
        file2.write_text("def bar():\n    pass\n", encoding="utf-8")

        file_docstrings = {
            str(file1): {"foo": "Foo function."},
            str(file2): {"bar": "Bar function."},
        }

        results = injector.inject_batch(file_docstrings)

        assert len(results) == 2
        assert all(r.modified for r in results)

    def test_batch_skips_missing_files(self, injector, tmp_path):
        """Test batch injection skips missing files."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def foo():\n    pass\n", encoding="utf-8")

        file_docstrings = {
            str(file1): {"foo": "Foo function."},
            "/nonexistent/file.py": {"bar": "Bar function."},
        }

        results = injector.inject_batch(file_docstrings)
        assert len(results) == 1


class TestFormatDocstring:
    """Tests for docstring formatting."""

    def test_single_line(self, injector):
        """Test formatting a single-line docstring."""
        result = injector._format_docstring("Hello world.", "    ")
        assert result == '    """Hello world."""\n'

    def test_multiline(self, injector):
        """Test formatting a multi-line docstring."""
        docstring = "Summary line.\n\nDetailed description."
        result = injector._format_docstring(docstring, "    ")
        assert '"""Summary line.' in result
        assert "Detailed description." in result
        assert result.endswith('"""\n')

    def test_strips_whitespace(self, injector):
        """Test that leading/trailing whitespace is stripped."""
        result = injector._format_docstring("  Hello world.  ", "    ")
        assert result == '    """Hello world."""\n'


class TestInjectionResult:
    """Tests for the InjectionResult class."""

    def test_default_values(self):
        """Test default initialization values."""
        result = InjectionResult(file_path="test.py")
        assert result.file_path == "test.py"
        assert result.diff == ""
        assert result.injected_count == 0
        assert result.modified is False

    def test_custom_values(self):
        """Test initialization with custom values."""
        result = InjectionResult(
            file_path="test.py",
            diff="some diff",
            injected_count=3,
            modified=True,
        )
        assert result.injected_count == 3
        assert result.modified is True
