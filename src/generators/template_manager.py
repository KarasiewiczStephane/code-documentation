"""Template manager for loading and rendering Jinja2 prompt templates.

Provides a centralized interface for rendering documentation prompts
from Jinja2 templates stored in the templates/ directory.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

from src.parsers.structure import ClassInfo, FunctionInfo, ModuleInfo

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


class TemplateManager:
    """Loads and renders Jinja2 prompt templates for documentation generation.

    Templates are loaded from a configurable directory and rendered
    with structured data from the parsing pipeline.
    """

    def __init__(self, templates_dir: Optional[str] = None) -> None:
        """Initialize the template manager.

        Args:
            templates_dir: Path to the templates directory. Uses the
                default templates/ directory if not specified.
        """
        self._templates_path = (
            Path(templates_dir) if templates_dir else _DEFAULT_TEMPLATES_DIR
        )

        if not self._templates_path.exists():
            logger.warning("Templates directory not found: %s", self._templates_path)

        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_path)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.debug("Template manager initialized with: %s", self._templates_path)

    def render_docstring_prompt(
        self,
        function: FunctionInfo,
        context: Optional[str] = None,
    ) -> str:
        """Render a docstring generation prompt for a function.

        Args:
            function: The function to generate a docstring for.
            context: Optional additional context about the function.

        Returns:
            Rendered prompt string ready for LLM submission.
        """
        return self._render(
            "docstring.j2",
            function=function,
            context=context,
        )

    def render_class_doc_prompt(
        self,
        class_info: ClassInfo,
        context: Optional[str] = None,
    ) -> str:
        """Render a class documentation prompt.

        Args:
            class_info: The class to generate documentation for.
            context: Optional additional context about the class.

        Returns:
            Rendered prompt string ready for LLM submission.
        """
        return self._render(
            "class_doc.j2",
            class_info=class_info,
            context=context,
        )

    def render_module_doc_prompt(
        self,
        module: ModuleInfo,
    ) -> str:
        """Render a module documentation prompt.

        Args:
            module: The module to generate documentation for.

        Returns:
            Rendered prompt string ready for LLM submission.
        """
        return self._render("module_doc.j2", module=module)

    def render_readme_prompt(
        self,
        project_name: str,
        modules: Optional[list[ModuleInfo]] = None,
        description: Optional[str] = None,
        entry_points: Optional[list[str]] = None,
        dependencies: Optional[list[str]] = None,
        structure: Optional[str] = None,
    ) -> str:
        """Render a README generation prompt.

        Args:
            project_name: Name of the project.
            modules: List of parsed modules in the project.
            description: Optional project description.
            entry_points: Optional list of entry point files.
            dependencies: Optional list of project dependencies.
            structure: Optional project directory structure string.

        Returns:
            Rendered prompt string ready for LLM submission.
        """
        return self._render(
            "readme.j2",
            project_name=project_name,
            modules=modules or [],
            description=description,
            entry_points=entry_points,
            dependencies=dependencies,
            structure=structure,
        )

    def _render(self, template_name: str, **kwargs: Any) -> str:
        """Render a template with the given context variables.

        Args:
            template_name: Name of the template file to render.
            **kwargs: Template context variables.

        Returns:
            Rendered template string.

        Raises:
            TemplateNotFound: If the template file does not exist.
        """
        template = self._env.get_template(template_name)
        rendered = template.render(**kwargs)
        logger.debug("Rendered template %s (%d chars)", template_name, len(rendered))
        return rendered

    def list_templates(self) -> list[str]:
        """List all available template files.

        Returns:
            List of template file names.
        """
        return self._env.list_templates()
