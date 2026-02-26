"""Tests for the docstring generator with mocked LLM responses."""

from unittest.mock import MagicMock

import pytest

from src.generators.docstring_gen import (
    DocstringGenerator,
    DocstringResult,
    ModuleDocResult,
)
from src.generators.llm_client import GenerationResult, LLMClient, TokenUsage
from src.parsers.structure import ClassInfo, FunctionInfo, ModuleInfo, ParameterInfo


def _mock_llm_client() -> MagicMock:
    """Create a mocked LLMClient that returns predictable results."""
    client = MagicMock(spec=LLMClient)
    client.generate.return_value = GenerationResult(
        content="Generated documentation content.",
        usage=TokenUsage(input_tokens=50, output_tokens=30),
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    )
    return client


@pytest.fixture
def generator() -> DocstringGenerator:
    """Create a DocstringGenerator with a mocked LLM client."""
    return DocstringGenerator(llm_client=_mock_llm_client())


class TestDocstringResult:
    """Tests for DocstringResult dataclass."""

    def test_creation(self) -> None:
        result = DocstringResult(name="func", docstring="A docstring.")
        assert result.name == "func"
        assert result.docstring == "A docstring."
        assert result.input_tokens == 0

    def test_with_tokens(self) -> None:
        result = DocstringResult(
            name="func", docstring="doc", input_tokens=10, output_tokens=20
        )
        assert result.input_tokens == 10


class TestModuleDocResult:
    """Tests for ModuleDocResult dataclass."""

    def test_defaults(self) -> None:
        result = ModuleDocResult(file_path="test.py")
        assert result.module_doc is None
        assert result.function_docs == []
        assert result.class_docs == []
        assert result.total_input_tokens == 0


class TestGenerateDocstring:
    """Tests for generating function docstrings."""

    def test_basic_function(self, generator: DocstringGenerator) -> None:
        func = FunctionInfo(name="add", return_type="int")
        result = generator.generate_docstring(func)
        assert isinstance(result, DocstringResult)
        assert result.name == "add"
        assert result.docstring == "Generated documentation content."
        assert result.input_tokens == 50

    def test_with_context(self, generator: DocstringGenerator) -> None:
        func = FunctionInfo(name="process")
        result = generator.generate_docstring(func, context="ETL pipeline function")
        assert result.name == "process"
        # Verify LLM was called
        generator.llm.generate.assert_called()

    def test_function_with_params(self, generator: DocstringGenerator) -> None:
        func = FunctionInfo(
            name="greet",
            parameters=[ParameterInfo(name="name", type_hint="str")],
        )
        result = generator.generate_docstring(func)
        assert result.docstring is not None


class TestGenerateClassDoc:
    """Tests for generating class documentation."""

    def test_basic_class(self, generator: DocstringGenerator) -> None:
        cls = ClassInfo(name="MyService")
        result = generator.generate_class_doc(cls)
        assert result.name == "MyService"
        assert result.docstring is not None

    def test_class_with_methods(self, generator: DocstringGenerator) -> None:
        cls = ClassInfo(
            name="Calculator",
            methods=[FunctionInfo(name="add"), FunctionInfo(name="subtract")],
        )
        result = generator.generate_class_doc(cls)
        assert result.name == "Calculator"

    def test_class_with_context(self, generator: DocstringGenerator) -> None:
        cls = ClassInfo(name="Handler")
        result = generator.generate_class_doc(cls, context="HTTP request handler")
        assert result.docstring is not None


class TestGenerateModuleDoc:
    """Tests for generating module documentation."""

    def test_basic_module(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(file_path="utils.py", line_count=50)
        result = generator.generate_module_doc(module)
        assert result.name == "utils.py"
        assert result.docstring is not None

    def test_module_with_functions(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(
            file_path="app.py",
            functions=[FunctionInfo(name="main")],
        )
        result = generator.generate_module_doc(module)
        assert result.docstring is not None


class TestGenerateAll:
    """Tests for batch generation across a module."""

    def test_full_module(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(
            file_path="service.py",
            functions=[
                FunctionInfo(name="start"),
                FunctionInfo(name="stop"),
            ],
            classes=[ClassInfo(name="Service")],
        )
        result = generator.generate_all(module)
        assert isinstance(result, ModuleDocResult)
        assert result.module_doc is not None
        assert len(result.function_docs) == 2
        assert len(result.class_docs) == 1
        assert result.total_input_tokens > 0
        assert result.total_output_tokens > 0

    def test_skip_existing_docstrings(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(
            file_path="documented.py",
            docstring="Already documented.",
            functions=[
                FunctionInfo(name="documented_func", docstring="Has a docstring."),
                FunctionInfo(name="undocumented_func"),
            ],
            classes=[
                ClassInfo(name="DocumentedClass", docstring="Has a docstring."),
            ],
        )
        result = generator.generate_all(module, skip_existing=True)
        # Should skip module doc, documented_func, and DocumentedClass
        assert result.module_doc is None
        assert len(result.function_docs) == 1
        assert result.function_docs[0].name == "undocumented_func"
        assert len(result.class_docs) == 0

    def test_no_skip_existing(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(
            file_path="all.py",
            docstring="Existing.",
            functions=[FunctionInfo(name="func", docstring="Existing.")],
        )
        result = generator.generate_all(module, skip_existing=False)
        assert result.module_doc is not None
        assert len(result.function_docs) == 1

    def test_empty_module(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(file_path="empty.py")
        result = generator.generate_all(module)
        assert result.module_doc is not None
        assert result.function_docs == []
        assert result.class_docs == []

    def test_token_accumulation(self, generator: DocstringGenerator) -> None:
        module = ModuleInfo(
            file_path="tokens.py",
            functions=[FunctionInfo(name="a"), FunctionInfo(name="b")],
        )
        result = generator.generate_all(module)
        # module_doc + 2 functions = 3 calls, each with 50 input + 30 output
        assert result.total_input_tokens == 150
        assert result.total_output_tokens == 90
