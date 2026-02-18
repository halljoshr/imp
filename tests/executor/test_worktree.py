"""Tests for executor.worktree — WorktreeManager subprocess-based git operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.executor.worktree import WorktreeError, WorktreeManager


def _make_manager(repo_root: Path) -> WorktreeManager:
    """Helper: create a WorktreeManager with a given root."""
    return WorktreeManager(repo_root)


class TestWorktreeManagerCreate:
    """Test create() method."""

    def test_create_calls_correct_git_command(self, tmp_path: Path) -> None:
        """create() runs the expected git worktree add command."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.create("IMP-001")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "git" in cmd
        assert "worktree" in cmd
        assert "add" in cmd
        assert ".trees/IMP-001" in " ".join(str(c) for c in cmd)
        assert "imp/IMP-001" in " ".join(str(c) for c in cmd)

    def test_create_uses_main_as_default_base_branch(self, tmp_path: Path) -> None:
        """create() defaults to 'main' as base branch."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.create("IMP-001")

        cmd = mock_run.call_args[0][0]
        assert "main" in " ".join(str(c) for c in cmd)

    def test_create_uses_custom_base_branch(self, tmp_path: Path) -> None:
        """create() uses the provided base branch."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.create("IMP-001", base_branch="develop")

        cmd = mock_run.call_args[0][0]
        assert "develop" in " ".join(str(c) for c in cmd)

    def test_create_returns_correct_path(self, tmp_path: Path) -> None:
        """create() returns the path to the new worktree."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = manager.create("IMP-001")

        assert str(result).endswith(".trees/IMP-001")

    def test_create_raises_worktree_error_on_failure(self, tmp_path: Path) -> None:
        """create() raises WorktreeError when subprocess returns non-zero."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: already exists"

        with patch("subprocess.run", return_value=mock_result), pytest.raises(WorktreeError):
            manager.create("IMP-001")

    def test_create_raises_worktree_error_on_subprocess_exception(self, tmp_path: Path) -> None:
        """create() raises WorktreeError when subprocess raises CalledProcessError."""
        manager = _make_manager(tmp_path)

        with (
            patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")),
            pytest.raises(WorktreeError),
        ):
            manager.create("IMP-001")


class TestWorktreeManagerRemove:
    """Test remove() method."""

    def test_remove_calls_correct_git_command(self, tmp_path: Path) -> None:
        """remove() runs the expected git worktree remove command."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.remove("IMP-001")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "worktree" in cmd
        assert "remove" in cmd
        assert ".trees/IMP-001" in " ".join(str(c) for c in cmd)

    def test_remove_raises_worktree_error_on_failure(self, tmp_path: Path) -> None:
        """remove() raises WorktreeError when subprocess returns non-zero."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: not a git repo"

        with patch("subprocess.run", return_value=mock_result), pytest.raises(WorktreeError):
            manager.remove("IMP-MISSING")

    def test_remove_raises_worktree_error_on_subprocess_exception(self, tmp_path: Path) -> None:
        """remove() raises WorktreeError when subprocess raises."""
        manager = _make_manager(tmp_path)

        with (
            patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")),
            pytest.raises(WorktreeError),
        ):
            manager.remove("IMP-001")


class TestWorktreeManagerListWorktrees:
    """Test list_worktrees() method."""

    PORCELAIN_OUTPUT = (
        "worktree /repo\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.trees/IMP-001\n"
        "HEAD def456\n"
        "branch refs/heads/imp/IMP-001\n"
        "\n"
    )

    def test_list_worktrees_calls_correct_git_command(self, tmp_path: Path) -> None:
        """list_worktrees() runs git worktree list --porcelain."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.PORCELAIN_OUTPUT

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.list_worktrees()

        cmd = mock_run.call_args[0][0]
        assert "worktree" in cmd
        assert "list" in cmd
        assert "--porcelain" in cmd

    def test_list_worktrees_parses_porcelain_output(self, tmp_path: Path) -> None:
        """list_worktrees() correctly parses porcelain output into dicts."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.PORCELAIN_OUTPUT

        with patch("subprocess.run", return_value=mock_result):
            trees = manager.list_worktrees()

        assert len(trees) == 2
        # First is the main worktree
        assert trees[0]["worktree"] == "/repo"
        assert trees[0]["HEAD"] == "abc123"
        assert trees[0]["branch"] == "refs/heads/main"
        # Second is the added worktree
        assert trees[1]["worktree"] == "/repo/.trees/IMP-001"
        assert trees[1]["HEAD"] == "def456"
        assert trees[1]["branch"] == "refs/heads/imp/IMP-001"

    def test_list_worktrees_returns_empty_list_when_no_output(self, tmp_path: Path) -> None:
        """list_worktrees() returns empty list when stdout is empty."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            trees = manager.list_worktrees()

        assert trees == []

    def test_list_worktrees_returns_list_of_dicts(self, tmp_path: Path) -> None:
        """list_worktrees() returns a list of dicts."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.PORCELAIN_OUTPUT

        with patch("subprocess.run", return_value=mock_result):
            trees = manager.list_worktrees()

        assert isinstance(trees, list)
        assert all(isinstance(t, dict) for t in trees)


class TestParsePorcelainEdgeCases:
    """Test _parse_porcelain edge cases for coverage."""

    def test_parse_porcelain_no_trailing_newline(self, tmp_path: Path) -> None:
        """Output that ends without a blank line still flushes the last entry."""
        manager = _make_manager(tmp_path)
        output = "worktree /repo\nHEAD abc123\nbranch refs/heads/main"
        trees = manager._parse_porcelain(output)
        assert len(trees) == 1
        assert trees[0]["worktree"] == "/repo"

    def test_parse_porcelain_consecutive_empty_lines(self, tmp_path: Path) -> None:
        """Consecutive empty lines don't produce empty dicts."""
        manager = _make_manager(tmp_path)
        output = "worktree /repo\nHEAD abc\n\n\nworktree /other\nHEAD def\n\n"
        trees = manager._parse_porcelain(output)
        assert len(trees) == 2


class TestWorktreeManagerExists:
    """Test exists() method."""

    PORCELAIN_WITH_IMP001 = (
        "worktree /repo\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.trees/IMP-001\n"
        "HEAD def456\n"
        "branch refs/heads/imp/IMP-001\n"
        "\n"
    )

    def test_exists_returns_true_when_worktree_present(self, tmp_path: Path) -> None:
        """exists() returns True when the ticket's worktree is in the list."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.PORCELAIN_WITH_IMP001

        with patch("subprocess.run", return_value=mock_result):
            assert manager.exists("IMP-001") is True

    def test_exists_returns_false_when_worktree_absent(self, tmp_path: Path) -> None:
        """exists() returns False when the ticket's worktree is not in the list."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.PORCELAIN_WITH_IMP001

        with patch("subprocess.run", return_value=mock_result):
            assert manager.exists("IMP-999") is False

    def test_exists_returns_false_when_no_worktrees(self, tmp_path: Path) -> None:
        """exists() returns False when there are no worktrees."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            assert manager.exists("IMP-001") is False


class TestWorktreeManagerPrune:
    """Test prune() method."""

    def test_prune_calls_git_worktree_prune(self, tmp_path: Path) -> None:
        """prune() runs git worktree prune."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.prune()

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "worktree" in cmd
        assert "prune" in cmd

    def test_prune_raises_worktree_error_on_failure(self, tmp_path: Path) -> None:
        """prune() raises WorktreeError when git worktree prune fails."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: prune failed"

        with patch("subprocess.run", return_value=mock_result), pytest.raises(WorktreeError):
            manager.prune()


class TestWorktreeManagerDeleteBranch:
    """Test delete_branch() method."""

    def test_delete_branch_uses_lowercase_d_by_default(self, tmp_path: Path) -> None:
        """delete_branch() uses -d (non-forced) by default."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.delete_branch("IMP-001")

        cmd = mock_run.call_args[0][0]
        # Should contain -d but not -D
        cmd_str = " ".join(str(c) for c in cmd)
        assert " -d " in cmd_str or cmd_str.endswith(" -d") or "-d" in cmd
        assert "-D" not in cmd_str

    def test_delete_branch_uses_uppercase_d_with_force(self, tmp_path: Path) -> None:
        """delete_branch() uses -D (forced) when force=True."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.delete_branch("IMP-001", force=True)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "-D" in cmd_str

    def test_delete_branch_targets_correct_branch_name(self, tmp_path: Path) -> None:
        """delete_branch() deletes imp/{ticket_id}."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.delete_branch("IMP-005")

        cmd = mock_run.call_args[0][0]
        assert "imp/IMP-005" in " ".join(str(c) for c in cmd)

    def test_delete_branch_calls_git_branch(self, tmp_path: Path) -> None:
        """delete_branch() runs git branch command."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.delete_branch("IMP-001")

        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "branch" in cmd

    def test_delete_branch_raises_worktree_error_on_failure(self, tmp_path: Path) -> None:
        """delete_branch() raises WorktreeError when git branch fails."""
        manager = _make_manager(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error: branch not found"

        with patch("subprocess.run", return_value=mock_result), pytest.raises(WorktreeError):
            manager.delete_branch("IMP-GONE")


class TestWorktreeError:
    """Test WorktreeError custom exception."""

    def test_worktree_error_is_exception(self) -> None:
        """WorktreeError is a subclass of Exception."""
        assert issubclass(WorktreeError, Exception)

    def test_worktree_error_can_be_raised(self) -> None:
        """WorktreeError can be raised and caught."""
        with pytest.raises(WorktreeError, match="test error"):
            raise WorktreeError("test error")

    def test_worktree_error_stores_message(self) -> None:
        """WorktreeError stores the message."""
        err = WorktreeError("something went wrong")
        assert "something went wrong" in str(err)
