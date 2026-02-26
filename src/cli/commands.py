"""CLI commands for the Code Documentation Generator.

Provides the Click-based command group 'doc' with subcommands for
generating documentation, READMEs, docstrings, complexity reports,
and cost estimates.
"""

import logging
from pathlib import Path
from typing import Optional

import click

from src.analysis.complexity import ComplexityAnalyzer
from src.generators.docstring_gen import DocstringGenerator
from src.generators.llm_client import LLMClient
from src.generators.readme_gen import ReadmeGenerator
from src.output.html import HtmlWriter
from src.output.markdown import MarkdownWriter
from src.parsers.js_parser import JSParser
from src.parsers.python_parser import PythonParser
from src.parsers.structure import Language
from src.utils.config import load_config
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def _collect_files(path: str) -> list[Path]:
    """Collect all supported source files from a path.

    Args:
        path: File or directory path to scan.

    Returns:
        List of source file paths.
    """
    root = Path(path)
    if root.is_file():
        return [root]

    config = load_config()
    exclude = set(config.parser.python.exclude_patterns)
    files = []
    for ext in (".py", ".js", ".jsx", ".ts", ".tsx"):
        for f in sorted(root.rglob(f"*{ext}")):
            if not any(part in exclude for part in f.parts):
                files.append(f)
    return files


def _parse_file(file_path: Path) -> Optional[object]:
    """Parse a source file using the appropriate parser.

    Args:
        file_path: Path to the source file.

    Returns:
        A ModuleInfo object, or None on error.
    """
    try:
        if file_path.suffix == ".py":
            parser = PythonParser()
            return parser.parse_file(str(file_path))
        elif file_path.suffix in (".js", ".jsx", ".ts", ".tsx"):
            parser = JSParser()
            return parser.parse_file(str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        logger.warning("Skipping %s: %s", file_path, e)
    return None


@click.group()
@click.version_option(version="0.1.0", prog_name="code-doc-gen")
def doc() -> None:
    """Code Documentation Generator — generate docs from source code."""
    config = load_config()
    setup_logging(
        level=config.logging.level,
        log_format=config.logging.format,
        log_file=config.logging.file,
    )


@doc.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["md", "html"]),
    default="md",
    help="Output format.",
)
@click.option("--output-dir", type=click.Path(), default=None, help="Output directory.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without calling the API.",
)
def generate(
    path: str, output_format: str, output_dir: Optional[str], dry_run: bool
) -> None:
    """Generate full documentation for a codebase.

    Parses all source files, generates docstrings and module docs
    via the LLM, and writes output in the specified format.
    """
    config = load_config()
    files = _collect_files(path)
    click.echo(f"Found {len(files)} source files")

    if dry_run:
        for f in files:
            click.echo(f"  Would process: {f}")
        click.echo("Dry run complete. No API calls made.")
        return

    modules = []
    with click.progressbar(files, label="Parsing files") as bar:
        for file_path in bar:
            module = _parse_file(file_path)
            if module:
                modules.append(module)

    # Enrich with complexity
    analyzer = ComplexityAnalyzer(config=config.complexity)
    for module in modules:
        if module.language == Language.PYTHON:
            analyzer.enrich_module(module)

    out_dir = output_dir or config.output.output_dir

    if output_format == "html":
        writer = HtmlWriter(output_dir=out_dir)
        writer.generate_mkdocs_config(Path(path).name, modules)
        writer.write_docs(modules)
        click.echo(f"HTML documentation written to {out_dir}")
    else:
        writer = MarkdownWriter(output_dir=out_dir)
        for module in modules:
            writer.write_module_doc(module)
        writer.write_index(modules)
        click.echo(f"Markdown documentation written to {out_dir}")


@doc.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output", "-o", type=click.Path(), default=None, help="Output file path."
)
def readme(path: str, output: Optional[str]) -> None:
    """Generate a README.md for a project.

    Analyzes the project structure and generates a comprehensive
    README using the LLM.
    """
    config = load_config()
    llm = LLMClient(config=config.api)
    gen = ReadmeGenerator(llm, config=config)

    click.echo(f"Analyzing project: {path}")
    project_info = gen.analyze_project(path)
    click.echo(
        f"Found {len(project_info.modules)} modules, {len(project_info.dependencies)} dependencies"
    )

    readme_content = gen.generate_readme(project_info)

    output_path = output or str(Path(path) / "README.md")
    Path(output_path).write_text(readme_content, encoding="utf-8")
    click.echo(f"README written to {output_path}")


@doc.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show which files need docstrings.")
def docstrings(path: str, dry_run: bool) -> None:
    """Generate missing docstrings for Python source files.

    Scans for functions and classes without docstrings and
    generates them via the LLM.
    """
    config = load_config()
    files = [f for f in _collect_files(path) if f.suffix == ".py"]
    click.echo(f"Found {len(files)} Python files")

    parser = PythonParser()
    modules = []
    for f in files:
        try:
            modules.append(parser.parse_file(str(f)))
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.warning("Skipping %s: %s", f, e)

    # Count missing docstrings
    missing = 0
    for module in modules:
        for func in module.functions:
            if not func.docstring:
                missing += 1
                if dry_run:
                    click.echo(f"  Missing: {module.file_path}:{func.name}")
        for cls in module.classes:
            if not cls.docstring:
                missing += 1
                if dry_run:
                    click.echo(f"  Missing: {module.file_path}:{cls.name}")

    click.echo(f"Found {missing} items without docstrings")

    if dry_run:
        return

    llm = LLMClient(config=config.api)
    gen = DocstringGenerator(llm)

    for module in modules:
        result = gen.generate_all(module, skip_existing=True)
        click.echo(
            f"  {module.file_path}: {len(result.function_docs)} functions, "
            f"{len(result.class_docs)} classes"
        )

    click.echo("Docstring generation complete.")


@doc.command()
@click.argument("path", type=click.Path(exists=True))
def complexity(path: str) -> None:
    """Generate a complexity report for Python files.

    Analyzes cyclomatic complexity of all functions and provides
    a summary with rankings.
    """
    files = [f for f in _collect_files(path) if f.suffix == ".py"]
    click.echo(f"Analyzing {len(files)} Python files\n")

    analyzer = ComplexityAnalyzer()
    total_functions = 0
    high_complexity = []

    for f in files:
        try:
            report = analyzer.analyze_file(str(f))
        except (SyntaxError, FileNotFoundError) as e:
            logger.warning("Skipping %s: %s", f, e)
            continue

        if report.functions:
            click.echo(f"📄 {f} (avg: {report.average_complexity:.1f})")
            for func in sorted(report.functions, key=lambda x: -x.complexity):
                marker = (
                    "🔴"
                    if func.complexity > 10
                    else "🟡"
                    if func.complexity > 5
                    else "🟢"
                )
                click.echo(f"  {marker} {func.name}: {func.complexity} ({func.rank})")
                if func.complexity > 10:
                    high_complexity.append((str(f), func.name, func.complexity))

            total_functions += report.total_functions

    click.echo(f"\nTotal: {total_functions} functions analyzed")
    if high_complexity:
        click.echo(f"\n⚠️  {len(high_complexity)} high-complexity functions found:")
        for fpath, fname, score in high_complexity:
            click.echo(f"  {fpath}:{fname} = {score}")


@doc.command()
@click.argument("path", type=click.Path(exists=True))
def estimate(path: str) -> None:
    """Estimate API cost without generating documentation.

    Counts tokens for all source files and estimates the
    approximate API cost for full documentation generation.
    """
    config = load_config()
    files = _collect_files(path)
    click.echo(f"Found {len(files)} source files\n")

    llm = LLMClient(config=config.api)
    total_input_tokens = 0
    total_cost = 0.0

    for f in files:
        module = _parse_file(f)
        if not module:
            continue

        # Estimate tokens for module doc + each function + each class
        items = 1  # module doc
        items += len(module.functions)
        items += len(module.classes)

        # Rough estimate: each prompt ~ 500 tokens, each response ~ 300 tokens
        est = llm.estimate_cost(
            "x" * 2000,  # ~500 token prompt
            estimated_output_tokens=300 * items,
        )
        total_input_tokens += est.input_tokens * items
        total_cost += est.total_cost_usd * items

    click.echo(f"Estimated input tokens: {total_input_tokens:,}")
    click.echo(f"Estimated cost: ${total_cost:.4f} USD")
    click.echo(f"Model: {config.api.model}")
