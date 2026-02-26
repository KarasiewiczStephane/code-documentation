"""Markdown output generation for module documentation.

Generates per-module Markdown documentation files, an index page
with a table of contents, and cross-reference links between modules.
"""

import logging
from pathlib import Path
from typing import Optional

from src.parsers.structure import ClassInfo, FunctionInfo, ModuleInfo, ParameterInfo

logger = logging.getLogger(__name__)


class MarkdownWriter:
    """Writes module documentation as Markdown files.

    Generates structured .md files for each module and an index
    page that links all documented modules together.
    """

    def __init__(self, output_dir: str = "docs/generated") -> None:
        """Initialize the Markdown writer.

        Args:
            output_dir: Directory where Markdown files will be written.
        """
        self.output_dir = Path(output_dir)

    def write_module_doc(
        self,
        module: ModuleInfo,
        generated_docs: Optional[dict[str, str]] = None,
    ) -> Path:
        """Write documentation for a single module to a .md file.

        Args:
            module: The parsed module information.
            generated_docs: Optional mapping of item names to their
                generated documentation strings.

        Returns:
            Path to the written Markdown file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Convert file path to a safe filename
        safe_name = module.file_path.replace("/", "_").replace("\\", "_")
        if safe_name.endswith(".py"):
            safe_name = safe_name[:-3]
        md_path = self.output_dir / f"{safe_name}.md"

        content = self._render_module(module, generated_docs or {})
        md_path.write_text(content, encoding="utf-8")

        logger.info("Wrote module documentation: %s", md_path)
        return md_path

    def write_index(
        self,
        modules: list[ModuleInfo],
        title: str = "API Reference",
    ) -> Path:
        """Generate an index/table of contents linking all modules.

        Args:
            modules: List of documented modules.
            title: Title for the index page.

        Returns:
            Path to the written index file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.output_dir / "index.md"

        lines = [f"# {title}\n"]

        if modules:
            lines.append("## Modules\n")
            for module in sorted(modules, key=lambda m: m.file_path):
                link = self._module_link(module)
                doc_summary = module.docstring or ""
                if doc_summary:
                    doc_summary = f" — {doc_summary.split(chr(10))[0]}"
                lines.append(f"- [{module.file_path}]({link}){doc_summary}")

        lines.append("")
        index_path.write_text("\n".join(lines), encoding="utf-8")

        logger.info("Wrote index: %s (%d modules)", index_path, len(modules))
        return index_path

    def _render_module(self, module: ModuleInfo, generated_docs: dict[str, str]) -> str:
        """Render a module's documentation as Markdown.

        Args:
            module: The parsed module information.
            generated_docs: Mapping of item names to documentation.

        Returns:
            Markdown string for the module.
        """
        lines: list[str] = []

        # Module header
        lines.append(f"# `{module.file_path}`\n")

        # Module docstring
        docstring = generated_docs.get(module.file_path) or module.docstring
        if docstring:
            lines.append(f"{docstring}\n")

        # Metadata
        lines.append(f"**Language:** {module.language.value}  ")
        lines.append(f"**Lines:** {module.line_count}\n")

        # Functions
        if module.functions:
            lines.append("## Functions\n")
            for func in module.functions:
                lines.append(self._render_function(func, generated_docs))

        # Classes
        if module.classes:
            lines.append("## Classes\n")
            for cls in module.classes:
                lines.append(self._render_class(cls, generated_docs))

        # Imports
        if module.imports:
            lines.append("## Dependencies\n")
            for imp in module.imports:
                if imp.is_from_import:
                    names = ", ".join(imp.names)
                    lines.append(f"- `from {imp.module} import {names}`")
                else:
                    lines.append(f"- `import {imp.module}`")
            lines.append("")

        return "\n".join(lines)

    def _render_function(
        self, func: FunctionInfo, generated_docs: dict[str, str]
    ) -> str:
        """Render a function's documentation as Markdown.

        Args:
            func: The function information.
            generated_docs: Mapping of names to documentation.

        Returns:
            Markdown string for the function.
        """
        lines: list[str] = []

        # Signature
        params = ", ".join(self._format_param(p) for p in func.parameters)
        async_prefix = "async " if func.is_async else ""
        return_hint = f" -> {func.return_type}" if func.return_type else ""
        lines.append(f"### `{async_prefix}{func.name}({params}){return_hint}`\n")

        # Decorators
        if func.decorators:
            decs = ", ".join(f"`@{d}`" for d in func.decorators)
            lines.append(f"Decorators: {decs}\n")

        # Complexity
        if func.complexity is not None:
            lines.append(f"Complexity: **{func.complexity}**\n")

        # Docstring
        docstring = generated_docs.get(func.name) or func.docstring
        if docstring:
            lines.append(f"{docstring}\n")

        lines.append(f"*Lines {func.line_number}–{func.end_line_number}*\n")
        return "\n".join(lines)

    def _render_class(self, cls: ClassInfo, generated_docs: dict[str, str]) -> str:
        """Render a class's documentation as Markdown.

        Args:
            cls: The class information.
            generated_docs: Mapping of names to documentation.

        Returns:
            Markdown string for the class.
        """
        lines: list[str] = []

        # Class header
        bases = f"({', '.join(cls.base_classes)})" if cls.base_classes else ""
        lines.append(f"### `class {cls.name}{bases}`\n")

        if cls.decorators:
            decs = ", ".join(f"`@{d}`" for d in cls.decorators)
            lines.append(f"Decorators: {decs}\n")

        docstring = generated_docs.get(cls.name) or cls.docstring
        if docstring:
            lines.append(f"{docstring}\n")

        # Methods
        if cls.methods:
            lines.append("#### Methods\n")
            for method in cls.methods:
                lines.append(self._render_function(method, generated_docs))

        lines.append(f"*Lines {cls.line_number}–{cls.end_line_number}*\n")
        return "\n".join(lines)

    def _format_param(self, param: ParameterInfo) -> str:
        """Format a parameter for display in a function signature.

        Args:
            param: The parameter information.

        Returns:
            Formatted parameter string.
        """
        parts = []
        if param.is_args:
            parts.append(f"*{param.name}")
        elif param.is_kwargs:
            parts.append(f"**{param.name}")
        else:
            parts.append(param.name)

        if param.type_hint:
            parts[0] += f": {param.type_hint}"

        if param.default_value:
            parts[0] += f" = {param.default_value}"

        return parts[0]

    def _module_link(self, module: ModuleInfo) -> str:
        """Generate a relative link to a module's documentation file.

        Args:
            module: The module to link to.

        Returns:
            Relative path string for the link.
        """
        safe_name = module.file_path.replace("/", "_").replace("\\", "_")
        if safe_name.endswith(".py"):
            safe_name = safe_name[:-3]
        return f"{safe_name}.md"
