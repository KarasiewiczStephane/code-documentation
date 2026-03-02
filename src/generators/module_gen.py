"""Module-level documentation generator using LLM and templates.

Orchestrates the generation of comprehensive per-module documentation by
combining parsed structures with LLM-generated content, including module
summaries, function docs, and class docs.
"""

import logging
from typing import Optional

from src.generators.docstring_gen import (
    DocstringGenerator,
    DocstringResult,
    ModuleDocResult,
)
from src.generators.llm_client import LLMClient
from src.generators.template_manager import TemplateManager
from src.parsers.structure import ModuleInfo

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert Python developer writing documentation. "
    "Generate clear, concise, and accurate documentation following "
    "Google Python style guide conventions. Return only the requested "
    "content without any wrapper formatting or explanation."
)


class ModuleDocGenerator:
    """Generates comprehensive per-module documentation.

    Combines LLM-generated module summaries with individual function
    and class documentation to produce complete module documentation
    suitable for standalone viewing or integration into larger docs.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        template_manager: Optional[TemplateManager] = None,
    ) -> None:
        """Initialize the module documentation generator.

        Args:
            llm_client: The LLM client for API calls.
            template_manager: Template manager for prompts. Creates
                a default instance if not provided.
        """
        self.llm = llm_client
        self.templates = template_manager or TemplateManager()
        self.docstring_gen = DocstringGenerator(llm_client, self.templates)

    def generate(
        self,
        module: ModuleInfo,
        include_source: bool = False,
        skip_existing: bool = True,
    ) -> ModuleDocResult:
        """Generate comprehensive documentation for a module.

        Produces a module-level summary, generates docstrings for all
        functions and classes, and aggregates token usage statistics.

        Args:
            module: The parsed module to document.
            include_source: Whether to include source code in context.
            skip_existing: If True, skip items that already have docstrings.

        Returns:
            A ModuleDocResult with all generated documentation.
        """
        result = ModuleDocResult(file_path=module.file_path)

        # Generate module-level summary
        module_summary = self._generate_module_summary(module)
        result.module_doc = module_summary
        result.total_input_tokens += module_summary.input_tokens
        result.total_output_tokens += module_summary.output_tokens

        # Generate docs for all functions
        for func in module.functions:
            if skip_existing and func.docstring:
                logger.debug("Skipping %s (has docstring)", func.name)
                continue
            context = self._build_function_context(module) if include_source else None
            doc = self.docstring_gen.generate_docstring(func, context=context)
            result.function_docs.append(doc)
            result.total_input_tokens += doc.input_tokens
            result.total_output_tokens += doc.output_tokens

        # Generate docs for all classes
        for cls in module.classes:
            if skip_existing and cls.docstring:
                logger.debug("Skipping class %s (has docstring)", cls.name)
                continue
            context = self._build_class_context(module) if include_source else None
            doc = self.docstring_gen.generate_class_doc(cls, context=context)
            result.class_docs.append(doc)
            result.total_input_tokens += doc.input_tokens
            result.total_output_tokens += doc.output_tokens

        logger.info(
            "Generated module docs for %s: %d functions, %d classes",
            module.file_path,
            len(result.function_docs),
            len(result.class_docs),
        )
        return result

    def generate_batch(
        self,
        modules: list[ModuleInfo],
        include_source: bool = False,
        skip_existing: bool = True,
    ) -> list[ModuleDocResult]:
        """Generate documentation for multiple modules.

        Args:
            modules: List of parsed modules to document.
            include_source: Whether to include source code in context.
            skip_existing: If True, skip items that already have docstrings.

        Returns:
            List of ModuleDocResult for each processed module.
        """
        results = []
        for module in modules:
            result = self.generate(
                module,
                include_source=include_source,
                skip_existing=skip_existing,
            )
            results.append(result)

        total_input = sum(r.total_input_tokens for r in results)
        total_output = sum(r.total_output_tokens for r in results)
        logger.info(
            "Generated docs for %d modules (tokens: %d input, %d output)",
            len(results),
            total_input,
            total_output,
        )
        return results

    def _generate_module_summary(self, module: ModuleInfo) -> DocstringResult:
        """Generate a module-level summary via the LLM.

        Args:
            module: The module to summarize.

        Returns:
            A DocstringResult with the generated summary.
        """
        prompt = self.templates.render_module_doc_prompt(module)
        result = self.llm.generate(prompt, system=_SYSTEM_PROMPT)

        logger.info("Generated summary for module: %s", module.file_path)
        return DocstringResult(
            name=module.file_path,
            docstring=result.content.strip(),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    def _build_function_context(self, module: ModuleInfo) -> str:
        """Build context string for function documentation.

        Args:
            module: The module containing the function.

        Returns:
            A context string with module-level information.
        """
        parts = [f"This function is defined in module: {module.file_path}"]
        if module.docstring:
            parts.append(f"Module purpose: {module.docstring}")
        if module.imports:
            import_names = [imp.module for imp in module.imports[:10]]
            parts.append(f"Module dependencies: {', '.join(import_names)}")
        return "\n".join(parts)

    def _build_class_context(self, module: ModuleInfo) -> str:
        """Build context string for class documentation.

        Args:
            module: The module containing the class.

        Returns:
            A context string with module-level information.
        """
        parts = [f"This class is defined in module: {module.file_path}"]
        if module.docstring:
            parts.append(f"Module purpose: {module.docstring}")
        return "\n".join(parts)
