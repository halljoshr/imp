"""Tests for JSONL metrics storage."""

from pathlib import Path

from imp.metrics.models import EventType, MetricsEvent
from imp.metrics.storage import MetricsStorage
from imp.providers.base import TokenUsage


class TestMetricsStorage:
    """Test JSONL storage for metrics events."""

    def test_write_single_event(self, tmp_path: Path) -> None:
        """Can write single event to JSONL file."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="interview",
            operation="ask_question",
            usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.01),
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1000,
        )

        storage.write_event(event)

        assert storage_path.exists()
        assert storage_path.stat().st_size > 0

    def test_write_multiple_events(self, tmp_path: Path) -> None:
        """Can write multiple events to JSONL file."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        events = [
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="interview",
                operation=f"operation-{i}",
                usage=TokenUsage(input_tokens=100 * i, cost_usd=0.01 * i),
                model="test",
                provider="test",
                duration_ms=1000 * i,
            )
            for i in range(1, 4)
        ]

        for event in events:
            storage.write_event(event)

        # Should have 3 lines
        lines = storage_path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_read_single_event(self, tmp_path: Path) -> None:
        """Can read single event from JSONL file."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        original_event = MetricsEvent(
            event_type=EventType.SESSION_START,
            agent_role="system",
            operation="initialize",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="session-123",
        )

        storage.write_event(original_event)

        # Read back
        events = storage.read_events()

        assert len(events) == 1
        assert events[0].event_type == EventType.SESSION_START
        assert events[0].session_id == "session-123"
        assert events[0].agent_role == "system"

    def test_read_multiple_events(self, tmp_path: Path) -> None:
        """Can read multiple events from JSONL file."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # Write 5 events
        for i in range(5):
            event = MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="test",
                operation=f"op-{i}",
                usage=TokenUsage(input_tokens=100 * i),
                model="test",
                provider="test",
                duration_ms=100,
                ticket_id=f"TICKET-{i}",
            )
            storage.write_event(event)

        # Read back
        events = storage.read_events()

        assert len(events) == 5
        assert events[0].ticket_id == "TICKET-0"
        assert events[4].ticket_id == "TICKET-4"
        assert events[2].usage.input_tokens == 200

    def test_read_empty_file(self, tmp_path: Path) -> None:
        """Reading empty file returns empty list."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # File doesn't exist yet
        events = storage.read_events()
        assert events == []

    def test_append_mode(self, tmp_path: Path) -> None:
        """Multiple writes append to file, not overwrite."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # Write first event
        event1 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="interview",
            operation="first",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )
        storage.write_event(event1)

        # Write second event
        event2 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="review",
            operation="second",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=200,
        )
        storage.write_event(event2)

        # Read back - should have both
        events = storage.read_events()
        assert len(events) == 2
        assert events[0].operation == "first"
        assert events[1].operation == "second"

    def test_write_batch_events(self, tmp_path: Path) -> None:
        """Can write batch of events at once."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        events = [
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="test",
                operation=f"batch-{i}",
                usage=TokenUsage(),
                model="test",
                provider="test",
                duration_ms=100,
            )
            for i in range(10)
        ]

        storage.write_batch(events)

        # Read back
        read_events = storage.read_events()
        assert len(read_events) == 10
        assert read_events[0].operation == "batch-0"
        assert read_events[9].operation == "batch-9"

    def test_corrupted_line_handling(self, tmp_path: Path) -> None:
        """Storage handles corrupted JSONL lines gracefully."""
        storage_path = tmp_path / "metrics.jsonl"

        # Write valid event
        storage = MetricsStorage(storage_path)
        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="valid",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )
        storage.write_event(event)

        # Manually append corrupted line
        with open(storage_path, "a") as f:
            f.write("this is not valid json\n")

        # Write another valid event
        event2 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="valid2",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=200,
        )
        storage.write_event(event2)

        # Read back - should skip corrupted line and return valid events
        events = storage.read_events()
        assert len(events) == 2
        assert events[0].operation == "valid"
        assert events[1].operation == "valid2"

    def test_file_creation_in_nested_directory(self, tmp_path: Path) -> None:
        """Storage creates parent directories if they don't exist."""
        storage_path = tmp_path / "nested" / "dir" / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="test",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )

        storage.write_event(event)

        assert storage_path.exists()
        assert storage_path.parent.exists()

    def test_concurrent_writes_same_file(self, tmp_path: Path) -> None:
        """Multiple storage instances can write to same file."""
        storage_path = tmp_path / "metrics.jsonl"

        storage1 = MetricsStorage(storage_path)
        storage2 = MetricsStorage(storage_path)

        event1 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="storage1",
            operation="write1",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )

        event2 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="storage2",
            operation="write2",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=200,
        )

        storage1.write_event(event1)
        storage2.write_event(event2)

        # Read from either storage instance
        events = storage1.read_events()
        assert len(events) == 2

    def test_read_with_filter(self, tmp_path: Path) -> None:
        """Can read events with filtering criteria."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # Write events with different roles
        for role in ["interview", "review", "coding", "interview"]:
            event = MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role=role,
                operation="test",
                usage=TokenUsage(),
                model="test",
                provider="test",
                duration_ms=100,
            )
            storage.write_event(event)

        # Read with filter
        interview_events = storage.read_events(filter_fn=lambda e: e.agent_role == "interview")
        assert len(interview_events) == 2
        assert all(e.agent_role == "interview" for e in interview_events)

    def test_clear_storage(self, tmp_path: Path) -> None:
        """Can clear all events from storage file."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # Write some events
        for i in range(5):
            event = MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="test",
                operation=f"op-{i}",
                usage=TokenUsage(),
                model="test",
                provider="test",
                duration_ms=100,
            )
            storage.write_event(event)

        assert len(storage.read_events()) == 5

        # Clear
        storage.clear()

        # File should be empty
        assert len(storage.read_events()) == 0
        assert not storage_path.exists() or storage_path.stat().st_size == 0

    def test_clear_nonexistent_file(self, tmp_path: Path) -> None:
        """Clearing when file doesn't exist doesn't raise error."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # File doesn't exist yet
        assert not storage_path.exists()

        # Clear should not error
        storage.clear()

        # File still doesn't exist
        assert not storage_path.exists()

    def test_read_with_empty_lines(self, tmp_path: Path) -> None:
        """Storage handles empty lines in JSONL file gracefully."""
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)

        # Write valid event
        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="valid",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=100,
        )
        storage.write_event(event)

        # Manually append empty lines
        with open(storage_path, "a") as f:
            f.write("\n")
            f.write("   \n")  # whitespace-only line
            f.write("\n")

        # Write another valid event
        event2 = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="valid2",
            usage=TokenUsage(),
            model="test",
            provider="test",
            duration_ms=200,
        )
        storage.write_event(event2)

        # Read back - should skip empty lines and return valid events
        events = storage.read_events()
        assert len(events) == 2
        assert events[0].operation == "valid"
        assert events[1].operation == "valid2"
