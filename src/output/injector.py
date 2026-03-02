"""Docstring injection into Python source files.

Provides the DocstringInjector class that updates source files in-place
with generated docstrings, preserving formatting and only modifying
items without existing docstrings.
"""

import ast
import difflib
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class DocstringInjector:
    """Injects generated docstrings into Python source files.

    Uses AST analysis to locate exact positions for docstring insertion,
    preserves original formatting and indentation, and supports dry-run
    mode for previewing changes.
    """

    def __init__(self, backup: bool = True) -> None:
        """Initialize the docstring injector.

        Args:
            backup: Whether to create backup files before modification.
        """
        self.backup = backup

    def inject(
        self,
        file_path: str,
        docstrings: dict[str, str],
        dry_run: bool = False,
    ) -> "InjectionResult":
        """Inject docstrings into a Python source file.

        Reads the file, identifies functions and classes without docstrings,
        inserts the provided docstrings, and writes the modified source back.

        Args:
            file_path: Path to the Python file to modify.
            docstrings: Mapping of function/class names to their generated
                docstring text.
            dry_run: If True, return the diff without modifying the file.

        Returns:
            An InjectionResult with the diff and injection count.

        Raises:
            FileNotFoundError: If the source file does not exist.
            SyntaxError: If the source file contains invalid Python.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        original = path.read_text(encoding="utf-8")
        modified = self._inject_docstrings(original, docstrings)

        diff = self._compute_diff(original, modified, file_path)
        injected_count = sum(
            1 for line in diff.splitlines() if line.startswith("+") and '"""' in line
        )

        if not dry_run and original != modified:
            if self.backup:
                backup_path = Path(f"{file_path}.bak")
                shutil.copy2(file_path, backup_path)
                logger.info("Created backup: %s", backup_path)

            path.write_text(modified, encoding="utf-8")
            logger.info("Injected %d docstrings into %s", injected_count, file_path)

        return InjectionResult(
            file_path=file_path,
            diff=diff,
            injected_count=injected_count,
            modified=original != modified,
        )

    def inject_batch(
        self,
        file_docstrings: dict[str, dict[str, str]],
        dry_run: bool = False,
    ) -> list["InjectionResult"]:
        """Inject docstrings into multiple files.

        Args:
            file_docstrings: Mapping of file paths to their docstring
                mappings (name -> docstring text).
            dry_run: If True, return diffs without modifying files.

        Returns:
            List of InjectionResult for each processed file.
        """
        results = []
        for file_path, docstrings in file_docstrings.items():
            try:
                result = self.inject(file_path, docstrings, dry_run=dry_run)
                results.append(result)
            except (FileNotFoundError, SyntaxError) as e:
                logger.warning("Skipping %s: %s", file_path, e)

        total = sum(r.injected_count for r in results)
        logger.info(
            "Batch injection complete: %d files, %d docstrings",
            len(results),
            total,
        )
        return results

    def _inject_docstrings(self, source: str, docstrings: dict[str, str]) -> str:
        """Insert docstrings into source code at the correct positions.

        Args:
            source: Original Python source code.
            docstrings: Mapping of item names to docstring text.

        Returns:
            Modified source code with docstrings inserted.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning("Cannot parse source for injection")
            raise

        lines = source.splitlines(keepends=True)
        # Collect insertion points sorted in reverse order to avoid offset issues
        insertions: list[tuple[int, str, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name not in docstrings:
                    continue
                if ast.get_docstring(node):
                    logger.debug("Skipping %s (already has docstring)", name)
                    continue

                indent = self._get_body_indent(node, lines)
                docstring_text = self._format_docstring(docstrings[name], indent)
                # Insert after the function/class def line (first line of body)
                insert_line = node.body[0].lineno - 1  # 0-indexed
                insertions.append((insert_line, docstring_text, name))

        # Sort by line number in reverse to maintain correct offsets
        insertions.sort(key=lambda x: x[0], reverse=True)

        for insert_line, docstring_text, name in insertions:
            lines.insert(insert_line, docstring_text)
            logger.debug("Inserted docstring for %s at line %d", name, insert_line + 1)

        return "".join(lines)

    def _get_body_indent(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        lines: list[str],
    ) -> str:
        """Determine the indentation level for the body of a node.

        Args:
            node: The AST node to get indentation for.
            lines: Source lines of the file.

        Returns:
            Indentation string (spaces/tabs) for the node body.
        """
        if node.body:
            body_line = lines[node.body[0].lineno - 1]
            return body_line[: len(body_line) - len(body_line.lstrip())]
        # Fallback: use node indentation + 4 spaces
        if node.col_offset >= 0:
            return " " * (node.col_offset + 4)
        return "    "

    def _format_docstring(self, docstring: str, indent: str) -> str:
        """Format a docstring with proper indentation and triple quotes.

        Args:
            docstring: Raw docstring text.
            indent: Indentation string to use.

        Returns:
            Formatted docstring string with newline.
        """
        docstring = docstring.strip()
        if "\n" in docstring:
            # Multi-line docstring
            doc_lines = docstring.splitlines()
            formatted = f'{indent}"""{doc_lines[0]}\n'
            for line in doc_lines[1:]:
                if line.strip():
                    formatted += f"{indent}{line}\n"
                else:
                    formatted += "\n"
            formatted += f'{indent}"""\n'
        else:
            # Single-line docstring
            formatted = f'{indent}"""{docstring}"""\n'
        return formatted

    def _compute_diff(self, original: str, modified: str, file_path: str) -> str:
        """Compute a unified diff between original and modified source.

        Args:
            original: Original source code.
            modified: Modified source code.
            file_path: File path for diff header.

        Returns:
            Unified diff string.
        """
        return "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )


class InjectionResult:
    """Result of a docstring injection operation.

    Attributes:
        file_path: Path to the processed file.
        diff: Unified diff of changes.
        injected_count: Number of docstrings injected.
        modified: Whether the file was actually modified.
    """

    def __init__(
        self,
        file_path: str,
        diff: str = "",
        injected_count: int = 0,
        modified: bool = False,
    ) -> None:
        """Initialize injection result.

        Args:
            file_path: Path to the processed file.
            diff: Unified diff of changes.
            injected_count: Number of docstrings injected.
            modified: Whether the file was modified.
        """
        self.file_path = file_path
        self.diff = diff
        self.injected_count = injected_count
        self.modified = modified
