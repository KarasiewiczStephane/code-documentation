"""Tests for the JavaScript/TypeScript parser."""

import textwrap
from pathlib import Path

import pytest

from src.parsers.js_parser import JSParser
from src.parsers.structure import Language


@pytest.fixture
def parser() -> JSParser:
    """Create a JSParser instance for testing."""
    return JSParser()


class TestParseSource:
    """Tests for parsing JS source code strings."""

    def test_empty_source(self, parser: JSParser) -> None:
        result = parser.parse_source("")
        assert result.language == Language.JAVASCRIPT
        assert result.functions == []
        assert result.classes == []

    def test_line_count(self, parser: JSParser) -> None:
        source = "const a = 1;\nconst b = 2;\nconst c = 3;\n"
        result = parser.parse_source(source)
        assert result.line_count == 3


class TestFunctionExtraction:
    """Tests for extracting function declarations."""

    def test_simple_function(self, parser: JSParser) -> None:
        source = "function hello() { return 42; }\n"
        result = parser.parse_source(source)
        assert len(result.functions) == 1
        assert result.functions[0].name == "hello"

    def test_function_with_params(self, parser: JSParser) -> None:
        source = "function add(x, y) { return x + y; }\n"
        result = parser.parse_source(source)
        func = result.functions[0]
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "x"
        assert func.parameters[1].name == "y"

    def test_async_function(self, parser: JSParser) -> None:
        source = "async function fetchData(url) { return await fetch(url); }\n"
        result = parser.parse_source(source)
        func = result.functions[0]
        assert func.is_async is True
        assert func.name == "fetchData"

    def test_function_line_numbers(self, parser: JSParser) -> None:
        source = "// comment\nfunction hello() {}\n"
        result = parser.parse_source(source)
        assert result.functions[0].line_number == 2

    def test_arrow_function(self, parser: JSParser) -> None:
        source = "const greet = (name) => { return `Hello ${name}`; };\n"
        result = parser.parse_source(source)
        assert len(result.functions) == 1
        assert result.functions[0].name == "greet"

    def test_rest_params(self, parser: JSParser) -> None:
        source = "function sum(...nums) { return nums.reduce((a, b) => a + b); }\n"
        result = parser.parse_source(source)
        params = result.functions[0].parameters
        assert any(p.is_args and p.name == "nums" for p in params)

    def test_source_extraction(self, parser: JSParser) -> None:
        source = "function add(a, b) { return a + b; }\n"
        result = parser.parse_source(source)
        assert "return a + b" in result.functions[0].source


class TestClassExtraction:
    """Tests for extracting class declarations."""

    def test_simple_class(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Animal {
                constructor(name) {
                    this.name = name;
                }
            }
        """)
        result = parser.parse_source(source)
        assert len(result.classes) == 1
        assert result.classes[0].name == "Animal"

    def test_class_with_extends(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Dog extends Animal {
                bark() { return "Woof!"; }
            }
        """)
        result = parser.parse_source(source)
        cls = result.classes[0]
        assert "Animal" in cls.base_classes

    def test_class_methods(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Calculator {
                add(a, b) { return a + b; }
                subtract(a, b) { return a - b; }
            }
        """)
        result = parser.parse_source(source)
        assert len(result.classes[0].methods) == 2

    def test_async_method(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Client {
                async fetch(url) { return await fetch(url); }
            }
        """)
        result = parser.parse_source(source)
        method = result.classes[0].methods[0]
        assert method.is_async is True

    def test_static_method(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Utils {
                static helper() { return true; }
            }
        """)
        result = parser.parse_source(source)
        method = result.classes[0].methods[0]
        assert "static" in method.decorators

    def test_getter_setter(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class Person {
                get name() { return this._name; }
                set name(value) { this._name = value; }
            }
        """)
        result = parser.parse_source(source)
        methods = result.classes[0].methods
        assert any("getter" in m.decorators for m in methods)
        assert any("setter" in m.decorators for m in methods)


class TestImportExtraction:
    """Tests for extracting import statements."""

    def test_default_import(self, parser: JSParser) -> None:
        source = "import React from 'react';\n"
        result = parser.parse_source(source)
        assert len(result.imports) == 1
        assert result.imports[0].module == "react"

    def test_named_imports(self, parser: JSParser) -> None:
        source = "import { useState, useEffect } from 'react';\n"
        result = parser.parse_source(source)
        imp = result.imports[0]
        assert imp.module == "react"
        assert "useState" in imp.names
        assert "useEffect" in imp.names

    def test_import_line_number(self, parser: JSParser) -> None:
        source = "// header\nimport fs from 'fs';\n"
        result = parser.parse_source(source)
        assert result.imports[0].line_number == 2


class TestExportExtraction:
    """Tests for extracting exported declarations."""

    def test_exported_function(self, parser: JSParser) -> None:
        source = "export function helper() { return true; }\n"
        result = parser.parse_source(source)
        assert len(result.functions) == 1
        assert result.functions[0].name == "helper"

    def test_exported_class(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            export class Service {
                run() {}
            }
        """)
        result = parser.parse_source(source)
        assert len(result.classes) == 1
        assert result.classes[0].name == "Service"

    def test_exported_arrow_function(self, parser: JSParser) -> None:
        source = "export const multiply = (a, b) => a * b;\n"
        result = parser.parse_source(source)
        assert len(result.functions) == 1
        assert result.functions[0].name == "multiply"


class TestJSDoc:
    """Tests for JSDoc comment extraction."""

    def test_function_jsdoc(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            /**
             * Adds two numbers together.
             * @param {number} a - First number
             * @param {number} b - Second number
             * @returns {number} The sum
             */
            function add(a, b) { return a + b; }
        """)
        result = parser.parse_source(source)
        doc = result.functions[0].docstring
        assert doc is not None
        assert "Adds two numbers" in doc

    def test_no_jsdoc(self, parser: JSParser) -> None:
        source = "function plain() {}\n"
        result = parser.parse_source(source)
        assert result.functions[0].docstring is None


class TestTypeScript:
    """Tests for TypeScript-specific parsing."""

    def test_typed_function(self, parser: JSParser) -> None:
        source = "function greet(name: string): string { return `Hi ${name}`; }\n"
        result = parser.parse_source(source, language=Language.TYPESCRIPT)
        func = result.functions[0]
        assert func.parameters[0].type_hint is not None
        assert func.return_type is not None

    def test_typescript_class(self, parser: JSParser) -> None:
        source = textwrap.dedent("""\
            class UserService {
                getUser(id: number): Promise<User> {
                    return this.db.find(id);
                }
            }
        """)
        result = parser.parse_source(source, language=Language.TYPESCRIPT)
        assert len(result.classes) == 1
        method = result.classes[0].methods[0]
        assert method.name == "getUser"


class TestParseFile:
    """Tests for file-based parsing."""

    def test_parse_js_file(self, parser: JSParser, tmp_path: Path) -> None:
        source = "function hello() { return 'world'; }\n"
        file_path = tmp_path / "test.js"
        file_path.write_text(source)
        result = parser.parse_file(str(file_path))
        assert result.language == Language.JAVASCRIPT
        assert len(result.functions) == 1

    def test_parse_ts_file(self, parser: JSParser, tmp_path: Path) -> None:
        source = "function greet(name: string): string { return name; }\n"
        file_path = tmp_path / "test.ts"
        file_path.write_text(source)
        result = parser.parse_file(str(file_path))
        assert result.language == Language.TYPESCRIPT

    def test_file_not_found(self, parser: JSParser) -> None:
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.js")

    def test_language_detection_tsx(self, parser: JSParser, tmp_path: Path) -> None:
        file_path = tmp_path / "component.tsx"
        file_path.write_text("export function App() {}\n")
        result = parser.parse_file(str(file_path))
        assert result.language == Language.TYPESCRIPT
