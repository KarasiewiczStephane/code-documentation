"""Python source code parser using the ast module.

Extracts functions, classes, methods, decorators, type hints,
docstrings, and imports from Python source files into the
shared structure data models.
"""

import ast
import logging
from pathlib import Path
from typing import Optional

from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)

logger = logging.getLogger(__name__)


class PythonParser:
    """Parses Python source files into ModuleInfo structures.

    Uses the built-in ast module to walk the syntax tree and
    extract all relevant code structures including functions,
    classes, imports, decorators, type hints, and docstrings.
    """

    def parse_file(self, file_path: str) -> ModuleInfo:
        """Parse a Python source file and extract its structure.

        Args:
            file_path: Path to the Python file to parse.

        Returns:
            A ModuleInfo object containing all extracted structures.

        Raises:
            FileNotFoundError: If the file does not exist.
            SyntaxError: If the file contains invalid Python syntax.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source = path.read_text(encoding="utf-8")
        return self.parse_source(source, file_path)

    def parse_source(self, source: str, file_path: str = "<string>") -> ModuleInfo:
        """Parse Python source code string and extract its structure.

        Args:
            source: Python source code as a string.
            file_path: Optional file path for reference in the result.

        Returns:
            A ModuleInfo object containing all extracted structures.

        Raises:
            SyntaxError: If the source contains invalid Python syntax.
        """
        tree = ast.parse(source, filename=file_path)
        lines = source.splitlines()

        module = ModuleInfo(
            file_path=file_path,
            language=Language.PYTHON,
            docstring=ast.get_docstring(tree),
            line_count=len(lines),
        )

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module.functions.append(self._extract_function(node, source))
            elif isinstance(node, ast.ClassDef):
                module.classes.append(self._extract_class(node, source))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                module.imports.extend(self._extract_import(node))

        logger.debug(
            "Parsed %s: %d functions, %d classes, %d imports",
            file_path,
            len(module.functions),
            len(module.classes),
            len(module.imports),
        )
        return module

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
    ) -> FunctionInfo:
        """Extract function information from an AST node.

        Args:
            node: An ast.FunctionDef or ast.AsyncFunctionDef node.
            source: Full source code for extracting the function body.

        Returns:
            A FunctionInfo object with all extracted details.
        """
        parameters = self._extract_parameters(node.args)
        return_type = self._annotation_to_str(node.returns) if node.returns else None
        decorators = [self._decorator_to_str(d) for d in node.decorator_list]
        func_source = self._get_source_segment(source, node)

        return FunctionInfo(
            name=node.name,
            parameters=parameters,
            return_type=return_type,
            docstring=ast.get_docstring(node),
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            line_number=node.lineno,
            end_line_number=node.end_lineno or node.lineno,
            source=func_source,
        )

    def _extract_class(self, node: ast.ClassDef, source: str) -> ClassInfo:
        """Extract class information from an AST node.

        Args:
            node: An ast.ClassDef node.
            source: Full source code for extracting source segments.

        Returns:
            A ClassInfo object with methods, bases, and metadata.
        """
        base_classes = [self._annotation_to_str(base) for base in node.bases]
        decorators = [self._decorator_to_str(d) for d in node.decorator_list]

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function(item, source))

        class_source = self._get_source_segment(source, node)

        return ClassInfo(
            name=node.name,
            base_classes=base_classes,
            methods=methods,
            docstring=ast.get_docstring(node),
            decorators=decorators,
            line_number=node.lineno,
            end_line_number=node.end_lineno or node.lineno,
            source=class_source,
        )

    def _extract_parameters(self, args: ast.arguments) -> list[ParameterInfo]:
        """Extract parameter information from function arguments.

        Handles regular args, defaults, *args, and **kwargs.

        Args:
            args: The ast.arguments node from a function definition.

        Returns:
            List of ParameterInfo objects for each parameter.
        """
        parameters: list[ParameterInfo] = []

        # Regular positional arguments
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for i, arg in enumerate(args.args):
            default_idx = i - default_offset
            default_value = None
            if default_idx >= 0:
                default_value = self._node_to_str(args.defaults[default_idx])

            parameters.append(
                ParameterInfo(
                    name=arg.arg,
                    type_hint=self._annotation_to_str(arg.annotation)
                    if arg.annotation
                    else None,
                    default_value=default_value,
                )
            )

        # *args
        if args.vararg:
            parameters.append(
                ParameterInfo(
                    name=args.vararg.arg,
                    type_hint=self._annotation_to_str(args.vararg.annotation)
                    if args.vararg.annotation
                    else None,
                    is_args=True,
                )
            )

        # keyword-only arguments
        for i, arg in enumerate(args.kwonlyargs):
            default_value = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default_value = self._node_to_str(args.kw_defaults[i])

            parameters.append(
                ParameterInfo(
                    name=arg.arg,
                    type_hint=self._annotation_to_str(arg.annotation)
                    if arg.annotation
                    else None,
                    default_value=default_value,
                )
            )

        # **kwargs
        if args.kwarg:
            parameters.append(
                ParameterInfo(
                    name=args.kwarg.arg,
                    type_hint=self._annotation_to_str(args.kwarg.annotation)
                    if args.kwarg.annotation
                    else None,
                    is_kwargs=True,
                )
            )

        return parameters

    def _extract_import(self, node: ast.Import | ast.ImportFrom) -> list[ImportInfo]:
        """Extract import information from an import AST node.

        Args:
            node: An ast.Import or ast.ImportFrom node.

        Returns:
            List of ImportInfo objects (one per import statement).
        """
        imports: list[ImportInfo] = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        is_from_import=False,
                        line_number=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(
                ImportInfo(
                    module=module,
                    names=names,
                    is_from_import=True,
                    line_number=node.lineno,
                )
            )

        return imports

    def _annotation_to_str(self, node: Optional[ast.expr]) -> Optional[str]:
        """Convert a type annotation AST node to its string representation.

        Args:
            node: An AST expression node representing a type annotation.

        Returns:
            String representation of the annotation, or None.
        """
        if node is None:
            return None
        return ast.unparse(node)

    def _decorator_to_str(self, node: ast.expr) -> str:
        """Convert a decorator AST node to its string representation.

        Args:
            node: An AST expression node representing a decorator.

        Returns:
            String representation of the decorator (without @).
        """
        return ast.unparse(node)

    def _node_to_str(self, node: ast.expr) -> str:
        """Convert an AST expression node to its string representation.

        Args:
            node: Any AST expression node.

        Returns:
            String representation of the expression.
        """
        return ast.unparse(node)

    def _get_source_segment(self, source: str, node: ast.AST) -> Optional[str]:
        """Extract the source code segment for an AST node.

        Args:
            source: Full source code of the file.
            node: AST node with lineno and end_lineno attributes.

        Returns:
            The source code segment, or None if extraction fails.
        """
        try:
            return ast.get_source_segment(source, node)
        except Exception:
            return None
