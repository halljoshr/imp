"""Tests for JSONL to SQLite migration."""

from pathlib import Path

from imp.metrics.migration import auto_migrate_if_needed, migrate_jsonl_to_sqlite
from imp.metrics.models import EventType, MetricsEvent
from imp.metrics.storage import MetricsStorage
from imp.metrics.store import SQLiteStore
from imp.types import TokenUsage


def _make_event(operation: str = "test_op", ticket_id: str | None = None) -> MetricsEvent:
    """Helper to create test events."""
    return MetricsEvent(
        event_type=EventType.AGENT_INVOCATION,
        agent_role="test",
        operation=operation,
        usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.01),
        model="test-model",
        provider="test",
        duration_ms=1000,
        ticket_id=ticket_id,
    )


class TestMigrateJsonlToSqlite:
    """Test migrate_jsonl_to_sqlite function."""

    def test_migrate_events(self, tmp_path: Path) -> None:
        """Can migrate events from JSONL to SQLite."""
        # Write events to JSONL
        jsonl_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        events = [_make_event(operation=f"op-{i}") for i in range(5)]
        storage.write_batch(events)

        # Migrate
        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            count = migrate_jsonl_to_sqlite(jsonl_path, store)
            assert count == 5

            # Verify events in SQLite
            migrated = store.query()
            assert len(migrated) == 5
            assert migrated[0].operation == "op-0"
            assert migrated[4].operation == "op-4"

    def test_migrate_empty_jsonl(self, tmp_path: Path) -> None:
        """Migrating empty JSONL returns 0."""
        jsonl_path = tmp_path / "empty.jsonl"
        jsonl_path.touch()

        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            count = migrate_jsonl_to_sqlite(jsonl_path, store)
            assert count == 0
            assert store.count() == 0

    def test_migrate_nonexistent_jsonl(self, tmp_path: Path) -> None:
        """Migrating nonexistent JSONL returns 0."""
        jsonl_path = tmp_path / "nonexistent.jsonl"

        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            count = migrate_jsonl_to_sqlite(jsonl_path, store)
            assert count == 0

    def test_migrate_preserves_all_fields(self, tmp_path: Path) -> None:
        """Migration preserves all event fields."""
        jsonl_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)

        event = MetricsEvent(
            event_type=EventType.AGENT_INVOCATION,
            agent_role="review",
            operation="analyze",
            usage=TokenUsage(input_tokens=500, output_tokens=250, cost_usd=0.05),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2500,
            session_id="session-123",
            ticket_id="IMP-042",
            metadata={"key": "value"},
        )
        storage.write_event(event)

        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            migrate_jsonl_to_sqlite(jsonl_path, store)
            result = store.query()[0]

        assert result.agent_role == "review"
        assert result.operation == "analyze"
        assert result.usage.input_tokens == 500
        assert result.usage.cost_usd == 0.05
        assert result.model == "claude-opus-4-6"
        assert result.session_id == "session-123"
        assert result.ticket_id == "IMP-042"
        assert result.metadata == {"key": "value"}

    def test_migrate_large_batch(self, tmp_path: Path) -> None:
        """Can migrate many events."""
        jsonl_path = tmp_path / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        events = [_make_event(operation=f"op-{i}") for i in range(100)]
        storage.write_batch(events)

        db_path = tmp_path / "metrics.db"
        with SQLiteStore(db_path) as store:
            count = migrate_jsonl_to_sqlite(jsonl_path, store)
            assert count == 100
            assert store.count() == 100


class TestAutoMigrateIfNeeded:
    """Test auto_migrate_if_needed function."""

    def test_auto_migrate_success(self, tmp_path: Path) -> None:
        """Auto-migrates when JSONL exists and DB doesn't."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        # Write JSONL
        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        storage.write_batch([_make_event(operation=f"op-{i}") for i in range(3)])

        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is True
        assert count == 3

        # JSONL should be renamed
        assert not jsonl_path.exists()
        assert (imp_dir / "metrics.jsonl.migrated").exists()

        # DB should exist with events
        db_path = imp_dir / "metrics.db"
        assert db_path.exists()
        with SQLiteStore(db_path) as store:
            assert store.count() == 3

    def test_skips_when_db_exists(self, tmp_path: Path) -> None:
        """Skips migration when DB already exists."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        # Create both JSONL and DB
        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        storage.write_event(_make_event())

        db_path = imp_dir / "metrics.db"
        SQLiteStore(db_path).close()

        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is False
        assert count == 0

    def test_skips_when_no_jsonl(self, tmp_path: Path) -> None:
        """Skips migration when no JSONL file exists."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is False
        assert count == 0

    def test_skips_when_no_imp_dir(self, tmp_path: Path) -> None:
        """Skips migration when .imp directory doesn't exist."""
        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is False
        assert count == 0

    def test_idempotent(self, tmp_path: Path) -> None:
        """Second auto-migrate is a no-op."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        storage.write_event(_make_event())

        # First migration
        migrated1, count1 = auto_migrate_if_needed(tmp_path)
        assert migrated1 is True
        assert count1 == 1

        # Second migration (DB exists now)
        migrated2, count2 = auto_migrate_if_needed(tmp_path)
        assert migrated2 is False
        assert count2 == 0

    def test_empty_jsonl_still_renames(self, tmp_path: Path) -> None:
        """Empty JSONL file: migrated=True but count=0, no rename."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        jsonl_path = imp_dir / "metrics.jsonl"
        jsonl_path.touch()  # empty file

        migrated, count = auto_migrate_if_needed(tmp_path)
        assert migrated is True
        assert count == 0
        # Empty file: count==0 so no rename happens
        assert jsonl_path.exists()
