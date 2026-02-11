"""Tests for MetricsCollector."""


from imp.metrics.collector import MetricsCollector
from imp.metrics.models import EventType, MetricsEvent
from imp.providers.base import AgentResult, TokenUsage


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_creation_with_defaults(self) -> None:
        """Can create MetricsCollector with no initial events."""
        collector = MetricsCollector()
        assert len(collector.get_events()) == 0

    def test_creation_with_session_id(self) -> None:
        """Can create MetricsCollector with session ID."""
        collector = MetricsCollector(session_id="session-123")
        assert collector.session_id == "session-123"

    def test_record_from_agent_result(self) -> None:
        """Can record event from AgentResult."""
        collector = MetricsCollector()

        usage = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.015)
        result = AgentResult(
            output="test output",
            usage=usage,
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1250,
        )

        collector.record_from_result(
            result=result,
            agent_role="interview",
            operation="ask_question",
            ticket_id="IMP-001",
        )

        events = collector.get_events()
        assert len(events) == 1
        assert events[0].agent_role == "interview"
        assert events[0].operation == "ask_question"
        assert events[0].usage.input_tokens == 100
        assert events[0].model == "claude-sonnet-4-5-20250929"
        assert events[0].ticket_id == "IMP-001"

    def test_record_custom_event(self) -> None:
        """Can record custom MetricsEvent."""
        collector = MetricsCollector()

        event = MetricsEvent(
            event_type=EventType.SESSION_START,
            agent_role="system",
            operation="initialize",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="session-456",
        )

        collector.record_event(event)

        events = collector.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.SESSION_START
        assert events[0].session_id == "session-456"

    def test_record_multiple_events(self) -> None:
        """Can record multiple events and retrieve them in order."""
        collector = MetricsCollector(session_id="session-789")

        for i in range(3):
            usage = TokenUsage(input_tokens=100 * (i + 1), cost_usd=0.01 * (i + 1))
            result = AgentResult(
                output=f"output-{i}",
                usage=usage,
                model="test-model",
                provider="test",
                duration_ms=1000 * (i + 1),
            )

            collector.record_from_result(
                result=result,
                agent_role="test",
                operation=f"operation-{i}",
            )

        events = collector.get_events()
        assert len(events) == 3
        assert events[0].operation == "operation-0"
        assert events[1].operation == "operation-1"
        assert events[2].operation == "operation-2"

    def test_get_summary_empty(self) -> None:
        """Summary for empty collector returns zeros."""
        collector = MetricsCollector()
        summary = collector.get_summary()

        assert summary.total_events == 0
        assert summary.total_tokens == 0
        assert summary.total_cost == 0.0
        assert summary.total_duration_ms == 0
        assert len(summary.by_agent_role) == 0
        assert len(summary.by_operation) == 0

    def test_get_summary_single_event(self) -> None:
        """Summary for single event calculates correctly."""
        collector = MetricsCollector()

        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.025,
        )
        result = AgentResult(
            output="test",
            usage=usage,
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1500,
        )

        collector.record_from_result(
            result=result,
            agent_role="interview",
            operation="ask_question",
        )

        summary = collector.get_summary()

        assert summary.total_events == 1
        assert summary.total_tokens == 150
        assert summary.total_cost == 0.025
        assert summary.total_duration_ms == 1500

    def test_get_summary_multiple_events(self) -> None:
        """Summary aggregates multiple events correctly."""
        collector = MetricsCollector()

        # Event 1: interview
        collector.record_from_result(
            result=AgentResult(
                output="q1",
                usage=TokenUsage(total_tokens=100, cost_usd=0.01),
                model="test",
                provider="test",
                duration_ms=1000,
            ),
            agent_role="interview",
            operation="ask_question",
        )

        # Event 2: review
        collector.record_from_result(
            result=AgentResult(
                output="r1",
                usage=TokenUsage(total_tokens=200, cost_usd=0.02),
                model="test",
                provider="test",
                duration_ms=2000,
            ),
            agent_role="review",
            operation="analyze_code",
        )

        # Event 3: interview again
        collector.record_from_result(
            result=AgentResult(
                output="q2",
                usage=TokenUsage(total_tokens=150, cost_usd=0.015),
                model="test",
                provider="test",
                duration_ms=1500,
            ),
            agent_role="interview",
            operation="ask_question",
        )

        summary = collector.get_summary()

        assert summary.total_events == 3
        assert summary.total_tokens == 450  # 100 + 200 + 150
        assert summary.total_cost == 0.045  # 0.01 + 0.02 + 0.015
        assert summary.total_duration_ms == 4500  # 1000 + 2000 + 1500

        # By agent role
        assert len(summary.by_agent_role) == 2
        assert summary.by_agent_role["interview"]["count"] == 2
        assert summary.by_agent_role["interview"]["tokens"] == 250
        assert summary.by_agent_role["interview"]["cost"] == 0.025
        assert summary.by_agent_role["review"]["count"] == 1
        assert summary.by_agent_role["review"]["tokens"] == 200

        # By operation
        assert len(summary.by_operation) == 2
        assert summary.by_operation["ask_question"]["count"] == 2
        assert summary.by_operation["analyze_code"]["count"] == 1

    def test_get_summary_handles_none_costs(self) -> None:
        """Summary handles events with None costs gracefully."""
        collector = MetricsCollector()

        # Event with cost
        collector.record_from_result(
            result=AgentResult(
                output="test",
                usage=TokenUsage(total_tokens=100, cost_usd=0.01),
                model="test",
                provider="test",
                duration_ms=1000,
            ),
            agent_role="test",
            operation="test_op",
        )

        # Event without cost
        collector.record_from_result(
            result=AgentResult(
                output="test",
                usage=TokenUsage(total_tokens=50, cost_usd=None),
                model="test",
                provider="test",
                duration_ms=500,
            ),
            agent_role="test",
            operation="test_op",
        )

        summary = collector.get_summary()

        assert summary.total_events == 2
        assert summary.total_tokens == 150
        assert summary.total_cost == 0.01  # Only counted the non-None cost

    def test_filter_by_agent_role(self) -> None:
        """Can filter events by agent role."""
        collector = MetricsCollector()

        # Record different roles
        for role in ["interview", "review", "interview", "coding"]:
            collector.record_from_result(
                result=AgentResult(
                    output="test",
                    usage=TokenUsage(),
                    model="test",
                    provider="test",
                    duration_ms=100,
                ),
                agent_role=role,
                operation="test",
            )

        interview_events = collector.filter_by_agent_role("interview")
        assert len(interview_events) == 2
        assert all(e.agent_role == "interview" for e in interview_events)

    def test_filter_by_ticket_id(self) -> None:
        """Can filter events by ticket ID."""
        collector = MetricsCollector()

        # Record different tickets
        for ticket_id in ["IMP-001", "IMP-002", "IMP-001", None]:
            collector.record_from_result(
                result=AgentResult(
                    output="test",
                    usage=TokenUsage(),
                    model="test",
                    provider="test",
                    duration_ms=100,
                ),
                agent_role="test",
                operation="test",
                ticket_id=ticket_id,
            )

        imp_001_events = collector.filter_by_ticket_id("IMP-001")
        assert len(imp_001_events) == 2
        assert all(e.ticket_id == "IMP-001" for e in imp_001_events)

    def test_clear_events(self) -> None:
        """Can clear all events from collector."""
        collector = MetricsCollector()

        # Add some events
        for _ in range(3):
            collector.record_from_result(
                result=AgentResult(
                    output="test",
                    usage=TokenUsage(),
                    model="test",
                    provider="test",
                    duration_ms=100,
                ),
                agent_role="test",
                operation="test",
            )

        assert len(collector.get_events()) == 3

        collector.clear()

        assert len(collector.get_events()) == 0
        summary = collector.get_summary()
        assert summary.total_events == 0
