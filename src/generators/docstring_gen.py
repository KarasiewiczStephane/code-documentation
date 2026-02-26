"""Docstring generation pipeline using LLM and templates.

Orchestrates the generation of Google-style docstrings for functions,
classes, and modules by building context, rendering prompts via
Jinja2 templates, and calling the Claude API.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.generators.llm_client import LLMClient
from src.generators.template_manager import TemplateManager
from src.parsers.structure import ClassInfo, FunctionInfo, ModuleInfo

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert Python developer writing documentation. "
    "Generate clear, concise, and accurate documentation following "
    "Google Python style guide conventions. Return only the requested "
    "content without any wrapper formatting or explanation."
)


@dataclass
class DocstringResult:
    """Result of a docstring generation for a single item.

    Attributes:
        name: Name of the function, class, or module.
        docstring: The generated docstring text.
        input_tokens: Tokens used in the prompt.
        output_tokens: Tokens used in the response.
    """

    name: str
    docstring: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ModuleDocResult:
    """Aggregate result of documentation generation for a module.

    Attributes:
        file_path: Path of the documented module.
        module_doc: Generated module-level documentation.
        function_docs: Per-function docstring results.
        class_docs: Per-class documentation results.
        total_input_tokens: Total input tokens across all calls.
        total_output_tokens: Total output tokens across all calls.
    """

    file_path: str
    module_doc: Optional[DocstringResult] = None
    function_docs: list[DocstringResult] = field(default_factory=list)
    class_docs: list[DocstringResult] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class DocstringGenerator:
    """Generates docstrings for functions, classes, and modules.

    Uses the LLM client and Jinja2 templates to produce Google-style
    docstrings for Python code structures. Supports single-item and
    batch generation modes.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        template_manager: Optional[TemplateManager] = None,
    ) -> None:
        """Initialize the docstring generator.

        Args:
            llm_client: The LLM client for API calls.
            template_manager: Template manager for prompts. Creates
                a default instance if not provided.
        """
        self.llm = llm_client
        self.templates = template_manager or TemplateManager()

    def generate_docstring(
        self,
        function: FunctionInfo,
        context: Optional[str] = None,
    ) -> DocstringResult:
        """Generate a docstring for a single function.

        Args:
            function: The function to document.
            context: Optional additional context.

        Returns:
            A DocstringResult with the generated docstring.
        """
        prompt = self.templates.render_docstring_prompt(function, context=context)
        result = self.llm.generate(prompt, system=_SYSTEM_PROMPT)

        logger.info("Generated docstring for function: %s", function.name)
        return DocstringResult(
            name=function.name,
            docstring=result.content.strip(),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    def generate_class_doc(
        self,
        class_info: ClassInfo,
        context: Optional[str] = None,
    ) -> DocstringResult:
        """Generate documentation for a class.

        Args:
            class_info: The class to document.
            context: Optional additional context.

        Returns:
            A DocstringResult with the generated class documentation.
        """
        prompt = self.templates.render_class_doc_prompt(class_info, context=context)
        result = self.llm.generate(prompt, system=_SYSTEM_PROMPT)

        logger.info("Generated documentation for class: %s", class_info.name)
        return DocstringResult(
            name=class_info.name,
            docstring=result.content.strip(),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    def generate_module_doc(
        self,
        module: ModuleInfo,
    ) -> DocstringResult:
        """Generate module-level documentation.

        Args:
            module: The module to document.

        Returns:
            A DocstringResult with the generated module documentation.
        """
        prompt = self.templates.render_module_doc_prompt(module)
        result = self.llm.generate(prompt, system=_SYSTEM_PROMPT)

        logger.info("Generated documentation for module: %s", module.file_path)
        return DocstringResult(
            name=module.file_path,
            docstring=result.content.strip(),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    def generate_all(
        self,
        module: ModuleInfo,
        skip_existing: bool = True,
    ) -> ModuleDocResult:
        """Generate documentation for all items in a module.

        Processes the module docstring, all top-level functions, and
        all classes. Optionally skips items that already have docstrings.

        Args:
            module: The module to fully document.
            skip_existing: If True, skip items that already have docstrings.

        Returns:
            A ModuleDocResult with all generated documentation.
        """
        result = ModuleDocResult(file_path=module.file_path)

        # Module-level doc
        if not skip_existing or not module.docstring:
            mod_doc = self.generate_module_doc(module)
            result.module_doc = mod_doc
            result.total_input_tokens += mod_doc.input_tokens
            result.total_output_tokens += mod_doc.output_tokens

        # Functions
        for func in module.functions:
            if skip_existing and func.docstring:
                logger.debug("Skipping %s (has docstring)", func.name)
                continue
            doc = self.generate_docstring(func)
            result.function_docs.append(doc)
            result.total_input_tokens += doc.input_tokens
            result.total_output_tokens += doc.output_tokens

        # Classes
        for cls in module.classes:
            if skip_existing and cls.docstring:
                logger.debug("Skipping class %s (has docstring)", cls.name)
                continue
            doc = self.generate_class_doc(cls)
            result.class_docs.append(doc)
            result.total_input_tokens += doc.input_tokens
            result.total_output_tokens += doc.output_tokens

        logger.info(
            "Generated docs for %s: %d functions, %d classes",
            module.file_path,
            len(result.function_docs),
            len(result.class_docs),
        )
        return result
