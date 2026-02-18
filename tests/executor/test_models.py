"""Tests for executor data models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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


class TestSessionStatus:
    """Test SessionStatus StrEnum."""

    def test_active_value(self) -> None:
        """SessionStatus.active has correct string value."""
        assert SessionStatus.active == "active"

    def test_done_value(self) -> None:
        """SessionStatus.done has correct string value."""
        assert SessionStatus.done == "done"

    def test_escalated_value(self) -> None:
        """SessionStatus.escalated has correct string value."""
        assert SessionStatus.escalated == "escalated"

    def test_all_values(self) -> None:
        """All required status values are defined."""
        values = {s.value for s in SessionStatus}
        assert values == {"active", "done", "escalated"}

    def test_string_comparison(self) -> None:
        """SessionStatus compares equal to string values."""
        assert SessionStatus.active == "active"
        assert SessionStatus.done == "done"
        assert SessionStatus.escalated == "escalated"


class TestContextBudget:
    """Test ContextBudget model."""

    def test_default_instantiation(self) -> None:
        """ContextBudget can be created with all defaults."""
        budget = ContextBudget()
        assert budget.max_tokens == 200_000
        assert budget.used_tokens == 0
        assert budget.reserved_tokens == 50_000

    def test_custom_instantiation(self) -> None:
        """ContextBudget can be created with custom values."""
        budget = ContextBudget(max_tokens=100_000, used_tokens=10_000, reserved_tokens=20_000)
        assert budget.max_tokens == 100_000
        assert budget.used_tokens == 10_000
        assert budget.reserved_tokens == 20_000

    def test_available_tokens_property(self) -> None:
        """available_tokens = max - used - reserved."""
        budget = ContextBudget(max_tokens=200_000, used_tokens=30_000, reserved_tokens=50_000)
        assert budget.available_tokens == 120_000

    def test_available_tokens_default(self) -> None:
        """Default available_tokens is 150_000."""
        budget = ContextBudget()
        assert budget.available_tokens == 150_000

    def test_usage_pct_property(self) -> None:
        """usage_pct = used / max * 100."""
        budget = ContextBudget(max_tokens=200_000, used_tokens=50_000)
        assert budget.usage_pct == pytest.approx(25.0)

    def test_usage_pct_zero(self) -> None:
        """usage_pct is 0.0 when nothing used."""
        budget = ContextBudget()
        assert budget.usage_pct == 0.0

    def test_usage_pct_high(self) -> None:
        """usage_pct works at high utilization."""
        budget = ContextBudget(max_tokens=200_000, used_tokens=180_000)
        assert budget.usage_pct == pytest.approx(90.0)

    def test_frozen(self) -> None:
        """ContextBudget is immutable (frozen=True)."""
        budget = ContextBudget()
        with pytest.raises((ValidationError, TypeError)):
            budget.used_tokens = 5000  # type: ignore[misc]

    def test_serialization(self) -> None:
        """ContextBudget serializes to dict correctly."""
        budget = ContextBudget(max_tokens=200_000, used_tokens=10_000, reserved_tokens=50_000)
        data = budget.model_dump()
        assert data["max_tokens"] == 200_000
        assert data["used_tokens"] == 10_000
        assert data["reserved_tokens"] == 50_000

    def test_deserialization(self) -> None:
        """ContextBudget deserializes from dict."""
        data = {"max_tokens": 100_000, "used_tokens": 5_000, "reserved_tokens": 25_000}
        budget = ContextBudget.model_validate(data)
        assert budget.max_tokens == 100_000
        assert budget.used_tokens == 5_000


class TestWorktreeSession:
    """Test WorktreeSession model."""

    def test_minimal_instantiation(self) -> None:
        """WorktreeSession can be created with required fields."""
        session = WorktreeSession(ticket_id="IMP-001", title="Add worktree manager")
        assert session.ticket_id == "IMP-001"
        assert session.title == "Add worktree manager"

    def test_default_values(self) -> None:
        """WorktreeSession has correct default values."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test ticket")
        assert session.description == ""
        assert session.status == SessionStatus.active
        assert session.attempt_count == 0
        assert session.max_attempts == 3

    def test_branch_computed_field(self) -> None:
        """Branch is computed as imp/{ticket_id}."""
        session = WorktreeSession(ticket_id="IMP-005", title="Test")
        assert session.branch == "imp/IMP-005"

    def test_worktree_path_computed_field(self) -> None:
        """worktree_path is computed as .trees/{ticket_id}."""
        session = WorktreeSession(ticket_id="IMP-007", title="Test")
        assert session.worktree_path == ".trees/IMP-007"

    def test_created_at_auto_set(self) -> None:
        """created_at is auto-populated."""
        before = datetime.now(UTC)
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        after = datetime.now(UTC)
        assert before <= session.created_at <= after

    def test_context_budget_default(self) -> None:
        """context_budget defaults to ContextBudget()."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        assert isinstance(session.context_budget, ContextBudget)
        assert session.context_budget.max_tokens == 200_000

    def test_is_mutable(self) -> None:
        """WorktreeSession is mutable (frozen=False)."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        session.status = SessionStatus.done
        assert session.status == SessionStatus.done

    def test_status_transition_active_to_done(self) -> None:
        """Can transition status from active to done."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        assert session.status == SessionStatus.active
        session.status = SessionStatus.done
        assert session.status == SessionStatus.done

    def test_status_transition_active_to_escalated(self) -> None:
        """Can transition status from active to escalated."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        session.status = SessionStatus.escalated
        assert session.status == SessionStatus.escalated

    def test_attempt_count_mutable(self) -> None:
        """attempt_count can be incremented."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        session.attempt_count += 1
        assert session.attempt_count == 1

    def test_full_instantiation(self) -> None:
        """WorktreeSession accepts all fields."""
        now = datetime.now(UTC)
        budget = ContextBudget(used_tokens=5000)
        session = WorktreeSession(
            ticket_id="IMP-010",
            title="Full session",
            description="A detailed description",
            status=SessionStatus.done,
            attempt_count=2,
            max_attempts=5,
            created_at=now,
            context_budget=budget,
        )
        assert session.description == "A detailed description"
        assert session.status == SessionStatus.done
        assert session.attempt_count == 2
        assert session.max_attempts == 5
        assert session.created_at == now
        assert session.context_budget.used_tokens == 5000

    def test_serialization(self) -> None:
        """WorktreeSession serializes to dict."""
        session = WorktreeSession(ticket_id="IMP-001", title="Test")
        data = session.model_dump()
        assert data["ticket_id"] == "IMP-001"
        assert data["title"] == "Test"
        assert data["branch"] == "imp/IMP-001"
        assert data["worktree_path"] == ".trees/IMP-001"
        assert data["status"] == "active"

    def test_deserialization(self) -> None:
        """WorktreeSession deserializes from dict."""
        data = {
            "ticket_id": "IMP-002",
            "title": "Deserialize test",
            "description": "desc",
            "status": "done",
            "branch": "imp/IMP-002",
            "worktree_path": ".trees/IMP-002",
            "attempt_count": 1,
            "max_attempts": 3,
            "created_at": datetime.now(UTC).isoformat(),
            "context_budget": {"max_tokens": 200000, "used_tokens": 0, "reserved_tokens": 50000},
        }
        session = WorktreeSession.model_validate(data)
        assert session.ticket_id == "IMP-002"
        assert session.status == SessionStatus.done
        assert session.attempt_count == 1

    def test_model_validate_from_existing_session(self) -> None:
        """model_validate with an existing WorktreeSession (non-dict values path)."""
        session = WorktreeSession(ticket_id="IMP-COPY", title="Copy test")
        validated = WorktreeSession.model_validate(session)
        assert validated.ticket_id == "IMP-COPY"
        assert validated.branch == "imp/IMP-COPY"


class TestCompletionAttempt:
    """Test CompletionAttempt model."""

    def test_minimal_instantiation(self) -> None:
        """CompletionAttempt can be created with required fields."""
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=True,
            timestamp=datetime.now(UTC),
        )
        assert attempt.attempt_number == 1
        assert attempt.check_passed is True

    def test_default_values(self) -> None:
        """CompletionAttempt has correct defaults."""
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=False,
            timestamp=datetime.now(UTC),
        )
        assert attempt.check_output == ""
        assert attempt.review_passed is None
        assert attempt.review_output == ""

    def test_review_passed_none_when_check_failed(self) -> None:
        """review_passed defaults to None (check failed, no review run)."""
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=False,
            timestamp=datetime.now(UTC),
        )
        assert attempt.review_passed is None

    def test_full_instantiation(self) -> None:
        """CompletionAttempt accepts all fields."""
        now = datetime.now(UTC)
        attempt = CompletionAttempt(
            attempt_number=2,
            check_passed=True,
            check_output="All checks passed",
            review_passed=True,
            review_output="LGTM",
            timestamp=now,
        )
        assert attempt.attempt_number == 2
        assert attempt.check_passed is True
        assert attempt.check_output == "All checks passed"
        assert attempt.review_passed is True
        assert attempt.review_output == "LGTM"
        assert attempt.timestamp == now

    def test_frozen(self) -> None:
        """CompletionAttempt is immutable (frozen=True)."""
        attempt = CompletionAttempt(
            attempt_number=1,
            check_passed=True,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises((ValidationError, TypeError)):
            attempt.check_passed = False  # type: ignore[misc]

    def test_serialization(self) -> None:
        """CompletionAttempt serializes to dict."""
        now = datetime.now(UTC)
        attempt = CompletionAttempt(attempt_number=1, check_passed=True, timestamp=now)
        data = attempt.model_dump()
        assert data["attempt_number"] == 1
        assert data["check_passed"] is True
        assert data["review_passed"] is None


class TestCompletionResult:
    """Test CompletionResult model."""

    def test_minimal_instantiation(self) -> None:
        """CompletionResult can be created with required fields."""
        result = CompletionResult(
            ticket_id="IMP-001",
            passed=True,
            attempts=[],
        )
        assert result.ticket_id == "IMP-001"
        assert result.passed is True
        assert result.attempts == []

    def test_default_values(self) -> None:
        """CompletionResult has correct defaults."""
        result = CompletionResult(ticket_id="IMP-001", passed=False, attempts=[])
        assert result.escalated is False
        assert result.committed is False
        assert result.commit_hash is None
        assert result.pm_updated is False

    def test_exit_code_passed(self) -> None:
        """exit_code is 0 when passed=True."""
        result = CompletionResult(ticket_id="IMP-001", passed=True, attempts=[])
        assert result.exit_code == 0

    def test_exit_code_escalated(self) -> None:
        """exit_code is 2 when escalated=True."""
        result = CompletionResult(ticket_id="IMP-001", passed=False, escalated=True, attempts=[])
        assert result.exit_code == 2

    def test_exit_code_failed(self) -> None:
        """exit_code is 1 when passed=False and not escalated."""
        result = CompletionResult(ticket_id="IMP-001", passed=False, attempts=[])
        assert result.exit_code == 1

    def test_full_instantiation(self) -> None:
        """CompletionResult accepts all fields."""
        now = datetime.now(UTC)
        attempt = CompletionAttempt(attempt_number=1, check_passed=True, timestamp=now)
        result = CompletionResult(
            ticket_id="IMP-003",
            passed=True,
            escalated=False,
            attempts=[attempt],
            committed=True,
            commit_hash="abc123def456",
            pm_updated=True,
        )
        assert result.committed is True
        assert result.commit_hash == "abc123def456"
        assert result.pm_updated is True
        assert len(result.attempts) == 1

    def test_frozen(self) -> None:
        """CompletionResult is immutable (frozen=True)."""
        result = CompletionResult(ticket_id="IMP-001", passed=True, attempts=[])
        with pytest.raises((ValidationError, TypeError)):
            result.passed = False  # type: ignore[misc]

    def test_serialization(self) -> None:
        """CompletionResult serializes to dict."""
        result = CompletionResult(ticket_id="IMP-001", passed=True, attempts=[])
        data = result.model_dump()
        assert data["ticket_id"] == "IMP-001"
        assert data["passed"] is True
        assert data["escalated"] is False
        assert data["commit_hash"] is None


class TestDecisionEntry:
    """Test DecisionEntry model."""

    def test_instantiation(self) -> None:
        """DecisionEntry can be created with required fields."""
        now = datetime.now(UTC)
        entry = DecisionEntry(
            ticket_id="IMP-001",
            timestamp=now,
            files_changed=["src/imp/executor/models.py"],
            diff_summary="Added WorktreeSession model",
            attempt_history=[],
            outcome="completed",
        )
        assert entry.ticket_id == "IMP-001"
        assert entry.outcome == "completed"
        assert entry.files_changed == ["src/imp/executor/models.py"]

    def test_frozen(self) -> None:
        """DecisionEntry is immutable (frozen=True)."""
        now = datetime.now(UTC)
        entry = DecisionEntry(
            ticket_id="IMP-001",
            timestamp=now,
            files_changed=[],
            diff_summary="summary",
            attempt_history=[],
            outcome="completed",
        )
        with pytest.raises((ValidationError, TypeError)):
            entry.outcome = "escalated"  # type: ignore[misc]

    def test_with_attempt_history(self) -> None:
        """DecisionEntry stores attempt history."""
        now = datetime.now(UTC)
        attempt = CompletionAttempt(attempt_number=1, check_passed=True, timestamp=now)
        entry = DecisionEntry(
            ticket_id="IMP-002",
            timestamp=now,
            files_changed=["file.py"],
            diff_summary="diff",
            attempt_history=[attempt],
            outcome="completed",
        )
        assert len(entry.attempt_history) == 1
        assert entry.attempt_history[0].attempt_number == 1

    def test_serialization(self) -> None:
        """DecisionEntry serializes to dict."""
        now = datetime.now(UTC)
        entry = DecisionEntry(
            ticket_id="IMP-001",
            timestamp=now,
            files_changed=["a.py", "b.py"],
            diff_summary="summary",
            attempt_history=[],
            outcome="escalated",
        )
        data = entry.model_dump()
        assert data["ticket_id"] == "IMP-001"
        assert data["outcome"] == "escalated"
        assert data["files_changed"] == ["a.py", "b.py"]


class TestSessionListEntry:
    """Test SessionListEntry model."""

    def test_instantiation(self) -> None:
        """SessionListEntry can be created with required fields."""
        now = datetime.now(UTC)
        entry = SessionListEntry(
            ticket_id="IMP-001",
            title="Test ticket",
            status=SessionStatus.active,
            branch="imp/IMP-001",
            attempt_count=0,
            created_at=now,
        )
        assert entry.ticket_id == "IMP-001"
        assert entry.status == SessionStatus.active

    def test_frozen(self) -> None:
        """SessionListEntry is immutable (frozen=True)."""
        now = datetime.now(UTC)
        entry = SessionListEntry(
            ticket_id="IMP-001",
            title="Test",
            status=SessionStatus.active,
            branch="imp/IMP-001",
            attempt_count=0,
            created_at=now,
        )
        with pytest.raises((ValidationError, TypeError)):
            entry.status = SessionStatus.done  # type: ignore[misc]

    def test_serialization(self) -> None:
        """SessionListEntry serializes to dict."""
        now = datetime.now(UTC)
        entry = SessionListEntry(
            ticket_id="IMP-002",
            title="Another ticket",
            status=SessionStatus.done,
            branch="imp/IMP-002",
            attempt_count=2,
            created_at=now,
        )
        data = entry.model_dump()
        assert data["ticket_id"] == "IMP-002"
        assert data["status"] == "done"
        assert data["attempt_count"] == 2


class TestCleanResult:
    """Test CleanResult model."""

    def test_instantiation(self) -> None:
        """CleanResult can be created with required fields."""
        result = CleanResult(
            removed_sessions=["IMP-001", "IMP-002"],
            skipped_sessions=["IMP-003"],
            pruned_branches=["imp/IMP-001"],
        )
        assert result.removed_sessions == ["IMP-001", "IMP-002"]
        assert result.skipped_sessions == ["IMP-003"]
        assert result.pruned_branches == ["imp/IMP-001"]

    def test_empty_lists(self) -> None:
        """CleanResult works with empty lists."""
        result = CleanResult(
            removed_sessions=[],
            skipped_sessions=[],
            pruned_branches=[],
        )
        assert result.removed_sessions == []
        assert result.skipped_sessions == []
        assert result.pruned_branches == []

    def test_frozen(self) -> None:
        """CleanResult is immutable (frozen=True)."""
        result = CleanResult(
            removed_sessions=[],
            skipped_sessions=[],
            pruned_branches=[],
        )
        with pytest.raises((ValidationError, TypeError)):
            result.removed_sessions = ["IMP-999"]  # type: ignore[misc]

    def test_serialization(self) -> None:
        """CleanResult serializes to dict."""
        result = CleanResult(
            removed_sessions=["IMP-001"],
            skipped_sessions=["IMP-002"],
            pruned_branches=["imp/IMP-001"],
        )
        data = result.model_dump()
        assert data["removed_sessions"] == ["IMP-001"]
        assert data["skipped_sessions"] == ["IMP-002"]
        assert data["pruned_branches"] == ["imp/IMP-001"]

    def test_deserialization(self) -> None:
        """CleanResult deserializes from dict."""
        data = {
            "removed_sessions": ["IMP-005"],
            "skipped_sessions": [],
            "pruned_branches": ["imp/IMP-005"],
        }
        result = CleanResult.model_validate(data)
        assert result.removed_sessions == ["IMP-005"]
        assert result.pruned_branches == ["imp/IMP-005"]
