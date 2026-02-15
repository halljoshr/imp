#!/usr/bin/env python3
"""Smoke test for metrics layer - validates real usage patterns.

This script tests the metrics layer as a real user would use it:
- Imports modules like a developer would
- Creates collectors and storage
- Records events and persists to JSONL
- SQLite store write/query/aggregate workflows
- JSONL to SQLite migration
- Validates all public APIs work in production

Run: python tests/smoke/smoke_test_metrics.py
Exit code: 0 = pass, 1 = fail

This is NOT a pytest test. This is a smoke test that validates the module
works in the wild, not just in a test harness.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path so we can import imp modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_imports():
    """Test: Can import all public APIs from imp.metrics."""
    try:
        from imp.metrics import (  # noqa: F401
            CostRollup,
            EventType,
            MetricsCollector,
            MetricsEvent,
            MetricsFilter,
            MetricsStorage,
            OperationStats,
            PerformanceSummary,
            RollupEntry,
            SQLiteStore,
            cost_rollup,
            performance_summary,
        )
        from imp.metrics.models import EventType as EventTypeModel  # noqa: F401

        print("✓ All imports successful (including new exports)")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_create_collector():
    """Test: Can create MetricsCollector instance."""
    try:
        from imp.metrics import MetricsCollector

        collector = MetricsCollector(session_id="smoke-test-session")
        assert collector.session_id == "smoke-test-session"
        assert len(collector.get_events()) == 0

        print("✓ MetricsCollector instance created")
        return collector
    except Exception as e:
        print(f"✗ MetricsCollector creation failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_record_from_provider():
    """Test: Can record metrics from provider invocation."""
    try:
        from pydantic_ai.models.test import TestModel

        from imp.metrics import MetricsCollector
        from imp.providers import PydanticAIProvider

        # Create provider
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="You are helpful.",
        )

        # Invoke
        result = await provider.invoke("Say hello")

        # Record metrics
        collector = MetricsCollector()
        collector.record_from_result(
            result=result,
            agent_role="test",
            operation="smoke_test",
            ticket_id="SMOKE-001",
        )

        # Verify
        events = collector.get_events()
        assert len(events) == 1
        assert events[0].agent_role == "test"
        assert events[0].operation == "smoke_test"
        assert events[0].ticket_id == "SMOKE-001"
        assert events[0].usage.total_tokens > 0

        print(f"✓ Recorded metrics from provider (tokens: {events[0].usage.total_tokens})")
        return collector
    except Exception as e:
        print(f"✗ Recording from provider failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_summary_calculation(collector):
    """Test: Summary calculation works correctly."""
    try:
        if not collector or len(collector.get_events()) == 0:
            print("✗ No events to summarize (previous test failed)")
            return False

        summary = collector.get_summary()
        assert summary.total_events > 0
        assert summary.total_tokens > 0
        assert summary.total_duration_ms >= 0
        assert len(summary.by_agent_role) > 0

        print(
            f"✓ Summary calculated (events: {summary.total_events}, "
            f"tokens: {summary.total_tokens})"
        )
        return True
    except Exception as e:
        print(f"✗ Summary calculation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_jsonl_storage():
    """Test: JSONL storage write and read."""
    try:
        from imp.metrics import EventType, MetricsStorage
        from imp.metrics.models import MetricsEvent
        from imp.providers.base import TokenUsage

        # Create temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "smoke_test.jsonl"
            storage = MetricsStorage(storage_path)

            # Create some events
            events = []
            for i in range(3):
                event = MetricsEvent(
                    event_type=EventType.AGENT_INVOCATION,
                    agent_role="smoke",
                    operation=f"test_{i}",
                    usage=TokenUsage(input_tokens=100 * (i + 1), cost_usd=0.01 * (i + 1)),
                    model="test-model",
                    provider="test",
                    duration_ms=1000 * (i + 1),
                    ticket_id=f"SMOKE-{i}",
                )
                events.append(event)

            # Write batch
            storage.write_batch(events)

            # Read back
            read_events = storage.read_events()
            assert len(read_events) == 3
            assert read_events[0].ticket_id == "SMOKE-0"
            assert read_events[1].usage.input_tokens == 200
            assert read_events[2].duration_ms == 3000

            print("✓ JSONL storage write and read successful")
            return True
    except Exception as e:
        print(f"✗ JSONL storage failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_filter_operations():
    """Test: Filtering operations work correctly."""
    try:
        from imp.metrics import MetricsCollector
        from imp.providers.base import AgentResult, TokenUsage

        collector = MetricsCollector()

        # Add events for different roles
        for role in ["interview", "review", "coding", "interview"]:
            result = AgentResult(
                output="test",
                usage=TokenUsage(input_tokens=100),
                model="test",
                provider="test",
                duration_ms=100,
            )
            collector.record_from_result(result, role, "test_op")

        # Filter by role
        interview_events = collector.filter_by_agent_role("interview")
        assert len(interview_events) == 2
        assert all(e.agent_role == "interview" for e in interview_events)

        print("✓ Filter operations working")
        return True
    except Exception as e:
        print(f"✗ Filter operations failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_event_serialization():
    """Test: Events can be serialized to dict and back."""
    try:
        from imp.metrics.models import EventType, MetricsEvent
        from imp.providers.base import TokenUsage

        # Create event
        original_event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="test",
            operation="serialize_test",
            usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.01),
            model="test-model",
            provider="test-provider",
            duration_ms=1234,
            session_id="session-123",
            ticket_id="TICKET-456",
            metadata={"key": "value"},
        )

        # Serialize
        data = original_event.model_dump()
        assert isinstance(data, dict)
        assert data["event_type"] == "agent_invocation"
        assert data["agent_role"] == "test"

        # Deserialize
        restored_event = MetricsEvent.model_validate(data)
        assert restored_event.event_type == original_event.event_type
        assert restored_event.agent_role == original_event.agent_role
        assert restored_event.usage.input_tokens == 100
        assert restored_event.metadata == {"key": "value"}

        print("✓ Event serialization/deserialization working")
        return True
    except Exception as e:
        print(f"✗ Event serialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_end_to_end_workflow():
    """Test: Complete workflow from provider to storage."""
    try:
        from pydantic_ai.models.test import TestModel

        from imp.metrics import MetricsCollector, MetricsStorage
        from imp.providers import PydanticAIProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "e2e_test.jsonl"

            # Setup
            provider = PydanticAIProvider(model=TestModel(), output_type=str, system_prompt="Test")
            collector = MetricsCollector(session_id="e2e-session")
            storage = MetricsStorage(storage_path)

            # Do work
            for i in range(3):
                result = await provider.invoke(f"Task {i}")
                collector.record_from_result(
                    result=result,
                    agent_role="test",
                    operation=f"task_{i}",
                    ticket_id="E2E-001",
                )

            # Get summary
            summary = collector.get_summary()
            assert summary.total_events == 3

            # Persist
            storage.write_batch(collector.get_events())

            # Read back
            events = storage.read_events()
            assert len(events) == 3
            assert all(e.session_id == "e2e-session" for e in events)
            assert all(e.ticket_id == "E2E-001" for e in events)

            print("✓ End-to-end workflow successful")
            return True
    except Exception as e:
        print(f"✗ End-to-end workflow failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_sqlite_store():
    """Test: SQLiteStore write, query, and count."""
    try:
        from imp.metrics import EventType, MetricsFilter, SQLiteStore
        from imp.metrics.models import MetricsEvent
        from imp.providers.base import TokenUsage

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "smoke_test.db"

            with SQLiteStore(db_path) as store:
                # Write events
                for i in range(5):
                    event = MetricsEvent(
                        event_type=EventType.AGENT_INVOCATION,
                        agent_role="smoke",
                        operation=f"test_{i}",
                        usage=TokenUsage(input_tokens=100 * (i + 1), cost_usd=0.01 * (i + 1)),
                        model="test-model",
                        provider="test",
                        duration_ms=1000 * (i + 1),
                        ticket_id=f"SMOKE-{i % 2}",
                    )
                    store.write_event(event)

                # Query all
                all_events = store.query()
                assert len(all_events) == 5

                # Query with filter
                filtered = store.query(MetricsFilter(ticket_id="SMOKE-0"))
                assert len(filtered) == 3  # i=0,2,4

                # Count
                assert store.count() == 5
                assert store.count(MetricsFilter(ticket_id="SMOKE-1")) == 2  # i=1,3

            print("✓ SQLiteStore write, query, and count successful")
            return True
    except Exception as e:
        print(f"✗ SQLiteStore failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_aggregation():
    """Test: Cost rollup and performance summary."""
    try:
        from imp.metrics import EventType, cost_rollup, performance_summary
        from imp.metrics.models import MetricsEvent
        from imp.providers.base import TokenUsage

        events = [
            MetricsEvent(
                event_type=EventType.AGENT_INVOCATION,
                agent_role=role,
                operation=op,
                usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.01),
                model="test",
                provider="test",
                duration_ms=ms,
            )
            for role, op, ms in [
                ("review", "analyze", 1000),
                ("review", "analyze", 2000),
                ("interview", "ask", 3000),
            ]
        ]

        rollup = cost_rollup(events)
        assert rollup.total_events == 3
        assert rollup.total_cost_usd == 0.03
        assert len(rollup.by_agent_role) == 2
        assert rollup.by_agent_role["review"].event_count == 2

        perf = performance_summary(events)
        assert perf.total_events == 3
        assert perf.avg_duration_ms == 2000.0
        assert len(perf.by_operation) == 2

        print("✓ Aggregation (cost rollup + performance summary) successful")
        return True
    except Exception as e:
        print(f"✗ Aggregation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_migration():
    """Test: JSONL to SQLite migration."""
    try:
        from imp.metrics import EventType, SQLiteStore
        from imp.metrics.migration import migrate_jsonl_to_sqlite
        from imp.metrics.models import MetricsEvent
        from imp.metrics.storage import MetricsStorage
        from imp.providers.base import TokenUsage

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write to JSONL
            jsonl_path = Path(tmpdir) / "metrics.jsonl"
            storage = MetricsStorage(jsonl_path)
            for i in range(3):
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

            # Migrate to SQLite
            db_path = Path(tmpdir) / "metrics.db"
            with SQLiteStore(db_path) as store:
                count = migrate_jsonl_to_sqlite(jsonl_path, store)
                assert count == 3
                assert store.count() == 3

            print("✓ JSONL to SQLite migration successful")
            return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cli_module_imports():
    """Test: Can import CLI module."""
    try:
        from imp.cli.metrics_cli import (  # noqa: F401
            export_command,
            metrics_command,
            migrate_command,
        )

        print("✓ CLI module imports successful")
        return True
    except ImportError as e:
        print(f"✗ CLI module import failed: {e}")
        return False


async def run_all_tests():
    """Run all smoke tests in sequence."""
    print("=" * 60)
    print("Metrics Layer Smoke Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Imports
    results.append(test_imports())

    # Test 2: Collector creation
    collector = test_create_collector()
    results.append(collector is not None)

    # Test 3: Record from provider
    collector_with_data = await test_record_from_provider()
    results.append(collector_with_data is not None)

    # Test 4: Summary calculation
    results.append(test_summary_calculation(collector_with_data))

    # Test 5: JSONL storage
    results.append(test_jsonl_storage())

    # Test 6: Filter operations
    results.append(test_filter_operations())

    # Test 7: Event serialization
    results.append(test_event_serialization())

    # Test 8: End-to-end workflow
    results.append(await test_end_to_end_workflow())

    # Test 9: SQLiteStore
    results.append(test_sqlite_store())

    # Test 10: Aggregation
    results.append(test_aggregation())

    # Test 11: Migration
    results.append(test_migration())

    # Test 12: CLI imports
    results.append(test_cli_module_imports())

    print()
    print("=" * 60)

    if all(results):
        print(f"All {len(results)} smoke tests passed!")
        print("=" * 60)
        return 0
    else:
        failed = len([r for r in results if not r])
        print(f"{failed} smoke test(s) failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    import asyncio

    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
