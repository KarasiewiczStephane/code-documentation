"""Configuration loader and validator for the code documentation generator.

Loads settings from configs/config.yaml and provides typed access
to all configuration sections via dataclasses.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "config.yaml"


@dataclass
class APIConfig:
    """Configuration for the Anthropic API client."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.2
    rate_limit_rpm: int = 50
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0


@dataclass
class LanguageParserConfig:
    """Configuration for a single language parser."""

    enabled: bool = True
    extensions: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class ParserConfig:
    """Configuration for all code parsers."""

    python: LanguageParserConfig = field(default_factory=LanguageParserConfig)
    javascript: LanguageParserConfig = field(default_factory=LanguageParserConfig)


@dataclass
class ComplexityConfig:
    """Configuration for complexity analysis."""

    enabled: bool = True
    thresholds: dict[str, int] = field(
        default_factory=lambda: {"low": 5, "medium": 10, "high": 20}
    )


@dataclass
class OutputConfig:
    """Configuration for documentation output."""

    default_format: str = "markdown"
    output_dir: str = "docs/generated"
    include_source_links: bool = True
    include_complexity: bool = True


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


@dataclass
class IncrementalConfig:
    """Configuration for incremental documentation mode."""

    state_file: str = ".codedoc-state.json"
    use_git_diff: bool = True


@dataclass
class AppConfig:
    """Top-level application configuration."""

    api: APIConfig = field(default_factory=APIConfig)
    parser: ParserConfig = field(default_factory=ParserConfig)
    complexity: ComplexityConfig = field(default_factory=ComplexityConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)


def _build_language_config(data: dict) -> LanguageParserConfig:
    """Build a LanguageParserConfig from a dictionary.

    Args:
        data: Dictionary with language parser settings.

    Returns:
        A configured LanguageParserConfig instance.
    """
    return LanguageParserConfig(
        enabled=data.get("enabled", True),
        extensions=data.get("extensions", []),
        exclude_patterns=data.get("exclude_patterns", []),
    )


def _build_parser_config(data: dict) -> ParserConfig:
    """Build a ParserConfig from a dictionary.

    Args:
        data: Dictionary with parser settings for all languages.

    Returns:
        A configured ParserConfig instance.
    """
    return ParserConfig(
        python=_build_language_config(data.get("python", {})),
        javascript=_build_language_config(data.get("javascript", {})),
    )


def find_project_config(start_path: str) -> Optional[Path]:
    """Search for .codedoc.yaml in start_path and parent directories.

    Traverses from start_path upward to find a project-local
    configuration file.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to the found config file, or None if not found.
    """
    path = Path(start_path).resolve()
    if path.is_file():
        path = path.parent

    for directory in [path, *path.parents]:
        config_file = directory / ".codedoc.yaml"
        if config_file.exists():
            logger.info("Found project config: %s", config_file)
            return config_file
        config_file = directory / ".codedoc.yml"
        if config_file.exists():
            logger.info("Found project config: %s", config_file)
            return config_file
    return None


def _merge_dicts(base: dict, override: dict) -> dict:
    """Deep merge override dict into base dict.

    Values in override take precedence. Nested dicts are merged
    recursively; non-dict values are replaced.

    Args:
        base: Base dictionary with default values.
        override: Dictionary with override values.

    Returns:
        Merged dictionary.
    """
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    config_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> AppConfig:
    """Load application configuration from a YAML file.

    Reads the YAML config file and constructs a fully typed AppConfig
    object. Falls back to defaults for any missing values. The API key
    is read from the ANTHROPIC_API_KEY environment variable, not from
    the config file.

    If project_path is provided, searches for a .codedoc.yaml file
    in that directory and its parents, merging it with the base config.

    Args:
        config_path: Path to the YAML config file. If None, uses the
            default path at configs/config.yaml.
        project_path: Optional project directory to search for
            .codedoc.yaml overrides.

    Returns:
        A fully populated AppConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the config file contains invalid YAML.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.warning("Config file not found at %s, using defaults", path)
        return AppConfig()

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    # Merge project-local config if found
    if project_path:
        local_config = find_project_config(project_path)
        if local_config:
            with open(local_config) as f:
                local_raw = yaml.safe_load(f) or {}
            raw = _merge_dicts(raw, local_raw)
            logger.info("Merged project config from %s", local_config)

    logger.info("Loaded configuration from %s", path)

    api_data = raw.get("api", {})
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set in environment")

    api_config = APIConfig(
        provider=api_data.get("provider", "anthropic"),
        model=api_data.get("model", "claude-sonnet-4-20250514"),
        max_tokens=api_data.get("max_tokens", 4096),
        temperature=api_data.get("temperature", 0.2),
        rate_limit_rpm=api_data.get("rate_limit_rpm", 50),
        retry_max_attempts=api_data.get("retry_max_attempts", 3),
        retry_base_delay=api_data.get("retry_base_delay", 1.0),
    )

    complexity_data = raw.get("complexity", {})
    complexity_config = ComplexityConfig(
        enabled=complexity_data.get("enabled", True),
        thresholds=complexity_data.get(
            "thresholds", {"low": 5, "medium": 10, "high": 20}
        ),
    )

    output_data = raw.get("output", {})
    output_config = OutputConfig(
        default_format=output_data.get("default_format", "markdown"),
        output_dir=output_data.get("output_dir", "docs/generated"),
        include_source_links=output_data.get("include_source_links", True),
        include_complexity=output_data.get("include_complexity", True),
    )

    logging_data = raw.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_data.get("level", "INFO"),
        format=logging_data.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        file=logging_data.get("file"),
    )

    incremental_data = raw.get("incremental", {})
    incremental_config = IncrementalConfig(
        state_file=incremental_data.get("state_file", ".codedoc-state.json"),
        use_git_diff=incremental_data.get("use_git_diff", True),
    )

    return AppConfig(
        api=api_config,
        parser=_build_parser_config(raw.get("parser", {})),
        complexity=complexity_config,
        output=output_config,
        logging=logging_config,
        incremental=incremental_config,
    )
