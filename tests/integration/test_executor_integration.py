"""Integration tests for the executor module — full workflow with real filesystem.

These tests cover:
- Session lifecycle: create → save → load → delete
- TASK.md generation with and without scan data
- Decision logging with real file I/O
- Session + context + logger working together end-to-end
- Model round-trip serialization (JSON file → model → JSON file)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from imp.executor.context import ContextGenerator
from imp.executor.logger import DecisionLogger
from imp.executor.models import (
    CleanResult,
    CompletionAttempt,
    CompletionResult,
    ContextBudget,
    SessionListEntry,
    SessionStatus,
    WorktreeSession,
)
from imp.executor.session import SessionStore


class TestSessionLifecycle:
    """Integration tests for SessionStore with real filesystem."""

    def test_create_save_load_round_trip(self, tmp_path: Path) -> None:
        """Save a session and load it back — all fields should survive."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-100",
            title="Test session lifecycle",
            description="Full round-trip test",
        )
        store.save(session)

        loaded = store.load("IMP-100")
        assert loaded is not None
        assert loaded.ticket_id == "IMP-100"
        assert loaded.title == "Test session lifecycle"
        assert loaded.description == "Full round-trip test"
        assert loaded.status == SessionStatus.active
        assert loaded.branch == "imp/IMP-100"
        assert loaded.worktree_path == ".trees/IMP-100"

    def test_multiple_sessions_list(self, tmp_path: Path) -> None:
        """Save multiple sessions and list them all."""
        store = SessionStore(tmp_path)
        for i in range(5):
            session = WorktreeSession(
                ticket_id=f"IMP-{i}",
                title=f"Session {i}",
            )
            store.save(session)

        sessions = store.list_sessions()
        assert len(sessions) == 5
        ids = {s.ticket_id for s in sessions}
        assert ids == {"IMP-0", "IMP-1", "IMP-2", "IMP-3", "IMP-4"}

    def test_delete_removes_session(self, tmp_path: Path) -> None:
        """Delete should remove the JSON file."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(ticket_id="IMP-DEL", title="To delete")
        store.save(session)
        assert store.exists("IMP-DEL")

        deleted = store.delete("IMP-DEL")
        assert deleted is True
        assert store.exists("IMP-DEL") is False
        assert store.load("IMP-DEL") is None

    def test_status_transition_persists(self, tmp_path: Path) -> None:
        """Mutating status and re-saving should persist the change."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(ticket_id="IMP-STAT", title="Status test")
        store.save(session)

        # Transition to done
        session.status = SessionStatus.done
        store.save(session)

        loaded = store.load("IMP-STAT")
        assert loaded is not None
        assert loaded.status == SessionStatus.done

    def test_overwrite_existing_session(self, tmp_path: Path) -> None:
        """Re-saving with same ticket_id overwrites."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(ticket_id="IMP-OW", title="Original")
        store.save(session)

        session.title = "Updated"
        store.save(session)

        loaded = store.load("IMP-OW")
        assert loaded is not None
        assert loaded.title == "Updated"

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        """No sessions directory → empty list."""
        store = SessionStore(tmp_path)
        assert store.list_sessions() == []


class TestContextGeneratorIntegration:
    """Integration tests for ContextGenerator with real filesystem."""

    def test_generate_without_scan_data(self, tmp_path: Path) -> None:
        """Generate TASK.md without scan data — should use fallback text."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-CTX",
            title="Context test",
            description="Build the context module",
        )
        content = gen.generate(session)

        assert "IMP-CTX" in content
        assert "Context test" in content
        assert "Build the context module" in content
        assert "imp init" in content  # fallback text
        assert "imp check" in content  # conventions
        assert "imp/IMP-CTX" in content  # branch name

    def test_generate_with_scan_data(self, tmp_path: Path) -> None:
        """Generate TASK.md with scan data — should list modules."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-SCAN",
            title="Scan test",
        )
        scan_data = {
            "modules": [
                {"name": "imp.executor", "path": "src/imp/executor"},
                {"name": "imp.context", "path": "src/imp/context"},
            ]
        }
        content = gen.generate(session, scan_data=scan_data)

        assert "imp.executor" in content
        assert "src/imp/executor" in content
        assert "imp.context" in content
        assert ".index.md" in content

    def test_write_task_file(self, tmp_path: Path) -> None:
        """Write TASK.md to a directory and verify content."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-WRITE",
            title="Write test",
            description="Verify file write",
        )
        content = gen.generate(session)
        worktree = tmp_path / ".trees" / "IMP-WRITE"
        worktree.mkdir(parents=True)

        task_path = gen.write_task_file(worktree, content)
        assert task_path.exists()
        assert task_path.name == "TASK.md"
        text = task_path.read_text()
        assert "IMP-WRITE" in text
        assert "Write test" in text

    def test_context_budget_in_task_md(self, tmp_path: Path) -> None:
        """Context budget numbers should appear in TASK.md."""
        gen = ContextGenerator(tmp_path)
        budget = ContextBudget(max_tokens=100_000, used_tokens=25_000, reserved_tokens=20_000)
        session = WorktreeSession(
            ticket_id="IMP-BUD",
            title="Budget test",
            context_budget=budget,
        )
        content = gen.generate(session)

        assert "25,000" in content
        assert "100,000" in content
        assert "25.0%" in content


class TestDecisionLoggerIntegration:
    """Integration tests for DecisionLogger with real filesystem."""

    def test_log_and_load_round_trip(self, tmp_path: Path) -> None:
        """Log a decision and load it back."""
        logger = DecisionLogger(tmp_path)

        # Create a mock worktree dir (git diff will fail gracefully)
        wt = tmp_path / ".trees" / "IMP-LOG"
        wt.mkdir(parents=True)

        attempts = [
            CompletionAttempt(
                attempt_number=1,
                check_passed=True,
                check_output="All passed",
                review_passed=True,
                review_output="No issues",
                timestamp=datetime.now(UTC),
            )
        ]

        entry = logger.log_completion(
            ticket_id="IMP-LOG",
            attempts=attempts,
            outcome="done",
            worktree_path=wt,
        )
        assert entry.ticket_id == "IMP-LOG"
        assert entry.outcome == "done"

        loaded = logger.load("IMP-LOG")
        assert loaded is not None
        assert loaded.ticket_id == "IMP-LOG"
        assert loaded.outcome == "done"
        assert len(loaded.attempt_history) == 1

    def test_list_decisions(self, tmp_path: Path) -> None:
        """Log multiple decisions and list them."""
        logger = DecisionLogger(tmp_path)
        wt = tmp_path / "worktree"
        wt.mkdir()

        for i in range(3):
            logger.log_completion(
                ticket_id=f"IMP-{i}",
                attempts=[],
                outcome="done",
                worktree_path=wt,
            )

        decisions = logger.list_decisions()
        assert len(decisions) == 3

    def test_empty_decisions(self, tmp_path: Path) -> None:
        """No decisions logged → empty list."""
        logger = DecisionLogger(tmp_path)
        assert logger.list_decisions() == []


class TestEndToEndWorkflow:
    """Integration tests exercising session + context + logger together."""

    def test_session_to_task_to_decision(self, tmp_path: Path) -> None:
        """Full flow: create session → generate TASK.md → log decision."""
        # 1. Create and save session
        store = SessionStore(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-E2E",
            title="End-to-end test",
            description="Verify full workflow",
        )
        store.save(session)

        # 2. Generate TASK.md
        ctx_gen = ContextGenerator(tmp_path)
        content = ctx_gen.generate(session)
        worktree = tmp_path / ".trees" / "IMP-E2E"
        worktree.mkdir(parents=True)
        ctx_gen.write_task_file(worktree, content)
        assert (worktree / "TASK.md").exists()

        # 3. Mark done + log decision
        session.status = SessionStatus.done
        store.save(session)

        logger = DecisionLogger(tmp_path)
        attempts = [
            CompletionAttempt(
                attempt_number=1,
                check_passed=True,
                check_output="ok",
                review_passed=True,
                review_output="clean",
                timestamp=datetime.now(UTC),
            )
        ]
        entry = logger.log_completion(
            ticket_id="IMP-E2E",
            attempts=attempts,
            outcome="done",
            worktree_path=worktree,
        )

        # Verify everything is on disk
        loaded_session = store.load("IMP-E2E")
        assert loaded_session is not None
        assert loaded_session.status == SessionStatus.done
        assert entry.outcome == "done"

    def test_escalation_flow(self, tmp_path: Path) -> None:
        """Test escalation: 3 failed checks → escalated status."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-ESC",
            title="Escalation test",
        )
        store.save(session)

        # Simulate 3 failed check attempts
        attempts = [
            CompletionAttempt(
                attempt_number=i + 1,
                check_passed=False,
                check_output=f"failed attempt {i + 1}",
                timestamp=datetime.now(UTC),
            )
            for i in range(3)
        ]

        # Mark escalated
        session.status = SessionStatus.escalated
        store.save(session)

        # Log decision
        logger = DecisionLogger(tmp_path)
        wt = tmp_path / ".trees" / "IMP-ESC"
        wt.mkdir(parents=True)
        entry = logger.log_completion(
            ticket_id="IMP-ESC",
            attempts=attempts,
            outcome="escalated",
            worktree_path=wt,
        )

        assert entry.outcome == "escalated"
        assert len(entry.attempt_history) == 3
        loaded = store.load("IMP-ESC")
        assert loaded is not None
        assert loaded.status == SessionStatus.escalated


class TestModelSerializationIntegration:
    """Integration tests for model JSON serialization round-trips via filesystem."""

    def test_worktree_session_json_file(self, tmp_path: Path) -> None:
        """Write WorktreeSession to JSON, read back, verify equality."""
        session = WorktreeSession(
            ticket_id="IMP-JSON",
            title="JSON round-trip",
            description="Testing serialization",
        )
        path = tmp_path / "session.json"
        path.write_text(session.model_dump_json(indent=2))

        loaded = WorktreeSession.model_validate_json(path.read_text())
        assert loaded.ticket_id == session.ticket_id
        assert loaded.title == session.title
        assert loaded.branch == "imp/IMP-JSON"

    def test_completion_result_json_file(self, tmp_path: Path) -> None:
        """Write CompletionResult to JSON, read back, verify equality."""
        result = CompletionResult(
            ticket_id="IMP-CR",
            passed=True,
            attempts=[
                CompletionAttempt(
                    attempt_number=1,
                    check_passed=True,
                    check_output="all green",
                    review_passed=True,
                    review_output="clean",
                    timestamp=datetime.now(UTC),
                )
            ],
            committed=True,
            commit_hash="abc123",
            pm_updated=False,
        )
        path = tmp_path / "result.json"
        path.write_text(result.model_dump_json(indent=2))

        loaded = CompletionResult.model_validate_json(path.read_text())
        assert loaded.ticket_id == "IMP-CR"
        assert loaded.passed is True
        assert loaded.committed is True
        assert loaded.commit_hash == "abc123"
        assert loaded.exit_code == 0

    def test_clean_result_serialization(self, tmp_path: Path) -> None:
        """CleanResult round-trip."""
        clean = CleanResult(
            removed_sessions=["IMP-1", "IMP-2"],
            skipped_sessions=["IMP-3"],
            pruned_branches=["imp/IMP-1", "imp/IMP-2"],
        )
        path = tmp_path / "clean.json"
        path.write_text(clean.model_dump_json())

        loaded = CleanResult.model_validate_json(path.read_text())
        assert loaded.removed_sessions == ["IMP-1", "IMP-2"]
        assert loaded.skipped_sessions == ["IMP-3"]

    def test_session_list_entry_from_session(self, tmp_path: Path) -> None:
        """SessionListEntry can be derived from WorktreeSession fields."""
        session = WorktreeSession(
            ticket_id="IMP-SLE",
            title="List entry",
            status=SessionStatus.done,
        )
        entry = SessionListEntry(
            ticket_id=session.ticket_id,
            title=session.title,
            status=session.status,
            branch=session.branch,
            attempt_count=session.attempt_count,
            created_at=session.created_at,
        )
        data = json.loads(entry.model_dump_json())
        assert data["ticket_id"] == "IMP-SLE"
        assert data["status"] == "done"
        assert data["branch"] == "imp/IMP-SLE"
