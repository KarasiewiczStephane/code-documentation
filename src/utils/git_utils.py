"""Git integration utilities for incremental documentation.

Provides functions to detect changed files via git diff, manage
documentation state tracking, and filter files for incremental
re-processing.
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DocState:
    """Tracks documentation generation state for incremental mode.

    Attributes:
        last_run: ISO timestamp of the last documentation run.
        file_hashes: Mapping of file paths to their content hashes.
        version: State file format version.
    """

    last_run: Optional[str] = None
    file_hashes: dict[str, str] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict:
        """Serialize state to a dictionary.

        Returns:
            Dictionary representation of the state.
        """
        return {
            "version": self.version,
            "last_run": self.last_run,
            "file_hashes": self.file_hashes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocState":
        """Deserialize state from a dictionary.

        Args:
            data: Dictionary with state fields.

        Returns:
            A DocState instance.
        """
        return cls(
            version=data.get("version", 1),
            last_run=data.get("last_run"),
            file_hashes=data.get("file_hashes", {}),
        )


def get_changed_files_git(repo_path: str, since_ref: Optional[str] = None) -> list[str]:
    """Get files changed in git since a given reference.

    Uses git diff to find modified, added, or renamed files.
    If no reference is given, returns files changed since HEAD~1.

    Args:
        repo_path: Path to the git repository root.
        since_ref: Git reference to diff against (e.g., 'HEAD~1', commit hash).

    Returns:
        List of changed file paths relative to the repo root.
    """
    ref = since_ref or "HEAD~1"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", ref],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        logger.info("Git diff found %d changed files since %s", len(files), ref)
        return files
    except subprocess.CalledProcessError as e:
        logger.warning("Git diff failed: %s", e.stderr.strip())
        return []
    except FileNotFoundError:
        logger.warning("Git not found in PATH")
        return []


def get_untracked_files(repo_path: str) -> list[str]:
    """Get untracked files in the git repository.

    Args:
        repo_path: Path to the git repository root.

    Returns:
        List of untracked file paths.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def compute_file_hash(file_path: str) -> str:
    """Compute the SHA-256 hash of a file's contents.

    Args:
        file_path: Path to the file.

    Returns:
        Hex digest of the file's SHA-256 hash.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_state(state_path: str) -> DocState:
    """Load documentation state from a JSON file.

    Args:
        state_path: Path to the state file.

    Returns:
        A DocState instance (empty state if file doesn't exist).
    """
    path = Path(state_path)
    if not path.exists():
        logger.info("No state file found at %s, starting fresh", state_path)
        return DocState()

    with open(path) as f:
        data = json.load(f)

    logger.info("Loaded state from %s (last run: %s)", state_path, data.get("last_run"))
    return DocState.from_dict(data)


def save_state(state: DocState, state_path: str) -> None:
    """Save documentation state to a JSON file.

    Args:
        state: The DocState to persist.
        state_path: Path to write the state file.
    """
    state.last_run = datetime.now(timezone.utc).isoformat()
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(state.to_dict(), f, indent=2)

    logger.info("Saved state to %s", state_path)


def filter_changed_files(
    all_files: list[str],
    state: DocState,
    repo_path: Optional[str] = None,
) -> list[str]:
    """Filter files to only those that have changed since last run.

    Compares current file hashes against stored hashes to determine
    which files need re-processing.

    Args:
        all_files: List of all file paths to consider.
        state: Previous documentation state with file hashes.
        repo_path: Optional repo root for resolving relative paths.

    Returns:
        List of file paths that have changed or are new.
    """
    changed = []
    root = Path(repo_path) if repo_path else Path.cwd()

    for file_path in all_files:
        full_path = (
            root / file_path if not Path(file_path).is_absolute() else Path(file_path)
        )

        if not full_path.exists():
            continue

        current_hash = compute_file_hash(str(full_path))
        stored_hash = state.file_hashes.get(file_path)

        if stored_hash != current_hash:
            changed.append(file_path)

    logger.info(
        "Filtered %d changed files from %d total",
        len(changed),
        len(all_files),
    )
    return changed


def update_state_hashes(
    state: DocState,
    files: list[str],
    repo_path: Optional[str] = None,
) -> None:
    """Update the state file hashes after processing files.

    Args:
        state: The DocState to update.
        files: List of processed file paths.
        repo_path: Optional repo root for resolving relative paths.
    """
    root = Path(repo_path) if repo_path else Path.cwd()

    for file_path in files:
        full_path = (
            root / file_path if not Path(file_path).is_absolute() else Path(file_path)
        )
        if full_path.exists():
            state.file_hashes[file_path] = compute_file_hash(str(full_path))
