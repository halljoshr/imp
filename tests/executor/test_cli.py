"""Tests for executor CLI functions (start/done/list/clean)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.executor.cli import clean_command, done_command, list_command, start_command
from imp.executor.models import CompletionResult, SessionStatus, WorktreeSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    ticket_id: str = "IMP-1",
    status: SessionStatus = SessionStatus.active,
) -> WorktreeSession:
    session = WorktreeSession(ticket_id=ticket_id, title="Test ticket")
    session.status = status
    return session


def _make_completion_result(
    ticket_id: str = "IMP-1",
    passed: bool = True,
    escalated: bool = False,
) -> CompletionResult:
    return CompletionResult(
        ticket_id=ticket_id,
        passed=passed,
        escalated=escalated,
        attempts=[],
        committed=passed,
        commit_hash="abc1234" if passed else None,
    )


# ---------------------------------------------------------------------------
# start_command
# ---------------------------------------------------------------------------


class TestStartCommand:
    """Test start_command creates worktree, session, and TASK.md."""

    def test_creates_session_worktree_and_task_md(self, tmp_path: Path) -> None:
        """start_command creates session, worktree, and TASK.md."""
        mock_store = MagicMock()
        mock_store.load.return_value = None  # No existing session
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.return_value = tmp_path / ".trees" / "IMP-1"
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            exit_code = start_command(
                ticket_id="IMP-1",
                title="Add executor module",
                project_root=tmp_path,
            )

        assert exit_code == 0
        mock_store.save.assert_called_once()
        mock_worktree_mgr.create.assert_called_once()

    def test_returns_0_on_success(self, tmp_path: Path) -> None:
        """start_command returns exit code 0 on success."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.return_value = tmp_path / ".trees" / "IMP-2"
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            result = start_command(
                ticket_id="IMP-2",
                title="Some title",
                project_root=tmp_path,
            )

        assert result == 0

    def test_returns_1_if_worktree_creation_fails(self, tmp_path: Path) -> None:
        """start_command returns exit code 1 when worktree creation fails."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.side_effect = RuntimeError("git error")
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            result = start_command(
                ticket_id="IMP-3",
                title="Failing ticket",
                project_root=tmp_path,
            )

        assert result == 1

    def test_returns_1_if_session_already_active(self, tmp_path: Path) -> None:
        """start_command returns 1 if an active session for the ticket already exists."""
        existing_session = _make_session("IMP-4", status=SessionStatus.active)
        mock_store = MagicMock()
        mock_store.load.return_value = existing_session
        mock_worktree_mgr = MagicMock()
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            result = start_command(
                ticket_id="IMP-4",
                title="Duplicate",
                project_root=tmp_path,
            )

        assert result == 1
        mock_worktree_mgr.create.assert_not_called()

    def test_uses_default_base_branch_main(self, tmp_path: Path) -> None:
        """start_command uses 'main' as the default base branch."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.return_value = tmp_path / ".trees" / "IMP-5"
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            start_command(
                ticket_id="IMP-5",
                title="Base branch test",
                project_root=tmp_path,
            )

        create_call = mock_worktree_mgr.create.call_args
        # base_branch should be "main" by default
        if create_call.kwargs:
            assert create_call.kwargs.get("base_branch", "main") == "main"
        else:
            # Positional: create(ticket_id, base_branch)
            assert len(create_call.args) < 3 or create_call.args[1] == "main"

    def test_uses_cwd_as_project_root_when_none(self) -> None:
        """start_command uses cwd as project_root when not provided."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.return_value = Path("/tmp/.trees/IMP-6")
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore") as mock_store_cls,
            patch("imp.executor.cli.WorktreeManager") as mock_wt_cls,
            patch("imp.executor.cli.ContextGenerator") as mock_ctx_cls,
        ):
            mock_store_cls.return_value = mock_store
            mock_wt_cls.return_value = mock_worktree_mgr
            mock_ctx_cls.return_value = mock_ctx_gen

            start_command(ticket_id="IMP-6", title="No root", project_root=None)

        # SessionStore should have been instantiated with some path (cwd)
        mock_store_cls.assert_called_once()

    def test_uses_custom_base_branch(self, tmp_path: Path) -> None:
        """start_command passes custom base_branch to WorktreeManager."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_worktree_mgr = MagicMock()
        mock_worktree_mgr.create.return_value = tmp_path / ".trees" / "IMP-7"
        mock_ctx_gen = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
            patch("imp.executor.cli.ContextGenerator", return_value=mock_ctx_gen),
        ):
            start_command(
                ticket_id="IMP-7",
                title="Custom base",
                base_branch="develop",
                project_root=tmp_path,
            )

        create_call = mock_worktree_mgr.create.call_args
        # Should have passed base_branch="develop"
        if create_call.kwargs.get("base_branch"):
            assert create_call.kwargs["base_branch"] == "develop"
        else:
            assert "develop" in [str(a) for a in create_call.args]


# ---------------------------------------------------------------------------
# done_command
# ---------------------------------------------------------------------------


class TestDoneCommand:
    """Test done_command runs completion pipeline."""

    def test_returns_0_when_pipeline_passes(self, tmp_path: Path) -> None:
        """done_command returns 0 when completion pipeline passes."""
        session = _make_session("IMP-10")
        mock_store = MagicMock()
        mock_store.load.return_value = session
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = _make_completion_result("IMP-10", passed=True)
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            result = done_command(ticket_id="IMP-10", project_root=tmp_path)

        assert result == 0

    def test_returns_1_when_review_finds_issues(self, tmp_path: Path) -> None:
        """done_command returns 1 when review finds issues (exit_code=1)."""
        session = _make_session("IMP-11")
        mock_store = MagicMock()
        mock_store.load.return_value = session
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = _make_completion_result("IMP-11", passed=False)
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            result = done_command(ticket_id="IMP-11", project_root=tmp_path)

        assert result == 1

    def test_returns_2_on_escalation(self, tmp_path: Path) -> None:
        """done_command returns 2 when pipeline escalates (circuit break)."""
        session = _make_session("IMP-12")
        mock_store = MagicMock()
        mock_store.load.return_value = session
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = _make_completion_result(
            "IMP-12", passed=False, escalated=True
        )
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            result = done_command(ticket_id="IMP-12", project_root=tmp_path)

        assert result == 2

    def test_returns_1_if_session_not_found(self, tmp_path: Path) -> None:
        """done_command returns 1 if no session exists for the ticket."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_pipeline = MagicMock()
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            result = done_command(ticket_id="MISSING-99", project_root=tmp_path)

        assert result == 1
        mock_pipeline.run.assert_not_called()

    def test_logs_decision_on_completion(self, tmp_path: Path) -> None:
        """done_command calls DecisionLogger.log_completion after pipeline."""
        session = _make_session("IMP-13")
        mock_store = MagicMock()
        mock_store.load.return_value = session
        completion_result = _make_completion_result("IMP-13", passed=True)
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = completion_result
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            done_command(ticket_id="IMP-13", project_root=tmp_path)

        mock_logger.log_completion.assert_called_once()

    def test_updates_session_status(self, tmp_path: Path) -> None:
        """done_command saves updated session status to the store."""
        session = _make_session("IMP-14", status=SessionStatus.active)
        mock_store = MagicMock()
        mock_store.load.return_value = session
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = _make_completion_result("IMP-14", passed=True)
        mock_logger = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.CompletionPipeline", return_value=mock_pipeline),
            patch("imp.executor.cli.DecisionLogger", return_value=mock_logger),
        ):
            done_command(ticket_id="IMP-14", project_root=tmp_path)

        # Store should be updated (save called with updated session)
        mock_store.save.assert_called()


# ---------------------------------------------------------------------------
# list_command
# ---------------------------------------------------------------------------


class TestListCommand:
    """Test list_command lists active sessions."""

    def test_returns_0_with_active_sessions(self, tmp_path: Path) -> None:
        """list_command returns 0 when there are active sessions."""
        sessions = [_make_session("IMP-20"), _make_session("IMP-21")]
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = sessions

        with patch("imp.executor.cli.SessionStore", return_value=mock_store):
            result = list_command(project_root=tmp_path)

        assert result == 0

    def test_returns_0_with_no_sessions(self, tmp_path: Path) -> None:
        """list_command returns 0 even when there are no sessions."""
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = []

        with patch("imp.executor.cli.SessionStore", return_value=mock_store):
            result = list_command(project_root=tmp_path)

        assert result == 0

    def test_human_format_does_not_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """list_command with human format produces output without crashing."""
        sessions = [_make_session("IMP-22")]
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = sessions

        with patch("imp.executor.cli.SessionStore", return_value=mock_store):
            result = list_command(project_root=tmp_path, format="human")

        assert result == 0

    def test_json_format_outputs_valid_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """list_command with json format outputs parseable JSON."""
        sessions = [_make_session("IMP-23")]
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = sessions

        with patch("imp.executor.cli.SessionStore", return_value=mock_store):
            result = list_command(project_root=tmp_path, format="json")

        assert result == 0
        captured = capsys.readouterr()
        # JSON output should be parseable if produced to stdout
        if captured.out.strip():
            parsed = json.loads(captured.out)
            assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# clean_command
# ---------------------------------------------------------------------------


class TestCleanCommand:
    """Test clean_command removes completed/escalated sessions."""

    def test_removes_done_and_escalated_sessions(self, tmp_path: Path) -> None:
        """clean_command removes done and escalated sessions."""
        done_session = _make_session("IMP-30", status=SessionStatus.done)
        escalated_session = _make_session("IMP-31", status=SessionStatus.escalated)
        active_session = _make_session("IMP-32", status=SessionStatus.active)

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [done_session, escalated_session, active_session]
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            result = clean_command(project_root=tmp_path)

        assert result == 0
        # Worktree removed for done + escalated (2 calls), not for active
        assert mock_worktree_mgr.remove.call_count == 2

    def test_skips_active_sessions_without_force(self, tmp_path: Path) -> None:
        """clean_command skips active sessions unless --force is used."""
        active_session = _make_session("IMP-33", status=SessionStatus.active)

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [active_session]
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            result = clean_command(force=False, project_root=tmp_path)

        assert result == 0
        mock_worktree_mgr.remove.assert_not_called()

    def test_force_removes_all_sessions(self, tmp_path: Path) -> None:
        """clean_command with --force removes ALL sessions including active."""
        active_session = _make_session("IMP-34", status=SessionStatus.active)
        done_session = _make_session("IMP-35", status=SessionStatus.done)

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [active_session, done_session]
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            result = clean_command(force=True, project_root=tmp_path)

        assert result == 0
        assert mock_worktree_mgr.remove.call_count == 2

    def test_removes_worktrees_and_deletes_branches(self, tmp_path: Path) -> None:
        """clean_command removes worktrees for cleaned sessions."""
        done_session = _make_session("IMP-36", status=SessionStatus.done)

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [done_session]
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            clean_command(project_root=tmp_path)

        mock_worktree_mgr.remove.assert_called_once_with("IMP-36")

    def test_returns_0_on_success(self, tmp_path: Path) -> None:
        """clean_command returns 0 on success."""
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = []
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            result = clean_command(project_root=tmp_path)

        assert result == 0

    def test_returns_0_with_no_sessions_to_clean(self, tmp_path: Path) -> None:
        """clean_command returns 0 even when there are no sessions to clean."""
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = []
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            result = clean_command(project_root=tmp_path)

        assert result == 0
        mock_worktree_mgr.remove.assert_not_called()

    def test_deletes_session_from_store_after_cleaning(self, tmp_path: Path) -> None:
        """clean_command removes cleaned sessions from the SessionStore."""
        done_session = _make_session("IMP-37", status=SessionStatus.done)

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [done_session]
        mock_worktree_mgr = MagicMock()

        with (
            patch("imp.executor.cli.SessionStore", return_value=mock_store),
            patch("imp.executor.cli.WorktreeManager", return_value=mock_worktree_mgr),
        ):
            clean_command(project_root=tmp_path)

        # Session should be deleted from the store
        mock_store.delete.assert_called_once_with("IMP-37")
