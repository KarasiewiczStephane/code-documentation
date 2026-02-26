"""JavaScript and TypeScript parser using tree-sitter.

Extracts functions, classes, exports, JSDoc comments, and type
annotations from JS/TS source files into the shared data models.
"""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts

from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)

logger = logging.getLogger(__name__)

_JS_LANGUAGE = tree_sitter.Language(tsjs.language())
_TS_LANGUAGE = tree_sitter.Language(tsts.language_typescript())

# Node types that represent function-like declarations
_FUNC_TYPES = {
    "function_declaration",
    "generator_function_declaration",
}
_METHOD_TYPES = {
    "method_definition",
}
_ARROW_TYPES = {
    "arrow_function",
}


class JSParser:
    """Parses JavaScript and TypeScript source files using tree-sitter.

    Extracts functions, classes, methods, imports, exports, JSDoc
    comments, and TypeScript type annotations.
    """

    def parse_file(self, file_path: str) -> ModuleInfo:
        """Parse a JavaScript or TypeScript file and extract its structure.

        Args:
            file_path: Path to the JS/TS file to parse.

        Returns:
            A ModuleInfo object containing all extracted structures.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source = path.read_text(encoding="utf-8")
        language = self._detect_language(path)
        return self.parse_source(source, file_path, language)

    def parse_source(
        self,
        source: str,
        file_path: str = "<string>",
        language: Language = Language.JAVASCRIPT,
    ) -> ModuleInfo:
        """Parse JS/TS source code string and extract its structure.

        Args:
            source: JavaScript or TypeScript source code.
            file_path: Optional file path for reference.
            language: Language variant (JAVASCRIPT or TYPESCRIPT).

        Returns:
            A ModuleInfo object containing all extracted structures.
        """
        ts_lang = _TS_LANGUAGE if language == Language.TYPESCRIPT else _JS_LANGUAGE
        parser = tree_sitter.Parser(ts_lang)
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node
        source_bytes = source.encode("utf-8")

        module = ModuleInfo(
            file_path=file_path,
            language=language,
            line_count=len(source.splitlines()),
        )

        for child in root.children:
            self._process_node(child, module, source_bytes, source)

        logger.debug(
            "Parsed %s: %d functions, %d classes, %d imports",
            file_path,
            len(module.functions),
            len(module.classes),
            len(module.imports),
        )
        return module

    def _process_node(
        self,
        node: tree_sitter.Node,
        module: ModuleInfo,
        source_bytes: bytes,
        source: str,
    ) -> None:
        """Process a top-level AST node and add results to the module.

        Args:
            node: A tree-sitter Node to process.
            module: The ModuleInfo to populate.
            source_bytes: Source as bytes for text extraction.
            source: Original source string.
        """
        node_type = node.type

        if node_type in _FUNC_TYPES:
            func = self._extract_function(node, source_bytes, source)
            if func:
                module.functions.append(func)

        elif node_type == "class_declaration":
            cls = self._extract_class(node, source_bytes, source)
            if cls:
                module.classes.append(cls)

        elif node_type == "import_statement":
            imp = self._extract_import(node, source_bytes)
            if imp:
                module.imports.append(imp)

        elif node_type == "export_statement":
            self._process_export(node, module, source_bytes, source)

        elif node_type == "lexical_declaration":
            # Handle: const foo = () => {} or const foo = function() {}
            for decl in self._iter_children_of_type(node, "variable_declarator"):
                self._process_variable_declarator(decl, module, source_bytes, source)

    def _process_export(
        self,
        node: tree_sitter.Node,
        module: ModuleInfo,
        source_bytes: bytes,
        source: str,
    ) -> None:
        """Process an export statement, extracting its declaration.

        Args:
            node: An export_statement node.
            module: The ModuleInfo to populate.
            source_bytes: Source as bytes.
            source: Original source string.
        """
        for child in node.children:
            if child.type in _FUNC_TYPES:
                func = self._extract_function(child, source_bytes, source)
                if func:
                    module.functions.append(func)
            elif child.type == "class_declaration":
                cls = self._extract_class(child, source_bytes, source)
                if cls:
                    module.classes.append(cls)
            elif child.type == "lexical_declaration":
                for decl in self._iter_children_of_type(child, "variable_declarator"):
                    self._process_variable_declarator(
                        decl, module, source_bytes, source
                    )

    def _process_variable_declarator(
        self,
        node: tree_sitter.Node,
        module: ModuleInfo,
        source_bytes: bytes,
        source: str,
    ) -> None:
        """Process a variable declarator that may contain an arrow function.

        Args:
            node: A variable_declarator node.
            module: The ModuleInfo to populate.
            source_bytes: Source as bytes.
            source: Original source string.
        """
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")

        if not name_node or not value_node:
            return

        if value_node.type in _ARROW_TYPES or value_node.type == "function":
            name = self._node_text(name_node, source_bytes)
            func = self._extract_arrow_or_expr_function(
                name, value_node, node, source_bytes, source
            )
            if func:
                module.functions.append(func)

    def _extract_function(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        source: str,
    ) -> Optional[FunctionInfo]:
        """Extract a function declaration node into FunctionInfo.

        Args:
            node: A function_declaration tree-sitter node.
            source_bytes: Source as bytes.
            source: Original source string.

        Returns:
            A FunctionInfo, or None if extraction fails.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._node_text(name_node, source_bytes)
        params = self._extract_parameters(node, source_bytes)
        return_type = self._extract_return_type(node, source_bytes)
        is_async = any(c.type == "async" for c in node.children)
        docstring = self._extract_jsdoc(node, source)
        func_source = self._node_text(node, source_bytes)

        return FunctionInfo(
            name=name,
            parameters=params,
            return_type=return_type,
            docstring=docstring,
            is_async=is_async,
            line_number=node.start_point.row + 1,
            end_line_number=node.end_point.row + 1,
            source=func_source,
        )

    def _extract_arrow_or_expr_function(
        self,
        name: str,
        value_node: tree_sitter.Node,
        declarator_node: tree_sitter.Node,
        source_bytes: bytes,
        source: str,
    ) -> Optional[FunctionInfo]:
        """Extract an arrow function or function expression.

        Args:
            name: The variable name assigned to the function.
            value_node: The arrow_function or function node.
            declarator_node: The parent variable_declarator node.
            source_bytes: Source as bytes.
            source: Original source string.

        Returns:
            A FunctionInfo, or None if extraction fails.
        """
        params = self._extract_parameters(value_node, source_bytes)
        return_type = self._extract_return_type(value_node, source_bytes)
        is_async = any(c.type == "async" for c in value_node.children)
        docstring = self._extract_jsdoc(declarator_node.parent, source)
        func_source = self._node_text(declarator_node.parent, source_bytes)

        return FunctionInfo(
            name=name,
            parameters=params,
            return_type=return_type,
            docstring=docstring,
            is_async=is_async,
            line_number=declarator_node.start_point.row + 1,
            end_line_number=value_node.end_point.row + 1,
            source=func_source,
        )

    def _extract_class(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        source: str,
    ) -> Optional[ClassInfo]:
        """Extract a class declaration into ClassInfo.

        Args:
            node: A class_declaration tree-sitter node.
            source_bytes: Source as bytes.
            source: Original source string.

        Returns:
            A ClassInfo, or None if extraction fails.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._node_text(name_node, source_bytes)

        # Extract base class (extends)
        base_classes = []
        for child in node.children:
            if child.type == "class_heritage":
                heritage_text = self._node_text(child, source_bytes)
                # Remove 'extends ' prefix
                base_name = heritage_text.replace("extends ", "").strip()
                if base_name:
                    base_classes.append(base_name)

        # Extract methods from class body
        methods = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type in _METHOD_TYPES:
                    method = self._extract_method(child, source_bytes, source)
                    if method:
                        methods.append(method)

        docstring = self._extract_jsdoc(node, source)
        class_source = self._node_text(node, source_bytes)

        return ClassInfo(
            name=name,
            base_classes=base_classes,
            methods=methods,
            docstring=docstring,
            line_number=node.start_point.row + 1,
            end_line_number=node.end_point.row + 1,
            source=class_source,
        )

    def _extract_method(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        source: str,
    ) -> Optional[FunctionInfo]:
        """Extract a class method definition.

        Args:
            node: A method_definition tree-sitter node.
            source_bytes: Source as bytes.
            source: Original source string.

        Returns:
            A FunctionInfo for the method, or None.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._node_text(name_node, source_bytes)
        params = self._extract_parameters(node, source_bytes)
        return_type = self._extract_return_type(node, source_bytes)
        is_async = any(c.type == "async" for c in node.children)
        decorators = []

        # Check for getter/setter
        for child in node.children:
            if child.type == "get":
                decorators.append("getter")
            elif child.type == "set":
                decorators.append("setter")
            elif child.type == "static":
                decorators.append("static")

        docstring = self._extract_jsdoc(node, source)
        method_source = self._node_text(node, source_bytes)

        return FunctionInfo(
            name=name,
            parameters=params,
            return_type=return_type,
            docstring=docstring,
            decorators=decorators,
            is_async=is_async,
            line_number=node.start_point.row + 1,
            end_line_number=node.end_point.row + 1,
            source=method_source,
        )

    def _extract_parameters(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> list[ParameterInfo]:
        """Extract function parameters from a function-like node.

        Args:
            node: A function or method tree-sitter node.
            source_bytes: Source as bytes.

        Returns:
            List of ParameterInfo objects.
        """
        params: list[ParameterInfo] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in (
                "identifier",
                "required_parameter",
                "optional_parameter",
            ):
                param = self._parse_single_param(child, source_bytes)
                if param:
                    params.append(param)
            elif child.type in ("rest_parameter", "rest_pattern"):
                param = self._parse_rest_param(child, source_bytes)
                if param:
                    params.append(param)

        return params

    def _parse_single_param(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> Optional[ParameterInfo]:
        """Parse a single parameter node.

        Args:
            node: An identifier, required_parameter, or optional_parameter node.
            source_bytes: Source as bytes.

        Returns:
            A ParameterInfo, or None.
        """
        if node.type == "identifier":
            return ParameterInfo(name=self._node_text(node, source_bytes))

        # required_parameter or optional_parameter
        name = None
        type_hint = None
        default_value = None

        pattern_node = node.child_by_field_name("pattern")
        if pattern_node:
            name = self._node_text(pattern_node, source_bytes)
        else:
            # Try first identifier child
            for child in node.children:
                if child.type == "identifier":
                    name = self._node_text(child, source_bytes)
                    break

        type_node = node.child_by_field_name("type")
        if type_node:
            type_hint = self._node_text(type_node, source_bytes)
            # Strip leading ': ' from type annotations
            if type_hint.startswith(": "):
                type_hint = type_hint[2:]

        value_node = node.child_by_field_name("value")
        if value_node:
            default_value = self._node_text(value_node, source_bytes)

        if not name:
            return None

        return ParameterInfo(
            name=name,
            type_hint=type_hint,
            default_value=default_value,
        )

    def _parse_rest_param(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> Optional[ParameterInfo]:
        """Parse a rest parameter (...args).

        Args:
            node: A rest_parameter tree-sitter node.
            source_bytes: Source as bytes.

        Returns:
            A ParameterInfo with is_args=True, or None.
        """
        for child in node.children:
            if child.type == "identifier":
                return ParameterInfo(
                    name=self._node_text(child, source_bytes),
                    is_args=True,
                )
        return None

    def _extract_return_type(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> Optional[str]:
        """Extract the return type annotation from a function node.

        Args:
            node: A function-like tree-sitter node.
            source_bytes: Source as bytes.

        Returns:
            Return type string, or None.
        """
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            text = self._node_text(return_type_node, source_bytes)
            # Strip leading ': ' from type annotations
            if text.startswith(": "):
                text = text[2:]
            return text
        return None

    def _extract_import(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> Optional[ImportInfo]:
        """Extract an import statement.

        Args:
            node: An import_statement tree-sitter node.
            source_bytes: Source as bytes.

        Returns:
            An ImportInfo, or None.
        """
        source_node = node.child_by_field_name("source")
        if not source_node:
            return None

        module = self._node_text(source_node, source_bytes).strip("'\"")
        names: list[str] = []

        for child in node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "identifier":
                        names.append(self._node_text(sub, source_bytes))
                    elif sub.type == "named_imports":
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    names.append(
                                        self._node_text(name_node, source_bytes)
                                    )

        return ImportInfo(
            module=module,
            names=names,
            is_from_import=True,
            line_number=node.start_point.row + 1,
        )

    def _extract_jsdoc(self, node: tree_sitter.Node, source: str) -> Optional[str]:
        """Extract JSDoc comment preceding a node.

        Looks for a block comment (/** ... */) immediately before the
        node in the source code.

        Args:
            node: The tree-sitter node to find JSDoc for.
            source: Original source string.

        Returns:
            Cleaned JSDoc text, or None if not found.
        """
        # Check the previous sibling for a comment
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = source[prev.start_byte : prev.end_byte]
            if text.startswith("/**"):
                return self._clean_jsdoc(text)
        return None

    def _clean_jsdoc(self, raw: str) -> str:
        """Clean a raw JSDoc comment string.

        Removes comment delimiters and leading asterisks.

        Args:
            raw: Raw JSDoc comment string including delimiters.

        Returns:
            Cleaned documentation text.
        """
        # Remove /** and */
        text = raw.strip()
        if text.startswith("/**"):
            text = text[3:]
        if text.endswith("*/"):
            text = text[:-2]
        # Remove leading * from each line
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if line.startswith("* "):
                line = line[2:]
            elif line == "*":
                line = ""
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _detect_language(self, path: Path) -> Language:
        """Detect whether a file is JavaScript or TypeScript.

        Args:
            path: File path to check.

        Returns:
            Language.TYPESCRIPT for .ts/.tsx files, JAVASCRIPT otherwise.
        """
        if path.suffix in (".ts", ".tsx"):
            return Language.TYPESCRIPT
        return Language.JAVASCRIPT

    def _node_text(self, node: tree_sitter.Node, source_bytes: bytes) -> str:
        """Extract the text content of a tree-sitter node.

        Args:
            node: A tree-sitter Node.
            source_bytes: Source as bytes.

        Returns:
            The text content of the node.
        """
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def _iter_children_of_type(
        self, node: tree_sitter.Node, type_name: str
    ) -> list[tree_sitter.Node]:
        """Get all direct children of a node with a specific type.

        Args:
            node: Parent tree-sitter node.
            type_name: Node type to filter by.

        Returns:
            List of matching child nodes.
        """
        return [c for c in node.children if c.type == type_name]
