"""Call graph analysis for Python source code.

Extracts function call relationships from Python AST to populate
the DependencyGraph with call edges, enabling visualization of
how functions interact within and across modules.
"""

import ast
import logging
from typing import Optional

from src.parsers.structure import DependencyGraph, ModuleInfo

logger = logging.getLogger(__name__)


class CallExtractor(ast.NodeVisitor):
    """Extract function calls from a Python function body.

    Walks the AST of a function to find all Call nodes and resolves
    their targets to qualified names using scope analysis.
    """

    def __init__(self, current_scope: str, module_path: str) -> None:
        """Initialize the call extractor.

        Args:
            current_scope: Qualified name of the current function/method.
            module_path: File path of the module being analyzed.
        """
        self.current_scope = current_scope
        self.module_path = module_path
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Visit a Call node and extract the call target.

        Args:
            node: The Call AST node.
        """
        target = self._resolve_call_target(node.func)
        if target:
            self.calls.append(target)
        self.generic_visit(node)

    def _resolve_call_target(self, node: ast.expr) -> Optional[str]:
        """Resolve a call target expression to a qualified name.

        Handles simple names (foo()), attribute access (self.foo(),
        obj.method()), and nested attribute access.

        Args:
            node: The function expression being called.

        Returns:
            Qualified name string, or None if unresolvable.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            value = self._resolve_value(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        return None

    def _resolve_value(self, node: ast.expr) -> Optional[str]:
        """Resolve the value part of an attribute access.

        Args:
            node: The value expression (e.g., 'self' in self.method()).

        Returns:
            Resolved name string, or None if unresolvable.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            value = self._resolve_value(node.value)
            if value:
                return f"{value}.{node.attr}"
        return None


class CallGraphAnalyzer:
    """Analyzes Python modules to extract function call relationships.

    Walks function bodies to find Call nodes, resolves call targets,
    and populates a DependencyGraph with call edges.
    """

    def analyze_module(
        self,
        module: ModuleInfo,
        graph: DependencyGraph,
    ) -> int:
        """Analyze a module and add call edges to the dependency graph.

        Args:
            module: The parsed module to analyze.
            graph: The dependency graph to populate with call edges.

        Returns:
            Number of call edges added.
        """
        try:
            source = self._read_source(module.file_path)
            tree = ast.parse(source, filename=module.file_path)
        except (FileNotFoundError, SyntaxError) as e:
            logger.warning("Cannot analyze %s: %s", module.file_path, e)
            return 0

        edges_added = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = f"{module.file_path}::{node.name}"
                extractor = CallExtractor(scope, module.file_path)
                extractor.visit(node)

                for call_target in extractor.calls:
                    qualified = self._qualify_call(
                        call_target, module.file_path, node.name
                    )
                    graph.add_call_edge(scope, qualified)
                    edges_added += 1

            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scope = f"{module.file_path}::{node.name}.{item.name}"
                        extractor = CallExtractor(scope, module.file_path)
                        extractor.visit(item)

                        for call_target in extractor.calls:
                            qualified = self._qualify_call(
                                call_target,
                                module.file_path,
                                f"{node.name}.{item.name}",
                            )
                            graph.add_call_edge(scope, qualified)
                            edges_added += 1

        logger.info(
            "Call graph analysis for %s: %d edges", module.file_path, edges_added
        )
        return edges_added

    def analyze_modules(
        self,
        modules: list[ModuleInfo],
        graph: Optional[DependencyGraph] = None,
    ) -> DependencyGraph:
        """Analyze multiple modules and build a call graph.

        Args:
            modules: List of modules to analyze.
            graph: Optional existing graph to extend. Creates new if None.

        Returns:
            The dependency graph with call edges populated.
        """
        if graph is None:
            graph = DependencyGraph()

        total_edges = 0
        for module in modules:
            edges = self.analyze_module(module, graph)
            total_edges += edges

        logger.info(
            "Total call graph analysis: %d modules, %d edges",
            len(modules),
            total_edges,
        )
        return graph

    def _read_source(self, file_path: str) -> str:
        """Read source code from a file.

        Args:
            file_path: Path to the source file.

        Returns:
            Source code string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return path.read_text(encoding="utf-8")

    def _qualify_call(
        self, call_target: str, module_path: str, caller_name: str
    ) -> str:
        """Qualify a call target with module context.

        For simple function calls that appear to be local, prepends
        the module path. For attribute-based calls, preserves as-is.

        Args:
            call_target: The raw call target name.
            module_path: Path of the module containing the call.
            caller_name: Name of the calling function.

        Returns:
            Qualified call target string.
        """
        # If it's a simple name (no dots), it might be a local function
        if "." not in call_target:
            return f"{module_path}::{call_target}"
        return call_target
