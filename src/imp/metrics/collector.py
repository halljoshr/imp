"""Metrics collector for agent invocations."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from imp.metrics.models import EventType, MetricsEvent
from imp.types import AgentResult


class MetricsSummary(BaseModel):
    """Summary statistics for a collection of metrics events."""

    total_events: int
    total_tokens: int
    total_cost: float
    total_duration_ms: int
    by_agent_role: dict[str, dict[str, int | float]]
    by_operation: dict[str, dict[str, int | float]]


class MetricsCollector:
    """In-memory metrics collector.

    Collects metrics events and provides aggregation/filtering capabilities.
    """

    def __init__(self, session_id: str | None = None) -> None:
        """Initialize collector.

        Args:
            session_id: Optional session ID to attach to all recorded events
        """
        self.session_id = session_id
        self._events: list[MetricsEvent] = []

    def record_from_result(
        self,
        result: AgentResult[Any],
        agent_role: str,
        operation: str,
        ticket_id: str | None = None,
    ) -> None:
        """Record metrics from an AgentResult.

        Args:
            result: Agent result containing usage and metadata
            agent_role: Role of the agent (interview, review, coding, etc.)
            operation: Operation name (ask_question, analyze_code, etc.)
            ticket_id: Optional ticket ID for PM integration
        """
        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            timestamp=datetime.now(UTC),
            agent_role=agent_role,
            operation=operation,
            usage=result.usage,
            model=result.model,
            provider=result.provider,
            duration_ms=result.duration_ms,
            session_id=self.session_id,
            ticket_id=ticket_id,
        )
        self._events.append(event)

    def record_event(self, event: MetricsEvent) -> None:
        """Record a custom MetricsEvent.

        Args:
            event: Pre-constructed event to record
        """
        self._events.append(event)

    def get_events(self) -> list[MetricsEvent]:
        """Get all recorded events.

        Returns:
            List of all events in order recorded
        """
        return self._events.copy()

    def get_summary(self) -> MetricsSummary:
        """Calculate summary statistics for all events.

        Returns:
            Summary with aggregated metrics
        """
        if not self._events:
            return MetricsSummary(
                total_events=0,
                total_tokens=0,
                total_cost=0.0,
                total_duration_ms=0,
                by_agent_role={},
                by_operation={},
            )

        total_tokens = sum(e.usage.total_tokens for e in self._events)
        total_cost = sum(e.usage.cost_usd for e in self._events if e.usage.cost_usd is not None)
        total_duration_ms = sum(e.duration_ms for e in self._events)

        # Aggregate by agent role
        by_agent_role: dict[str, dict[str, int | float]] = {}
        for event in self._events:
            if event.agent_role not in by_agent_role:
                by_agent_role[event.agent_role] = {
                    "count": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "duration_ms": 0,
                }

            role_stats = by_agent_role[event.agent_role]
            role_stats["count"] += 1
            role_stats["tokens"] += event.usage.total_tokens
            if event.usage.cost_usd is not None:
                role_stats["cost"] += event.usage.cost_usd
            role_stats["duration_ms"] += event.duration_ms

        # Aggregate by operation
        by_operation: dict[str, dict[str, int | float]] = {}
        for event in self._events:
            if event.operation not in by_operation:
                by_operation[event.operation] = {
                    "count": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "duration_ms": 0,
                }

            op_stats = by_operation[event.operation]
            op_stats["count"] += 1
            op_stats["tokens"] += event.usage.total_tokens
            if event.usage.cost_usd is not None:
                op_stats["cost"] += event.usage.cost_usd
            op_stats["duration_ms"] += event.duration_ms

        return MetricsSummary(
            total_events=len(self._events),
            total_tokens=total_tokens,
            total_cost=total_cost,
            total_duration_ms=total_duration_ms,
            by_agent_role=by_agent_role,
            by_operation=by_operation,
        )

    def filter_by_agent_role(self, agent_role: str) -> list[MetricsEvent]:
        """Filter events by agent role.

        Args:
            agent_role: Role to filter by

        Returns:
            List of events matching the role
        """
        return [e for e in self._events if e.agent_role == agent_role]

    def filter_by_ticket_id(self, ticket_id: str) -> list[MetricsEvent]:
        """Filter events by ticket ID.

        Args:
            ticket_id: Ticket ID to filter by

        Returns:
            List of events matching the ticket ID
        """
        return [e for e in self._events if e.ticket_id == ticket_id]

    def clear(self) -> None:
        """Clear all events from collector."""
        self._events.clear()
