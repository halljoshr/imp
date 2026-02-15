"""Metrics query filter for building parameterized SQL queries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from imp.metrics.models import EventType


class MetricsFilter(BaseModel):
    """Filter criteria for querying metrics events.

    Builds parameterized SQL WHERE clauses (safe from injection).
    """

    agent_role: str | None = None
    ticket_id: str | None = None
    session_id: str | None = None
    model: str | None = None
    provider: str | None = None
    event_type: EventType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int | None = None

    def to_sql(self) -> tuple[str, list[object]]:
        """Build a WHERE clause with parameterized values.

        Returns:
            Tuple of (SQL string starting with WHERE, list of parameter values)
        """
        conditions: list[str] = []
        params: list[object] = []

        if self.agent_role is not None:
            conditions.append("agent_role = ?")
            params.append(self.agent_role)

        if self.ticket_id is not None:
            conditions.append("ticket_id = ?")
            params.append(self.ticket_id)

        if self.session_id is not None:
            conditions.append("session_id = ?")
            params.append(self.session_id)

        if self.model is not None:
            conditions.append("model = ?")
            params.append(self.model)

        if self.provider is not None:
            conditions.append("provider = ?")
            params.append(self.provider)

        if self.event_type is not None:
            conditions.append("event_type = ?")
            params.append(self.event_type.value)

        if self.start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(self.start_time.isoformat())

        if self.end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(self.end_time.isoformat())

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"WHERE {where}"

        return sql, params

    def limit_clause(self) -> tuple[str, list[object]]:
        """Build LIMIT clause if limit is set.

        Returns:
            Tuple of (SQL LIMIT clause or empty string, list of parameter values)
        """
        if self.limit is not None:
            return "LIMIT ?", [self.limit]
        return "", []
