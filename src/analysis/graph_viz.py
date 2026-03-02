"""Dependency graph visualization using Mermaid diagram syntax.

Generates Mermaid flowchart diagrams from DependencyGraph objects,
showing import relationships and call graphs between modules.
"""

import logging
import re

from src.parsers.structure import DependencyGraph

logger = logging.getLogger(__name__)


class DependencyVisualizer:
    """Generates visual representations of code dependency graphs.

    Produces Mermaid diagram syntax showing import relationships
    between modules, with support for filtering and size limits.
    """

    def __init__(self, graph: DependencyGraph) -> None:
        """Initialize the dependency visualizer.

        Args:
            graph: The dependency graph to visualize.
        """
        self.graph = graph

    def to_mermaid_imports(
        self,
        filter_external: bool = True,
        max_nodes: int = 50,
    ) -> str:
        """Generate a Mermaid flowchart for import relationships.

        Args:
            filter_external: If True, exclude external (non-project) imports.
            max_nodes: Maximum number of nodes to include.

        Returns:
            Mermaid diagram syntax string.
        """
        lines = ["graph LR"]
        nodes: set[str] = set()
        edges: list[tuple[str, str]] = []

        project_modules = set(self.graph.modules.keys())

        for source, target in self.graph.import_edges:
            if filter_external and target not in project_modules:
                # Check if target is a subpath of any project module
                if not any(target.startswith(m.split("/")[0]) for m in project_modules):
                    continue

            if len(nodes) >= max_nodes:
                break

            source_id = _sanitize_id(source)
            target_id = _sanitize_id(target)
            nodes.add(source)
            nodes.add(target)
            edges.append((source_id, target_id))

        # Add node declarations
        for node in sorted(nodes):
            node_id = _sanitize_id(node)
            label = _short_label(node)
            lines.append(f'    {node_id}["{label}"]')

        # Add edges
        for source_id, target_id in edges:
            lines.append(f"    {source_id} --> {target_id}")

        if not edges:
            lines.append("    no_deps[No dependencies found]")

        logger.info(
            "Generated Mermaid import graph: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )
        return "\n".join(lines)

    def to_mermaid_calls(self, max_nodes: int = 50) -> str:
        """Generate a Mermaid flowchart for function call relationships.

        Args:
            max_nodes: Maximum number of nodes to include.

        Returns:
            Mermaid diagram syntax string.
        """
        lines = ["graph TD"]
        nodes: set[str] = set()
        edges: list[tuple[str, str]] = []

        for caller, callee in self.graph.call_edges:
            if len(nodes) >= max_nodes:
                break

            caller_id = _sanitize_id(caller)
            callee_id = _sanitize_id(callee)
            nodes.add(caller)
            nodes.add(callee)
            edges.append((caller_id, callee_id))

        for node in sorted(nodes):
            node_id = _sanitize_id(node)
            label = _short_label(node)
            lines.append(f'    {node_id}["{label}"]')

        for caller_id, callee_id in edges:
            lines.append(f"    {caller_id} --> {callee_id}")

        if not edges:
            lines.append("    no_calls[No call relationships found]")

        logger.info(
            "Generated Mermaid call graph: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )
        return "\n".join(lines)

    def to_markdown(
        self,
        include_imports: bool = True,
        include_calls: bool = True,
        filter_external: bool = True,
    ) -> str:
        """Generate a Markdown section with embedded Mermaid diagrams.

        Args:
            include_imports: Whether to include the import graph.
            include_calls: Whether to include the call graph.
            filter_external: Whether to filter external dependencies.

        Returns:
            Markdown string with Mermaid code blocks.
        """
        sections = []

        if include_imports and self.graph.import_edges:
            mermaid = self.to_mermaid_imports(filter_external=filter_external)
            sections.append("## Import Dependencies\n")
            sections.append(f"```mermaid\n{mermaid}\n```\n")

        if include_calls and self.graph.call_edges:
            mermaid = self.to_mermaid_calls()
            sections.append("## Call Graph\n")
            sections.append(f"```mermaid\n{mermaid}\n```\n")

        if not sections:
            sections.append("## Dependencies\n")
            sections.append("No dependency relationships found.\n")

        return "\n".join(sections)

    def get_module_dependencies(self, file_path: str) -> dict[str, list[str]]:
        """Get the import and dependent modules for a specific file.

        Args:
            file_path: Path of the module to query.

        Returns:
            Dictionary with 'imports' and 'imported_by' lists.
        """
        return {
            "imports": self.graph.get_dependencies(file_path),
            "imported_by": self.graph.get_dependents(file_path),
        }


def _sanitize_id(name: str) -> str:
    """Sanitize a module/function name for use as a Mermaid node ID.

    Args:
        name: Original name with dots, slashes, etc.

    Returns:
        A valid Mermaid node identifier.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "n_" + sanitized
    return sanitized or "unknown"


def _short_label(name: str) -> str:
    """Create a short display label from a full module path.

    Args:
        name: Full module path (e.g., 'src/utils/config.py').

    Returns:
        Shortened label (e.g., 'config.py').
    """
    # Remove common prefixes
    parts = name.replace("\\", "/").split("/")
    if len(parts) > 2:
        return "/".join(parts[-2:])
    return name
