"""Tests for the module documentation generator."""

from unittest.mock import MagicMock

import pytest

from src.generators.docstring_gen import DocstringResult, ModuleDocResult
from src.generators.module_gen import ModuleDocGenerator
from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns predictable results."""
    client = MagicMock()
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    result = MagicMock()
    result.content = "Generated documentation content."
    result.usage = usage
    result.model = "test-model"
    result.stop_reason = "end_turn"

    client.generate.return_value = result
    return client


@pytest.fixture
def mock_template_manager():
    """Create a mock template manager."""
    manager = MagicMock()
    manager.render_module_doc_prompt.return_value = "Module prompt"
    manager.render_docstring_prompt.return_value = "Docstring prompt"
    manager.render_class_doc_prompt.return_value = "Class doc prompt"
    return manager


@pytest.fixture
def sample_module():
    """Create a sample module with functions and classes."""
    return ModuleInfo(
        file_path="src/example.py",
        language=Language.PYTHON,
        docstring="Example module for testing.",
        functions=[
            FunctionInfo(
                name="process_data",
                parameters=[
                    ParameterInfo(name="data", type_hint="list[str]"),
                    ParameterInfo(name="limit", type_hint="int", default_value="10"),
                ],
                return_type="dict",
                line_number=10,
                end_line_number=25,
            ),
            FunctionInfo(
                name="validate_input",
                parameters=[ParameterInfo(name="value", type_hint="str")],
                return_type="bool",
                docstring="Validate the input value.",
                line_number=28,
                end_line_number=35,
            ),
        ],
        classes=[
            ClassInfo(
                name="DataProcessor",
                base_classes=["BaseProcessor"],
                methods=[
                    FunctionInfo(
                        name="__init__",
                        parameters=[ParameterInfo(name="self")],
                        line_number=40,
                        end_line_number=45,
                    ),
                    FunctionInfo(
                        name="run",
                        parameters=[ParameterInfo(name="self")],
                        return_type="None",
                        line_number=47,
                        end_line_number=55,
                    ),
                ],
                line_number=38,
                end_line_number=55,
            ),
        ],
        imports=[
            ImportInfo(module="os", line_number=1),
            ImportInfo(
                module="pathlib",
                names=["Path"],
                is_from_import=True,
                line_number=2,
            ),
        ],
        line_count=60,
    )


@pytest.fixture
def empty_module():
    """Create an empty module with no functions or classes."""
    return ModuleInfo(
        file_path="src/empty.py",
        language=Language.PYTHON,
        line_count=5,
    )


@pytest.fixture
def generator(mock_llm_client, mock_template_manager):
    """Create a ModuleDocGenerator with mocked dependencies."""
    return ModuleDocGenerator(mock_llm_client, mock_template_manager)


class TestModuleDocGenerator:
    """Tests for ModuleDocGenerator initialization and configuration."""

    def test_init_with_defaults(self, mock_llm_client):
        """Test initialization with default template manager."""
        gen = ModuleDocGenerator(mock_llm_client)
        assert gen.llm is mock_llm_client
        assert gen.templates is not None
        assert gen.docstring_gen is not None

    def test_init_with_custom_template_manager(
        self, mock_llm_client, mock_template_manager
    ):
        """Test initialization with a custom template manager."""
        gen = ModuleDocGenerator(mock_llm_client, mock_template_manager)
        assert gen.templates is mock_template_manager


class TestGenerate:
    """Tests for the generate method."""

    def test_generate_with_sample_module(self, generator, sample_module):
        """Test generating docs for a module with functions and classes."""
        result = generator.generate(sample_module)

        assert isinstance(result, ModuleDocResult)
        assert result.file_path == "src/example.py"
        assert result.module_doc is not None
        assert result.module_doc.docstring == "Generated documentation content."
        # 1 function without docstring + 1 class = 2 LLM calls + 1 module summary
        assert len(result.function_docs) == 1  # skip validate_input (has docstring)
        assert len(result.class_docs) == 1

    def test_generate_empty_module(self, generator, empty_module):
        """Test generating docs for an empty module."""
        result = generator.generate(empty_module)

        assert result.file_path == "src/empty.py"
        assert result.module_doc is not None
        assert len(result.function_docs) == 0
        assert len(result.class_docs) == 0

    def test_generate_skip_existing_true(self, generator, sample_module):
        """Test that existing docstrings are skipped when skip_existing=True."""
        result = generator.generate(sample_module, skip_existing=True)

        # validate_input has docstring, so it should be skipped
        func_names = [d.name for d in result.function_docs]
        assert "process_data" in func_names
        assert "validate_input" not in func_names

    def test_generate_skip_existing_false(self, generator, sample_module):
        """Test that all items are processed when skip_existing=False."""
        result = generator.generate(sample_module, skip_existing=False)

        func_names = [d.name for d in result.function_docs]
        assert "process_data" in func_names
        assert "validate_input" in func_names

    def test_generate_with_source_context(self, generator, sample_module):
        """Test generating docs with source code context."""
        result = generator.generate(sample_module, include_source=True)

        assert result.module_doc is not None
        assert len(result.function_docs) >= 1

    def test_generate_token_aggregation(self, generator, sample_module):
        """Test that token usage is properly aggregated."""
        result = generator.generate(sample_module)

        # Module summary + 1 function + 1 class = 3 calls x 100 input + 50 output
        assert result.total_input_tokens == 300
        assert result.total_output_tokens == 150


class TestGenerateBatch:
    """Tests for the generate_batch method."""

    def test_batch_multiple_modules(self, generator, sample_module, empty_module):
        """Test batch generation with multiple modules."""
        results = generator.generate_batch([sample_module, empty_module])

        assert len(results) == 2
        assert results[0].file_path == "src/example.py"
        assert results[1].file_path == "src/empty.py"

    def test_batch_empty_list(self, generator):
        """Test batch generation with empty module list."""
        results = generator.generate_batch([])
        assert results == []

    def test_batch_with_options(self, generator, sample_module):
        """Test batch generation passes options through."""
        results = generator.generate_batch(
            [sample_module],
            include_source=True,
            skip_existing=False,
        )
        assert len(results) == 1
        # All functions should be processed since skip_existing=False
        assert len(results[0].function_docs) == 2


class TestModuleSummary:
    """Tests for the module summary generation."""

    def test_module_summary_generation(self, generator, sample_module):
        """Test that module summary calls the template and LLM."""
        result = generator._generate_module_summary(sample_module)

        assert isinstance(result, DocstringResult)
        assert result.name == "src/example.py"
        assert result.docstring == "Generated documentation content."
        generator.templates.render_module_doc_prompt.assert_called_once_with(
            sample_module
        )
        generator.llm.generate.assert_called_once()


class TestContextBuilding:
    """Tests for context string building methods."""

    def test_function_context_with_docstring(self, generator, sample_module):
        """Test function context includes module docstring."""
        context = generator._build_function_context(sample_module)

        assert "src/example.py" in context
        assert "Example module for testing." in context

    def test_function_context_with_imports(self, generator, sample_module):
        """Test function context includes import names."""
        context = generator._build_function_context(sample_module)

        assert "os" in context
        assert "pathlib" in context

    def test_function_context_no_docstring(self, generator, empty_module):
        """Test function context without module docstring."""
        context = generator._build_function_context(empty_module)

        assert "src/empty.py" in context
        assert "Module purpose" not in context

    def test_class_context_with_docstring(self, generator, sample_module):
        """Test class context includes module docstring."""
        context = generator._build_class_context(sample_module)

        assert "src/example.py" in context
        assert "Example module for testing." in context

    def test_class_context_no_docstring(self, generator, empty_module):
        """Test class context without module docstring."""
        context = generator._build_class_context(empty_module)

        assert "src/empty.py" in context
        assert "Module purpose" not in context
