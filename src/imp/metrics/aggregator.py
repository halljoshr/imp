"""Aggregation functions for metrics events."""

from __future__ import annotations

import math

from pydantic import BaseModel

from imp.metrics.models import MetricsEvent


class RollupEntry(BaseModel):
    """Aggregated metrics for a single dimension value."""

    event_count: int
    total_tokens: int
    total_cost_usd: float
    total_duration_ms: int


class CostRollup(BaseModel):
    """Cost and token usage rollup across dimensions."""

    total_cost_usd: float
    total_tokens: int
    total_events: int
    total_duration_ms: int
    by_agent_role: dict[str, RollupEntry]
    by_model: dict[str, RollupEntry]
    by_ticket: dict[str, RollupEntry]


class OperationStats(BaseModel):
    """Performance statistics for a single operation type."""

    event_count: int
    avg_duration_ms: float
    p50_duration_ms: int
    p95_duration_ms: int


class PerformanceSummary(BaseModel):
    """Performance summary with percentile statistics."""

    total_events: int
    avg_duration_ms: float
    p50_duration_ms: int
    p95_duration_ms: int
    by_operation: dict[str, OperationStats]


def _percentile(values: list[int], pct: float) -> int:
    """Calculate percentile from a sorted list of integers.

    Args:
        values: Sorted list of values
        pct: Percentile (0-100)

    Returns:
        Value at the given percentile
    """
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lower = math.floor(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    weight = idx - lower
    return int(sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight)


def _build_rollup_entry(events: list[MetricsEvent]) -> RollupEntry:
    """Build a RollupEntry from a list of events."""
    return RollupEntry(
        event_count=len(events),
        total_tokens=sum(e.usage.total_tokens for e in events),
        total_cost_usd=sum(e.usage.cost_usd for e in events if e.usage.cost_usd is not None),
        total_duration_ms=sum(e.duration_ms for e in events),
    )


def cost_rollup(events: list[MetricsEvent]) -> CostRollup:
    """Calculate cost rollup across agent roles, models, and tickets.

    Args:
        events: List of metrics events to aggregate

    Returns:
        CostRollup with totals and per-dimension breakdowns
    """
    if not events:
        return CostRollup(
            total_cost_usd=0.0,
            total_tokens=0,
            total_events=0,
            total_duration_ms=0,
            by_agent_role={},
            by_model={},
            by_ticket={},
        )

    # Group by dimensions
    by_role: dict[str, list[MetricsEvent]] = {}
    by_model: dict[str, list[MetricsEvent]] = {}
    by_ticket: dict[str, list[MetricsEvent]] = {}

    for event in events:
        by_role.setdefault(event.agent_role, []).append(event)
        by_model.setdefault(event.model, []).append(event)
        if event.ticket_id is not None:
            by_ticket.setdefault(event.ticket_id, []).append(event)

    return CostRollup(
        total_cost_usd=sum(e.usage.cost_usd for e in events if e.usage.cost_usd is not None),
        total_tokens=sum(e.usage.total_tokens for e in events),
        total_events=len(events),
        total_duration_ms=sum(e.duration_ms for e in events),
        by_agent_role={k: _build_rollup_entry(v) for k, v in by_role.items()},
        by_model={k: _build_rollup_entry(v) for k, v in by_model.items()},
        by_ticket={k: _build_rollup_entry(v) for k, v in by_ticket.items()},
    )


def _build_operation_stats(events: list[MetricsEvent]) -> OperationStats:
    """Build OperationStats from a list of events."""
    durations = [e.duration_ms for e in events]
    return OperationStats(
        event_count=len(events),
        avg_duration_ms=sum(durations) / len(durations) if durations else 0.0,
        p50_duration_ms=_percentile(durations, 50),
        p95_duration_ms=_percentile(durations, 95),
    )


def performance_summary(events: list[MetricsEvent]) -> PerformanceSummary:
    """Calculate performance summary with percentile statistics.

    Args:
        events: List of metrics events to aggregate

    Returns:
        PerformanceSummary with overall and per-operation stats
    """
    if not events:
        return PerformanceSummary(
            total_events=0,
            avg_duration_ms=0.0,
            p50_duration_ms=0,
            p95_duration_ms=0,
            by_operation={},
        )

    durations = [e.duration_ms for e in events]

    # Group by operation
    by_op: dict[str, list[MetricsEvent]] = {}
    for event in events:
        by_op.setdefault(event.operation, []).append(event)

    return PerformanceSummary(
        total_events=len(events),
        avg_duration_ms=sum(durations) / len(durations),
        p50_duration_ms=_percentile(durations, 50),
        p95_duration_ms=_percentile(durations, 95),
        by_operation={k: _build_operation_stats(v) for k, v in by_op.items()},
    )
