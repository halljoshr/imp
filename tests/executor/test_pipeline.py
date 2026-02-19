"""Tests for CompletionPipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from imp.executor.models import (
    CompletionAttempt,
    CompletionResult,
    SessionStatus,
    WorktreeSession,
)
from imp.executor.pipeline import CompletionPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(ticket_id: str = "IMP-1") -> WorktreeSession:
    return WorktreeSession(ticket_id=ticket_id, title="Test ticket")


def _completed_process(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestCompletionPipelineCreation:
    """Test CompletionPipeline initialization."""

    def test_creation_with_project_root(self, tmp_path: Path) -> None:
        """Can create CompletionPipeline with project_root."""
        pipeline = CompletionPipeline(project_root=tmp_path)

        assert pipeline.project_root == tmp_path

    def test_default_max_retries(self, tmp_path: Path) -> None:
        """Default circuit breaker max retries is 3."""
        pipeline = CompletionPipeline(project_root=tmp_path)

        assert pipeline.max_retries == 3


# ---------------------------------------------------------------------------
# _run_check
# ---------------------------------------------------------------------------


class TestRunCheck:
    """Test _run_check helper."""

    def test_run_check_calls_correct_command(self, tmp_path: Path) -> None:
        """_run_check calls 'imp check' in the worktree directory."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(returncode=0, stdout="All checks passed")
            passed, output = pipeline._run_check(worktree)

        call_kwargs = mock_run.call_args.kwargs
        assert mock_run.call_args.args[0] == ["imp", "check"]
        assert call_kwargs["cwd"] == worktree
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert passed is True
        assert "All checks passed" in output

    def test_run_check_strips_virtual_env_from_env(self, tmp_path: Path) -> None:
        """_run_check removes VIRTUAL_ENV from subprocess env to avoid venv conflicts."""
        import os

        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with (
            patch("subprocess.run") as mock_run,
            patch.dict(os.environ, {"VIRTUAL_ENV": "/some/parent/venv"}),
        ):
            mock_run.return_value = _completed_process(returncode=0)
            pipeline._run_check(worktree)

        env_passed = mock_run.call_args.kwargs.get("env", {})
        assert "VIRTUAL_ENV" not in env_passed

    def test_run_check_returns_false_on_nonzero_exit(self, tmp_path: Path) -> None:
        """_run_check returns (False, output) when imp check fails."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(
                returncode=1, stdout="", stderr="Lint errors"
            )
            passed, _output = pipeline._run_check(worktree)

        assert passed is False

    def test_run_check_includes_stderr_in_output(self, tmp_path: Path) -> None:
        """_run_check includes stderr content in output string."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(
                returncode=1, stdout="", stderr="Type error"
            )
            passed, output = pipeline._run_check(worktree)

        assert passed is False
        assert "Type error" in output


# ---------------------------------------------------------------------------
# _run_review
# ---------------------------------------------------------------------------


class TestRunReview:
    """Test _run_review helper."""

    def test_run_review_calls_correct_command(self, tmp_path: Path) -> None:
        """_run_review calls 'imp review --format json' in the worktree directory."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(returncode=0, stdout='{"passed": true}')
            passed, _output = pipeline._run_review(worktree)

        call_kwargs = mock_run.call_args.kwargs
        assert mock_run.call_args.args[0] == ["imp", "review", "--format", "json"]
        assert call_kwargs["cwd"] == worktree
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert passed is True

    def test_run_review_returns_false_on_review_issues(self, tmp_path: Path) -> None:
        """_run_review returns (False, output) when review finds issues."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(returncode=1, stdout='{"passed": false}')
            passed, _output = pipeline._run_review(worktree)

        assert passed is False

    def test_run_review_returns_output(self, tmp_path: Path) -> None:
        """_run_review returns the subprocess output."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        raw = '{"passed": true, "issues": []}'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(returncode=0, stdout=raw)
            _, output = pipeline._run_review(worktree)

        assert output == raw


# ---------------------------------------------------------------------------
# _commit_changes
# ---------------------------------------------------------------------------


class TestCommitChanges:
    """Test _commit_changes helper."""

    def test_commit_changes_runs_git_add_and_commit(self, tmp_path: Path) -> None:
        """_commit_changes runs git add then git commit."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _completed_process(returncode=0),  # git add
                _completed_process(returncode=0, stdout="abc1234"),  # git commit
                _completed_process(returncode=0, stdout="abc1234\n"),  # git rev-parse
            ]
            pipeline._commit_changes(worktree, "IMP-1")

        assert mock_run.call_count >= 2
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "git" in first_call_args
        assert "add" in first_call_args

    def test_commit_changes_returns_hash_on_success(self, tmp_path: Path) -> None:
        """_commit_changes returns commit hash on success."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _completed_process(returncode=0),  # git add
                _completed_process(
                    returncode=0, stdout="[imp/IMP-1 abc1234] IMP-1: complete"
                ),  # git commit
                _completed_process(returncode=0, stdout="abc1234\n"),  # git rev-parse
            ]
            result = pipeline._commit_changes(worktree, "IMP-1")

        assert result is not None

    def test_commit_changes_returns_none_on_failure(self, tmp_path: Path) -> None:
        """_commit_changes returns None when git commit fails."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _completed_process(returncode=0),  # git add
                _completed_process(returncode=1, stderr="nothing to commit"),  # git commit fails
            ]
            result = pipeline._commit_changes(worktree, "IMP-1")

        assert result is None

    def test_commit_changes_returns_none_when_git_add_fails(self, tmp_path: Path) -> None:
        """_commit_changes returns None when git add fails."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _completed_process(returncode=1, stderr="add failed")
            result = pipeline._commit_changes(worktree, "IMP-1")

        assert result is None

    def test_commit_changes_returns_none_when_rev_parse_fails(self, tmp_path: Path) -> None:
        """_commit_changes returns None when git rev-parse fails."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _completed_process(returncode=0),  # git add
                _completed_process(returncode=0),  # git commit
                _completed_process(returncode=1, stderr="rev-parse failed"),  # git rev-parse
            ]
            result = pipeline._commit_changes(worktree, "IMP-1")

        assert result is None


# ---------------------------------------------------------------------------
# _update_pm
# ---------------------------------------------------------------------------


class TestUpdatePm:
    """Test _update_pm helper."""

    def test_update_pm_returns_false_when_no_api_key(self, tmp_path: Path) -> None:
        """_update_pm returns False when PLANE_API_KEY is not set."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        result = CompletionResult(
            ticket_id="IMP-1",
            passed=True,
            attempts=[],
            commit_hash="abc1234",
        )

        import os

        env_backup = os.environ.pop("PLANE_API_KEY", None)
        try:
            outcome = pipeline._update_pm("IMP-1", result)
        finally:
            if env_backup is not None:
                os.environ["PLANE_API_KEY"] = env_backup

        assert outcome is False

    def test_update_pm_does_not_raise_on_failure(self, tmp_path: Path) -> None:
        """_update_pm never raises — best-effort only."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        result = CompletionResult(
            ticket_id="IMP-1",
            passed=True,
            attempts=[],
            commit_hash=None,
        )

        import os

        os.environ["PLANE_API_KEY"] = "fake-key"
        try:
            with patch("imp.pm.plane.PlaneAdapter") as mock_adapter_cls:
                mock_adapter_cls.return_value.add_comment.side_effect = RuntimeError("PM failure")
                # Should NOT raise
                outcome = pipeline._update_pm("IMP-1", result)
        finally:
            del os.environ["PLANE_API_KEY"]

        assert outcome is False

    def test_update_pm_returns_true_on_success(self, tmp_path: Path) -> None:
        """_update_pm returns True when PlaneAdapter.add_comment succeeds."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        result = CompletionResult(
            ticket_id="IMP-1",
            passed=True,
            attempts=[],
            commit_hash="abc1234",
        )

        import os

        os.environ["PLANE_API_KEY"] = "fake-key"
        try:
            with (
                patch("imp.pm.models.PlaneConfig"),
                patch("imp.pm.plane.PlaneAdapter") as mock_adapter_cls,
            ):
                mock_adapter_cls.return_value.add_comment.return_value = None
                outcome = pipeline._update_pm("IMP-1", result)
        finally:
            del os.environ["PLANE_API_KEY"]

        assert outcome is True
        mock_adapter_cls.return_value.add_comment.assert_called_once()


# ---------------------------------------------------------------------------
# run — happy path
# ---------------------------------------------------------------------------


class TestCompletionPipelineRun:
    """Test CompletionPipeline.run full workflow."""

    def test_successful_completion_check_then_review_then_commit(self, tmp_path: Path) -> None:
        """Successful run: check passes, review passes, commit succeeds."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()
        expected_wt = tmp_path / session.worktree_path

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")) as mock_check,
            patch.object(
                pipeline, "_run_review", return_value=(True, '{"passed":true}')
            ) as mock_review,
            patch.object(pipeline, "_commit_changes", return_value="abc1234") as mock_commit,
            patch.object(pipeline, "_update_pm", return_value=True),
        ):
            result = pipeline.run(session)

        mock_check.assert_called_once_with(expected_wt)
        mock_review.assert_called_once_with(expected_wt)
        mock_commit.assert_called_once()
        assert result.passed is True
        assert result.exit_code == 0
        assert result.commit_hash == "abc1234"

    def test_result_includes_all_attempts_in_history(self, tmp_path: Path) -> None:
        """Result has attempt history even on first-try success."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")),
            patch.object(pipeline, "_run_review", return_value=(True, "{}")),
            patch.object(pipeline, "_commit_changes", return_value="abc"),
            patch.object(pipeline, "_update_pm", return_value=True),
        ):
            result = pipeline.run(session)

        assert isinstance(result.attempts, list)
        assert len(result.attempts) >= 1

    def test_session_status_updated_to_done_on_success(self, tmp_path: Path) -> None:
        """Session status is set to done when pipeline completes successfully."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")),
            patch.object(pipeline, "_run_review", return_value=(True, "{}")),
            patch.object(pipeline, "_commit_changes", return_value="abc"),
            patch.object(pipeline, "_update_pm", return_value=True),
        ):
            pipeline.run(session)

        assert session.status == SessionStatus.done

    def test_commit_only_happens_after_check_and_review_pass(self, tmp_path: Path) -> None:
        """Commit is NOT called when check or review fails."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(False, "lint error")),
            patch.object(pipeline, "_run_review") as mock_review,
            patch.object(pipeline, "_commit_changes") as mock_commit,
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            pipeline.run(session)

        mock_review.assert_not_called()
        mock_commit.assert_not_called()

    def test_review_finding_issues_returns_exit_code_1(self, tmp_path: Path) -> None:
        """When review finds issues, result has exit_code=1."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")),
            patch.object(pipeline, "_run_review", return_value=(False, '{"passed":false}')),
            patch.object(pipeline, "_commit_changes") as mock_commit,
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            result = pipeline.run(session)

        mock_commit.assert_not_called()
        assert result.exit_code == 1
        assert result.passed is False

    def test_pm_update_failure_does_not_affect_result(self, tmp_path: Path) -> None:
        """PM update failure doesn't change the pipeline result."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")),
            patch.object(pipeline, "_run_review", return_value=(True, "{}")),
            patch.object(pipeline, "_commit_changes", return_value="abc"),
            patch.object(pipeline, "_update_pm", return_value=False),  # PM fails
        ):
            result = pipeline.run(session)

        assert result.passed is True
        assert result.exit_code == 0

    def test_pm_update_is_called_after_success(self, tmp_path: Path) -> None:
        """PM update is attempted after successful check + review + commit."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(True, "ok")),
            patch.object(pipeline, "_run_review", return_value=(True, "{}")),
            patch.object(pipeline, "_commit_changes", return_value="abc"),
            patch.object(pipeline, "_update_pm") as mock_pm,
        ):
            mock_pm.return_value = True
            pipeline.run(session)

        mock_pm.assert_called_once()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Test circuit breaker: 3 check failures → escalate."""

    def test_check_failure_increments_attempt_count(self, tmp_path: Path) -> None:
        """Each failed check increments the attempt counter."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        call_count = 0

        def _check_always_fail(worktree: Path) -> tuple[bool, str]:
            nonlocal call_count
            call_count += 1
            return (False, f"fail #{call_count}")

        with (
            patch.object(pipeline, "_run_check", side_effect=_check_always_fail),
            patch.object(pipeline, "_run_review") as mock_review,
            patch.object(pipeline, "_commit_changes") as mock_commit,
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            pipeline.run(session)

        # Circuit breaks after max_retries (3) — review and commit never called
        mock_review.assert_not_called()
        mock_commit.assert_not_called()
        assert call_count == 3

    def test_circuit_breaker_three_failures_escalates(self, tmp_path: Path) -> None:
        """After 3 check failures the result is escalated."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(False, "error")),
            patch.object(pipeline, "_run_review"),
            patch.object(pipeline, "_commit_changes"),
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            result = pipeline.run(session)

        assert result.exit_code == 2

    def test_escalated_result_has_exit_code_2(self, tmp_path: Path) -> None:
        """Escalated CompletionResult has exit_code == 2."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(False, "error")),
            patch.object(pipeline, "_run_review"),
            patch.object(pipeline, "_commit_changes"),
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            result = pipeline.run(session)

        assert result.exit_code == 2
        assert result.passed is False

    def test_session_status_updated_to_escalated_on_circuit_break(self, tmp_path: Path) -> None:
        """Session status becomes escalated when circuit breaker fires."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(False, "error")),
            patch.object(pipeline, "_run_review"),
            patch.object(pipeline, "_commit_changes"),
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            pipeline.run(session)

        assert session.status == SessionStatus.escalated

    def test_attempt_history_recorded_for_each_failure(self, tmp_path: Path) -> None:
        """Each attempt is recorded in result.attempts."""
        pipeline = CompletionPipeline(project_root=tmp_path)
        session = _make_session()

        with (
            patch.object(pipeline, "_run_check", return_value=(False, "error")),
            patch.object(pipeline, "_run_review"),
            patch.object(pipeline, "_commit_changes"),
            patch.object(pipeline, "_update_pm", return_value=False),
        ):
            result = pipeline.run(session)

        assert len(result.attempts) == pipeline.max_retries
        for attempt in result.attempts:
            assert isinstance(attempt, CompletionAttempt)
