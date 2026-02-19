"""CompletionPipeline — check → review → commit → PM update."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from imp.executor.models import (
    CompletionAttempt,
    CompletionResult,
    SessionStatus,
    WorktreeSession,
)


class CompletionPipeline:
    """Runs the completion pipeline for a managed executor session.

    Circuit breaker: 3 consecutive check failures → escalate.
    Review issues → return exit_code=1 (user can fix).
    Success → commit + PM update → exit_code=0.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.max_retries = 3

    def run(self, session: WorktreeSession) -> CompletionResult:
        """Run completion pipeline on the session's worktree."""
        worktree = self.project_root / session.worktree_path
        attempts: list[CompletionAttempt] = []

        for i in range(self.max_retries):
            check_passed, check_output = self._run_check(worktree)
            attempt = CompletionAttempt(
                attempt_number=i + 1,
                check_passed=check_passed,
                check_output=check_output,
                timestamp=datetime.now(UTC),
            )

            if check_passed:
                review_passed, review_output = self._run_review(worktree)
                attempt = CompletionAttempt(
                    attempt_number=i + 1,
                    check_passed=True,
                    check_output=check_output,
                    review_passed=review_passed,
                    review_output=review_output,
                    timestamp=attempt.timestamp,
                )
                attempts.append(attempt)

                if review_passed:
                    commit_hash = self._commit_changes(worktree, session.ticket_id)
                    completion = CompletionResult(
                        ticket_id=session.ticket_id,
                        passed=True,
                        attempts=attempts,
                        committed=True,
                        commit_hash=commit_hash,
                        pm_updated=False,
                    )
                    pm_updated = self._update_pm(session.ticket_id, completion)
                    session.status = SessionStatus.done
                    return CompletionResult(
                        ticket_id=session.ticket_id,
                        passed=True,
                        attempts=attempts,
                        committed=True,
                        commit_hash=commit_hash,
                        pm_updated=pm_updated,
                    )
                else:
                    # Review found issues — fixable by agent
                    return CompletionResult(
                        ticket_id=session.ticket_id,
                        passed=False,
                        attempts=attempts,
                    )
            else:
                attempts.append(attempt)

        # Circuit breaker: all retries exhausted → escalate
        session.status = SessionStatus.escalated
        return CompletionResult(
            ticket_id=session.ticket_id,
            passed=False,
            escalated=True,
            attempts=attempts,
        )

    @staticmethod
    def _subprocess_env() -> dict[str, str]:
        """Return a clean env for worktree subprocesses.

        Strips VIRTUAL_ENV so uv picks up the worktree's own venv rather than
        inheriting the parent process's venv path.
        """
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env.pop("VIRTUAL_ENV_PROMPT", None)
        return env

    def _run_check(self, worktree_path: Path) -> tuple[bool, str]:
        """Run 'imp check' in the worktree directory."""
        result = subprocess.run(
            ["imp", "check"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            env=self._subprocess_env(),
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output

    def _run_review(self, worktree_path: Path) -> tuple[bool, str]:
        """Run 'imp review --format json' in the worktree directory."""
        result = subprocess.run(
            ["imp", "review", "--format", "json"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            env=self._subprocess_env(),
        )
        return result.returncode == 0, result.stdout

    def _commit_changes(self, worktree_path: Path, ticket_id: str) -> str | None:
        """Stage all changes, commit, and return the commit hash."""
        add_result = subprocess.run(
            ["git", "add", "-A"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            return None

        commit_result = subprocess.run(
            ["git", "commit", "-m", f"{ticket_id}: complete"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if commit_result.returncode != 0:
            return None

        rev_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if rev_result.returncode != 0:
            return None

        return rev_result.stdout.strip() or None

    def _update_pm(self, ticket_id: str, result: CompletionResult) -> bool:
        """Best-effort PM update. Returns False if no PLANE_API_KEY or on failure."""
        api_key = os.environ.get("PLANE_API_KEY")
        if not api_key:
            return False

        try:
            from imp.pm.models import PlaneConfig  # lazy: plane-sdk is optional
            from imp.pm.plane import PlaneAdapter

            workspace = os.environ.get("PLANE_WORKSPACE_SLUG", "")
            project = os.environ.get("PLANE_PROJECT_ID", "")
            base_url = os.environ.get("PLANE_BASE_URL", "http://localhost")
            config = PlaneConfig(
                api_key=api_key,
                workspace_slug=workspace,
                project_id=project,
                base_url=base_url,
            )
            adapter = PlaneAdapter(config)
            status = "done" if result.passed else "escalated"
            message = f"imp code done: ticket={ticket_id} status={status}"
            adapter.add_comment(ticket_id, message)
            return True
        except Exception:
            return False
