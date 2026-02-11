"""Tests for metrics data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from imp.metrics.models import EventType, MetricsEvent
from imp.providers.base import TokenUsage


class TestMetricsEvent:
    """Test MetricsEvent model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create MetricsEvent with all fields."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.025,
        )

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            timestamp=datetime.now(UTC),
            agent_role="interview",
            operation="generate_question",
            usage=usage,
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1250,
            session_id="session-123",
            ticket_id="IMP-001",
            metadata={"question_number": 1},
        )

        assert event.event_type == EventType.AGENT_INVOCATION
        assert event.agent_role == "interview"
        assert event.operation == "generate_question"
        assert event.usage.input_tokens == 100
        assert event.model == "claude-sonnet-4-5-20250929"
        assert event.provider == "anthropic"
        assert event.duration_ms == 1250
        assert event.session_id == "session-123"
        assert event.ticket_id == "IMP-001"
        assert event.metadata == {"question_number": 1}

    def test_creation_with_defaults(self) -> None:
        """Can create MetricsEvent with minimal fields."""
        usage = TokenUsage()

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="context",
            operation="analyze",
            usage=usage,
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            duration_ms=500,
        )

        assert event.session_id is None
        assert event.ticket_id is None
        assert event.metadata == {}
        assert event.timestamp is not None  # Auto-populated

    def test_timestamp_auto_populated(self) -> None:
        """Timestamp is auto-populated if not provided."""
        before = datetime.now(UTC)

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="coding",
            operation="implement",
            usage=TokenUsage(),
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=3000,
        )

        after = datetime.now(UTC)

        assert before <= event.timestamp <= after

    def test_serialization_to_dict(self) -> None:
        """MetricsEvent can be serialized to dict for JSONL storage."""
        usage = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.015)

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="review",
            operation="analyze_code",
            usage=usage,
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
            ticket_id="IMP-002",
        )

        data = event.model_dump()

        assert data["event_type"] == "agent_invocation"
        assert data["agent_role"] == "review"
        assert data["usage"]["input_tokens"] == 100
        assert data["usage"]["cost_usd"] == 0.015
        assert data["model"] == "claude-opus-4-6"
        assert data["ticket_id"] == "IMP-002"

    def test_deserialization_from_dict(self) -> None:
        """MetricsEvent can be deserialized from dict."""
        data = {
            "event_type": "agent_invocation",
            "timestamp": "2026-02-11T10:00:00Z",
            "agent_role": "interview",
            "operation": "ask_question",
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25,
                "total_tokens": 75,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "requests": 1,
                "tool_calls": 0,
                "cost_usd": 0.005,
            },
            "model": "claude-sonnet-4-5-20250929",
            "provider": "anthropic",
            "duration_ms": 800,
            "session_id": None,
            "ticket_id": None,
            "metadata": {},
        }

        event = MetricsEvent.model_validate(data)

        assert event.event_type == EventType.AGENT_INVOCATION
        assert event.agent_role == "interview"
        assert event.usage.input_tokens == 50
        assert event.duration_ms == 800

    def test_event_type_enum_validation(self) -> None:
        """Event type must be valid enum value."""
        with pytest.raises(ValidationError):
            MetricsEvent(
                event_type="invalid_type",  # type: ignore[arg-type]
                agent_role="test",
                operation="test",
                usage=TokenUsage(),
                model="test",
                provider="test",
                duration_ms=100,
            )

    def test_immutability(self) -> None:
        """MetricsEvent is frozen after creation."""
        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="test",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )

        with pytest.raises(ValidationError):
            event.duration_ms = 200  # type: ignore[misc]


class TestEventType:
    """Test EventType enum."""

    def test_all_event_types_defined(self) -> None:
        """All required event types are defined."""
        assert EventType.AGENT_INVOCATION == "agent_invocation"
        assert EventType.SESSION_START == "session_start"
        assert EventType.SESSION_END == "session_end"
        assert EventType.TICKET_START == "ticket_start"
        assert EventType.TICKET_END == "ticket_end"

    def test_event_type_string_values(self) -> None:
        """Event types have correct string values for JSONL."""
        # String values matter for JSONL serialization
        assert EventType.AGENT_INVOCATION.value == "agent_invocation"
        assert EventType.SESSION_START.value == "session_start"
