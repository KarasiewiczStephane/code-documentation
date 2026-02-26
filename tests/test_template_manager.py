"""Tests for the Jinja2 template manager."""

import pytest

from src.generators.template_manager import TemplateManager
from src.parsers.structure import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ModuleInfo,
    ParameterInfo,
)


@pytest.fixture
def manager() -> TemplateManager:
    """Create a TemplateManager with the default templates directory."""
    return TemplateManager()


class TestTemplateManagerInit:
    """Tests for TemplateManager initialization."""

    def test_default_templates_dir(self) -> None:
        manager = TemplateManager()
        assert manager._templates_path.exists()

    def test_custom_templates_dir(self, tmp_path) -> None:
        # Create a dummy template
        (tmp_path / "test.j2").write_text("Hello {{ name }}")
        manager = TemplateManager(templates_dir=str(tmp_path))
        assert manager._templates_path == tmp_path

    def test_list_templates(self, manager: TemplateManager) -> None:
        templates = manager.list_templates()
        assert "docstring.j2" in templates
        assert "class_doc.j2" in templates
        assert "module_doc.j2" in templates
        assert "readme.j2" in templates


class TestDocstringPrompt:
    """Tests for docstring prompt rendering."""

    def test_simple_function(self, manager: TemplateManager) -> None:
        func = FunctionInfo(
            name="add",
            parameters=[
                ParameterInfo(name="x", type_hint="int"),
                ParameterInfo(name="y", type_hint="int"),
            ],
            return_type="int",
        )
        prompt = manager.render_docstring_prompt(func)
        assert "add" in prompt
        assert "int" in prompt

    def test_async_function(self, manager: TemplateManager) -> None:
        func = FunctionInfo(name="fetch", is_async=True)
        prompt = manager.render_docstring_prompt(func)
        assert "async" in prompt

    def test_with_decorators(self, manager: TemplateManager) -> None:
        func = FunctionInfo(name="cached", decorators=["cache", "staticmethod"])
        prompt = manager.render_docstring_prompt(func)
        assert "cache" in prompt
        assert "staticmethod" in prompt

    def test_with_source(self, manager: TemplateManager) -> None:
        func = FunctionInfo(
            name="double",
            source="def double(x): return x * 2",
        )
        prompt = manager.render_docstring_prompt(func)
        assert "return x * 2" in prompt

    def test_with_context(self, manager: TemplateManager) -> None:
        func = FunctionInfo(name="process")
        prompt = manager.render_docstring_prompt(
            func, context="Part of the ETL pipeline"
        )
        assert "ETL pipeline" in prompt

    def test_with_args_kwargs(self, manager: TemplateManager) -> None:
        func = FunctionInfo(
            name="flexible",
            parameters=[
                ParameterInfo(name="args", is_args=True),
                ParameterInfo(name="kwargs", is_kwargs=True),
            ],
        )
        prompt = manager.render_docstring_prompt(func)
        assert "*args" in prompt
        assert "**kwargs" in prompt

    def test_with_default_value(self, manager: TemplateManager) -> None:
        func = FunctionInfo(
            name="greet",
            parameters=[ParameterInfo(name="name", default_value="'world'")],
        )
        prompt = manager.render_docstring_prompt(func)
        assert "'world'" in prompt


class TestClassDocPrompt:
    """Tests for class documentation prompt rendering."""

    def test_simple_class(self, manager: TemplateManager) -> None:
        cls = ClassInfo(name="MyClass")
        prompt = manager.render_class_doc_prompt(cls)
        assert "MyClass" in prompt

    def test_class_with_bases(self, manager: TemplateManager) -> None:
        cls = ClassInfo(name="Child", base_classes=["Parent", "Mixin"])
        prompt = manager.render_class_doc_prompt(cls)
        assert "Parent" in prompt
        assert "Mixin" in prompt

    def test_class_with_methods(self, manager: TemplateManager) -> None:
        cls = ClassInfo(
            name="Service",
            methods=[
                FunctionInfo(name="start", return_type="None"),
                FunctionInfo(name="stop", return_type="None"),
            ],
        )
        prompt = manager.render_class_doc_prompt(cls)
        assert "start" in prompt
        assert "stop" in prompt

    def test_class_with_context(self, manager: TemplateManager) -> None:
        cls = ClassInfo(name="Handler")
        prompt = manager.render_class_doc_prompt(cls, context="Handles HTTP requests")
        assert "HTTP requests" in prompt


class TestModuleDocPrompt:
    """Tests for module documentation prompt rendering."""

    def test_basic_module(self, manager: TemplateManager) -> None:
        module = ModuleInfo(file_path="src/utils.py", line_count=100)
        prompt = manager.render_module_doc_prompt(module)
        assert "src/utils.py" in prompt
        assert "100" in prompt

    def test_module_with_functions(self, manager: TemplateManager) -> None:
        module = ModuleInfo(
            file_path="app.py",
            functions=[
                FunctionInfo(
                    name="main",
                    parameters=[ParameterInfo(name="args")],
                    return_type="None",
                    docstring="Entry point.",
                )
            ],
        )
        prompt = manager.render_module_doc_prompt(module)
        assert "main" in prompt
        assert "Entry point" in prompt

    def test_module_with_classes(self, manager: TemplateManager) -> None:
        module = ModuleInfo(
            file_path="models.py",
            classes=[
                ClassInfo(name="User", docstring="A user model."),
            ],
        )
        prompt = manager.render_module_doc_prompt(module)
        assert "User" in prompt

    def test_module_with_imports(self, manager: TemplateManager) -> None:
        module = ModuleInfo(
            file_path="service.py",
            imports=[
                ImportInfo(module="os"),
                ImportInfo(module="pathlib", names=["Path"], is_from_import=True),
            ],
        )
        prompt = manager.render_module_doc_prompt(module)
        assert "import os" in prompt
        assert "from pathlib import Path" in prompt


class TestReadmePrompt:
    """Tests for README generation prompt rendering."""

    def test_basic_readme(self, manager: TemplateManager) -> None:
        prompt = manager.render_readme_prompt(project_name="My Project")
        assert "My Project" in prompt

    def test_readme_with_description(self, manager: TemplateManager) -> None:
        prompt = manager.render_readme_prompt(
            project_name="DocGen",
            description="A documentation generator tool",
        )
        assert "documentation generator" in prompt

    def test_readme_with_modules(self, manager: TemplateManager) -> None:
        modules = [
            ModuleInfo(
                file_path="src/main.py",
                docstring="Main entry point.",
                functions=[FunctionInfo(name="main")],
            )
        ]
        prompt = manager.render_readme_prompt(
            project_name="Test",
            modules=modules,
        )
        assert "src/main.py" in prompt
        assert "Main entry point" in prompt

    def test_readme_with_dependencies(self, manager: TemplateManager) -> None:
        prompt = manager.render_readme_prompt(
            project_name="Test",
            dependencies=["click", "jinja2", "anthropic"],
        )
        assert "click" in prompt
        assert "anthropic" in prompt

    def test_readme_with_structure(self, manager: TemplateManager) -> None:
        structure = "src/\n  main.py\n  utils.py"
        prompt = manager.render_readme_prompt(
            project_name="Test",
            structure=structure,
        )
        assert "src/" in prompt
        assert "utils.py" in prompt

    def test_readme_with_entry_points(self, manager: TemplateManager) -> None:
        prompt = manager.render_readme_prompt(
            project_name="CLI Tool",
            entry_points=["src/main.py", "src/cli/commands.py"],
        )
        assert "src/main.py" in prompt
