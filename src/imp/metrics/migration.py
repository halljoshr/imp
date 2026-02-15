"""JSONL to SQLite migration utilities."""

from __future__ import annotations

from pathlib import Path

from imp.metrics.storage import MetricsStorage
from imp.metrics.store import SQLiteStore


def migrate_jsonl_to_sqlite(jsonl_path: Path, store: SQLiteStore) -> int:
    """Import JSONL events into SQLite.

    Args:
        jsonl_path: Path to JSONL metrics file
        store: SQLiteStore to write events into

    Returns:
        Number of events migrated
    """
    storage = MetricsStorage(jsonl_path)
    events = storage.read_events()
    if events:
        store.write_batch(events)
    return len(events)


def auto_migrate_if_needed(project_root: Path) -> tuple[bool, int]:
    """Auto-migrate .imp/metrics.jsonl to .imp/metrics.db if needed.

    Skips if .db already exists or .jsonl doesn't exist.
    Renames .jsonl to .jsonl.migrated after success.

    Args:
        project_root: Project root directory

    Returns:
        Tuple of (migrated: bool, event_count: int)
    """
    jsonl_path = project_root / ".imp" / "metrics.jsonl"
    db_path = project_root / ".imp" / "metrics.db"

    if not jsonl_path.exists() or db_path.exists():
        return False, 0

    with SQLiteStore(db_path) as store:
        count = migrate_jsonl_to_sqlite(jsonl_path, store)

    if count > 0:
        migrated_path = jsonl_path.with_suffix(".jsonl.migrated")
        jsonl_path.rename(migrated_path)

    return True, count
