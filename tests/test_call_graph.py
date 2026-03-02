"""Tests for the call graph analysis module."""

import textwrap

import pytest

from src.analysis.call_graph import CallExtractor, CallGraphAnalyzer
from src.parsers.structure import DependencyGraph, Language, ModuleInfo


@pytest.fixture
def analyzer():
    """Create a CallGraphAnalyzer instance."""
    return CallGraphAnalyzer()


@pytest.fixture
def sample_source():
    """Sample Python source with various call patterns."""
    return textwrap.dedent("""\
        import os
        from pathlib import Path

        def helper():
            return True

        def main():
            result = helper()
            path = Path(".")
            items = os.listdir(".")
            return result

        class Processor:
            def __init__(self):
                self.data = []

            def process(self):
                result = helper()
                self.validate()
                return result

            def validate(self):
                pass
    """)


@pytest.fixture
def sample_file(tmp_path, sample_source):
    """Create a temporary Python file."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(sample_source, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_module(sample_file):
    """Create a ModuleInfo for the sample file."""
    return ModuleInfo(
        file_path=str(sample_file),
        language=Language.PYTHON,
        line_count=25,
    )


class TestCallExtractor:
    """Tests for the CallExtractor AST visitor."""

    def test_extract_simple_calls(self):
        """Test extraction of simple function calls."""
        import ast

        source = "def foo():\n    bar()\n    baz(1, 2)\n"
        tree = ast.parse(source)
        func_node = tree.body[0]

        extractor = CallExtractor("test.py::foo", "test.py")
        extractor.visit(func_node)

        assert "bar" in extractor.calls
        assert "baz" in extractor.calls

    def test_extract_method_calls(self):
        """Test extraction of method calls (obj.method())."""
        import ast

        source = "def foo(self):\n    self.bar()\n    obj.method()\n"
        tree = ast.parse(source)
        func_node = tree.body[0]

        extractor = CallExtractor("test.py::foo", "test.py")
        extractor.visit(func_node)

        assert "self.bar" in extractor.calls
        assert "obj.method" in extractor.calls

    def test_extract_chained_calls(self):
        """Test extraction of chained attribute calls."""
        import ast

        source = "def foo():\n    os.path.join('a', 'b')\n"
        tree = ast.parse(source)
        func_node = tree.body[0]

        extractor = CallExtractor("test.py::foo", "test.py")
        extractor.visit(func_node)

        assert "os.path.join" in extractor.calls

    def test_no_calls(self):
        """Test extraction from function with no calls."""
        import ast

        source = "def foo():\n    x = 1\n    return x\n"
        tree = ast.parse(source)
        func_node = tree.body[0]

        extractor = CallExtractor("test.py::foo", "test.py")
        extractor.visit(func_node)

        assert extractor.calls == []


class TestCallGraphAnalyzer:
    """Tests for the CallGraphAnalyzer class."""

    def test_analyze_module(self, analyzer, sample_module):
        """Test analyzing a single module."""
        graph = DependencyGraph()
        edges = analyzer.analyze_module(sample_module, graph)

        assert edges > 0
        assert len(graph.call_edges) > 0

    def test_analyze_module_missing_file(self, analyzer):
        """Test analyzing a module with missing file."""
        module = ModuleInfo(
            file_path="/nonexistent/file.py",
            language=Language.PYTHON,
        )
        graph = DependencyGraph()
        edges = analyzer.analyze_module(module, graph)

        assert edges == 0

    def test_analyze_modules(self, analyzer, sample_module):
        """Test analyzing multiple modules."""
        graph = analyzer.analyze_modules([sample_module])

        assert len(graph.call_edges) > 0

    def test_analyze_modules_creates_graph(self, analyzer, sample_module):
        """Test that analyze_modules creates a graph when none provided."""
        graph = analyzer.analyze_modules([sample_module])

        assert isinstance(graph, DependencyGraph)
        assert len(graph.call_edges) > 0

    def test_analyze_modules_extends_existing_graph(self, analyzer, sample_module):
        """Test that analyze_modules extends an existing graph."""
        graph = DependencyGraph()
        graph.add_call_edge("existing::caller", "existing::callee")

        result = analyzer.analyze_modules([sample_module], graph=graph)

        assert result is graph
        assert len(graph.call_edges) > 1

    def test_call_edges_contain_module_path(self, analyzer, sample_module):
        """Test that call edges reference the correct module."""
        graph = DependencyGraph()
        analyzer.analyze_module(sample_module, graph)

        callers = [caller for caller, _ in graph.call_edges]
        assert any(sample_module.file_path in c for c in callers)

    def test_class_method_calls_extracted(self, analyzer, sample_module):
        """Test that calls from class methods are extracted."""
        graph = DependencyGraph()
        analyzer.analyze_module(sample_module, graph)

        # Should find calls from Processor.process
        callers = [caller for caller, _ in graph.call_edges]
        assert any("Processor.process" in c for c in callers)

    def test_self_method_calls(self, analyzer, sample_module):
        """Test that self.method() calls are captured."""
        graph = DependencyGraph()
        analyzer.analyze_module(sample_module, graph)

        callees = [callee for _, callee in graph.call_edges]
        assert any("self.validate" in c for c in callees)


class TestQualifyCall:
    """Tests for the _qualify_call method."""

    def test_simple_local_call(self, analyzer):
        """Test qualifying a simple local function call."""
        result = analyzer._qualify_call("helper", "module.py", "main")
        assert result == "module.py::helper"

    def test_attribute_call_preserved(self, analyzer):
        """Test that attribute calls are preserved as-is."""
        result = analyzer._qualify_call("self.method", "module.py", "main")
        assert result == "self.method"

    def test_module_call_preserved(self, analyzer):
        """Test that module-level calls are preserved."""
        result = analyzer._qualify_call("os.path.join", "module.py", "main")
        assert result == "os.path.join"
