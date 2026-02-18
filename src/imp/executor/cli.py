"""Executor CLI functions — start, done, list, clean."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from imp.executor.context import ContextGenerator
from imp.executor.logger import DecisionLogger
from imp.executor.models import SessionStatus, WorktreeSession
from imp.executor.pipeline import CompletionPipeline
from imp.executor.session import SessionStore
from imp.executor.worktree import WorktreeManager


def start_command(
    ticket_id: str,
    title: str,
    description: str = "",
    base_branch: str = "main",
    project_root: Path | None = None,
) -> int:
    """Start a new executor session for a ticket.

    Returns 0 on success, 1 on error or if session already active.
    """
    root = project_root if project_root is not None else Path.cwd()
    store = SessionStore(root)
    worktree_mgr = WorktreeManager(root)
    ctx_gen = ContextGenerator(root)

    # Check for existing active session
    existing = store.load(ticket_id)
    if existing is not None and existing.status == SessionStatus.active:
        return 1

    # Create worktree
    try:
        worktree_path = worktree_mgr.create(ticket_id, base_branch=base_branch)
    except Exception:
        return 1

    # Create and persist session
    session = WorktreeSession(
        ticket_id=ticket_id,
        title=title,
        description=description,
    )
    store.save(session)

    # Generate and write TASK.md into the worktree (best-effort)
    with contextlib.suppress(Exception):
        task_md = str(ctx_gen.generate(session))
        task_md_path = worktree_path / "TASK.md"
        task_md_path.parent.mkdir(parents=True, exist_ok=True)
        task_md_path.write_text(task_md, encoding="utf-8")

    return 0


def done_command(ticket_id: str, project_root: Path | None = None) -> int:
    """Run the completion pipeline for a ticket session.

    Returns the pipeline exit_code (0=passed, 1=issues, 2=escalated).
    Returns 1 if no session found.
    """
    root = project_root if project_root is not None else Path.cwd()
    store = SessionStore(root)
    pipeline = CompletionPipeline(root)
    logger = DecisionLogger(root)

    session = store.load(ticket_id)
    if session is None:
        return 1

    result = pipeline.run(session)

    # Log the decision
    worktree_path = root / session.worktree_path
    outcome = "done" if result.passed else ("escalated" if result.escalated else "failed")
    logger.log_completion(
        ticket_id=ticket_id,
        attempts=result.attempts,
        outcome=outcome,
        worktree_path=worktree_path,
    )

    # Persist updated session status
    store.save(session)

    return result.exit_code


def list_command(project_root: Path | None = None, format: str = "human") -> int:
    """List all executor sessions.

    Returns 0 always.
    """
    root = project_root if project_root is not None else Path.cwd()
    store = SessionStore(root)

    sessions = store.list_sessions()

    if format == "json":
        data = [
            {
                "ticket_id": s.ticket_id,
                "title": s.title,
                "status": s.status,
                "branch": s.branch,
                "attempt_count": s.attempt_count,
            }
            for s in sessions
        ]
        print(json.dumps(data))
    else:
        if not sessions:
            print("No sessions found.")
        else:
            for s in sessions:
                print(f"{s.ticket_id}  {s.status}  {s.title}")

    return 0


def clean_command(force: bool = False, project_root: Path | None = None) -> int:
    """Remove completed and escalated session worktrees.

    With --force, also removes active sessions.
    Returns 0 always.
    """
    root = project_root if project_root is not None else Path.cwd()
    store = SessionStore(root)
    worktree_mgr = WorktreeManager(root)

    sessions = store.list_sessions()

    for session in sessions:
        should_clean = force or session.status != SessionStatus.active
        if should_clean:
            with contextlib.suppress(Exception):
                worktree_mgr.remove(session.ticket_id)
            store.delete(session.ticket_id)

    return 0
