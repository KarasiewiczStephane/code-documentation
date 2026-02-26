"""Tests for the complexity analysis module."""

import textwrap
from pathlib import Path

import pytest

from src.analysis.complexity import (
    ComplexityAnalyzer,
    FileComplexityReport,
    FunctionComplexity,
    _complexity_rank,
)
from src.parsers.python_parser import PythonParser
from src.parsers.structure import ModuleInfo
from src.utils.config import ComplexityConfig


@pytest.fixture
def analyzer() -> ComplexityAnalyzer:
    """Create a ComplexityAnalyzer instance."""
    return ComplexityAnalyzer()


class TestComplexityRank:
    """Tests for the complexity rank function."""

    def test_rank_a(self) -> None:
        assert _complexity_rank(1) == "A"
        assert _complexity_rank(5) == "A"

    def test_rank_b(self) -> None:
        assert _complexity_rank(6) == "B"
        assert _complexity_rank(10) == "B"

    def test_rank_c(self) -> None:
        assert _complexity_rank(11) == "C"
        assert _complexity_rank(20) == "C"

    def test_rank_d(self) -> None:
        assert _complexity_rank(21) == "D"
        assert _complexity_rank(30) == "D"

    def test_rank_e(self) -> None:
        assert _complexity_rank(31) == "E"
        assert _complexity_rank(40) == "E"

    def test_rank_f(self) -> None:
        assert _complexity_rank(41) == "F"


class TestAnalyzeSource:
    """Tests for analyzing source code strings."""

    def test_simple_function(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            def simple():
                return 1
        """)
        report = analyzer.analyze_source(source)
        assert report.total_functions == 1
        assert report.functions[0].complexity == 1
        assert report.functions[0].rank == "A"

    def test_complex_function(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            def complex_func(x, y, z):
                if x > 0:
                    if y > 0:
                        return 'both positive'
                    return 'x positive'
                elif z > 0:
                    return 'z positive'
                else:
                    for i in range(10):
                        if i % 2 == 0:
                            continue
                    return 'negative'
        """)
        report = analyzer.analyze_source(source)
        func = report.functions[0]
        assert func.complexity > 1

    def test_multiple_functions(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            def func_a():
                return 1

            def func_b(x):
                if x:
                    return True
                return False
        """)
        report = analyzer.analyze_source(source)
        assert report.total_functions == 2

    def test_average_complexity(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            def a():
                return 1

            def b():
                return 2
        """)
        report = analyzer.analyze_source(source)
        assert report.average_complexity == 1.0

    def test_max_complexity(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            def simple():
                return 1

            def branching(x):
                if x > 0:
                    return 'pos'
                return 'neg'
        """)
        report = analyzer.analyze_source(source)
        assert report.max_complexity >= 1
        assert report.most_complex_function is not None

    def test_empty_source(self, analyzer: ComplexityAnalyzer) -> None:
        report = analyzer.analyze_source("")
        assert report.total_functions == 0
        assert report.average_complexity == 0.0
        assert report.most_complex_function is None

    def test_class_methods(self, analyzer: ComplexityAnalyzer) -> None:
        source = textwrap.dedent("""\
            class MyClass:
                def method_a(self):
                    return 1

                def method_b(self, x):
                    if x:
                        return True
                    return False
        """)
        report = analyzer.analyze_source(source)
        assert report.total_functions >= 2

    def test_file_path_in_report(self, analyzer: ComplexityAnalyzer) -> None:
        report = analyzer.analyze_source("def f(): pass", file_path="test.py")
        assert report.file_path == "test.py"


class TestAnalyzeFile:
    """Tests for analyzing from file paths."""

    def test_analyze_real_file(
        self, analyzer: ComplexityAnalyzer, tmp_path: Path
    ) -> None:
        source = textwrap.dedent("""\
            def hello():
                return "world"
        """)
        file_path = tmp_path / "sample.py"
        file_path.write_text(source)

        report = analyzer.analyze_file(str(file_path))
        assert report.total_functions == 1
        assert report.file_path == str(file_path)

    def test_file_not_found(self, analyzer: ComplexityAnalyzer) -> None:
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_file("/nonexistent/file.py")


class TestEnrichModule:
    """Tests for enriching ModuleInfo with complexity data."""

    def test_enrich_functions(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            def simple():
                return 1

            def branching(x):
                if x > 0:
                    return 'pos'
                return 'neg'
        """)
        file_path = tmp_path / "module.py"
        file_path.write_text(source)

        parser = PythonParser()
        module = parser.parse_file(str(file_path))
        assert module.functions[0].complexity is None

        analyzer = ComplexityAnalyzer()
        enriched = analyzer.enrich_module(module)
        assert enriched.functions[0].complexity is not None
        assert enriched.functions[0].complexity >= 1

    def test_enrich_class_methods(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            class Calc:
                def add(self, a, b):
                    return a + b
        """)
        file_path = tmp_path / "calc.py"
        file_path.write_text(source)

        parser = PythonParser()
        module = parser.parse_file(str(file_path))

        analyzer = ComplexityAnalyzer()
        enriched = analyzer.enrich_module(module)
        assert enriched.classes[0].methods[0].complexity is not None

    def test_enrich_nonexistent_file(self) -> None:
        module = ModuleInfo(file_path="/nonexistent/file.py")
        analyzer = ComplexityAnalyzer()
        result = analyzer.enrich_module(module)
        assert result is module


class TestComplexityLabels:
    """Tests for human-readable complexity labels."""

    def test_low(self) -> None:
        analyzer = ComplexityAnalyzer()
        assert analyzer.get_complexity_label(1) == "low"
        assert analyzer.get_complexity_label(5) == "low"

    def test_medium(self) -> None:
        analyzer = ComplexityAnalyzer()
        assert analyzer.get_complexity_label(6) == "medium"
        assert analyzer.get_complexity_label(10) == "medium"

    def test_high(self) -> None:
        analyzer = ComplexityAnalyzer()
        assert analyzer.get_complexity_label(11) == "high"
        assert analyzer.get_complexity_label(20) == "high"

    def test_very_high(self) -> None:
        analyzer = ComplexityAnalyzer()
        assert analyzer.get_complexity_label(21) == "very high"

    def test_custom_thresholds(self) -> None:
        config = ComplexityConfig(thresholds={"low": 3, "medium": 6, "high": 10})
        analyzer = ComplexityAnalyzer(config=config)
        assert analyzer.get_complexity_label(3) == "low"
        assert analyzer.get_complexity_label(4) == "medium"
        assert analyzer.get_complexity_label(7) == "high"
        assert analyzer.get_complexity_label(11) == "very high"


class TestFunctionComplexity:
    """Tests for the FunctionComplexity dataclass."""

    def test_creation(self) -> None:
        fc = FunctionComplexity(
            name="test", complexity=5, rank="A", line_number=1, end_line_number=3
        )
        assert fc.name == "test"
        assert fc.complexity == 5
        assert fc.rank == "A"


class TestFileComplexityReport:
    """Tests for the FileComplexityReport dataclass."""

    def test_defaults(self) -> None:
        report = FileComplexityReport(file_path="test.py")
        assert report.functions == []
        assert report.average_complexity == 0.0
        assert report.total_functions == 0
