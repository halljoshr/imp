"""Executor data models — sessions, budgets, completion, and decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class SessionStatus(StrEnum):
    """Status of a managed executor session."""

    active = "active"
    done = "done"
    escalated = "escalated"


class ContextBudget(BaseModel):
    """Tracks context window usage for an executor session."""

    model_config = ConfigDict(frozen=True)

    max_tokens: int = 200_000
    used_tokens: int = 0
    reserved_tokens: int = 50_000

    @property
    def available_tokens(self) -> int:
        """Tokens available for use: max - used - reserved."""
        return self.max_tokens - self.used_tokens - self.reserved_tokens

    @property
    def usage_pct(self) -> float:
        """Percentage of max tokens currently used."""
        return self.used_tokens / self.max_tokens * 100


class WorktreeSession(BaseModel):
    """A managed executor session for a single ticket."""

    model_config = ConfigDict(frozen=False)

    ticket_id: str
    title: str
    description: str = ""
    status: SessionStatus = SessionStatus.active
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: datetime = None  # type: ignore[assignment]
    context_budget: ContextBudget = None  # type: ignore[assignment]
    branch: str = ""
    worktree_path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _set_defaults(cls, values: Any) -> Any:
        """Auto-compute branch, worktree_path, created_at, and context_budget."""
        if isinstance(values, dict):  # pragma: no branch
            ticket_id = values.get("ticket_id", "")
            if not values.get("branch"):
                values["branch"] = f"imp/{ticket_id}"
            if not values.get("worktree_path"):
                values["worktree_path"] = f".trees/{ticket_id}"
            if values.get("created_at") is None:
                values["created_at"] = datetime.now(UTC)
            if values.get("context_budget") is None:
                values["context_budget"] = ContextBudget()
        return values


class CompletionAttempt(BaseModel):
    """A single attempt to validate and review completed work."""

    model_config = ConfigDict(frozen=True)

    attempt_number: int
    check_passed: bool
    check_output: str = ""
    review_passed: bool | None = None
    review_output: str = ""
    timestamp: datetime


class CompletionResult(BaseModel):
    """Final result of the completion pipeline for a session."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str
    passed: bool
    escalated: bool = False
    attempts: list[CompletionAttempt]
    committed: bool = False
    commit_hash: str | None = None
    pm_updated: bool = False

    @property
    def exit_code(self) -> int:
        """Exit code: 0=passed, 2=escalated, 1=otherwise."""
        if self.passed:
            return 0
        if self.escalated:
            return 2
        return 1


class DecisionEntry(BaseModel):
    """A logged decision entry for a completed session."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str
    timestamp: datetime
    files_changed: list[str]
    diff_summary: str
    attempt_history: list[CompletionAttempt]
    outcome: str


class SessionListEntry(BaseModel):
    """A summary entry for listing active sessions."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str
    title: str
    status: SessionStatus
    branch: str
    attempt_count: int
    created_at: datetime


class CleanResult(BaseModel):
    """Result of cleaning up sessions and worktrees."""

    model_config = ConfigDict(frozen=True)

    removed_sessions: list[str]
    skipped_sessions: list[str]
    pruned_branches: list[str]
