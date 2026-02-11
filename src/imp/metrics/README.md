# Metrics Collection Layer

Lightweight metrics collection for tracking token usage, costs, and performance across all AI operations in Imp.

## Overview

The metrics module provides:
- **MetricsCollector** - Record and aggregate AI operation metrics
- **MetricsStorage** - JSONL-based persistent storage
- **MetricsEvent** - Structured event model with full metadata
- **EventType** - Standardized event type classification

## Quick Start

```python
from imp.metrics import MetricsCollector
from imp.providers import PydanticAIProvider

# Create collector (optionally scoped to a session)
collector = MetricsCollector(session_id="feature-auth-123")

# Create provider
provider = PydanticAIProvider(model="claude-sonnet-4-5")

# Invoke provider
result = provider.invoke(
    prompt="Explain authentication flow",
    agent_name="interview"
)

# Record metrics from result
collector.record_from_result(
    result=result,
    agent_role="interview",
    operation="ask_question",
    ticket_id="PROJ-456"
)

# Get summary
summary = collector.get_summary()
print(f"Total tokens: {summary.total_tokens}")
print(f"Total cost: ${summary.total_cost:.4f}")
print(f"By role: {summary.by_agent_role}")
```

## Core API

### MetricsCollector

Main interface for recording and querying metrics.

```python
class MetricsCollector:
    def __init__(self, session_id: str | None = None):
        """Create collector, optionally scoped to a session."""

    def record_from_result(
        self,
        result: AgentResult,
        agent_role: str,
        operation: str,
        ticket_id: str | None = None
    ):
        """Record metrics from an AgentResult."""

    def record_event(self, event: MetricsEvent):
        """Record a custom metrics event."""

    def get_events(self) -> list[MetricsEvent]:
        """Get all recorded events."""

    def get_summary(self) -> MetricsSummary:
        """Get aggregated summary statistics."""

    def filter_by_agent_role(self, role: str) -> list[MetricsEvent]:
        """Get events for a specific agent role."""

    def filter_by_ticket_id(self, ticket_id: str) -> list[MetricsEvent]:
        """Get events for a specific ticket."""

    def clear(self):
        """Clear all recorded events."""
```

### MetricsEvent

Structured event model with full metadata.

```python
class MetricsEvent(BaseModel):
    event_type: EventType                # Type of event
    timestamp: datetime                  # Auto-populated
    agent_role: str                      # e.g., "interview", "review", "coding"
    operation: str                       # Operation performed
    usage: TokenUsage                    # Token counts from provider
    model: str                           # Model name
    provider: str                        # Provider name
    duration_ms: int                     # Operation duration
    session_id: str | None = None        # Optional session ID
    ticket_id: str | None = None         # Optional PM ticket ID
    metadata: dict = {}                  # Additional context
```

### EventType

Standardized event types for classification.

```python
class EventType(str, Enum):
    AGENT_INVOCATION = "agent_invocation"  # AI model invocation
    SESSION_START = "session_start"        # Work session started
    SESSION_END = "session_end"            # Work session ended
    TICKET_START = "ticket_start"          # Ticket work started
    TICKET_END = "ticket_end"              # Ticket work completed
```

### MetricsSummary

Aggregated statistics across events.

```python
class MetricsSummary(BaseModel):
    total_events: int                    # Total events recorded
    total_tokens: int                    # Sum of all tokens
    total_cost: float                    # Sum of all costs (USD)
    total_duration_ms: int               # Sum of all durations
    by_agent_role: dict[str, dict]       # Stats grouped by role
    by_operation: dict[str, dict]        # Stats grouped by operation
```

## Persistent Storage

### MetricsStorage

JSONL-based storage for metrics events.

```python
from pathlib import Path
from imp.metrics import MetricsStorage, MetricsEvent

# Create storage
storage = MetricsStorage(Path("metrics.jsonl"))

# Write single event
storage.write_event(event)

# Write batch
storage.write_batch([event1, event2, event3])

# Read all events
events = storage.read_events()

# Read with filter
interview_events = storage.read_events(
    filter_fn=lambda e: e.agent_role == "interview"
)

# Clear storage
storage.clear()
```

### JSONL Format

Each event is stored as one line of JSON:

```jsonl
{"event_type":"agent_invocation","timestamp":"2026-02-11T12:00:00","agent_role":"interview","operation":"ask_question","usage":{"input_tokens":100,"output_tokens":50,"cost_usd":0.01},"model":"claude-sonnet-4-5","provider":"anthropic","duration_ms":1500,"session_id":"session-123","ticket_id":"PROJ-456","metadata":{}}
{"event_type":"agent_invocation","timestamp":"2026-02-11T12:01:30","agent_role":"review","operation":"code_review","usage":{"input_tokens":500,"output_tokens":200,"cost_usd":0.04},"model":"claude-sonnet-4-5","provider":"anthropic","duration_ms":2300,"session_id":"session-123","ticket_id":"PROJ-456","metadata":{}}
```

Features:
- **Append-only** - New events append, never overwrite
- **One event per line** - Easy to stream and process
- **Self-describing** - Full context in each event
- **Robust** - Corrupted lines are skipped during read
- **Filterable** - Apply filters during read

## PM Export Format

For integration with project management tools (Plane, Linear):

```python
summary = collector.get_summary()

# Export format for PM tool
pm_data = {
    "ticket_id": "PROJ-456",
    "session_id": "session-123",
    "metrics": {
        "total_tokens": summary.total_tokens,
        "total_cost_usd": summary.total_cost,
        "total_duration_ms": summary.total_duration_ms,
        "event_count": summary.total_events,
    },
    "by_agent_role": summary.by_agent_role,
    "timestamp": datetime.now().isoformat(),
}
```

This data can be posted to PM tool APIs to track:
- Token usage per ticket
- Cost per feature
- Agent efficiency
- Session duration

## Usage Patterns

### Session-scoped Tracking

```python
# Track all work for a session
collector = MetricsCollector(session_id="feature-auth-123")

# Record session start
start_event = MetricsEvent(
    event_type=EventType.SESSION_START,
    agent_role="system",
    operation="initialize",
    usage=TokenUsage(),
    model="n/a",
    provider="n/a",
    duration_ms=0,
    session_id="feature-auth-123",
)
collector.record_event(start_event)

# ... do work ...

# Record session end
end_event = MetricsEvent(
    event_type=EventType.SESSION_END,
    agent_role="system",
    operation="finalize",
    usage=TokenUsage(),
    model="n/a",
    provider="n/a",
    duration_ms=0,
    session_id="feature-auth-123",
)
collector.record_event(end_event)

# Get session summary
summary = collector.get_summary()
```

### Ticket-scoped Tracking

```python
# Track all work for a ticket across sessions
all_events = storage.read_events(
    filter_fn=lambda e: e.ticket_id == "PROJ-456"
)

ticket_collector = MetricsCollector()
for event in all_events:
    ticket_collector.record_event(event)

ticket_summary = ticket_collector.get_summary()
print(f"Ticket PROJ-456 total cost: ${ticket_summary.total_cost:.2f}")
```

### Multi-agent Workflow

```python
collector = MetricsCollector(session_id="session-123")

# Interview agent
interview_result = interview_provider.invoke(...)
collector.record_from_result(
    interview_result,
    agent_role="interview",
    operation="gather_requirements",
    ticket_id="PROJ-456"
)

# Review agent
review_result = review_provider.invoke(...)
collector.record_from_result(
    review_result,
    agent_role="review",
    operation="code_review",
    ticket_id="PROJ-456"
)

# Coding agent
coding_result = coding_provider.invoke(...)
collector.record_from_result(
    coding_result,
    agent_role="coding",
    operation="implement",
    ticket_id="PROJ-456"
)

# Analyze by role
summary = collector.get_summary()
print(summary.by_agent_role)
# {
#   "interview": {"events": 1, "tokens": 150, "cost": 0.01, ...},
#   "review": {"events": 1, "tokens": 700, "cost": 0.04, ...},
#   "coding": {"events": 1, "tokens": 2000, "cost": 0.10, ...}
# }
```

## Architecture

### Layer Boundaries

The metrics module is **L0 foundation** - independent with no internal dependencies:

```
imp/
├── types/          (L0 - shared types)
│   └── base.py     TokenUsage, AgentResult
├── metrics/        (L0 - metrics collection)
│   ├── models.py   EventType, MetricsEvent, MetricsSummary
│   ├── collector.py  MetricsCollector
│   └── storage.py  MetricsStorage (JSONL)
├── providers/      (L0 - AI providers)
└── ... other modules
```

**Dependencies:**
- Imports `TokenUsage` and `AgentResult` from `imp.types` (L0 shared types)
- No dependencies on other Imp modules
- Pure Pydantic models for data structures

### Design Principles

1. **Lightweight** - Minimal overhead, fast operations
2. **Provider-agnostic** - Works with any `AgentProvider` implementation
3. **Append-only storage** - JSONL for reliability and simplicity
4. **Flexible filtering** - Query by role, ticket, session, custom criteria
5. **PM-ready** - Export format designed for PM tool integration

## Testing

The metrics module has comprehensive three-tier testing:

```bash
# Tier 1: Unit tests (35 tests, 100% coverage)
uv run pytest tests/metrics/ -v

# Tier 2: Integration tests (6 tests)
uv run pytest tests/integration/test_metrics_integration.py -v

# Tier 3: Smoke tests (8 tests)
uv run python tests/smoke/smoke_test_metrics.py
```

All tests must pass before any changes are committed.

## Future Enhancements

Planned for later versions:

- **DuckDB/SQLite backend** - Optional database storage for complex queries
- **Cost budgets** - Circuit breaker when budgets are exceeded
- **Real-time dashboards** - Live metrics visualization
- **Anomaly detection** - Alert on unusual token usage or costs
- **Cost attribution** - Per-developer, per-team, per-project tracking
