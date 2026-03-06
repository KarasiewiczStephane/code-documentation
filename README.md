# Code Documentation Generator

An LLM-powered tool that generates comprehensive documentation from Python and JavaScript/TypeScript source code. Parses code structures, analyzes complexity, and produces Markdown or MkDocs-compatible HTML documentation.

## Features

- **Multi-language parsing** — Python (via AST) and JavaScript/TypeScript (via tree-sitter)
- **Docstring generation** — Generates Google-style docstrings using the Claude API
- **Docstring injection** — Inserts generated docstrings directly into source files with dry-run preview
- **Complexity analysis** — Cyclomatic complexity scoring with Radon
- **Call graph analysis** — Extracts function call relationships across modules
- **Dependency visualization** — Generates Mermaid diagrams for import and call graphs
- **Multiple output formats** — Markdown files or MkDocs-compatible HTML sites
- **Incremental mode** — Only re-processes files changed since the last run
- **Project-local config** — `.codedoc.yaml` overrides per project directory
- **Cost estimation** — Estimate API costs before running full generation
- **Analytics dashboard** — Streamlit dashboard with complexity metrics, coverage tracking, and cost estimation

## Quick Start

1. **Install dependencies**

   ```bash
   git clone git@github.com:KarasiewiczStephane/code-documentation.git
   cd code-documentation
   make install
   ```

2. **Set your API key** (required for LLM-powered features)

   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   ```

   Or create a `.env` file in the project root:

   ```
   ANTHROPIC_API_KEY=your-key-here
   ```

3. **Run the CLI** against any Python or JavaScript/TypeScript project

   ```bash
   # Generate Markdown documentation
   python -m src.main generate ./my-project --format md

   # Dry run to preview what would be processed (no API calls)
   python -m src.main generate ./my-project --dry-run
   ```

4. **Launch the dashboard** (uses synthetic data, no API key needed)

   ```bash
   make dashboard
   ```

   This starts a Streamlit app displaying complexity metrics, documentation coverage, and LLM cost estimation charts.

### Docker

```bash
docker build -t code-doc-gen .
docker run -v $(pwd)/target:/data code-doc-gen generate /data
```

## CLI Reference

The CLI is invoked via `python -m src.main` (or `make run`), which delegates to the Click command group.

### `generate`

Generate full documentation for a codebase.

```bash
python -m src.main generate PATH [OPTIONS]
```

| Option | Description |
|---|---|
| `--format md\|html` | Output format (default: `md`) |
| `--output-dir PATH` | Output directory |
| `--dry-run` | Preview without API calls |
| `--incremental, -i` | Only process changed files |
| `--config PATH` | Path to configuration file |

### `docstrings`

Generate missing docstrings for Python files.

```bash
python -m src.main docstrings PATH [OPTIONS]
```

| Option | Description |
|---|---|
| `--dry-run` | Show which files need docstrings |
| `--incremental, -i` | Only process changed files |

### `readme`

Generate a README.md for a project.

```bash
python -m src.main readme PATH [OPTIONS]
```

| Option | Description |
|---|---|
| `--output, -o PATH` | Output file path |

### `complexity`

Generate a complexity report for Python files.

```bash
python -m src.main complexity PATH
```

### `estimate`

Estimate API cost without generating documentation.

```bash
python -m src.main estimate PATH
```

## Configuration

### Global Configuration

Settings are defined in `configs/config.yaml`:

```yaml
api:
  provider: "anthropic"
  model: "claude-sonnet-4-20250514"
  max_tokens: 4096
  temperature: 0.2
  rate_limit_rpm: 50

parser:
  python:
    enabled: true
    extensions: [".py"]
    exclude_patterns: ["__pycache__", ".venv", "node_modules"]
  javascript:
    enabled: true
    extensions: [".js", ".jsx", ".ts", ".tsx"]

complexity:
  thresholds:
    low: 5
    medium: 10
    high: 20

output:
  default_format: "markdown"
  output_dir: "docs/generated"

logging:
  level: "INFO"

incremental:
  state_file: ".codedoc-state.json"
  use_git_diff: true
```

### Project-Local Configuration

Create a `.codedoc.yaml` file in your project root to override defaults:

```yaml
output:
  default_format: html
  output_dir: docs/api

api:
  max_tokens: 8192

logging:
  level: DEBUG
```

The tool searches for `.codedoc.yaml` (or `.codedoc.yml`) in the target directory and parent directories.

### Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Required for LLM-powered features |

## Project Structure

```
code-documentation/
├── configs/
│   └── config.yaml          # Global configuration
├── src/
│   ├── main.py              # Entry point (delegates to CLI)
│   ├── analysis/
│   │   ├── call_graph.py     # Function call graph extraction
│   │   ├── complexity.py     # Cyclomatic complexity analysis
│   │   └── graph_viz.py      # Mermaid diagram generation
│   ├── cli/
│   │   ├── commands.py       # Click CLI commands
│   │   └── progress.py       # Progress reporting utilities
│   ├── dashboard/
│   │   └── app.py            # Streamlit analytics dashboard
│   ├── generators/
│   │   ├── docstring_gen.py  # Docstring generation pipeline
│   │   ├── llm_client.py     # Claude API client with retries
│   │   ├── module_gen.py     # Module documentation generator
│   │   ├── readme_gen.py     # README generation (multi-language)
│   │   └── template_manager.py # Jinja2 prompt templates
│   ├── output/
│   │   ├── html.py           # MkDocs-compatible output
│   │   ├── injector.py       # Docstring injection into source
│   │   └── markdown.py       # Markdown output generation
│   ├── parsers/
│   │   ├── js_parser.py      # JavaScript/TypeScript parser
│   │   ├── python_parser.py  # Python AST parser
│   │   └── structure.py      # Shared data models
│   └── utils/
│       ├── config.py         # Configuration loader
│       ├── git_utils.py      # Git integration for incremental mode
│       └── logging.py        # Structured logging setup
├── templates/                # Jinja2 prompt templates
├── tests/                    # Unit and integration tests
├── Dockerfile
├── Makefile
├── requirements.txt
└── pyproject.toml
```

## Architecture

```
Source Files ──► Parsers (AST/tree-sitter)
                    │
                    ▼
              Data Models (ModuleInfo, FunctionInfo, ClassInfo)
                    │
           ┌────────┼────────┐
           ▼        ▼        ▼
      Complexity  Call Graph  Dependency Graph
      Analysis    Analysis    Visualization
           │        │             │
           └────────┼─────────────┘
                    ▼
              Generators (LLM-powered)
                    │
           ┌────────┼────────┐
           ▼        ▼        ▼
        Markdown   HTML    Injector
        Output    (MkDocs)  (in-place)
```

## Development

```bash
# Install dependencies
make install

# Run tests
make test

# Lint and format
make lint

# Launch the analytics dashboard
make dashboard

# Run all pre-commit hooks
pre-commit run --all-files
```

## Testing

```bash
# Full test suite with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_module_gen.py -v

# Run integration tests only
pytest tests/test_integration.py -v
```

## License

MIT
