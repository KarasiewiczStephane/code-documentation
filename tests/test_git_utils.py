"""Tests for git utilities and incremental mode."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.utils.git_utils import (
    DocState,
    compute_file_hash,
    filter_changed_files,
    get_changed_files_git,
    get_untracked_files,
    load_state,
    save_state,
    update_state_hashes,
)


class TestDocState:
    """Tests for DocState dataclass."""

    def test_defaults(self) -> None:
        state = DocState()
        assert state.last_run is None
        assert state.file_hashes == {}
        assert state.version == 1

    def test_to_dict(self) -> None:
        state = DocState(last_run="2025-01-01T00:00:00Z", file_hashes={"a.py": "abc"})
        d = state.to_dict()
        assert d["last_run"] == "2025-01-01T00:00:00Z"
        assert d["file_hashes"]["a.py"] == "abc"

    def test_from_dict(self) -> None:
        data = {
            "version": 1,
            "last_run": "2025-06-01T12:00:00Z",
            "file_hashes": {"b.py": "def"},
        }
        state = DocState.from_dict(data)
        assert state.last_run == "2025-06-01T12:00:00Z"
        assert state.file_hashes["b.py"] == "def"

    def test_roundtrip(self) -> None:
        original = DocState(
            last_run="2025-01-01T00:00:00Z",
            file_hashes={"a.py": "hash1", "b.py": "hash2"},
        )
        restored = DocState.from_dict(original.to_dict())
        assert restored.last_run == original.last_run
        assert restored.file_hashes == original.file_hashes


class TestGetChangedFilesGit:
    """Tests for git diff integration."""

    @patch("src.utils.git_utils.subprocess.run")
    def test_returns_changed_files(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="src/main.py\nsrc/utils.py\n", returncode=0
        )
        files = get_changed_files_git("/repo")
        assert "src/main.py" in files
        assert "src/utils.py" in files

    @patch("src.utils.git_utils.subprocess.run")
    def test_custom_ref(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="a.py\n", returncode=0)
        get_changed_files_git("/repo", since_ref="abc123")
        call_args = mock_run.call_args[0][0]
        assert "abc123" in call_args

    @patch("src.utils.git_utils.subprocess.run")
    def test_empty_diff(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        files = get_changed_files_git("/repo")
        assert files == []

    @patch("src.utils.git_utils.subprocess.run")
    def test_git_error(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        files = get_changed_files_git("/repo")
        assert files == []

    @patch("src.utils.git_utils.subprocess.run")
    def test_git_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("git not found")
        files = get_changed_files_git("/repo")
        assert files == []


class TestGetUntrackedFiles:
    """Tests for getting untracked files."""

    @patch("src.utils.git_utils.subprocess.run")
    def test_returns_untracked(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="new_file.py\n", returncode=0)
        files = get_untracked_files("/repo")
        assert "new_file.py" in files

    @patch("src.utils.git_utils.subprocess.run")
    def test_error_returns_empty(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        files = get_untracked_files("/repo")
        assert files == []


class TestComputeFileHash:
    """Tests for file hashing."""

    def test_hash_consistency(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        hash1 = compute_file_hash(str(f))
        hash2 = compute_file_hash(str(f))
        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_file_hash(str(f1)) != compute_file_hash(str(f2))

    def test_hash_is_hex_string(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("data")
        h = compute_file_hash(str(f))
        assert len(h) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in h)


class TestLoadSaveState:
    """Tests for state persistence."""

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        state = load_state(str(tmp_path / "nonexistent.json"))
        assert state.last_run is None
        assert state.file_hashes == {}

    def test_save_and_load(self, tmp_path: Path) -> None:
        state_path = str(tmp_path / "state.json")
        state = DocState(file_hashes={"a.py": "hash1"})
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert loaded.file_hashes["a.py"] == "hash1"
        assert loaded.last_run is not None

    def test_save_creates_directories(self, tmp_path: Path) -> None:
        state_path = str(tmp_path / "deep" / "nested" / "state.json")
        save_state(DocState(), state_path)
        assert Path(state_path).exists()


class TestFilterChangedFiles:
    """Tests for filtering changed files."""

    def test_new_files_are_changed(self, tmp_path: Path) -> None:
        (tmp_path / "new.py").write_text("def new(): pass")
        state = DocState()
        changed = filter_changed_files(["new.py"], state, str(tmp_path))
        assert "new.py" in changed

    def test_unchanged_files_filtered(self, tmp_path: Path) -> None:
        f = tmp_path / "same.py"
        f.write_text("def same(): pass")
        h = compute_file_hash(str(f))
        state = DocState(file_hashes={"same.py": h})
        changed = filter_changed_files(["same.py"], state, str(tmp_path))
        assert changed == []

    def test_modified_files_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def old(): pass")
        state = DocState(file_hashes={"mod.py": "old_hash"})
        changed = filter_changed_files(["mod.py"], state, str(tmp_path))
        assert "mod.py" in changed

    def test_nonexistent_files_skipped(self, tmp_path: Path) -> None:
        state = DocState()
        changed = filter_changed_files(["missing.py"], state, str(tmp_path))
        assert changed == []


class TestUpdateStateHashes:
    """Tests for updating state hashes."""

    def test_updates_hashes(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("content")
        state = DocState()
        update_state_hashes(state, ["a.py"], str(tmp_path))
        assert "a.py" in state.file_hashes
        assert state.file_hashes["a.py"] == compute_file_hash(str(f))

    def test_skips_nonexistent(self, tmp_path: Path) -> None:
        state = DocState()
        update_state_hashes(state, ["missing.py"], str(tmp_path))
        assert "missing.py" not in state.file_hashes
