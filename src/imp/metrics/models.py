"""Metrics data models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from imp.types import TokenUsage


class EventType(StrEnum):
    """Event types for metrics tracking."""

    AGENT_INVOCATION = "agent_invocation"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TICKET_START = "ticket_start"
    TICKET_END = "ticket_end"


class MetricsEvent(BaseModel):
    """Single metrics event.

    Records a single agent invocation or lifecycle event with full context.
    """

    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_role: str
    operation: str
    usage: TokenUsage
    model: str
    provider: str
    duration_ms: int
    session_id: str | None = None
    ticket_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
