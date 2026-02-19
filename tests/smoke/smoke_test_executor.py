#!/usr/bin/env python3
"""Smoke test for executor module.

This is a standalone script that validates the executor module works
in the wild, not just in test harnesses.

Run with: uv run python tests/smoke/smoke_test_executor.py

Exit codes:
- 0: All smoke tests passed
- 1: At least one smoke test failed
"""

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def test_imports() -> bool:
    """Test that all executor modules can be imported."""
    print("Testing imports...")

    try:
        from imp.executor import (  # noqa: F401
            CleanResult,
            CompletionAttempt,
            CompletionPipeline,
            CompletionResult,
            ContextBudget,
            ContextGenerator,
            DecisionEntry,
            DecisionLogger,
            SessionListEntry,
            SessionStatus,
            SessionStore,
            WorktreeError,
            WorktreeManager,
            WorktreeSession,
            clean_command,
            done_command,
            list_command,
            start_command,
        )

        print("  All executor exports imported successfully")
        return True
    except ImportError as e:
        print(f"  Import error: {e}")
        return False


def test_models() -> bool:
    """Test that executor models instantiate correctly."""
    print("\nTesting models...")

    try:
        from imp.executor.models import (
            CleanResult,
            CompletionAttempt,
            CompletionResult,
            ContextBudget,
            DecisionEntry,
            SessionListEntry,
            SessionStatus,
            WorktreeSession,
        )

        # SessionStatus enum
        assert SessionStatus.active == "active"
        assert SessionStatus.done == "done"
        assert SessionStatus.escalated == "escalated"

        # ContextBudget
        budget = ContextBudget(max_tokens=200_000, used_tokens=50_000, reserved_tokens=50_000)
        assert budget.available_tokens == 100_000
        assert budget.usage_pct == 25.0

        # WorktreeSession (mutable, auto-computed fields)
        session = WorktreeSession(
            ticket_id="SMOKE-1",
            title="Smoke test session",
            description="Testing executor",
        )
        assert session.branch == "imp/SMOKE-1"
        assert session.worktree_path == ".trees/SMOKE-1"
        assert session.status == SessionStatus.active
        assert session.context_budget is not None

        # Mutability
        session.status = SessionStatus.done
        assert session.status == SessionStatus.done

        # CompletionAttempt
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=True,
            check_output="All passed",
            review_passed=True,
            review_output="Clean",
            timestamp=datetime.now(UTC),
        )
        assert attempt.attempt_number == 1

        # CompletionResult with exit_code property
        result_pass = CompletionResult(
            ticket_id="SMOKE-1",
            passed=True,
            attempts=[attempt],
            committed=True,
            commit_hash="abc123",
        )
        assert result_pass.exit_code == 0

        result_fail = CompletionResult(
            ticket_id="SMOKE-1",
            passed=False,
            attempts=[attempt],
        )
        assert result_fail.exit_code == 1

        result_esc = CompletionResult(
            ticket_id="SMOKE-1",
            passed=False,
            escalated=True,
            attempts=[attempt],
        )
        assert result_esc.exit_code == 2

        # DecisionEntry
        entry = DecisionEntry(
            ticket_id="SMOKE-1",
            timestamp=datetime.now(UTC),
            files_changed=["src/foo.py"],
            diff_summary="1 file changed",
            attempt_history=[attempt],
            outcome="done",
        )
        assert entry.outcome == "done"

        # SessionListEntry
        sle = SessionListEntry(
            ticket_id="SMOKE-1",
            title="Smoke",
            status=SessionStatus.active,
            branch="imp/SMOKE-1",
            attempt_count=0,
            created_at=datetime.now(UTC),
        )
        assert sle.ticket_id == "SMOKE-1"

        # CleanResult
        clean = CleanResult(
            removed_sessions=["A"],
            skipped_sessions=["B"],
            pruned_branches=["imp/A"],
        )
        assert len(clean.removed_sessions) == 1

        print("  Models work correctly")
        return True
    except Exception as e:
        print(f"  Model test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_session_store() -> bool:
    """Test SessionStore CRUD with temp directory."""
    print("\nTesting SessionStore...")

    try:
        from imp.executor.models import WorktreeSession
        from imp.executor.session import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = SessionStore(root)

            # Save
            session = WorktreeSession(ticket_id="SS-1", title="Store test")
            store.save(session)
            assert store.exists("SS-1")

            # Load
            loaded = store.load("SS-1")
            assert loaded is not None
            assert loaded.ticket_id == "SS-1"

            # List
            sessions = store.list_sessions()
            assert len(sessions) == 1

            # Delete
            assert store.delete("SS-1") is True
            assert store.exists("SS-1") is False
            assert store.delete("SS-1") is False

        print("  SessionStore works correctly")
        return True
    except Exception as e:
        print(f"  SessionStore test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_context_generator() -> bool:
    """Test ContextGenerator generates valid TASK.md content."""
    print("\nTesting ContextGenerator...")

    try:
        from imp.executor.context import ContextGenerator
        from imp.executor.models import WorktreeSession

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gen = ContextGenerator(root)
            session = WorktreeSession(
                ticket_id="CG-1",
                title="Context gen test",
                description="Build something",
            )

            # Without scan data
            content = gen.generate(session)
            assert "CG-1" in content
            assert "Context gen test" in content
            assert "imp init" in content

            # With scan data
            scan = {"modules": [{"name": "mod.a", "path": "src/mod/a"}]}
            content_with_scan = gen.generate(session, scan_data=scan)
            assert "mod.a" in content_with_scan
            assert "src/mod/a" in content_with_scan

            # Write to file
            wt = root / ".trees" / "CG-1"
            wt.mkdir(parents=True)
            path = gen.write_task_file(wt, content)
            assert path.exists()
            assert "CG-1" in path.read_text()

        print("  ContextGenerator works correctly")
        return True
    except Exception as e:
        print(f"  ContextGenerator test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_json_serialization() -> bool:
    """Test JSON round-trip for all models."""
    print("\nTesting JSON serialization...")

    try:
        from imp.executor.models import (
            CompletionAttempt,
            CompletionResult,
            DecisionEntry,
            WorktreeSession,
        )

        # WorktreeSession round-trip
        session = WorktreeSession(ticket_id="JSON-1", title="JSON test")
        json_str = session.model_dump_json()
        restored = WorktreeSession.model_validate_json(json_str)
        assert restored.ticket_id == "JSON-1"
        assert restored.branch == "imp/JSON-1"

        # CompletionResult round-trip
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=True,
            timestamp=datetime.now(UTC),
        )
        result = CompletionResult(
            ticket_id="JSON-1",
            passed=True,
            attempts=[attempt],
            committed=True,
            commit_hash="def456",
        )
        result_json = result.model_dump_json()
        result_restored = CompletionResult.model_validate_json(result_json)
        assert result_restored.exit_code == 0
        assert result_restored.commit_hash == "def456"

        # DecisionEntry round-trip
        entry = DecisionEntry(
            ticket_id="JSON-1",
            timestamp=datetime.now(UTC),
            files_changed=["a.py", "b.py"],
            diff_summary="2 files changed",
            attempt_history=[attempt],
            outcome="done",
        )
        entry_json = entry.model_dump_json()
        entry_restored = DecisionEntry.model_validate_json(entry_json)
        assert len(entry_restored.files_changed) == 2
        assert entry_restored.outcome == "done"

        print("  JSON serialization works correctly")
        return True
    except Exception as e:
        print(f"  JSON serialization test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_decision_logger() -> bool:
    """Test DecisionLogger writes and reads decisions."""
    print("\nTesting DecisionLogger...")

    try:
        from imp.executor.logger import DecisionLogger
        from imp.executor.models import CompletionAttempt

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            logger = DecisionLogger(root)
            wt = root / "worktree"
            wt.mkdir()

            # Log a decision (git diff will fail gracefully in non-git dir)
            entry = logger.log_completion(
                ticket_id="DL-1",
                attempts=[
                    CompletionAttempt(
                        attempt_number=1,
                        check_passed=True,
                        timestamp=datetime.now(UTC),
                    )
                ],
                outcome="done",
                worktree_path=wt,
            )
            assert entry.ticket_id == "DL-1"

            # Load it back
            loaded = logger.load("DL-1")
            assert loaded is not None
            assert loaded.outcome == "done"

            # List
            decisions = logger.list_decisions()
            assert len(decisions) == 1

        print("  DecisionLogger works correctly")
        return True
    except Exception as e:
        print(f"  DecisionLogger test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main() -> int:
    """Run all smoke tests."""
    print("=" * 60)
    print("Executor Module Smoke Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_models,
        test_session_store,
        test_context_generator,
        test_json_serialization,
        test_decision_logger,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n  Test {test.__name__} crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if all(results):
        print("\nAll smoke tests passed!")
        return 0
    else:
        print("\nSome smoke tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
