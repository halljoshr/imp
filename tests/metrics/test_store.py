"""Tests for SQLite metrics store."""

from datetime import UTC, datetime
from pathlib import Path

from imp.metrics.models import EventType, MetricsEvent
from imp.metrics.query import MetricsFilter
from imp.metrics.store import SQLiteStore
from imp.types import TokenUsage


def _make_event(
    agent_role: str = "test",
    operation: str = "test_op",
    model: str = "test-model",
    provider: str = "test-provider",
    duration_ms: int = 1000,
    session_id: str | None = None,
    ticket_id: str | None = None,
    cost_usd: float | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    timestamp: datetime | None = None,
    event_type: EventType = EventType.AGENT_INVOCATION,
    metadata: dict[str, object] | None = None,
) -> MetricsEvent:
    """Helper to create test events."""
    return MetricsEvent(
        event_type=event_type,
        timestamp=timestamp or datetime.now(UTC),
        agent_role=agent_role,
        operation=operation,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        ),
        model=model,
        provider=provider,
        duration_ms=duration_ms,
        session_id=session_id,
        ticket_id=ticket_id,
        metadata=metadata or {},
    )


class TestSQLiteStoreCreation:
    """Test SQLiteStore initialization and schema creation."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Database file is created on init."""
        db_path = tmp_path / "metrics.db"
        store = SQLiteStore(db_path)
        assert db_path.exists()
        store.close()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created if needed."""
        db_path = tmp_path / "nested" / "dir" / "metrics.db"
        store = SQLiteStore(db_path)
        assert db_path.exists()
        store.close()

    def test_context_manager(self, tmp_path: Path) -> None:
        """Can use store as context manager."""
        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            store.write_event(_make_event())
        # Connection should be closed after exiting
        assert db_path.exists()

    def test_idempotent_schema_creation(self, tmp_path: Path) -> None:
        """Creating store twice on same DB doesn't error."""
        db_path = tmp_path / "metrics.db"
        store1 = SQLiteStore(db_path)
        store1.write_event(_make_event())
        store1.close()

        store2 = SQLiteStore(db_path)
        events = store2.query()
        assert len(events) == 1
        store2.close()


class TestSQLiteStoreWrite:
    """Test writing events to SQLiteStore."""

    def test_write_single_event(self, tmp_path: Path) -> None:
        """Can write a single event."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            event = _make_event(agent_role="interview", operation="ask_question")
            store.write_event(event)
            events = store.query()
            assert len(events) == 1
            assert events[0].agent_role == "interview"
            assert events[0].operation == "ask_question"

    def test_write_event_preserves_all_fields(self, tmp_path: Path) -> None:
        """All event fields survive write/read round-trip."""
        ts = datetime(2026, 2, 15, 10, 30, 0, tzinfo=UTC)
        event = _make_event(
            agent_role="review",
            operation="analyze",
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2500,
            session_id="session-abc",
            ticket_id="IMP-042",
            cost_usd=0.035,
            input_tokens=200,
            output_tokens=100,
            timestamp=ts,
            metadata={"key": "value"},
        )

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(event)
            result = store.query()[0]

        assert result.event_type == EventType.AGENT_INVOCATION
        assert result.timestamp == ts
        assert result.agent_role == "review"
        assert result.operation == "analyze"
        assert result.model == "claude-opus-4-6"
        assert result.provider == "anthropic"
        assert result.duration_ms == 2500
        assert result.session_id == "session-abc"
        assert result.ticket_id == "IMP-042"
        assert result.usage.input_tokens == 200
        assert result.usage.output_tokens == 100
        assert result.usage.cost_usd == 0.035
        assert result.metadata == {"key": "value"}

    def test_write_event_with_none_optional_fields(self, tmp_path: Path) -> None:
        """Events with None optional fields round-trip correctly."""
        event = _make_event(session_id=None, ticket_id=None)

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(event)
            result = store.query()[0]

        assert result.session_id is None
        assert result.ticket_id is None

    def test_write_batch(self, tmp_path: Path) -> None:
        """Can write batch of events in a single transaction."""
        events = [_make_event(operation=f"op-{i}") for i in range(10)]

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch(events)
            results = store.query()

        assert len(results) == 10
        assert results[0].operation == "op-0"
        assert results[9].operation == "op-9"

    def test_write_batch_empty_list(self, tmp_path: Path) -> None:
        """Writing empty batch is a no-op."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch([])
            assert store.count() == 0

    def test_write_preserves_event_types(self, tmp_path: Path) -> None:
        """All EventType values survive round-trip."""
        for event_type in EventType:
            event = _make_event(event_type=event_type)
            with SQLiteStore(tmp_path / f"metrics_{event_type.value}.db") as store:
                store.write_event(event)
                result = store.query()[0]
                assert result.event_type == event_type

    def test_multiple_writes_append(self, tmp_path: Path) -> None:
        """Multiple write calls append, don't overwrite."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(operation="first"))
            store.write_event(_make_event(operation="second"))
            store.write_event(_make_event(operation="third"))

            events = store.query()
            assert len(events) == 3
            assert events[0].operation == "first"
            assert events[2].operation == "third"


class TestSQLiteStoreQuery:
    """Test querying events from SQLiteStore."""

    def test_query_all(self, tmp_path: Path) -> None:
        """Query with no filter returns all events."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch([_make_event(operation=f"op-{i}") for i in range(5)])
            events = store.query()
            assert len(events) == 5

    def test_query_empty_store(self, tmp_path: Path) -> None:
        """Query on empty store returns empty list."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            events = store.query()
            assert events == []

    def test_query_by_agent_role(self, tmp_path: Path) -> None:
        """Can filter by agent role."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(agent_role="interview"))
            store.write_event(_make_event(agent_role="review"))
            store.write_event(_make_event(agent_role="interview"))

            events = store.query(MetricsFilter(agent_role="interview"))
            assert len(events) == 2
            assert all(e.agent_role == "interview" for e in events)

    def test_query_by_ticket_id(self, tmp_path: Path) -> None:
        """Can filter by ticket ID."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(ticket_id="IMP-001"))
            store.write_event(_make_event(ticket_id="IMP-002"))
            store.write_event(_make_event(ticket_id="IMP-001"))

            events = store.query(MetricsFilter(ticket_id="IMP-001"))
            assert len(events) == 2
            assert all(e.ticket_id == "IMP-001" for e in events)

    def test_query_by_session_id(self, tmp_path: Path) -> None:
        """Can filter by session ID."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(session_id="sess-1"))
            store.write_event(_make_event(session_id="sess-2"))

            events = store.query(MetricsFilter(session_id="sess-1"))
            assert len(events) == 1
            assert events[0].session_id == "sess-1"

    def test_query_by_model(self, tmp_path: Path) -> None:
        """Can filter by model."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(model="claude-opus-4-6"))
            store.write_event(_make_event(model="claude-haiku-4-5-20251001"))

            events = store.query(MetricsFilter(model="claude-opus-4-6"))
            assert len(events) == 1
            assert events[0].model == "claude-opus-4-6"

    def test_query_by_provider(self, tmp_path: Path) -> None:
        """Can filter by provider."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(provider="anthropic"))
            store.write_event(_make_event(provider="openai"))

            events = store.query(MetricsFilter(provider="anthropic"))
            assert len(events) == 1
            assert events[0].provider == "anthropic"

    def test_query_by_event_type(self, tmp_path: Path) -> None:
        """Can filter by event type."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(event_type=EventType.AGENT_INVOCATION))
            store.write_event(_make_event(event_type=EventType.SESSION_START))
            store.write_event(_make_event(event_type=EventType.AGENT_INVOCATION))

            events = store.query(MetricsFilter(event_type=EventType.SESSION_START))
            assert len(events) == 1
            assert events[0].event_type == EventType.SESSION_START

    def test_query_by_time_range(self, tmp_path: Path) -> None:
        """Can filter by time range."""
        t1 = datetime(2026, 2, 10, tzinfo=UTC)
        t2 = datetime(2026, 2, 12, tzinfo=UTC)
        t3 = datetime(2026, 2, 14, tzinfo=UTC)

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(timestamp=t1, operation="early"))
            store.write_event(_make_event(timestamp=t2, operation="middle"))
            store.write_event(_make_event(timestamp=t3, operation="late"))

            events = store.query(
                MetricsFilter(
                    start_time=datetime(2026, 2, 11, tzinfo=UTC),
                    end_time=datetime(2026, 2, 13, tzinfo=UTC),
                )
            )
            assert len(events) == 1
            assert events[0].operation == "middle"

    def test_query_with_multiple_filters(self, tmp_path: Path) -> None:
        """Multiple filter criteria combine with AND."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(agent_role="review", ticket_id="IMP-001"))
            store.write_event(_make_event(agent_role="interview", ticket_id="IMP-001"))
            store.write_event(_make_event(agent_role="review", ticket_id="IMP-002"))

            events = store.query(
                MetricsFilter(
                    agent_role="review",
                    ticket_id="IMP-001",
                )
            )
            assert len(events) == 1
            assert events[0].agent_role == "review"
            assert events[0].ticket_id == "IMP-001"

    def test_query_with_limit(self, tmp_path: Path) -> None:
        """Can limit number of results."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch([_make_event(operation=f"op-{i}") for i in range(10)])

            events = store.query(MetricsFilter(limit=3))
            assert len(events) == 3

    def test_query_ordered_by_timestamp(self, tmp_path: Path) -> None:
        """Results are ordered by timestamp ascending."""
        t1 = datetime(2026, 2, 10, tzinfo=UTC)
        t2 = datetime(2026, 2, 12, tzinfo=UTC)
        t3 = datetime(2026, 2, 11, tzinfo=UTC)

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(timestamp=t1, operation="first"))
            store.write_event(_make_event(timestamp=t2, operation="third"))
            store.write_event(_make_event(timestamp=t3, operation="second"))

            events = store.query()
            assert events[0].operation == "first"
            assert events[1].operation == "second"
            assert events[2].operation == "third"


class TestSQLiteStoreCount:
    """Test counting events in SQLiteStore."""

    def test_count_empty(self, tmp_path: Path) -> None:
        """Count of empty store is 0."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            assert store.count() == 0

    def test_count_all(self, tmp_path: Path) -> None:
        """Count without filter returns total count."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch([_make_event() for _ in range(5)])
            assert store.count() == 5

    def test_count_with_filter(self, tmp_path: Path) -> None:
        """Count with filter returns matching count."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(agent_role="interview"))
            store.write_event(_make_event(agent_role="review"))
            store.write_event(_make_event(agent_role="interview"))

            assert store.count(MetricsFilter(agent_role="interview")) == 2
            assert store.count(MetricsFilter(agent_role="review")) == 1
            assert store.count(MetricsFilter(agent_role="coding")) == 0


class TestSQLiteStoreClear:
    """Test clearing events from SQLiteStore."""

    def test_clear_removes_all_events(self, tmp_path: Path) -> None:
        """Clear removes all events."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_batch([_make_event() for _ in range(5)])
            assert store.count() == 5
            store.clear()
            assert store.count() == 0

    def test_clear_empty_store(self, tmp_path: Path) -> None:
        """Clearing empty store doesn't error."""
        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.clear()
            assert store.count() == 0


class TestSQLiteStoreUsageRoundTrip:
    """Test that TokenUsage JSON survives round-trip."""

    def test_full_usage_round_trip(self, tmp_path: Path) -> None:
        """All TokenUsage fields survive write/read."""
        usage = TokenUsage(
            input_tokens=500,
            output_tokens=250,
            total_tokens=750,
            cache_read_tokens=100,
            cache_write_tokens=50,
            requests=3,
            tool_calls=2,
            cost_usd=0.045,
        )
        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="test",
            usage=usage,
            model="test",
            provider="test",
            duration_ms=100,
        )

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(event)
            result = store.query()[0]

        assert result.usage.input_tokens == 500
        assert result.usage.output_tokens == 250
        assert result.usage.total_tokens == 750
        assert result.usage.cache_read_tokens == 100
        assert result.usage.cache_write_tokens == 50
        assert result.usage.requests == 3
        assert result.usage.tool_calls == 2
        assert result.usage.cost_usd == 0.045

    def test_metadata_round_trip(self, tmp_path: Path) -> None:
        """Metadata dict survives write/read."""
        event = _make_event(metadata={"nested": "value", "number": 42})

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(event)
            result = store.query()[0]

        assert result.metadata["nested"] == "value"
        assert result.metadata["number"] == 42

    def test_start_time_filter(self, tmp_path: Path) -> None:
        """Start time filter works correctly."""
        old = datetime(2026, 1, 1, tzinfo=UTC)
        recent = datetime(2026, 2, 15, tzinfo=UTC)

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(timestamp=old))
            store.write_event(_make_event(timestamp=recent))

            events = store.query(
                MetricsFilter(
                    start_time=datetime(2026, 2, 1, tzinfo=UTC),
                )
            )
            assert len(events) == 1
            assert events[0].timestamp == recent

    def test_end_time_filter(self, tmp_path: Path) -> None:
        """End time filter works correctly."""
        old = datetime(2026, 1, 1, tzinfo=UTC)
        recent = datetime(2026, 2, 15, tzinfo=UTC)

        with SQLiteStore(tmp_path / "metrics.db") as store:
            store.write_event(_make_event(timestamp=old))
            store.write_event(_make_event(timestamp=recent))

            events = store.query(
                MetricsFilter(
                    end_time=datetime(2026, 1, 31, tzinfo=UTC),
                )
            )
            assert len(events) == 1
            assert events[0].timestamp == old
