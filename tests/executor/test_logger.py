"""Tests for DecisionLogger."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from imp.executor.logger import DecisionLogger
from imp.executor.models import CompletionAttempt, DecisionEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attempt(
    attempt_num: int = 1, passed: bool = False, output: str = "error"
) -> CompletionAttempt:
    return CompletionAttempt(
        attempt_number=attempt_num,
        check_passed=passed,
        check_output=output,
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestDecisionLoggerCreation:
    """Test DecisionLogger initialization."""

    def test_creation_with_project_root(self, tmp_path: Path) -> None:
        """Can create DecisionLogger with project_root."""
        logger = DecisionLogger(project_root=tmp_path)

        assert logger.project_root == tmp_path

    def test_decisions_dir_path(self, tmp_path: Path) -> None:
        """Decisions stored at .imp/decisions/ inside project_root."""
        logger = DecisionLogger(project_root=tmp_path)

        assert logger.decisions_dir == tmp_path / ".imp" / "decisions"


# ---------------------------------------------------------------------------
# log_completion
# ---------------------------------------------------------------------------


class TestLogCompletion:
    """Test log_completion saves decision entries."""

    def test_log_completion_creates_decision_entry(self, tmp_path: Path) -> None:
        """log_completion returns a DecisionEntry with correct fields."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-1"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt(1, passed=True, output="ok")]

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = (
                " src/imp/executor/models.py | 10 ++++\n 1 file changed, 10 insertions(+)"
            )
            mock_run.return_value = proc

            entry = logger.log_completion(
                ticket_id="IMP-1",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        assert entry.ticket_id == "IMP-1"
        assert entry.outcome == "done"
        assert entry.attempt_history == attempts

    def test_log_completion_saves_to_correct_path(self, tmp_path: Path) -> None:
        """log_completion saves JSON to .imp/decisions/{ticket_id}.json."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-2"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt()]

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = " 1 file changed"
            mock_run.return_value = proc

            logger.log_completion(
                ticket_id="IMP-2",
                attempts=attempts,
                outcome="escalated",
                worktree_path=worktree,
            )

        expected_path = tmp_path / ".imp" / "decisions" / "IMP-2.json"
        assert expected_path.exists()

    def test_log_completion_calls_git_diff_stat(self, tmp_path: Path) -> None:
        """log_completion runs git diff --stat in the worktree."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-3"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt()]

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = " 2 files changed"
            mock_run.return_value = proc

            logger.log_completion(
                ticket_id="IMP-3",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "diff" in call_args
        assert "--stat" in call_args

    def test_log_completion_parses_files_changed_from_git_diff(self, tmp_path: Path) -> None:
        """log_completion extracts file paths from git diff output."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-4"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt()]

        diff_output = (
            " src/imp/executor/pipeline.py | 42 ++++++++++++\n"
            " src/imp/executor/logger.py   | 18 +++++\n"
            " 2 files changed, 60 insertions(+)"
        )

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = diff_output
            mock_run.return_value = proc

            entry = logger.log_completion(
                ticket_id="IMP-4",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        assert isinstance(entry.files_changed, list)
        assert len(entry.files_changed) >= 2

    def test_log_completion_skips_empty_file_parts_in_diff(self, tmp_path: Path) -> None:
        """Lines with | but empty file part are skipped."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-6"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt()]

        diff_output = " src/a.py | 10 +++\n | 3 +++\n 1 file changed, 13 insertions(+)"

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = diff_output
            mock_run.return_value = proc

            entry = logger.log_completion(
                ticket_id="IMP-6",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        assert entry.files_changed == ["src/a.py"]

    def test_log_completion_directory_auto_created_on_first_write(self, tmp_path: Path) -> None:
        """The .imp/decisions/ directory is created automatically."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-5"
        worktree.mkdir(parents=True)

        decisions_dir = tmp_path / ".imp" / "decisions"
        assert not decisions_dir.exists()

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = ""
            mock_run.return_value = proc

            logger.log_completion(
                ticket_id="IMP-5",
                attempts=[],
                outcome="done",
                worktree_path=worktree,
            )

        assert decisions_dir.exists()

    def test_log_completion_outcome_field_preserved(self, tmp_path: Path) -> None:
        """The outcome string is preserved correctly in the saved entry."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-6"
        worktree.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = ""
            mock_run.return_value = proc

            entry = logger.log_completion(
                ticket_id="IMP-6",
                attempts=[],
                outcome="escalated",
                worktree_path=worktree,
            )

        assert entry.outcome == "escalated"

    def test_log_completion_git_diff_failure_handled_gracefully(self, tmp_path: Path) -> None:
        """If git diff fails, log_completion still succeeds (empty files_changed)."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-7"
        worktree.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 1
            proc.stdout = ""
            mock_run.return_value = proc

            # Should not raise
            entry = logger.log_completion(
                ticket_id="IMP-7",
                attempts=[],
                outcome="done",
                worktree_path=worktree,
            )

        assert entry is not None
        assert entry.ticket_id == "IMP-7"


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------


class TestLoad:
    """Test load retrieves saved decision entries."""

    def test_load_returns_saved_entry(self, tmp_path: Path) -> None:
        """load returns the DecisionEntry after a log_completion."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-10"
        worktree.mkdir(parents=True)
        attempts = [_make_attempt(1, passed=True, output="ok")]

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = " 1 file changed"
            mock_run.return_value = proc

            saved_entry = logger.log_completion(
                ticket_id="IMP-10",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        loaded = logger.load("IMP-10")

        assert loaded is not None
        assert loaded.ticket_id == saved_entry.ticket_id
        assert loaded.outcome == saved_entry.outcome

    def test_load_returns_none_for_nonexistent_ticket(self, tmp_path: Path) -> None:
        """load returns None when no log exists for the given ticket."""
        logger = DecisionLogger(project_root=tmp_path)

        result = logger.load("NONEXISTENT-999")

        assert result is None

    def test_load_preserves_attempt_count(self, tmp_path: Path) -> None:
        """load correctly restores the attempt_history list."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-11"
        worktree.mkdir(parents=True)
        attempts = [
            _make_attempt(1, passed=False, output="lint error"),
            _make_attempt(2, passed=True, output="ok"),
        ]

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = ""
            mock_run.return_value = proc

            logger.log_completion(
                ticket_id="IMP-11",
                attempts=attempts,
                outcome="done",
                worktree_path=worktree,
            )

        loaded = logger.load("IMP-11")
        assert loaded is not None
        assert len(loaded.attempt_history) == 2


# ---------------------------------------------------------------------------
# list_decisions
# ---------------------------------------------------------------------------


class TestListDecisions:
    """Test list_decisions returns all saved entries."""

    def test_list_decisions_returns_empty_list_when_no_decisions(self, tmp_path: Path) -> None:
        """list_decisions returns [] when no decisions have been logged."""
        logger = DecisionLogger(project_root=tmp_path)

        result = logger.list_decisions()

        assert result == []

    def test_list_decisions_returns_all_entries(self, tmp_path: Path) -> None:
        """list_decisions returns all logged decision entries."""
        logger = DecisionLogger(project_root=tmp_path)

        ticket_ids = ["IMP-20", "IMP-21", "IMP-22"]
        for tid in ticket_ids:
            worktree = tmp_path / "trees" / tid
            worktree.mkdir(parents=True)
            with patch("subprocess.run") as mock_run:
                proc = MagicMock()
                proc.returncode = 0
                proc.stdout = ""
                mock_run.return_value = proc

                logger.log_completion(
                    ticket_id=tid,
                    attempts=[],
                    outcome="done",
                    worktree_path=worktree,
                )

        entries = logger.list_decisions()

        assert len(entries) == 3
        entry_ids = {e.ticket_id for e in entries}
        assert entry_ids == set(ticket_ids)

    def test_list_decisions_returns_list_of_decision_entries(self, tmp_path: Path) -> None:
        """Each item returned by list_decisions is a DecisionEntry."""
        logger = DecisionLogger(project_root=tmp_path)
        worktree = tmp_path / "trees" / "IMP-30"
        worktree.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = ""
            mock_run.return_value = proc

            logger.log_completion(
                ticket_id="IMP-30",
                attempts=[],
                outcome="done",
                worktree_path=worktree,
            )

        entries = logger.list_decisions()

        for entry in entries:
            assert isinstance(entry, DecisionEntry)
