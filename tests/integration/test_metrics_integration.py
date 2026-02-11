"""Integration tests for metrics layer - full end-to-end workflows."""

from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from imp.metrics.collector import MetricsCollector
from imp.metrics.models import EventType
from imp.metrics.storage import MetricsStorage
from imp.providers import PydanticAIProvider


class Question(BaseModel):
    """Test model for structured output."""

    text: str
    category: str


class TestMetricsWithProviderIntegration:
    """Integration tests for metrics collection with provider layer."""

    async def test_full_workflow_with_provider(self, tmp_path: Path) -> None:
        """End-to-end: provider invocation → metrics collection → JSONL storage."""
        # Setup
        storage_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(storage_path)
        collector = MetricsCollector(session_id="integration-test-1")

        # Create provider
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="You are a helpful assistant.",
        )

        # Invoke provider
        result = await provider.invoke("Tell me about Python")

        # Record metrics
        collector.record_from_result(
            result=result,
            agent_role="interview",
            operation="ask_question",
            ticket_id="IMP-INT-001",
        )

        # Verify collection
        events = collector.get_events()
        assert len(events) == 1
        assert events[0].agent_role == "interview"
        assert events[0].usage.input_tokens > 0
        assert events[0].model == "test"

        # Persist to storage
        storage.write_batch(events)

        # Read back from storage
        persisted_events = storage.read_events()
        assert len(persisted_events) == 1
        assert persisted_events[0].ticket_id == "IMP-INT-001"
        assert persisted_events[0].session_id == "integration-test-1"

    async def test_multi_agent_workflow(self, tmp_path: Path) -> None:
        """Simulate multiple agents working on different operations."""
        storage_path = tmp_path / "multi_agent.jsonl"
        storage = MetricsStorage(storage_path)
        collector = MetricsCollector(session_id="multi-agent-session")

        # Interview Agent
        interview_provider = PydanticAIProvider(
            model=TestModel(),
            output_type=Question,
            system_prompt="Generate interview questions.",
        )

        result1 = await interview_provider.invoke("Generate a question about requirements")
        collector.record_from_result(
            result=result1,
            agent_role="interview",
            operation="generate_question",
            ticket_id="IMP-INT-002",
        )

        # Review Agent
        review_provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Review code for issues.",
        )

        result2 = await review_provider.invoke("Review this code: print('hello')")
        collector.record_from_result(
            result=result2,
            agent_role="review",
            operation="analyze_code",
            ticket_id="IMP-INT-002",
        )

        # Context Agent
        context_provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Analyze codebase context.",
        )

        result3 = await context_provider.invoke("Summarize the authentication module")
        collector.record_from_result(
            result=result3,
            agent_role="context",
            operation="analyze_module",
            ticket_id="IMP-INT-002",
        )

        # Verify summary
        summary = collector.get_summary()
        assert summary.total_events == 3
        assert len(summary.by_agent_role) == 3
        assert summary.by_agent_role["interview"]["count"] == 1
        assert summary.by_agent_role["review"]["count"] == 1
        assert summary.by_agent_role["context"]["count"] == 1

        # Persist all
        storage.write_batch(collector.get_events())

        # Filter by ticket
        ticket_events = storage.read_events(filter_fn=lambda e: e.ticket_id == "IMP-INT-002")
        assert len(ticket_events) == 3

    async def test_session_lifecycle_tracking(self, tmp_path: Path) -> None:
        """Track complete session lifecycle with start/end events."""
        storage_path = tmp_path / "session_lifecycle.jsonl"
        storage = MetricsStorage(storage_path)
        collector = MetricsCollector(session_id="session-lifecycle-1")

        # Session start event
        from imp.metrics.models import MetricsEvent
        from imp.providers.base import TokenUsage

        start_event = MetricsEvent(
            event_type=EventType.SESSION_START,
            agent_role="system",
            operation="session_start",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="session-lifecycle-1",
        )
        collector.record_event(start_event)

        # Do some work
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Test",
        )

        for i in range(3):
            result = await provider.invoke(f"Task {i}")
            collector.record_from_result(
                result=result,
                agent_role="test",
                operation=f"task_{i}",
            )

        # Session end event
        end_event = MetricsEvent(
            event_type=EventType.SESSION_END,
            agent_role="system",
            operation="session_end",
            usage=TokenUsage(),
            model="n/a",
            provider="n/a",
            duration_ms=0,
            session_id="session-lifecycle-1",
        )
        collector.record_event(end_event)

        # Verify lifecycle
        events = collector.get_events()
        assert len(events) == 5
        assert events[0].event_type == EventType.SESSION_START
        assert events[-1].event_type == EventType.SESSION_END

        # Persist and verify
        storage.write_batch(events)
        persisted = storage.read_events()
        assert len(persisted) == 5

    async def test_cost_aggregation_realistic_usage(self, tmp_path: Path) -> None:
        """Test cost aggregation with realistic token counts."""
        storage_path = tmp_path / "cost_tracking.jsonl"
        storage = MetricsStorage(storage_path)
        collector = MetricsCollector(session_id="cost-test")

        # Simulate interview agent with Sonnet
        from imp.providers import calculate_cost
        from imp.providers.base import AgentResult, TokenUsage

        # Interview question (Sonnet)
        usage1 = TokenUsage(input_tokens=500, output_tokens=250)
        cost1 = calculate_cost(usage1, "claude-sonnet-4-5-20250929")
        result1 = AgentResult(
            output="What are the key requirements?",
            usage=TokenUsage(
                input_tokens=500,
                output_tokens=250,
                total_tokens=750,
                cost_usd=cost1,
            ),
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1200,
        )
        collector.record_from_result(result1, "interview", "ask_question", "IMP-COST-1")

        # Review with Opus (more expensive)
        usage2 = TokenUsage(input_tokens=2000, output_tokens=1000)
        cost2 = calculate_cost(usage2, "claude-opus-4-6")
        result2 = AgentResult(
            output="Critical security issue found...",
            usage=TokenUsage(
                input_tokens=2000,
                output_tokens=1000,
                total_tokens=3000,
                cost_usd=cost2,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=3500,
        )
        collector.record_from_result(result2, "review", "security_review", "IMP-COST-1")

        # Context with Haiku (cheap)
        usage3 = TokenUsage(input_tokens=5000, output_tokens=500)
        cost3 = calculate_cost(usage3, "claude-haiku-4-5-20251001")
        result3 = AgentResult(
            output="Module summary...",
            usage=TokenUsage(
                input_tokens=5000,
                output_tokens=500,
                total_tokens=5500,
                cost_usd=cost3,
            ),
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            duration_ms=800,
        )
        collector.record_from_result(result3, "context", "summarize_module", "IMP-COST-1")

        # Verify summary
        summary = collector.get_summary()
        assert summary.total_events == 3
        assert summary.total_tokens == 9250  # 750 + 3000 + 5500
        total_cost = cost1 + cost2 + cost3
        assert abs(summary.total_cost - total_cost) < 0.001

        # Verify by role
        assert summary.by_agent_role["review"]["cost"] == cost2
        assert summary.by_agent_role["context"]["cost"] == cost3

        # Persist
        storage.write_batch(collector.get_events())

        # Read back and verify cost tracking
        events = storage.read_events()
        review_events = [e for e in events if e.agent_role == "review"]
        assert len(review_events) == 1
        assert review_events[0].usage.cost_usd == cost2

    async def test_incremental_storage_append(self, tmp_path: Path) -> None:
        """Test that metrics can be appended incrementally during long session."""
        storage_path = tmp_path / "incremental.jsonl"
        storage = MetricsStorage(storage_path)
        collector = MetricsCollector(session_id="incremental-session")

        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Test",
        )

        # Batch 1: Do some work and persist
        for i in range(3):
            result = await provider.invoke(f"Task batch 1, item {i}")
            collector.record_from_result(result, "test", f"batch1_task{i}")

        storage.write_batch(collector.get_events())
        collector.clear()

        # Verify batch 1 written
        assert len(storage.read_events()) == 3

        # Batch 2: More work, append to same file
        for i in range(2):
            result = await provider.invoke(f"Task batch 2, item {i}")
            collector.record_from_result(result, "test", f"batch2_task{i}")

        storage.write_batch(collector.get_events())

        # Verify total
        all_events = storage.read_events()
        assert len(all_events) == 5
        batch1_events = [e for e in all_events if "batch1" in e.operation]
        batch2_events = [e for e in all_events if "batch2" in e.operation]
        assert len(batch1_events) == 3
        assert len(batch2_events) == 2

    async def test_pm_export_format(self, tmp_path: Path) -> None:
        """Test that metrics can be formatted for PM tool export."""
        collector = MetricsCollector(session_id="pm-export-session")

        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="Test",
        )

        # Simulate work on a ticket
        ticket_id = "IMP-PM-001"
        for op in ["analyze", "implement", "test"]:
            result = await provider.invoke(f"Doing {op}")
            collector.record_from_result(
                result=result,
                agent_role="coding",
                operation=op,
                ticket_id=ticket_id,
            )

        # Get summary by ticket
        summary = collector.get_summary()
        events = collector.filter_by_ticket_id(ticket_id)

        # Verify PM-relevant data is present
        assert len(events) == 3
        assert all(e.ticket_id == ticket_id for e in events)
        assert summary.total_tokens > 0
        assert summary.total_duration_ms >= 0  # TestModel can be fast enough to round to 0ms

        # Verify can be serialized for PM export
        pm_export = {
            "ticket_id": ticket_id,
            "total_cost": summary.total_cost,
            "total_tokens": summary.total_tokens,
            "total_duration_ms": summary.total_duration_ms,
            "operations": [
                {
                    "operation": e.operation,
                    "duration_ms": e.duration_ms,
                    "tokens": e.usage.total_tokens,
                }
                for e in events
            ],
        }

        assert pm_export["ticket_id"] == ticket_id
        assert len(pm_export["operations"]) == 3
