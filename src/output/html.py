"""HTML output generator compatible with MkDocs.

Generates mkdocs.yml configuration, proper directory structure,
and navigation for MkDocs-based documentation sites.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from src.output.markdown import MarkdownWriter
from src.parsers.structure import ModuleInfo

logger = logging.getLogger(__name__)


class HtmlWriter:
    """Generates MkDocs-compatible documentation structure.

    Creates the directory layout, writes Markdown files in the
    MkDocs docs/ format, and generates the mkdocs.yml config.
    """

    def __init__(self, output_dir: str = "site_docs") -> None:
        """Initialize the HTML writer.

        Args:
            output_dir: Root directory for MkDocs output.
        """
        self.output_dir = Path(output_dir)
        self.docs_dir = self.output_dir / "docs"

    def generate_mkdocs_config(
        self,
        project_name: str,
        modules: list[ModuleInfo],
        theme: str = "readthedocs",
    ) -> Path:
        """Generate the mkdocs.yml configuration file.

        Args:
            project_name: Name of the project for the site title.
            modules: List of documented modules for navigation.
            theme: MkDocs theme name.

        Returns:
            Path to the generated mkdocs.yml file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        nav = self._build_navigation(modules)

        config = {
            "site_name": f"{project_name} Documentation",
            "theme": {"name": theme},
            "nav": nav,
            "markdown_extensions": [
                "admonition",
                "codehilite",
                "toc",
            ],
        }

        config_path = self.output_dir / "mkdocs.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info("Generated mkdocs.yml at %s", config_path)
        return config_path

    def write_docs(
        self,
        modules: list[ModuleInfo],
        generated_docs: Optional[dict[str, str]] = None,
    ) -> Path:
        """Write all module documentation in MkDocs-compatible structure.

        Creates the docs/ directory with an index and per-module
        Markdown files organized by package hierarchy.

        Args:
            modules: List of parsed modules to document.
            generated_docs: Optional mapping of item names to docs.

        Returns:
            Path to the docs/ directory.
        """
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Write module files into appropriate subdirectories
        md_writer = MarkdownWriter(output_dir=str(self.docs_dir / "api"))

        for module in modules:
            md_writer.write_module_doc(module, generated_docs)

        md_writer.write_index(modules, title="API Reference")

        # Write the main index page
        self._write_main_index(modules)

        logger.info("Wrote MkDocs docs to %s (%d modules)", self.docs_dir, len(modules))
        return self.docs_dir

    def _write_main_index(self, modules: list[ModuleInfo]) -> Path:
        """Write the main index.md page for the documentation site.

        Args:
            modules: List of documented modules.

        Returns:
            Path to the main index.md file.
        """
        lines = ["# Welcome\n"]
        lines.append("Welcome to the project documentation.\n")
        lines.append("## Quick Links\n")
        lines.append("- [API Reference](api/index.md)\n")

        if modules:
            lines.append("## Modules\n")
            total_functions = sum(len(m.functions) for m in modules)
            total_classes = sum(len(m.classes) for m in modules)
            lines.append(f"- **{len(modules)}** modules documented")
            lines.append(f"- **{total_functions}** functions")
            lines.append(f"- **{total_classes}** classes")
            lines.append("")

        index_path = self.docs_dir / "index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        return index_path

    def _build_navigation(self, modules: list[ModuleInfo]) -> list:
        """Build the MkDocs navigation structure.

        Organizes modules into a nested navigation based on their
        file path hierarchy.

        Args:
            modules: List of documented modules.

        Returns:
            Navigation list for mkdocs.yml.
        """
        nav = [{"Home": "index.md"}]

        if modules:
            api_nav: list[dict[str, str]] = []
            api_nav.append({"Overview": "api/index.md"})

            for module in sorted(modules, key=lambda m: m.file_path):
                safe_name = module.file_path.replace("/", "_").replace("\\", "_")
                if safe_name.endswith(".py"):
                    safe_name = safe_name[:-3]
                label = module.file_path
                api_nav.append({label: f"api/{safe_name}.md"})

            nav.append({"API Reference": api_nav})

        return nav
