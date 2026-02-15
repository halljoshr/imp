"""Tests for MetricsFilter query builder."""

from datetime import UTC, datetime

from imp.metrics.models import EventType
from imp.metrics.query import MetricsFilter


class TestMetricsFilter:
    """Test MetricsFilter model and SQL generation."""

    def test_empty_filter_generates_passthrough(self) -> None:
        """Empty filter generates WHERE 1=1."""
        f = MetricsFilter()
        sql, params = f.to_sql()
        assert "WHERE 1=1" in sql
        assert params == []

    def test_single_agent_role_filter(self) -> None:
        """Single agent_role filter generates correct SQL."""
        f = MetricsFilter(agent_role="review")
        sql, params = f.to_sql()
        assert "agent_role = ?" in sql
        assert params == ["review"]

    def test_single_ticket_id_filter(self) -> None:
        """Single ticket_id filter generates correct SQL."""
        f = MetricsFilter(ticket_id="IMP-001")
        sql, params = f.to_sql()
        assert "ticket_id = ?" in sql
        assert params == ["IMP-001"]

    def test_single_session_id_filter(self) -> None:
        """Single session_id filter generates correct SQL."""
        f = MetricsFilter(session_id="session-abc")
        sql, params = f.to_sql()
        assert "session_id = ?" in sql
        assert params == ["session-abc"]

    def test_single_model_filter(self) -> None:
        """Single model filter generates correct SQL."""
        f = MetricsFilter(model="claude-opus-4-6")
        sql, params = f.to_sql()
        assert "model = ?" in sql
        assert params == ["claude-opus-4-6"]

    def test_single_provider_filter(self) -> None:
        """Single provider filter generates correct SQL."""
        f = MetricsFilter(provider="anthropic")
        sql, params = f.to_sql()
        assert "provider = ?" in sql
        assert params == ["anthropic"]

    def test_event_type_filter(self) -> None:
        """Event type filter uses string value."""
        f = MetricsFilter(event_type=EventType.SESSION_START)
        sql, params = f.to_sql()
        assert "event_type = ?" in sql
        assert params == ["session_start"]

    def test_start_time_filter(self) -> None:
        """Start time generates >= comparison."""
        t = datetime(2026, 2, 10, tzinfo=UTC)
        f = MetricsFilter(start_time=t)
        sql, params = f.to_sql()
        assert "timestamp >= ?" in sql
        assert params == [t.isoformat()]

    def test_end_time_filter(self) -> None:
        """End time generates <= comparison."""
        t = datetime(2026, 2, 15, tzinfo=UTC)
        f = MetricsFilter(end_time=t)
        sql, params = f.to_sql()
        assert "timestamp <= ?" in sql
        assert params == [t.isoformat()]

    def test_limit_in_limit_clause(self) -> None:
        """Limit is in separate limit_clause()."""
        f = MetricsFilter(limit=10)
        sql, _params = f.to_sql()
        assert "LIMIT" not in sql  # Limit is separate

        limit_sql, limit_params = f.limit_clause()
        assert "LIMIT ?" in limit_sql
        assert limit_params == [10]

    def test_no_limit(self) -> None:
        """No limit returns empty clause."""
        f = MetricsFilter()
        limit_sql, limit_params = f.limit_clause()
        assert limit_sql == ""
        assert limit_params == []

    def test_multiple_filters_combined_with_and(self) -> None:
        """Multiple filters are combined with AND."""
        f = MetricsFilter(agent_role="review", ticket_id="IMP-001", model="claude-opus-4-6")
        sql, params = f.to_sql()
        assert "AND" in sql
        assert len(params) == 3
        assert "review" in params
        assert "IMP-001" in params
        assert "claude-opus-4-6" in params

    def test_all_filters_combined(self) -> None:
        """All filters can be set simultaneously."""
        t1 = datetime(2026, 2, 1, tzinfo=UTC)
        t2 = datetime(2026, 2, 28, tzinfo=UTC)
        f = MetricsFilter(
            agent_role="review",
            ticket_id="IMP-001",
            session_id="sess-1",
            model="claude-opus-4-6",
            provider="anthropic",
            event_type=EventType.AGENT_INVOCATION,
            start_time=t1,
            end_time=t2,
            limit=5,
        )
        _sql, params = f.to_sql()
        # 8 conditions (limit is separate)
        assert len(params) == 8

        limit_sql, limit_params = f.limit_clause()
        assert "LIMIT ?" in limit_sql
        assert limit_params == [5]

    def test_filter_uses_parameterized_queries(self) -> None:
        """Filter values are in params list, not interpolated into SQL."""
        f = MetricsFilter(agent_role="'; DROP TABLE events; --")
        sql, params = f.to_sql()
        # SQL injection attempt should be in params, not in SQL string
        assert "DROP TABLE" not in sql
        assert "'; DROP TABLE events; --" in params

    def test_limit_with_filter(self) -> None:
        """Limit works together with other filters."""
        f = MetricsFilter(agent_role="review", limit=5)
        sql, params = f.to_sql()
        assert "agent_role = ?" in sql
        assert params == ["review"]

        limit_sql, limit_params = f.limit_clause()
        assert "LIMIT ?" in limit_sql
        assert limit_params == [5]
