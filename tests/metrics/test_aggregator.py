"""Tests for metrics aggregation functions."""

from datetime import UTC, datetime

from imp.metrics.aggregator import (
    CostRollup,
    OperationStats,
    PerformanceSummary,
    RollupEntry,
    _percentile,
    cost_rollup,
    performance_summary,
)
from imp.metrics.models import EventType, MetricsEvent
from imp.types import TokenUsage


def _make_event(
    agent_role: str = "test",
    operation: str = "test_op",
    model: str = "test-model",
    duration_ms: int = 1000,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: float | None = None,
    ticket_id: str | None = None,
) -> MetricsEvent:
    """Helper to create test events."""
    return MetricsEvent(
        event_type=EventType.AGENT_INVOCATION,
        timestamp=datetime.now(UTC),
        agent_role=agent_role,
        operation=operation,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
        ),
        model=model,
        provider="test",
        duration_ms=duration_ms,
        ticket_id=ticket_id,
    )


class TestPercentile:
    """Test percentile calculation."""

    def test_empty_list(self) -> None:
        """Percentile of empty list is 0."""
        assert _percentile([], 50) == 0

    def test_single_value(self) -> None:
        """Percentile of single value is that value."""
        assert _percentile([100], 50) == 100
        assert _percentile([100], 95) == 100

    def test_two_values_p50(self) -> None:
        """P50 of two values is the midpoint."""
        assert _percentile([100, 200], 50) == 150

    def test_sorted_list_p50(self) -> None:
        """P50 of sorted list."""
        assert _percentile([10, 20, 30, 40, 50], 50) == 30

    def test_unsorted_list(self) -> None:
        """Percentile sorts internally."""
        assert _percentile([50, 10, 30, 20, 40], 50) == 30

    def test_p95(self) -> None:
        """P95 calculation."""
        values = list(range(1, 101))  # 1..100
        p95 = _percentile(values, 95)
        assert 94 <= p95 <= 96

    def test_p0(self) -> None:
        """P0 returns minimum."""
        assert _percentile([10, 20, 30], 0) == 10

    def test_p100(self) -> None:
        """P100 returns maximum."""
        assert _percentile([10, 20, 30], 100) == 30


class TestRollupEntry:
    """Test RollupEntry model."""

    def test_creation(self) -> None:
        """Can create RollupEntry."""
        entry = RollupEntry(
            event_count=10,
            total_tokens=5000,
            total_cost_usd=0.50,
            total_duration_ms=30000,
        )
        assert entry.event_count == 10
        assert entry.total_tokens == 5000
        assert entry.total_cost_usd == 0.50
        assert entry.total_duration_ms == 30000


class TestCostRollup:
    """Test cost_rollup function."""

    def test_empty_events(self) -> None:
        """Cost rollup of empty list returns zeros."""
        rollup = cost_rollup([])
        assert rollup.total_cost_usd == 0.0
        assert rollup.total_tokens == 0
        assert rollup.total_events == 0
        assert rollup.total_duration_ms == 0
        assert rollup.by_agent_role == {}
        assert rollup.by_model == {}
        assert rollup.by_ticket == {}

    def test_single_event(self) -> None:
        """Cost rollup of single event."""
        event = _make_event(
            agent_role="review",
            model="claude-opus-4-6",
            cost_usd=0.05,
            input_tokens=500,
            output_tokens=250,
            duration_ms=2000,
            ticket_id="IMP-001",
        )
        rollup = cost_rollup([event])

        assert rollup.total_events == 1
        assert rollup.total_cost_usd == 0.05
        assert rollup.total_tokens == 750
        assert rollup.total_duration_ms == 2000

        assert "review" in rollup.by_agent_role
        assert rollup.by_agent_role["review"].event_count == 1
        assert "claude-opus-4-6" in rollup.by_model
        assert "IMP-001" in rollup.by_ticket

    def test_multiple_events_by_role(self) -> None:
        """Cost rollup groups by agent role correctly."""
        events = [
            _make_event(agent_role="interview", cost_usd=0.01, duration_ms=1000),
            _make_event(agent_role="review", cost_usd=0.05, duration_ms=3000),
            _make_event(agent_role="interview", cost_usd=0.02, duration_ms=1500),
        ]
        rollup = cost_rollup(events)

        assert rollup.total_events == 3
        assert rollup.total_cost_usd == 0.08
        assert len(rollup.by_agent_role) == 2

        interview = rollup.by_agent_role["interview"]
        assert interview.event_count == 2
        assert interview.total_cost_usd == 0.03
        assert interview.total_duration_ms == 2500

        review = rollup.by_agent_role["review"]
        assert review.event_count == 1
        assert review.total_cost_usd == 0.05

    def test_multiple_events_by_model(self) -> None:
        """Cost rollup groups by model correctly."""
        events = [
            _make_event(model="claude-opus-4-6", input_tokens=1000),
            _make_event(model="claude-haiku-4-5-20251001", input_tokens=5000),
            _make_event(model="claude-opus-4-6", input_tokens=2000),
        ]
        rollup = cost_rollup(events)

        assert len(rollup.by_model) == 2
        assert rollup.by_model["claude-opus-4-6"].event_count == 2
        assert rollup.by_model["claude-haiku-4-5-20251001"].event_count == 1

    def test_events_by_ticket(self) -> None:
        """Cost rollup groups by ticket, excluding None tickets."""
        events = [
            _make_event(ticket_id="IMP-001", cost_usd=0.01),
            _make_event(ticket_id="IMP-002", cost_usd=0.02),
            _make_event(ticket_id="IMP-001", cost_usd=0.03),
            _make_event(ticket_id=None, cost_usd=0.04),
        ]
        rollup = cost_rollup(events)

        assert len(rollup.by_ticket) == 2  # None tickets excluded
        assert rollup.by_ticket["IMP-001"].event_count == 2
        assert rollup.by_ticket["IMP-001"].total_cost_usd == 0.04
        assert rollup.by_ticket["IMP-002"].event_count == 1

    def test_none_costs_treated_as_zero(self) -> None:
        """Events with None cost are treated as 0 in rollup."""
        events = [
            _make_event(cost_usd=0.01),
            _make_event(cost_usd=None),
            _make_event(cost_usd=0.02),
        ]
        rollup = cost_rollup(events)
        assert rollup.total_cost_usd == 0.03

    def test_token_totals(self) -> None:
        """Token totals sum correctly."""
        events = [
            _make_event(input_tokens=100, output_tokens=50),
            _make_event(input_tokens=200, output_tokens=100),
        ]
        rollup = cost_rollup(events)
        assert rollup.total_tokens == 450  # (100+50) + (200+100)

    def test_duration_totals(self) -> None:
        """Duration totals sum correctly."""
        events = [
            _make_event(duration_ms=1000),
            _make_event(duration_ms=2000),
            _make_event(duration_ms=3000),
        ]
        rollup = cost_rollup(events)
        assert rollup.total_duration_ms == 6000

    def test_rollup_serialization(self) -> None:
        """CostRollup can be serialized to JSON."""
        rollup = CostRollup(
            total_cost_usd=0.05,
            total_tokens=1000,
            total_events=5,
            total_duration_ms=10000,
            by_agent_role={},
            by_model={},
            by_ticket={},
        )
        data = rollup.model_dump()
        assert data["total_cost_usd"] == 0.05
        assert data["total_events"] == 5


class TestPerformanceSummary:
    """Test performance_summary function."""

    def test_empty_events(self) -> None:
        """Performance summary of empty list returns zeros."""
        summary = performance_summary([])
        assert summary.total_events == 0
        assert summary.avg_duration_ms == 0.0
        assert summary.p50_duration_ms == 0
        assert summary.p95_duration_ms == 0
        assert summary.by_operation == {}

    def test_single_event(self) -> None:
        """Performance summary of single event."""
        event = _make_event(operation="analyze", duration_ms=2000)
        summary = performance_summary([event])

        assert summary.total_events == 1
        assert summary.avg_duration_ms == 2000.0
        assert summary.p50_duration_ms == 2000
        assert summary.p95_duration_ms == 2000

        assert "analyze" in summary.by_operation
        assert summary.by_operation["analyze"].event_count == 1

    def test_multiple_operations(self) -> None:
        """Performance summary groups by operation."""
        events = [
            _make_event(operation="analyze", duration_ms=1000),
            _make_event(operation="review", duration_ms=3000),
            _make_event(operation="analyze", duration_ms=2000),
            _make_event(operation="review", duration_ms=4000),
        ]
        summary = performance_summary(events)

        assert summary.total_events == 4
        assert len(summary.by_operation) == 2

        analyze = summary.by_operation["analyze"]
        assert analyze.event_count == 2
        assert analyze.avg_duration_ms == 1500.0

        review = summary.by_operation["review"]
        assert review.event_count == 2
        assert review.avg_duration_ms == 3500.0

    def test_percentiles(self) -> None:
        """Performance summary calculates correct percentiles."""
        events = [_make_event(duration_ms=ms) for ms in [100, 200, 300, 400, 500]]
        summary = performance_summary(events)

        assert summary.p50_duration_ms == 300
        assert summary.avg_duration_ms == 300.0

    def test_operation_stats_percentiles(self) -> None:
        """Per-operation stats have correct percentiles."""
        events = [
            _make_event(operation="test", duration_ms=100),
            _make_event(operation="test", duration_ms=200),
            _make_event(operation="test", duration_ms=300),
        ]
        summary = performance_summary(events)
        stats = summary.by_operation["test"]

        assert stats.p50_duration_ms == 200
        assert stats.event_count == 3

    def test_summary_serialization(self) -> None:
        """PerformanceSummary can be serialized to JSON."""
        summary = PerformanceSummary(
            total_events=5,
            avg_duration_ms=1500.0,
            p50_duration_ms=1200,
            p95_duration_ms=2800,
            by_operation={},
        )
        data = summary.model_dump()
        assert data["total_events"] == 5
        assert data["avg_duration_ms"] == 1500.0

    def test_operation_stats_model(self) -> None:
        """OperationStats model works correctly."""
        stats = OperationStats(
            event_count=10,
            avg_duration_ms=1500.5,
            p50_duration_ms=1200,
            p95_duration_ms=2800,
        )
        assert stats.event_count == 10
        assert stats.avg_duration_ms == 1500.5
