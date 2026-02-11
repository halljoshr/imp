"""JSONL storage for metrics events."""

import json
from collections.abc import Callable
from pathlib import Path

from imp.metrics.models import MetricsEvent


class MetricsStorage:
    """JSONL storage backend for metrics events.

    Append-only storage with one event per line.
    """

    def __init__(self, storage_path: Path) -> None:
        """Initialize storage with path to JSONL file.

        Args:
            storage_path: Path to JSONL file (will be created if doesn't exist)
        """
        self.storage_path = storage_path

    def write_event(self, event: MetricsEvent) -> None:
        """Write single event to JSONL file.

        Args:
            event: Event to write
        """
        # Create parent directories if they don't exist
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Append event as JSON line
        with open(self.storage_path, "a") as f:
            json_line = event.model_dump_json()
            f.write(json_line + "\n")

    def write_batch(self, events: list[MetricsEvent]) -> None:
        """Write batch of events to JSONL file.

        Args:
            events: List of events to write
        """
        for event in events:
            self.write_event(event)

    def read_events(
        self, filter_fn: Callable[[MetricsEvent], bool] | None = None
    ) -> list[MetricsEvent]:
        """Read all events from JSONL file.

        Args:
            filter_fn: Optional filter function to apply to events

        Returns:
            List of events (filtered if filter_fn provided)
        """
        if not self.storage_path.exists():
            return []

        events = []
        with open(self.storage_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = MetricsEvent.model_validate(data)

                    # Apply filter if provided
                    if filter_fn is None or filter_fn(event):
                        events.append(event)
                except (json.JSONDecodeError, ValueError):
                    # Skip corrupted lines
                    continue

        return events

    def clear(self) -> None:
        """Clear all events from storage file."""
        if self.storage_path.exists():
            self.storage_path.unlink()
