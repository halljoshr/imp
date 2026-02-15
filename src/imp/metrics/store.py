"""SQLite storage backend for metrics events."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import TracebackType

from imp.metrics.models import MetricsEvent
from imp.metrics.query import MetricsFilter


class SQLiteStore:
    """SQLite storage backend for metrics events.

    Uses WAL mode for concurrent reads, stores usage/metadata as JSON columns.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize store and create schema.

        Args:
            db_path: Path to SQLite database file (created if doesn't exist)
        """
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema()

    def _create_schema(self) -> None:
        """Create events table and indexes if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                operation TEXT NOT NULL,
                usage TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                session_id TEXT,
                ticket_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_agent_role ON events(agent_role)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ticket_id ON events(ticket_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_model ON events(model)")
        self._conn.commit()

    def _event_to_row(self, event: MetricsEvent) -> tuple[object, ...]:
        """Convert MetricsEvent to a database row tuple."""
        return (
            event.event_type.value,
            event.timestamp.isoformat(),
            event.agent_role,
            event.operation,
            json.dumps(event.usage.model_dump()),
            event.model,
            event.provider,
            event.duration_ms,
            event.session_id,
            event.ticket_id,
            json.dumps(event.metadata, default=str),
        )

    def _row_to_event(self, row: tuple[object, ...]) -> MetricsEvent:
        """Convert a database row to MetricsEvent."""
        from datetime import datetime

        from imp.metrics.models import EventType
        from imp.types import TokenUsage

        return MetricsEvent(
            event_type=EventType(str(row[1])),
            timestamp=datetime.fromisoformat(str(row[2])),
            agent_role=str(row[3]),
            operation=str(row[4]),
            usage=TokenUsage.model_validate(json.loads(str(row[5]))),
            model=str(row[6]),
            provider=str(row[7]),
            duration_ms=int(str(row[8])),
            session_id=str(row[9]) if row[9] is not None else None,
            ticket_id=str(row[10]) if row[10] is not None else None,
            metadata=json.loads(str(row[11])),
        )

    def write_event(self, event: MetricsEvent) -> None:
        """Write a single event to the database.

        Args:
            event: MetricsEvent to persist
        """
        row = self._event_to_row(event)
        self._conn.execute(
            """INSERT INTO events
            (event_type, timestamp, agent_role, operation, usage,
             model, provider, duration_ms, session_id, ticket_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
        self._conn.commit()

    def write_batch(self, events: list[MetricsEvent]) -> None:
        """Write a batch of events in a single transaction.

        Args:
            events: List of events to persist
        """
        rows = [self._event_to_row(e) for e in events]
        self._conn.executemany(
            """INSERT INTO events
            (event_type, timestamp, agent_role, operation, usage,
             model, provider, duration_ms, session_id, ticket_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    def query(self, filter: MetricsFilter | None = None) -> list[MetricsEvent]:
        """Query events with optional filtering.

        Args:
            filter: Optional filter criteria

        Returns:
            List of matching MetricsEvent objects
        """
        base_sql = "SELECT * FROM events"
        if filter is not None:
            where_clause, where_params = filter.to_sql()
            limit_clause, limit_params = filter.limit_clause()
            sql = f"{base_sql} {where_clause} ORDER BY timestamp ASC {limit_clause}"
            params = where_params + limit_params
        else:
            sql = f"{base_sql} ORDER BY timestamp ASC"
            params = []

        cursor = self._conn.execute(sql, params)
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def count(self, filter: MetricsFilter | None = None) -> int:
        """Count events matching optional filter.

        Args:
            filter: Optional filter criteria

        Returns:
            Number of matching events
        """
        base_sql = "SELECT COUNT(*) FROM events"
        if filter is not None:
            where_clause, params = filter.to_sql()
            sql = f"{base_sql} {where_clause}"
        else:
            sql = base_sql
            params = []

        cursor = self._conn.execute(sql, params)
        result = cursor.fetchone()
        return int(str(result[0])) if result else 0

    def clear(self) -> None:
        """Delete all events from the database."""
        self._conn.execute("DELETE FROM events")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
