"""Tests for configuration loading and validation."""

from pathlib import Path

import yaml

from src.utils.config import (
    APIConfig,
    AppConfig,
    ComplexityConfig,
    IncrementalConfig,
    LanguageParserConfig,
    LoggingConfig,
    OutputConfig,
    ParserConfig,
    load_config,
)


class TestAPIConfig:
    """Tests for APIConfig defaults."""

    def test_defaults(self) -> None:
        config = APIConfig()
        assert config.provider == "anthropic"
        assert config.max_tokens == 4096
        assert config.temperature == 0.2
        assert config.rate_limit_rpm == 50
        assert config.retry_max_attempts == 3


class TestAppConfigDefaults:
    """Tests for AppConfig with all defaults."""

    def test_default_construction(self) -> None:
        config = AppConfig()
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.parser, ParserConfig)
        assert isinstance(config.complexity, ComplexityConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.incremental, IncrementalConfig)

    def test_default_logging_level(self) -> None:
        config = AppConfig()
        assert config.logging.level == "INFO"

    def test_default_output_format(self) -> None:
        config = AppConfig()
        assert config.output.default_format == "markdown"


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_default_config(self) -> None:
        config = load_config()
        assert isinstance(config, AppConfig)
        assert config.api.provider == "anthropic"

    def test_load_from_explicit_path(self, tmp_path: Path) -> None:
        config_data = {
            "api": {"model": "claude-haiku-4-5-20251001", "max_tokens": 2048},
            "output": {"default_format": "html"},
            "logging": {"level": "DEBUG"},
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        assert config.api.model == "claude-haiku-4-5-20251001"
        assert config.api.max_tokens == 2048
        assert config.output.default_format == "html"
        assert config.logging.level == "DEBUG"

    def test_load_nonexistent_returns_defaults(self, tmp_path: Path) -> None:
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert isinstance(config, AppConfig)
        assert config.api.provider == "anthropic"

    def test_load_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = load_config(str(config_file))
        assert isinstance(config, AppConfig)

    def test_parser_config_loaded(self) -> None:
        config = load_config()
        assert config.parser.python.enabled is True
        assert ".py" in config.parser.python.extensions

    def test_complexity_thresholds(self) -> None:
        config = load_config()
        assert config.complexity.thresholds["low"] == 5
        assert config.complexity.thresholds["medium"] == 10
        assert config.complexity.thresholds["high"] == 20

    def test_incremental_defaults(self) -> None:
        config = load_config()
        assert config.incremental.state_file == ".codedoc-state.json"
        assert config.incremental.use_git_diff is True


class TestLanguageParserConfig:
    """Tests for LanguageParserConfig."""

    def test_defaults(self) -> None:
        config = LanguageParserConfig()
        assert config.enabled is True
        assert config.extensions == []
        assert config.exclude_patterns == []

    def test_custom_values(self) -> None:
        config = LanguageParserConfig(
            enabled=False,
            extensions=[".py"],
            exclude_patterns=["__pycache__"],
        )
        assert config.enabled is False
        assert config.extensions == [".py"]
