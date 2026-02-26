"""README generation for projects using LLM analysis.

Analyzes a full codebase directory, gathers project metadata, and
generates a comprehensive README.md via the LLM client.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.generators.llm_client import LLMClient
from src.generators.template_manager import TemplateManager
from src.parsers.python_parser import PythonParser
from src.parsers.structure import ModuleInfo
from src.utils.config import AppConfig, load_config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a technical writer creating a README.md for an open-source project. "
    "Write clear, professional documentation in Markdown format. "
    "Include realistic code examples and a well-organized structure. "
    "Return only the Markdown content without any wrapper."
)


@dataclass
class ProjectInfo:
    """Aggregated metadata about a project for README generation.

    Attributes:
        name: Project name.
        description: Short project description.
        root_path: Root directory of the project.
        modules: Parsed module structures.
        entry_points: Main entry point files.
        dependencies: List of project dependencies.
        structure: Directory tree string.
    """

    name: str
    description: str = ""
    root_path: str = ""
    modules: list[ModuleInfo] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    structure: str = ""


class ReadmeGenerator:
    """Generates README.md files from project analysis.

    Scans a project directory, parses source files, gathers
    metadata, and uses the LLM to produce a comprehensive README.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        template_manager: Optional[TemplateManager] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        """Initialize the README generator.

        Args:
            llm_client: The LLM client for API calls.
            template_manager: Template manager for prompts.
            config: Application configuration.
        """
        self.llm = llm_client
        self.templates = template_manager or TemplateManager()
        self.config = config or load_config()
        self._parser = PythonParser()

    def analyze_project(self, project_path: str) -> ProjectInfo:
        """Analyze a project directory and gather metadata.

        Scans for Python source files, parses them, reads
        requirements.txt, and builds a directory tree.

        Args:
            project_path: Path to the project root directory.

        Returns:
            A ProjectInfo with all gathered metadata.

        Raises:
            FileNotFoundError: If the project path does not exist.
        """
        root = Path(project_path)
        if not root.exists():
            raise FileNotFoundError(f"Project path not found: {project_path}")

        name = root.name
        logger.info("Analyzing project: %s at %s", name, root)

        # Parse Python files
        modules = self._scan_python_files(root)

        # Read dependencies
        dependencies = self._read_dependencies(root)

        # Find entry points
        entry_points = self._find_entry_points(root)

        # Build directory tree
        structure = self._build_tree(root)

        return ProjectInfo(
            name=name,
            root_path=str(root),
            modules=modules,
            entry_points=entry_points,
            dependencies=dependencies,
            structure=structure,
        )

    def generate_readme(self, project_info: ProjectInfo) -> str:
        """Generate a README.md from project information.

        Args:
            project_info: Analyzed project metadata.

        Returns:
            The generated README content as a Markdown string.
        """
        prompt = self.templates.render_readme_prompt(
            project_name=project_info.name,
            modules=project_info.modules,
            description=project_info.description,
            entry_points=project_info.entry_points,
            dependencies=project_info.dependencies,
            structure=project_info.structure,
        )

        result = self.llm.generate(prompt, system=_SYSTEM_PROMPT)
        logger.info(
            "Generated README for %s (%d tokens)",
            project_info.name,
            result.usage.total_tokens,
        )
        return result.content.strip()

    def _scan_python_files(self, root: Path) -> list[ModuleInfo]:
        """Scan and parse all Python files in the project.

        Args:
            root: Project root directory.

        Returns:
            List of parsed ModuleInfo objects.
        """
        modules = []
        exclude = set(self.config.parser.python.exclude_patterns)

        for py_file in sorted(root.rglob("*.py")):
            # Skip excluded directories
            if any(part in exclude for part in py_file.parts):
                continue
            try:
                relative = str(py_file.relative_to(root))
                module = self._parser.parse_file(str(py_file))
                module.file_path = relative
                modules.append(module)
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning("Skipping %s: %s", py_file, e)

        logger.info("Parsed %d Python files", len(modules))
        return modules

    def _read_dependencies(self, root: Path) -> list[str]:
        """Read project dependencies from requirements.txt.

        Args:
            root: Project root directory.

        Returns:
            List of dependency strings.
        """
        req_file = root / "requirements.txt"
        if not req_file.exists():
            return []

        deps = []
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line)
        return deps

    def _find_entry_points(self, root: Path) -> list[str]:
        """Find likely entry point files in the project.

        Args:
            root: Project root directory.

        Returns:
            List of entry point file paths relative to root.
        """
        candidates = ["main.py", "app.py", "cli.py", "__main__.py"]
        entry_points = []

        for py_file in sorted(root.rglob("*.py")):
            if py_file.name in candidates:
                entry_points.append(str(py_file.relative_to(root)))

        return entry_points

    def _build_tree(self, root: Path, max_depth: int = 3) -> str:
        """Build a directory tree string representation.

        Args:
            root: Root directory to build the tree from.
            max_depth: Maximum directory depth to include.

        Returns:
            A formatted directory tree string.
        """
        lines = [f"{root.name}/"]
        self._tree_walk(root, "", lines, 0, max_depth)
        return "\n".join(lines)

    def _tree_walk(
        self,
        directory: Path,
        prefix: str,
        lines: list[str],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively walk a directory to build the tree string.

        Args:
            directory: Current directory to walk.
            prefix: Line prefix for tree formatting.
            lines: Accumulator for tree lines.
            depth: Current depth.
            max_depth: Maximum allowed depth.
        """
        if depth >= max_depth:
            return

        exclude = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".taskmaster",
        }
        entries = sorted(
            [
                e
                for e in directory.iterdir()
                if e.name not in exclude and not e.name.startswith(".")
            ],
            key=lambda e: (e.is_file(), e.name),
        )

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._tree_walk(entry, prefix + extension, lines, depth + 1, max_depth)
