"""Tests for code structure data models and serialization."""

import json

from src.parsers.structure import (
    ClassInfo,
    DependencyGraph,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ParameterInfo,
)


class TestParameterInfo:
    """Tests for ParameterInfo dataclass."""

    def test_basic_parameter(self) -> None:
        param = ParameterInfo(name="x", type_hint="int")
        assert param.name == "x"
        assert param.type_hint == "int"
        assert param.default_value is None
        assert param.is_args is False

    def test_args_parameter(self) -> None:
        param = ParameterInfo(name="args", is_args=True)
        assert param.is_args is True

    def test_kwargs_parameter(self) -> None:
        param = ParameterInfo(name="kwargs", is_kwargs=True)
        assert param.is_kwargs is True

    def test_default_value(self) -> None:
        param = ParameterInfo(name="x", default_value="42")
        assert param.default_value == "42"

    def test_to_dict(self) -> None:
        param = ParameterInfo(name="x", type_hint="int", default_value="0")
        d = param.to_dict()
        assert d["name"] == "x"
        assert d["type_hint"] == "int"
        assert d["default_value"] == "0"

    def test_from_dict(self) -> None:
        data = {"name": "y", "type_hint": "str", "is_kwargs": True}
        param = ParameterInfo.from_dict(data)
        assert param.name == "y"
        assert param.type_hint == "str"
        assert param.is_kwargs is True

    def test_roundtrip(self) -> None:
        original = ParameterInfo(name="data", type_hint="list[int]", is_args=True)
        restored = ParameterInfo.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.type_hint == original.type_hint
        assert restored.is_args == original.is_args


class TestFunctionInfo:
    """Tests for FunctionInfo dataclass."""

    def test_basic_function(self) -> None:
        func = FunctionInfo(name="my_func", line_number=10)
        assert func.name == "my_func"
        assert func.parameters == []
        assert func.is_async is False

    def test_async_function(self) -> None:
        func = FunctionInfo(name="async_func", is_async=True)
        assert func.is_async is True

    def test_with_parameters(self) -> None:
        params = [ParameterInfo(name="x", type_hint="int")]
        func = FunctionInfo(name="f", parameters=params, return_type="bool")
        assert len(func.parameters) == 1
        assert func.return_type == "bool"

    def test_with_decorators(self) -> None:
        func = FunctionInfo(name="f", decorators=["staticmethod", "cache"])
        assert func.decorators == ["staticmethod", "cache"]

    def test_with_docstring(self) -> None:
        func = FunctionInfo(name="f", docstring="Does something.")
        assert func.docstring == "Does something."

    def test_to_dict(self) -> None:
        func = FunctionInfo(
            name="f",
            parameters=[ParameterInfo(name="x")],
            return_type="int",
            is_async=True,
            decorators=["property"],
            line_number=5,
            end_line_number=10,
            complexity=3,
        )
        d = func.to_dict()
        assert d["name"] == "f"
        assert d["is_async"] is True
        assert d["complexity"] == 3
        assert len(d["parameters"]) == 1

    def test_from_dict(self) -> None:
        data = {
            "name": "g",
            "parameters": [{"name": "a", "type_hint": "str"}],
            "return_type": "None",
            "is_async": False,
            "line_number": 1,
        }
        func = FunctionInfo.from_dict(data)
        assert func.name == "g"
        assert func.parameters[0].type_hint == "str"

    def test_roundtrip(self) -> None:
        original = FunctionInfo(
            name="process",
            parameters=[ParameterInfo(name="data", type_hint="bytes")],
            return_type="str",
            docstring="Process data.",
            decorators=["staticmethod"],
            is_async=True,
            line_number=15,
            end_line_number=25,
            complexity=7,
            source="async def process(data: bytes) -> str: ...",
        )
        restored = FunctionInfo.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.is_async == original.is_async
        assert restored.complexity == original.complexity
        assert restored.source == original.source


class TestClassInfo:
    """Tests for ClassInfo dataclass."""

    def test_basic_class(self) -> None:
        cls = ClassInfo(name="MyClass")
        assert cls.name == "MyClass"
        assert cls.base_classes == []
        assert cls.methods == []

    def test_with_bases(self) -> None:
        cls = ClassInfo(name="Child", base_classes=["Parent", "Mixin"])
        assert cls.base_classes == ["Parent", "Mixin"]

    def test_with_methods(self) -> None:
        methods = [FunctionInfo(name="__init__"), FunctionInfo(name="run")]
        cls = ClassInfo(name="Worker", methods=methods)
        assert len(cls.methods) == 2

    def test_to_dict(self) -> None:
        cls = ClassInfo(
            name="Foo",
            base_classes=["Bar"],
            methods=[FunctionInfo(name="baz")],
            docstring="A foo.",
            decorators=["dataclass"],
            line_number=1,
            end_line_number=20,
        )
        d = cls.to_dict()
        assert d["name"] == "Foo"
        assert d["base_classes"] == ["Bar"]
        assert len(d["methods"]) == 1

    def test_from_dict(self) -> None:
        data = {
            "name": "X",
            "base_classes": ["Y"],
            "methods": [{"name": "m", "parameters": []}],
            "decorators": [],
        }
        cls = ClassInfo.from_dict(data)
        assert cls.name == "X"
        assert len(cls.methods) == 1

    def test_roundtrip(self) -> None:
        original = ClassInfo(
            name="Engine",
            base_classes=["ABC"],
            methods=[
                FunctionInfo(name="start", is_async=True),
                FunctionInfo(name="stop"),
            ],
            docstring="An engine.",
            decorators=["dataclass"],
            line_number=10,
            end_line_number=50,
        )
        restored = ClassInfo.from_dict(original.to_dict())
        assert restored.name == original.name
        assert len(restored.methods) == 2
        assert restored.methods[0].is_async is True


class TestImportInfo:
    """Tests for ImportInfo dataclass."""

    def test_simple_import(self) -> None:
        imp = ImportInfo(module="os")
        assert imp.module == "os"
        assert imp.is_from_import is False

    def test_from_import(self) -> None:
        imp = ImportInfo(
            module="os.path", names=["join", "exists"], is_from_import=True
        )
        assert imp.is_from_import is True
        assert "join" in imp.names

    def test_alias(self) -> None:
        imp = ImportInfo(module="numpy", alias="np")
        assert imp.alias == "np"

    def test_to_dict(self) -> None:
        imp = ImportInfo(module="sys", line_number=1)
        d = imp.to_dict()
        assert d["module"] == "sys"

    def test_roundtrip(self) -> None:
        original = ImportInfo(
            module="pathlib",
            names=["Path"],
            is_from_import=True,
            line_number=3,
        )
        restored = ImportInfo.from_dict(original.to_dict())
        assert restored.module == original.module
        assert restored.names == original.names


class TestModuleInfo:
    """Tests for ModuleInfo dataclass."""

    def test_basic_module(self) -> None:
        mod = ModuleInfo(file_path="src/main.py")
        assert mod.file_path == "src/main.py"
        assert mod.language == Language.PYTHON
        assert mod.functions == []
        assert mod.classes == []

    def test_with_language(self) -> None:
        mod = ModuleInfo(file_path="index.js", language=Language.JAVASCRIPT)
        assert mod.language == Language.JAVASCRIPT

    def test_with_contents(self) -> None:
        mod = ModuleInfo(
            file_path="app.py",
            docstring="App module.",
            functions=[FunctionInfo(name="main")],
            classes=[ClassInfo(name="App")],
            imports=[ImportInfo(module="sys")],
            line_count=100,
        )
        assert len(mod.functions) == 1
        assert len(mod.classes) == 1
        assert len(mod.imports) == 1
        assert mod.line_count == 100

    def test_to_dict(self) -> None:
        mod = ModuleInfo(
            file_path="test.py",
            language=Language.PYTHON,
            functions=[FunctionInfo(name="f")],
        )
        d = mod.to_dict()
        assert d["file_path"] == "test.py"
        assert d["language"] == "python"

    def test_roundtrip(self) -> None:
        original = ModuleInfo(
            file_path="module.ts",
            language=Language.TYPESCRIPT,
            docstring="A module.",
            functions=[FunctionInfo(name="helper", return_type="void")],
            classes=[ClassInfo(name="Service", base_classes=["Base"])],
            imports=[ImportInfo(module="express", is_from_import=True)],
            line_count=200,
        )
        restored = ModuleInfo.from_dict(original.to_dict())
        assert restored.file_path == original.file_path
        assert restored.language == Language.TYPESCRIPT
        assert len(restored.functions) == 1
        assert len(restored.classes) == 1

    def test_json_serializable(self) -> None:
        mod = ModuleInfo(
            file_path="a.py",
            functions=[FunctionInfo(name="f", parameters=[ParameterInfo(name="x")])],
        )
        json_str = json.dumps(mod.to_dict())
        data = json.loads(json_str)
        restored = ModuleInfo.from_dict(data)
        assert restored.functions[0].parameters[0].name == "x"


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert graph.modules == {}
        assert graph.import_edges == []
        assert graph.call_edges == []

    def test_add_module(self) -> None:
        graph = DependencyGraph()
        mod = ModuleInfo(file_path="a.py")
        graph.add_module(mod)
        assert "a.py" in graph.modules

    def test_add_import_edge(self) -> None:
        graph = DependencyGraph()
        graph.add_import_edge("a.py", "os")
        assert ("a.py", "os") in graph.import_edges

    def test_add_call_edge(self) -> None:
        graph = DependencyGraph()
        graph.add_call_edge("a.main", "b.helper")
        assert ("a.main", "b.helper") in graph.call_edges

    def test_get_dependencies(self) -> None:
        graph = DependencyGraph()
        graph.add_import_edge("a.py", "os")
        graph.add_import_edge("a.py", "sys")
        graph.add_import_edge("b.py", "json")
        deps = graph.get_dependencies("a.py")
        assert deps == ["os", "sys"]

    def test_get_dependents(self) -> None:
        graph = DependencyGraph()
        graph.add_import_edge("a.py", "utils")
        graph.add_import_edge("b.py", "utils")
        dependents = graph.get_dependents("utils")
        assert set(dependents) == {"a.py", "b.py"}

    def test_to_dict(self) -> None:
        graph = DependencyGraph()
        graph.add_module(ModuleInfo(file_path="x.py"))
        graph.add_import_edge("x.py", "os")
        d = graph.to_dict()
        assert "x.py" in d["modules"]
        assert d["import_edges"] == [("x.py", "os")]

    def test_roundtrip(self) -> None:
        graph = DependencyGraph()
        graph.add_module(ModuleInfo(file_path="a.py", line_count=50))
        graph.add_import_edge("a.py", "b")
        graph.add_call_edge("a.main", "b.run")

        restored = DependencyGraph.from_dict(graph.to_dict())
        assert "a.py" in restored.modules
        assert restored.modules["a.py"].line_count == 50
        assert len(restored.import_edges) == 1
        assert len(restored.call_edges) == 1


class TestLanguageEnum:
    """Tests for the Language enum."""

    def test_values(self) -> None:
        assert Language.PYTHON.value == "python"
        assert Language.JAVASCRIPT.value == "javascript"
        assert Language.TYPESCRIPT.value == "typescript"

    def test_from_string(self) -> None:
        assert Language("python") == Language.PYTHON
        assert Language("typescript") == Language.TYPESCRIPT
