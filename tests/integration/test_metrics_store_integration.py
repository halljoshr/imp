"""Integration tests for SQLite metrics store — full end-to-end workflows."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai.models.test import TestModel

from imp.metrics.aggregator import cost_rollup, performance_summary
from imp.metrics.collector import MetricsCollector
from imp.metrics.migration import auto_migrate_if_needed, migrate_jsonl_to_sqlite
from imp.metrics.models import EventType, MetricsEvent
from imp.metrics.query import MetricsFilter
from imp.metrics.storage import MetricsStorage
from imp.metrics.store import SQLiteStore
from imp.providers import PydanticAIProvider
from imp.types import TokenUsage


class TestProviderToSQLiteWorkflow:
    """Integration: Provider invocation → collector → SQLite store."""

    async def test_provider_to_sqlite_roundtrip(self, tmp_path: Path) -> None:
        """Full pipeline: provider invoke → collector → SQLite → query → aggregate."""
        db_path = tmp_path / "metrics.db"

        # Create provider and invoke
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Test assistant.",
        )
        collector = MetricsCollector(session_id="integration-test")

        for i in range(3):
            result = await provider.invoke(f"Task {i}")
            collector.record_from_result(
                result=result,
                agent_role="test",
                operation=f"task_{i}",
                ticket_id="INT-001",
            )

        # Write to SQLite
        with SQLiteStore(db_path) as store:
            store.write_batch(collector.get_events())

            # Query back
            events = store.query()
            assert len(events) == 3
            assert all(e.session_id == "integration-test" for e in events)
            assert all(e.ticket_id == "INT-001" for e in events)

            # Filter by ticket
            filtered = store.query(MetricsFilter(ticket_id="INT-001"))
            assert len(filtered) == 3

            # Count
            assert store.count() == 3
            assert store.count(MetricsFilter(agent_role="test")) == 3
            assert store.count(MetricsFilter(agent_role="other")) == 0

    async def test_multi_agent_sqlite_workflow(self, tmp_path: Path) -> None:
        """Multiple agents writing to same SQLite store."""
        db_path = tmp_path / "metrics.db"
        collector = MetricsCollector(session_id="multi-agent")

        # Simulate different agent types
        for role in ["interview", "review", "coding", "interview"]:
            provider = PydanticAIProvider(
                model=TestModel(),
                output_type=str,
                system_prompt=f"{role} agent",
            )
            result = await provider.invoke(f"Doing {role} work")
            collector.record_from_result(
                result=result,
                agent_role=role,
                operation=f"{role}_task",
                ticket_id="INT-002",
            )

        # Store and aggregate
        with SQLiteStore(db_path) as store:
            store.write_batch(collector.get_events())
            events = store.query()

        rollup = cost_rollup(events)
        assert rollup.total_events == 4
        assert len(rollup.by_agent_role) == 3  # interview, review, coding
        assert rollup.by_agent_role["interview"].event_count == 2


class TestSQLiteQueryIntegration:
    """Integration: Complex queries across multiple dimensions."""

    def test_time_range_query(self, tmp_path: Path) -> None:
        """Query events within a time range."""
        db_path = tmp_path / "metrics.db"

        events = [
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                timestamp=datetime(2026, 2, 10, tzinfo=UTC),
                agent_role="test",
                operation="early",
                usage=TokenUsage(input_tokens=100),
                model="test",
                provider="test",
                duration_ms=1000,
            ),
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                timestamp=datetime(2026, 2, 12, tzinfo=UTC),
                agent_role="test",
                operation="middle",
                usage=TokenUsage(input_tokens=200),
                model="test",
                provider="test",
                duration_ms=2000,
            ),
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                timestamp=datetime(2026, 2, 14, tzinfo=UTC),
                agent_role="test",
                operation="late",
                usage=TokenUsage(input_tokens=300),
                model="test",
                provider="test",
                duration_ms=3000,
            ),
        ]

        with SQLiteStore(db_path) as store:
            store.write_batch(events)

            # Query middle range
            filtered = store.query(
                MetricsFilter(
                    start_time=datetime(2026, 2, 11, tzinfo=UTC),
                    end_time=datetime(2026, 2, 13, tzinfo=UTC),
                )
            )
            assert len(filtered) == 1
            assert filtered[0].operation == "middle"

    def test_query_then_aggregate(self, tmp_path: Path) -> None:
        """Query events, then aggregate them."""
        db_path = tmp_path / "metrics.db"

        events = [
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role=role,
                operation="work",
                usage=TokenUsage(input_tokens=100, cost_usd=0.01),
                model="test",
                provider="test",
                duration_ms=ms,
            )
            for role, ms in [
                ("review", 1000),
                ("review", 2000),
                ("interview", 3000),
            ]
        ]

        with SQLiteStore(db_path) as store:
            store.write_batch(events)
            all_events = store.query()

        perf = performance_summary(all_events)
        assert perf.total_events == 3
        assert perf.avg_duration_ms == 2000.0


class TestJSONLToSQLiteMigration:
    """Integration: JSONL → SQLite migration workflow."""

    def test_full_migration_workflow(self, tmp_path: Path) -> None:
        """Complete migration from JSONL to SQLite and back to queries."""
        # Write events to JSONL (simulating existing data)
        jsonl_path = tmp_path / "metrics.jsonl"
        jsonl_storage = MetricsStorage(jsonl_path)

        for i in range(10):
            event = MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="test",
                operation=f"op-{i}",
                usage=TokenUsage(
                    input_tokens=100 * (i + 1),
                    total_tokens=100 * (i + 1),
                    cost_usd=0.01 * (i + 1),
                ),
                model="test",
                provider="test",
                duration_ms=1000 * (i + 1),
                ticket_id=f"TICKET-{i % 3}",
            )
            jsonl_storage.write_event(event)

        # Migrate to SQLite
        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            count = migrate_jsonl_to_sqlite(jsonl_path, store)
            assert count == 10

            # Query and aggregate migrated data
            events = store.query()
            rollup = cost_rollup(events)

            assert rollup.total_events == 10
            assert len(rollup.by_ticket) == 3  # TICKET-0, TICKET-1, TICKET-2
            assert rollup.total_tokens > 0

    def test_auto_migrate_full_lifecycle(self, tmp_path: Path) -> None:
        """Auto-migrate lifecycle: JSONL → SQLite → query → aggregate."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        # Create JSONL
        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        for i in range(5):
            event = MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role="test",
                operation=f"op-{i}",
                usage=TokenUsage(input_tokens=100, cost_usd=0.01),
                model="test",
                provider="test",
                duration_ms=1000,
            )
            storage.write_event(event)

        # Auto-migrate
        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is True
        assert count == 5

        # Query migrated data
        with SQLiteStore(imp_dir / "metrics.db") as store:
            events = store.query()
            rollup = cost_rollup(events)

        assert rollup.total_events == 5
        assert rollup.total_cost_usd == 0.05


class TestSessionLifecycleWithSQLite:
    """Integration: Session lifecycle tracking in SQLite."""

    async def test_session_start_end_tracking(self, tmp_path: Path) -> None:
        """Track session start/end events alongside invocations."""
        db_path = tmp_path / "metrics.db"
        collector = MetricsCollector(session_id="lifecycle-test")

        # Session start
        start_event = MetricsEvent(
            event_type=EventType.SESSION_START,
            agent_role="system",
            operation="session_start",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="lifecycle-test",
        )
        collector.record_event(start_event)

        # Do work
        provider = PydanticAIProvider(model=TestModel(), output_type=str, system_prompt="Test")
        result = await provider.invoke("Test task")
        collector.record_from_result(result, "test", "work")

        # Session end
        end_event = MetricsEvent(
            event_type=EventType.SESSION_END,
            agent_role="system",
            operation="session_end",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="lifecycle-test",
        )
        collector.record_event(end_event)

        # Store and query
        with SQLiteStore(db_path) as store:
            store.write_batch(collector.get_events())

            # Filter by event type
            starts = store.query(MetricsFilter(event_type=EventType.SESSION_START))
            assert len(starts) == 1

            ends = store.query(MetricsFilter(event_type=EventType.SESSION_END))
            assert len(ends) == 1

            invocations = store.query(MetricsFilter(event_type=EventType.AGENT_INVOCATION))
            assert len(invocations) == 1
