"""Tests for metrics CLI commands."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from imp.cli.metrics_cli import (
    _format_cost,
    _format_tokens,
    _generate_export_markdown,
    _parse_date_range,
    export_command,
    metrics_command,
    migrate_command,
)
from imp.metrics.aggregator import CostRollup, RollupEntry
from imp.metrics.models import EventType, MetricsEvent
from imp.metrics.storage import MetricsStorage
from imp.metrics.store import SQLiteStore
from imp.types import TokenUsage


def _make_event(
    agent_role: str = "test",
    operation: str = "test_op",
    model: str = "test-model",
    duration_ms: int = 1000,
    cost_usd: float | None = 0.01,
    ticket_id: str | None = None,
    timestamp: datetime | None = None,
) -> MetricsEvent:
    """Helper to create test events."""
    return MetricsEvent(
        event_type=EventType.AGENT_INVOCATION,
        timestamp=timestamp or datetime.now(UTC),
        agent_role=agent_role,
        operation=operation,
        usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=cost_usd),
        model=model,
        provider="test",
        duration_ms=duration_ms,
        ticket_id=ticket_id,
    )


def _setup_db(tmp_path: Path, events: list[MetricsEvent] | None = None) -> Path:
    """Create a metrics DB with optional events."""
    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir(parents=True, exist_ok=True)
    db_path = imp_dir / "metrics.db"

    with SQLiteStore(db_path) as store:
        if events:
            store.write_batch(events)

    return tmp_path


class TestParseDateRange:
    """Test date range parsing."""

    def test_valid_range(self) -> None:
        """Parses valid date range."""
        start, end = _parse_date_range("2026-02-01:2026-02-15")
        assert start.year == 2026
        assert start.month == 2
        assert start.day == 1
        assert end.day == 15
        assert end.hour == 23

    def test_invalid_format_no_colon(self) -> None:
        """Raises ValueError for missing colon."""
        with pytest.raises(ValueError, match="Invalid date range"):
            _parse_date_range("2026-02-01")

    def test_invalid_format_bad_date(self) -> None:
        """Raises ValueError for invalid date."""
        with pytest.raises(ValueError):
            _parse_date_range("2026-13-01:2026-02-15")


class TestFormatHelpers:
    """Test formatting helper functions."""

    def test_format_cost_small(self) -> None:
        """Small costs show 4 decimal places."""
        assert _format_cost(0.0015) == "$0.0015"

    def test_format_cost_large(self) -> None:
        """Costs >= $1 show 2 decimal places."""
        assert _format_cost(1.50) == "$1.50"

    def test_format_tokens(self) -> None:
        """Tokens formatted with commas."""
        assert _format_tokens(123456) == "123,456"

    def test_format_tokens_small(self) -> None:
        """Small token counts formatted correctly."""
        assert _format_tokens(42) == "42"


class TestGenerateExportMarkdown:
    """Test markdown export generation."""

    def test_basic_markdown(self) -> None:
        """Generates markdown with ticket ID and totals."""
        rollup = CostRollup(
            total_cost_usd=0.05,
            total_tokens=1000,
            total_events=5,
            total_duration_ms=10000,
            by_agent_role={},
            by_model={},
            by_ticket={},
        )
        md = _generate_export_markdown(rollup, "IMP-001")
        assert "IMP-001" in md
        assert "$0.0500" in md
        assert "1,000" in md

    def test_markdown_with_roles(self) -> None:
        """Generates role breakdown table."""
        rollup = CostRollup(
            total_cost_usd=0.10,
            total_tokens=2000,
            total_events=3,
            total_duration_ms=5000,
            by_agent_role={
                "review": RollupEntry(
                    event_count=2, total_tokens=1500, total_cost_usd=0.08, total_duration_ms=4000
                ),
                "interview": RollupEntry(
                    event_count=1, total_tokens=500, total_cost_usd=0.02, total_duration_ms=1000
                ),
            },
            by_model={},
            by_ticket={},
        )
        md = _generate_export_markdown(rollup, "IMP-001")
        assert "By Agent Role" in md
        assert "review" in md
        assert "interview" in md

    def test_markdown_with_models(self) -> None:
        """Generates model breakdown table."""
        rollup = CostRollup(
            total_cost_usd=0.10,
            total_tokens=2000,
            total_events=2,
            total_duration_ms=5000,
            by_agent_role={},
            by_model={
                "claude-opus-4-6": RollupEntry(
                    event_count=1, total_tokens=1000, total_cost_usd=0.08, total_duration_ms=3000
                ),
            },
            by_ticket={},
        )
        md = _generate_export_markdown(rollup, "IMP-001")
        assert "By Model" in md
        assert "claude-opus-4-6" in md


class TestMetricsCommand:
    """Test metrics_command function."""

    def test_no_db_returns_error(self, tmp_path: Path) -> None:
        """Returns 1 when no database exists."""
        result = metrics_command(project_root=tmp_path)
        assert result == 1

    def test_no_db_json_output(self, tmp_path: Path) -> None:
        """Returns error JSON when no database exists."""
        result = metrics_command(project_root=tmp_path, output_format="json")
        assert result == 1

    def test_empty_db_returns_0(self, tmp_path: Path) -> None:
        """Returns 0 with message when DB exists but no matching events."""
        root = _setup_db(tmp_path)
        result = metrics_command(project_root=root)
        assert result == 0

    def test_empty_db_json_output(self, tmp_path: Path) -> None:
        """Returns 0 with JSON message when no matching events."""
        root = _setup_db(tmp_path)
        result = metrics_command(project_root=root, output_format="json")
        assert result == 0

    def test_dashboard_with_events(self, tmp_path: Path) -> None:
        """Returns 0 and shows dashboard when events exist."""
        events = [_make_event(agent_role=r) for r in ["review", "interview", "review"]]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, days=365)
        assert result == 0

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON output includes cost and performance data."""
        events = [_make_event()]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, output_format="json", days=365)
        assert result == 0

    def test_filter_by_ticket(self, tmp_path: Path) -> None:
        """Can filter by ticket ID."""
        events = [
            _make_event(ticket_id="IMP-001"),
            _make_event(ticket_id="IMP-002"),
        ]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, ticket="IMP-001", days=365)
        assert result == 0

    def test_filter_by_agent(self, tmp_path: Path) -> None:
        """Can filter by agent role."""
        events = [_make_event(agent_role="review"), _make_event(agent_role="interview")]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, agent="review", days=365)
        assert result == 0

    def test_date_range_filter(self, tmp_path: Path) -> None:
        """Can filter by date range."""
        events = [_make_event()]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, date_range="2026-01-01:2026-12-31")
        assert result == 0

    def test_invalid_date_range(self, tmp_path: Path) -> None:
        """Returns error for invalid date range."""
        events = [_make_event()]
        root = _setup_db(tmp_path, events)
        result = metrics_command(project_root=root, date_range="bad-format")
        assert result == 1


class TestExportCommand:
    """Test export_command function."""

    def test_no_db_returns_error(self, tmp_path: Path) -> None:
        """Returns 1 when no database exists."""
        result = export_command(ticket_id="IMP-001", project_root=tmp_path)
        assert result == 1

    def test_no_events_returns_error(self, tmp_path: Path) -> None:
        """Returns 1 when no events for ticket."""
        root = _setup_db(tmp_path)
        result = export_command(ticket_id="IMP-001", project_root=root)
        assert result == 1

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON output includes ticket ID and markdown."""
        events = [_make_event(ticket_id="IMP-001")]
        root = _setup_db(tmp_path, events)
        result = export_command(ticket_id="IMP-001", output_format="json", project_root=root)
        assert result == 0

    def test_human_output_import_error(self, tmp_path: Path) -> None:
        """Falls back to printing markdown when Plane SDK not installed."""
        events = [_make_event(ticket_id="IMP-001")]
        root = _setup_db(tmp_path, events)

        # Mock the import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "imp.pm.plane":
                raise ImportError("No module named 'plane_sdk'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = export_command(ticket_id="IMP-001", output_format="human", project_root=root)
        assert result == 0

    def test_human_output_plane_success(self, tmp_path: Path) -> None:
        """Posts markdown to Plane when adapter works."""
        events = [_make_event(ticket_id="IMP-001")]
        root = _setup_db(tmp_path, events)

        with (
            patch("imp.pm.models.PlaneConfig.from_env"),
            patch("imp.pm.plane.PlaneAdapter") as mock_cls,
        ):
            mock_adapter = mock_cls.return_value
            mock_adapter.add_comment.return_value = None
            result = export_command(ticket_id="IMP-001", output_format="human", project_root=root)
        assert result == 0
        mock_adapter.add_comment.assert_called_once()

    def test_human_output_plane_error(self, tmp_path: Path) -> None:
        """Falls back to printing markdown on Plane error."""
        events = [_make_event(ticket_id="IMP-001")]
        root = _setup_db(tmp_path, events)

        with (
            patch("imp.pm.models.PlaneConfig.from_env"),
            patch("imp.pm.plane.PlaneAdapter") as mock_cls,
        ):
            mock_cls.return_value.add_comment.side_effect = RuntimeError("Connection failed")
            result = export_command(ticket_id="IMP-001", output_format="human", project_root=root)
        assert result == 0


class TestMigrateCommand:
    """Test migrate_command function."""

    def test_db_already_exists(self, tmp_path: Path) -> None:
        """Skips migration when DB exists."""
        root = _setup_db(tmp_path)
        result = migrate_command(project_root=root)
        assert result == 0

    def test_no_jsonl_file(self, tmp_path: Path) -> None:
        """Returns 0 when no JSONL file."""
        result = migrate_command(project_root=tmp_path)
        assert result == 0

    def test_successful_migration(self, tmp_path: Path) -> None:
        """Migrates JSONL to SQLite and renames file."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        storage.write_batch([_make_event(operation=f"op-{i}") for i in range(5)])

        result = migrate_command(project_root=tmp_path)
        assert result == 0

        # JSONL renamed
        assert not jsonl_path.exists()
        assert (imp_dir / "metrics.jsonl.migrated").exists()

        # DB has events
        with SQLiteStore(imp_dir / "metrics.db") as store:
            assert store.count() == 5

    def test_migration_json_output(self, tmp_path: Path) -> None:
        """JSON output shows migration status."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        jsonl_path = imp_dir / "metrics.jsonl"
        storage = MetricsStorage(jsonl_path)
        storage.write_event(_make_event())

        result = migrate_command(project_root=tmp_path, output_format="json")
        assert result == 0

    def test_db_exists_json_output(self, tmp_path: Path) -> None:
        """JSON output when DB already exists."""
        root = _setup_db(tmp_path)
        result = migrate_command(project_root=root, output_format="json")
        assert result == 0

    def test_no_jsonl_json_output(self, tmp_path: Path) -> None:
        """JSON output when no JSONL file."""
        result = migrate_command(project_root=tmp_path, output_format="json")
        assert result == 0

    def test_empty_jsonl_migration(self, tmp_path: Path) -> None:
        """Migrating empty JSONL doesn't rename the file."""
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        jsonl_path = imp_dir / "metrics.jsonl"
        jsonl_path.touch()  # empty file

        result = migrate_command(project_root=tmp_path)
        assert result == 0

        # File should NOT be renamed (count == 0)
        assert jsonl_path.exists()
        assert not (imp_dir / "metrics.jsonl.migrated").exists()
