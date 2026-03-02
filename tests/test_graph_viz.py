"""Tests for the dependency graph visualization module."""

import pytest

from src.analysis.graph_viz import DependencyVisualizer, _sanitize_id, _short_label
from src.parsers.structure import DependencyGraph, Language, ModuleInfo


@pytest.fixture
def empty_graph():
    """Create an empty dependency graph."""
    return DependencyGraph()


@pytest.fixture
def sample_graph():
    """Create a dependency graph with modules and edges."""
    graph = DependencyGraph()

    mod_a = ModuleInfo(file_path="src/main.py", language=Language.PYTHON, line_count=50)
    mod_b = ModuleInfo(
        file_path="src/utils.py", language=Language.PYTHON, line_count=30
    )
    mod_c = ModuleInfo(
        file_path="src/api/views.py", language=Language.PYTHON, line_count=80
    )

    graph.add_module(mod_a)
    graph.add_module(mod_b)
    graph.add_module(mod_c)

    graph.add_import_edge("src/main.py", "src/utils.py")
    graph.add_import_edge("src/main.py", "src/api/views.py")
    graph.add_import_edge("src/api/views.py", "src/utils.py")
    graph.add_import_edge("src/main.py", "os")  # external

    graph.add_call_edge("src/main.py::main", "src/utils.py::helper")
    graph.add_call_edge("src/api/views.py::index", "src/utils.py::helper")

    return graph


class TestDependencyVisualizer:
    """Tests for DependencyVisualizer initialization."""

    def test_init(self, sample_graph):
        """Test visualizer initialization."""
        viz = DependencyVisualizer(sample_graph)
        assert viz.graph is sample_graph


class TestMermaidImports:
    """Tests for Mermaid import graph generation."""

    def test_basic_import_graph(self, sample_graph):
        """Test basic Mermaid import graph output."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_imports(filter_external=False)

        assert result.startswith("graph LR")
        assert "-->" in result

    def test_filter_external(self, sample_graph):
        """Test that external imports are filtered."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_imports(filter_external=True)

        assert "os" not in result

    def test_include_external(self, sample_graph):
        """Test that external imports are included when not filtering."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_imports(filter_external=False)

        # os should appear in some form
        assert "os" in result

    def test_empty_graph(self, empty_graph):
        """Test Mermaid output for empty graph."""
        viz = DependencyVisualizer(empty_graph)
        result = viz.to_mermaid_imports()

        assert "No dependencies found" in result

    def test_max_nodes_limit(self, sample_graph):
        """Test that max_nodes limits the output."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_imports(filter_external=False, max_nodes=2)

        # Should still produce valid output
        assert "graph LR" in result

    def test_node_labels(self, sample_graph):
        """Test that nodes have readable labels."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_imports(filter_external=False)

        # Should contain quoted labels
        assert '"' in result


class TestMermaidCalls:
    """Tests for Mermaid call graph generation."""

    def test_basic_call_graph(self, sample_graph):
        """Test basic Mermaid call graph output."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_calls()

        assert result.startswith("graph TD")
        assert "-->" in result

    def test_empty_call_graph(self, empty_graph):
        """Test Mermaid output for empty call graph."""
        viz = DependencyVisualizer(empty_graph)
        result = viz.to_mermaid_calls()

        assert "No call relationships found" in result

    def test_max_nodes_limit(self, sample_graph):
        """Test that max_nodes limits the call graph."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_mermaid_calls(max_nodes=2)

        assert "graph TD" in result


class TestToMarkdown:
    """Tests for Markdown output generation."""

    def test_full_markdown(self, sample_graph):
        """Test full Markdown output with both graphs."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_markdown()

        assert "## Import Dependencies" in result
        assert "## Call Graph" in result
        assert "```mermaid" in result

    def test_imports_only(self, sample_graph):
        """Test Markdown with only import graph."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_markdown(include_calls=False)

        assert "## Import Dependencies" in result
        assert "## Call Graph" not in result

    def test_calls_only(self, sample_graph):
        """Test Markdown with only call graph."""
        viz = DependencyVisualizer(sample_graph)
        result = viz.to_markdown(include_imports=False)

        assert "## Import Dependencies" not in result
        assert "## Call Graph" in result

    def test_empty_graphs(self, empty_graph):
        """Test Markdown for empty graph."""
        viz = DependencyVisualizer(empty_graph)
        result = viz.to_markdown()

        assert "No dependency relationships found" in result


class TestModuleDependencies:
    """Tests for get_module_dependencies."""

    def test_get_dependencies(self, sample_graph):
        """Test getting module dependencies."""
        viz = DependencyVisualizer(sample_graph)
        deps = viz.get_module_dependencies("src/main.py")

        assert "src/utils.py" in deps["imports"]
        assert "src/api/views.py" in deps["imports"]

    def test_get_dependents(self, sample_graph):
        """Test getting modules that depend on a module."""
        viz = DependencyVisualizer(sample_graph)
        deps = viz.get_module_dependencies("src/utils.py")

        assert "src/main.py" in deps["imported_by"]
        assert "src/api/views.py" in deps["imported_by"]

    def test_no_dependencies(self, sample_graph):
        """Test module with no outgoing dependencies."""
        viz = DependencyVisualizer(sample_graph)
        deps = viz.get_module_dependencies("src/utils.py")

        assert deps["imports"] == []


class TestSanitizeId:
    """Tests for the _sanitize_id helper."""

    def test_simple_name(self):
        """Test simple names pass through."""
        assert _sanitize_id("main") == "main"

    def test_path_with_slashes(self):
        """Test paths are sanitized."""
        result = _sanitize_id("src/utils/config.py")
        assert "/" not in result
        assert "." not in result

    def test_starts_with_digit(self):
        """Test names starting with digits get prefixed."""
        result = _sanitize_id("123abc")
        assert result.startswith("n_")

    def test_empty_string(self):
        """Test empty string returns unknown."""
        assert _sanitize_id("") == "unknown"

    def test_special_characters(self):
        """Test special characters are replaced."""
        result = _sanitize_id("my-module.name")
        assert "-" not in result
        assert "." not in result


class TestShortLabel:
    """Tests for the _short_label helper."""

    def test_short_path(self):
        """Test short paths are not modified."""
        assert _short_label("main.py") == "main.py"

    def test_long_path(self):
        """Test long paths are shortened."""
        result = _short_label("src/utils/config.py")
        assert result == "utils/config.py"

    def test_two_parts(self):
        """Test two-part paths are preserved."""
        assert _short_label("src/main.py") == "src/main.py"

    def test_backslash_paths(self):
        """Test Windows-style paths are handled."""
        result = _short_label("src\\utils\\config.py")
        assert result == "utils/config.py"
