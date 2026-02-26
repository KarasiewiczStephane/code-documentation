"""Data models for representing parsed code structures.

Defines dataclasses for functions, classes, methods, parameters,
imports, modules, and dependency graphs. These models form the
shared vocabulary between parsers and documentation generators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


@dataclass
class ParameterInfo:
    """Represents a function or method parameter.

    Attributes:
        name: Parameter name.
        type_hint: Optional type annotation string.
        default_value: Optional default value as a string.
        is_args: Whether this is a *args parameter.
        is_kwargs: Whether this is a **kwargs parameter.
    """

    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_args: bool = False
    is_kwargs: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of this parameter.
        """
        return {
            "name": self.name,
            "type_hint": self.type_hint,
            "default_value": self.default_value,
            "is_args": self.is_args,
            "is_kwargs": self.is_kwargs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParameterInfo:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with parameter fields.

        Returns:
            A new ParameterInfo instance.
        """
        return cls(
            name=data["name"],
            type_hint=data.get("type_hint"),
            default_value=data.get("default_value"),
            is_args=data.get("is_args", False),
            is_kwargs=data.get("is_kwargs", False),
        )


@dataclass
class FunctionInfo:
    """Represents a parsed function or standalone method.

    Attributes:
        name: Function name.
        parameters: List of parameter definitions.
        return_type: Optional return type annotation string.
        docstring: Existing docstring if present.
        decorators: List of decorator names.
        is_async: Whether the function is async.
        line_number: Starting line number in the source file.
        end_line_number: Ending line number in the source file.
        complexity: Cyclomatic complexity score (filled by analysis).
        source: Raw source code of the function body.
    """

    name: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    line_number: int = 0
    end_line_number: int = 0
    complexity: Optional[int] = None
    source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of this function.
        """
        return {
            "name": self.name,
            "parameters": [p.to_dict() for p in self.parameters],
            "return_type": self.return_type,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "is_async": self.is_async,
            "line_number": self.line_number,
            "end_line_number": self.end_line_number,
            "complexity": self.complexity,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionInfo:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with function fields.

        Returns:
            A new FunctionInfo instance.
        """
        return cls(
            name=data["name"],
            parameters=[ParameterInfo.from_dict(p) for p in data.get("parameters", [])],
            return_type=data.get("return_type"),
            docstring=data.get("docstring"),
            decorators=data.get("decorators", []),
            is_async=data.get("is_async", False),
            line_number=data.get("line_number", 0),
            end_line_number=data.get("end_line_number", 0),
            complexity=data.get("complexity"),
            source=data.get("source"),
        )


@dataclass
class ClassInfo:
    """Represents a parsed class definition.

    Attributes:
        name: Class name.
        base_classes: List of base class names.
        methods: List of methods defined in the class.
        docstring: Existing class docstring if present.
        decorators: List of decorator names.
        line_number: Starting line number in the source file.
        end_line_number: Ending line number in the source file.
        source: Raw source code of the class.
    """

    name: str
    base_classes: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    line_number: int = 0
    end_line_number: int = 0
    source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of this class.
        """
        return {
            "name": self.name,
            "base_classes": self.base_classes,
            "methods": [m.to_dict() for m in self.methods],
            "docstring": self.docstring,
            "decorators": self.decorators,
            "line_number": self.line_number,
            "end_line_number": self.end_line_number,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassInfo:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with class fields.

        Returns:
            A new ClassInfo instance.
        """
        return cls(
            name=data["name"],
            base_classes=data.get("base_classes", []),
            methods=[FunctionInfo.from_dict(m) for m in data.get("methods", [])],
            docstring=data.get("docstring"),
            decorators=data.get("decorators", []),
            line_number=data.get("line_number", 0),
            end_line_number=data.get("end_line_number", 0),
            source=data.get("source"),
        )


@dataclass
class ImportInfo:
    """Represents an import statement.

    Attributes:
        module: The module being imported (e.g., 'os.path').
        names: List of imported names (e.g., ['join', 'exists']).
        alias: Optional alias for the import.
        is_from_import: Whether this is a 'from X import Y' style.
        line_number: Line number of the import statement.
    """

    module: str
    names: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from_import: bool = False
    line_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of this import.
        """
        return {
            "module": self.module,
            "names": self.names,
            "alias": self.alias,
            "is_from_import": self.is_from_import,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportInfo:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with import fields.

        Returns:
            A new ImportInfo instance.
        """
        return cls(
            module=data["module"],
            names=data.get("names", []),
            alias=data.get("alias"),
            is_from_import=data.get("is_from_import", False),
            line_number=data.get("line_number", 0),
        )


@dataclass
class ModuleInfo:
    """Represents a parsed source file / module.

    Attributes:
        file_path: Absolute or relative path to the source file.
        language: Programming language of the module.
        docstring: Module-level docstring if present.
        functions: Top-level functions defined in the module.
        classes: Classes defined in the module.
        imports: Import statements in the module.
        line_count: Total number of lines in the source file.
    """

    file_path: str
    language: Language = Language.PYTHON
    docstring: Optional[str] = None
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of this module.
        """
        return {
            "file_path": self.file_path,
            "language": self.language.value,
            "docstring": self.docstring,
            "functions": [f.to_dict() for f in self.functions],
            "classes": [c.to_dict() for c in self.classes],
            "imports": [i.to_dict() for i in self.imports],
            "line_count": self.line_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleInfo:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with module fields.

        Returns:
            A new ModuleInfo instance.
        """
        return cls(
            file_path=data["file_path"],
            language=Language(data.get("language", "python")),
            docstring=data.get("docstring"),
            functions=[FunctionInfo.from_dict(f) for f in data.get("functions", [])],
            classes=[ClassInfo.from_dict(c) for c in data.get("classes", [])],
            imports=[ImportInfo.from_dict(i) for i in data.get("imports", [])],
            line_count=data.get("line_count", 0),
        )


@dataclass
class DependencyGraph:
    """Tracks import relationships and function call graphs.

    Attributes:
        modules: Mapping of file paths to ModuleInfo objects.
        import_edges: List of (source_module, target_module) import relationships.
        call_edges: List of (caller_function, callee_function) call relationships.
    """

    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    import_edges: list[tuple[str, str]] = field(default_factory=list)
    call_edges: list[tuple[str, str]] = field(default_factory=list)

    def add_module(self, module: ModuleInfo) -> None:
        """Register a parsed module in the dependency graph.

        Args:
            module: The ModuleInfo to add.
        """
        self.modules[module.file_path] = module

    def add_import_edge(self, source: str, target: str) -> None:
        """Record an import relationship between two modules.

        Args:
            source: File path of the importing module.
            target: Module name or path being imported.
        """
        self.import_edges.append((source, target))

    def add_call_edge(self, caller: str, callee: str) -> None:
        """Record a function call relationship.

        Args:
            caller: Fully qualified name of the calling function.
            callee: Fully qualified name of the called function.
        """
        self.call_edges.append((caller, callee))

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get all modules that a given file imports.

        Args:
            file_path: Path of the module to query.

        Returns:
            List of imported module names/paths.
        """
        return [target for source, target in self.import_edges if source == file_path]

    def get_dependents(self, module_name: str) -> list[str]:
        """Get all modules that import a given module.

        Args:
            module_name: Name or path of the module to query.

        Returns:
            List of file paths that import this module.
        """
        return [source for source, target in self.import_edges if target == module_name]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary.

        Returns:
            Dictionary representation of the dependency graph.
        """
        return {
            "modules": {k: v.to_dict() for k, v in self.modules.items()},
            "import_edges": self.import_edges,
            "call_edges": self.call_edges,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyGraph:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with dependency graph fields.

        Returns:
            A new DependencyGraph instance.
        """
        graph = cls()
        for path, mod_data in data.get("modules", {}).items():
            graph.modules[path] = ModuleInfo.from_dict(mod_data)
        graph.import_edges = [tuple(e) for e in data.get("import_edges", [])]
        graph.call_edges = [tuple(e) for e in data.get("call_edges", [])]
        return graph
