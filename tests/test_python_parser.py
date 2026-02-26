"""Tests for the Python AST parser."""

import textwrap
from pathlib import Path

import pytest

from src.parsers.python_parser import PythonParser
from src.parsers.structure import Language


@pytest.fixture
def parser() -> PythonParser:
    """Create a PythonParser instance for testing."""
    return PythonParser()


class TestParseSource:
    """Tests for parsing Python source code strings."""

    def test_empty_module(self, parser: PythonParser) -> None:
        result = parser.parse_source("")
        assert result.language == Language.PYTHON
        assert result.functions == []
        assert result.classes == []

    def test_module_docstring(self, parser: PythonParser) -> None:
        source = '"""Module docstring."""\n'
        result = parser.parse_source(source)
        assert result.docstring == "Module docstring."

    def test_line_count(self, parser: PythonParser) -> None:
        source = "a = 1\nb = 2\nc = 3\n"
        result = parser.parse_source(source)
        assert result.line_count == 3


class TestFunctionExtraction:
    """Tests for extracting function definitions."""

    def test_simple_function(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def hello():
                pass
        """)
        result = parser.parse_source(source)
        assert len(result.functions) == 1
        assert result.functions[0].name == "hello"

    def test_function_with_params(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                return x + y
        """)
        result = parser.parse_source(source)
        func = result.functions[0]
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "x"
        assert func.parameters[0].type_hint == "int"
        assert func.return_type == "int"

    def test_function_with_defaults(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def greet(name: str = "world"):
                pass
        """)
        result = parser.parse_source(source)
        param = result.functions[0].parameters[0]
        assert param.default_value == "'world'"

    def test_function_with_args_kwargs(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def func(*args: int, **kwargs: str):
                pass
        """)
        result = parser.parse_source(source)
        params = result.functions[0].parameters
        assert any(p.is_args and p.name == "args" for p in params)
        assert any(p.is_kwargs and p.name == "kwargs" for p in params)

    def test_async_function(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            async def fetch(url: str) -> bytes:
                pass
        """)
        result = parser.parse_source(source)
        func = result.functions[0]
        assert func.is_async is True
        assert func.name == "fetch"
        assert func.return_type == "bytes"

    def test_function_with_docstring(self, parser: PythonParser) -> None:
        source = textwrap.dedent('''\
            def documented():
                """This function is documented."""
                pass
        ''')
        result = parser.parse_source(source)
        assert result.functions[0].docstring == "This function is documented."

    def test_function_with_decorators(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            @staticmethod
            @cache
            def cached_func():
                pass
        """)
        result = parser.parse_source(source)
        assert "staticmethod" in result.functions[0].decorators
        assert "cache" in result.functions[0].decorators

    def test_function_line_numbers(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            # comment
            def func():
                pass
        """)
        result = parser.parse_source(source)
        assert result.functions[0].line_number == 2

    def test_function_source_extraction(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def add(a, b):
                return a + b
        """)
        result = parser.parse_source(source)
        assert "return a + b" in result.functions[0].source

    def test_kwonly_args(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def func(*, key: str, value: int = 0):
                pass
        """)
        result = parser.parse_source(source)
        params = result.functions[0].parameters
        assert len(params) == 2
        assert params[0].name == "key"
        assert params[1].default_value == "0"

    def test_complex_return_type(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def func() -> dict[str, list[int]]:
                pass
        """)
        result = parser.parse_source(source)
        assert result.functions[0].return_type == "dict[str, list[int]]"


class TestClassExtraction:
    """Tests for extracting class definitions."""

    def test_simple_class(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class MyClass:
                pass
        """)
        result = parser.parse_source(source)
        assert len(result.classes) == 1
        assert result.classes[0].name == "MyClass"

    def test_class_with_bases(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class Child(Parent, Mixin):
                pass
        """)
        result = parser.parse_source(source)
        cls = result.classes[0]
        assert cls.base_classes == ["Parent", "Mixin"]

    def test_class_with_docstring(self, parser: PythonParser) -> None:
        source = textwrap.dedent('''\
            class Documented:
                """A documented class."""
                pass
        ''')
        result = parser.parse_source(source)
        assert result.classes[0].docstring == "A documented class."

    def test_class_methods(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class Calc:
                def add(self, x: int, y: int) -> int:
                    return x + y

                def sub(self, x: int, y: int) -> int:
                    return x - y
        """)
        result = parser.parse_source(source)
        cls = result.classes[0]
        assert len(cls.methods) == 2
        assert cls.methods[0].name == "add"
        assert cls.methods[1].name == "sub"

    def test_class_with_decorators(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            @dataclass
            class Config:
                name: str = "default"
        """)
        result = parser.parse_source(source)
        assert "dataclass" in result.classes[0].decorators

    def test_class_with_property(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class Thing:
                @property
                def value(self) -> int:
                    return self._value
        """)
        result = parser.parse_source(source)
        method = result.classes[0].methods[0]
        assert method.name == "value"
        assert "property" in method.decorators

    def test_class_with_async_method(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class Client:
                async def fetch(self, url: str) -> bytes:
                    pass
        """)
        result = parser.parse_source(source)
        method = result.classes[0].methods[0]
        assert method.is_async is True

    def test_class_init_with_self(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            class Foo:
                def __init__(self, x: int):
                    self.x = x
        """)
        result = parser.parse_source(source)
        init_method = result.classes[0].methods[0]
        assert init_method.name == "__init__"
        # self is included as a parameter
        assert init_method.parameters[0].name == "self"


class TestImportExtraction:
    """Tests for extracting import statements."""

    def test_simple_import(self, parser: PythonParser) -> None:
        source = "import os\n"
        result = parser.parse_source(source)
        assert len(result.imports) == 1
        assert result.imports[0].module == "os"
        assert result.imports[0].is_from_import is False

    def test_import_alias(self, parser: PythonParser) -> None:
        source = "import numpy as np\n"
        result = parser.parse_source(source)
        assert result.imports[0].alias == "np"

    def test_from_import(self, parser: PythonParser) -> None:
        source = "from os.path import join, exists\n"
        result = parser.parse_source(source)
        imp = result.imports[0]
        assert imp.module == "os.path"
        assert imp.is_from_import is True
        assert "join" in imp.names
        assert "exists" in imp.names

    def test_multiple_imports(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            import os
            import sys
            from pathlib import Path
        """)
        result = parser.parse_source(source)
        assert len(result.imports) == 3

    def test_import_line_number(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            # header
            import os
        """)
        result = parser.parse_source(source)
        assert result.imports[0].line_number == 2


class TestParseFile:
    """Tests for parsing from file paths."""

    def test_parse_real_file(self, parser: PythonParser, tmp_path: Path) -> None:
        source = textwrap.dedent('''\
            """Test module."""

            def hello(name: str) -> str:
                """Say hello."""
                return f"Hello, {name}!"
        ''')
        file_path = tmp_path / "test_module.py"
        file_path.write_text(source)

        result = parser.parse_file(str(file_path))
        assert result.docstring == "Test module."
        assert result.functions[0].name == "hello"
        assert result.file_path == str(file_path)

    def test_file_not_found(self, parser: PythonParser) -> None:
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.py")

    def test_syntax_error(self, parser: PythonParser, tmp_path: Path) -> None:
        file_path = tmp_path / "bad.py"
        file_path.write_text("def broken(:\n")
        with pytest.raises(SyntaxError):
            parser.parse_file(str(file_path))


class TestEdgeCases:
    """Tests for edge cases and complex patterns."""

    def test_nested_function_not_extracted(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def outer():
                def inner():
                    pass
                return inner
        """)
        result = parser.parse_source(source)
        # Only top-level functions are extracted
        assert len(result.functions) == 1
        assert result.functions[0].name == "outer"

    def test_multiple_functions_and_classes(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            def func_a():
                pass

            class ClassA:
                pass

            def func_b():
                pass

            class ClassB:
                pass
        """)
        result = parser.parse_source(source)
        assert len(result.functions) == 2
        assert len(result.classes) == 2

    def test_decorator_with_arguments(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            @app.route("/api", methods=["GET"])
            def endpoint():
                pass
        """)
        result = parser.parse_source(source)
        dec = result.functions[0].decorators[0]
        assert "app.route" in dec

    def test_complex_type_annotations(self, parser: PythonParser) -> None:
        source = textwrap.dedent("""\
            from typing import Optional

            def process(
                data: list[dict[str, int]],
                callback: Optional[callable] = None,
            ) -> tuple[bool, str]:
                pass
        """)
        result = parser.parse_source(source)
        func = result.functions[0]
        assert func.parameters[0].type_hint == "list[dict[str, int]]"
        assert func.return_type == "tuple[bool, str]"
