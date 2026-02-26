"""Cyclomatic complexity analysis for Python source code.

Uses the radon library to compute per-function complexity scores,
file-level summaries, and structured complexity reports.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from radon.complexity import cc_visit

from src.parsers.structure import ModuleInfo
from src.utils.config import ComplexityConfig

logger = logging.getLogger(__name__)


@dataclass
class FunctionComplexity:
    """Complexity data for a single function.

    Attributes:
        name: Function or method name.
        complexity: Cyclomatic complexity score.
        rank: Complexity rank (A-F).
        line_number: Starting line number.
        end_line_number: Ending line number.
    """

    name: str
    complexity: int
    rank: str
    line_number: int
    end_line_number: int


@dataclass
class FileComplexityReport:
    """Complexity report for a single file.

    Attributes:
        file_path: Path to the analyzed file.
        functions: List of per-function complexity data.
        average_complexity: Mean complexity across all functions.
        max_complexity: Highest complexity score in the file.
        most_complex_function: Name of the most complex function.
        total_functions: Number of functions analyzed.
    """

    file_path: str
    functions: list[FunctionComplexity] = field(default_factory=list)
    average_complexity: float = 0.0
    max_complexity: int = 0
    most_complex_function: Optional[str] = None
    total_functions: int = 0


def _complexity_rank(score: int) -> str:
    """Map a complexity score to a letter rank.

    Args:
        score: Cyclomatic complexity score.

    Returns:
        A rank from A (simple) to F (very complex).
    """
    if score <= 5:
        return "A"
    elif score <= 10:
        return "B"
    elif score <= 20:
        return "C"
    elif score <= 30:
        return "D"
    elif score <= 40:
        return "E"
    return "F"


class ComplexityAnalyzer:
    """Analyzes cyclomatic complexity of Python source code.

    Uses radon to compute per-function complexity and generates
    file-level summary statistics.
    """

    def __init__(self, config: Optional[ComplexityConfig] = None) -> None:
        """Initialize the complexity analyzer.

        Args:
            config: Optional complexity configuration with thresholds.
        """
        self.config = config or ComplexityConfig()

    def analyze_file(self, file_path: str) -> FileComplexityReport:
        """Analyze a Python file and return its complexity report.

        Args:
            file_path: Path to the Python source file.

        Returns:
            A FileComplexityReport with per-function complexity data.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source = path.read_text(encoding="utf-8")
        return self.analyze_source(source, file_path)

    def analyze_source(
        self, source: str, file_path: str = "<string>"
    ) -> FileComplexityReport:
        """Analyze Python source code and return its complexity report.

        Args:
            source: Python source code string.
            file_path: Optional file path for the report.

        Returns:
            A FileComplexityReport with per-function complexity data.
        """
        results = cc_visit(source)

        functions = []
        for block in results:
            functions.append(
                FunctionComplexity(
                    name=block.name,
                    complexity=block.complexity,
                    rank=_complexity_rank(block.complexity),
                    line_number=block.lineno,
                    end_line_number=block.endline,
                )
            )

        report = FileComplexityReport(
            file_path=file_path,
            functions=functions,
            total_functions=len(functions),
        )

        if functions:
            complexities = [f.complexity for f in functions]
            report.average_complexity = sum(complexities) / len(complexities)
            report.max_complexity = max(complexities)
            most_complex = max(functions, key=lambda f: f.complexity)
            report.most_complex_function = most_complex.name

        logger.debug(
            "Analyzed %s: %d functions, avg complexity %.1f",
            file_path,
            report.total_functions,
            report.average_complexity,
        )
        return report

    def enrich_module(self, module: ModuleInfo) -> ModuleInfo:
        """Enrich a ModuleInfo with complexity scores for each function.

        Reads the source file and matches radon results to the parsed
        functions by line number, updating their complexity fields.

        Args:
            module: A parsed ModuleInfo object.

        Returns:
            The same ModuleInfo with complexity fields populated.
        """
        path = Path(module.file_path)
        if not path.exists():
            logger.warning("Cannot analyze complexity: %s not found", module.file_path)
            return module

        source = path.read_text(encoding="utf-8")
        results = cc_visit(source)

        # Build a lookup by (name, line_number)
        complexity_map: dict[tuple[str, int], int] = {}
        for block in results:
            complexity_map[(block.name, block.lineno)] = block.complexity

        for func in module.functions:
            key = (func.name, func.line_number)
            if key in complexity_map:
                func.complexity = complexity_map[key]

        for cls in module.classes:
            for method in cls.methods:
                key = (method.name, method.line_number)
                if key in complexity_map:
                    method.complexity = complexity_map[key]

        return module

    def get_complexity_label(self, score: int) -> str:
        """Get a human-readable complexity label based on thresholds.

        Args:
            score: Cyclomatic complexity score.

        Returns:
            One of 'low', 'medium', 'high', or 'very high'.
        """
        thresholds = self.config.thresholds
        if score <= thresholds.get("low", 5):
            return "low"
        elif score <= thresholds.get("medium", 10):
            return "medium"
        elif score <= thresholds.get("high", 20):
            return "high"
        return "very high"
