"""Metrics CLI commands — dashboard, export, migrate."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rich import print as rprint
from rich.table import Table

from imp.metrics.aggregator import CostRollup, cost_rollup, performance_summary
from imp.metrics.migration import migrate_jsonl_to_sqlite
from imp.metrics.query import MetricsFilter
from imp.metrics.store import SQLiteStore


def _resolve_db_path(project_root: Path) -> Path:
    """Resolve metrics database path."""
    return project_root / ".imp" / "metrics.db"


def _parse_date_range(date_range: str) -> tuple[datetime, datetime]:
    """Parse a date range string like '2026-02-01:2026-02-15'.

    Args:
        date_range: Colon-separated date range

    Returns:
        Tuple of (start_time, end_time) as aware datetimes

    Raises:
        ValueError: If format is invalid
    """
    parts = date_range.split(":")
    if len(parts) != 2:
        msg = f"Invalid date range format: {date_range}. Use YYYY-MM-DD:YYYY-MM-DD"
        raise ValueError(msg)

    start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    end = (
        datetime.strptime(parts[1].strip(), "%Y-%m-%d").replace(tzinfo=UTC)
        + timedelta(days=1)
        - timedelta(microseconds=1)
    )
    return start, end


def _format_cost(cost: float) -> str:
    """Format cost as USD string."""
    return f"${cost:.4f}" if cost < 1.0 else f"${cost:.2f}"


def _format_tokens(tokens: int) -> str:
    """Format token count with commas."""
    return f"{tokens:,}"


def _render_dashboard(rollup: CostRollup, start: datetime, end: datetime) -> None:
    """Render Rich dashboard to terminal."""
    rprint(
        f"\n[bold]Metrics Dashboard[/bold] ({start.strftime('%Y-%m-%d')} "
        f"→ {end.strftime('%Y-%m-%d')})\n"
    )

    # Cost Summary table
    table = Table(title="Cost Summary")
    table.add_column("Dimension", style="cyan")
    table.add_column("Events", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Duration", justify="right")

    # Total row
    table.add_row(
        "[bold]Total[/bold]",
        str(rollup.total_events),
        _format_tokens(rollup.total_tokens),
        _format_cost(rollup.total_cost_usd),
        f"{rollup.total_duration_ms:,}ms",
    )
    table.add_row("", "", "", "", "")  # spacer

    # By agent role
    for role, entry in sorted(rollup.by_agent_role.items()):
        table.add_row(
            f"  {role}",
            str(entry.event_count),
            _format_tokens(entry.total_tokens),
            _format_cost(entry.total_cost_usd),
            f"{entry.total_duration_ms:,}ms",
        )

    rprint(table)


def _rollup_to_dict(rollup: CostRollup) -> dict[str, object]:
    """Convert CostRollup to a JSON-serializable dict."""
    result: dict[str, object] = json.loads(rollup.model_dump_json())
    return result


def _generate_export_markdown(rollup: CostRollup, ticket_id: str) -> str:
    """Generate markdown summary for PM export.

    Args:
        rollup: Cost rollup data
        ticket_id: Ticket being summarized

    Returns:
        Markdown-formatted cost summary
    """
    lines = [
        f"## Metrics Summary — {ticket_id}",
        "",
        f"**Total Cost:** {_format_cost(rollup.total_cost_usd)}",
        f"**Total Tokens:** {_format_tokens(rollup.total_tokens)}",
        f"**Total Events:** {rollup.total_events}",
        f"**Total Duration:** {rollup.total_duration_ms:,}ms",
        "",
    ]

    if rollup.by_agent_role:
        lines.append("### By Agent Role")
        lines.append("")
        lines.append("| Role | Events | Tokens | Cost |")
        lines.append("|------|--------|--------|------|")
        for role, entry in sorted(rollup.by_agent_role.items()):
            lines.append(
                f"| {role} | {entry.event_count} "
                f"| {_format_tokens(entry.total_tokens)} "
                f"| {_format_cost(entry.total_cost_usd)} |"
            )
        lines.append("")

    if rollup.by_model:
        lines.append("### By Model")
        lines.append("")
        lines.append("| Model | Events | Tokens | Cost |")
        lines.append("|-------|--------|--------|------|")
        for model, entry in sorted(rollup.by_model.items()):
            lines.append(
                f"| {model} | {entry.event_count} "
                f"| {_format_tokens(entry.total_tokens)} "
                f"| {_format_cost(entry.total_cost_usd)} |"
            )

    return "\n".join(lines)


def metrics_command(
    *,
    ticket: str | None = None,
    agent: str | None = None,
    model: str | None = None,
    session: str | None = None,
    days: int = 7,
    date_range: str | None = None,
    output_format: str = "human",
    project_root: Path | None = None,
) -> int:
    """Display metrics dashboard.

    Args:
        ticket: Filter by ticket ID
        agent: Filter by agent role
        model: Filter by model name
        session: Filter by session ID
        days: Number of days to show (default: 7)
        date_range: Date range string (YYYY-MM-DD:YYYY-MM-DD)
        output_format: Output format (human, json)
        project_root: Project root directory

    Returns:
        Exit code (0 = success, 1 = error)
    """
    root = project_root or Path.cwd()
    db_path = _resolve_db_path(root)

    if not db_path.exists():
        if output_format == "json":
            rprint(json.dumps({"error": "No metrics database found", "path": str(db_path)}))
        else:
            rprint(f"[yellow]No metrics database found at {db_path}[/yellow]")
            rprint(
                "Run [bold]imp metrics migrate[/bold] to migrate from JSONL, "
                "or start collecting metrics."
            )
        return 1

    # Build time range
    if date_range:
        try:
            start_time, end_time = _parse_date_range(date_range)
        except ValueError as e:
            rprint(f"[red]Error:[/red] {e}")
            return 1
    else:
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=days)

    # Build filter
    filter_ = MetricsFilter(
        agent_role=agent,
        ticket_id=ticket,
        model=model,
        session_id=session,
        start_time=start_time,
        end_time=end_time,
    )

    with SQLiteStore(db_path) as store:
        events = store.query(filter_)

    if not events:
        if output_format == "json":
            rprint(json.dumps({"events": 0, "message": "No events found"}))
        else:
            rprint("[yellow]No events found for the given filters.[/yellow]")
        return 0

    rollup = cost_rollup(events)
    perf = performance_summary(events)

    if output_format == "json":
        output = {
            "cost": _rollup_to_dict(rollup),
            "performance": json.loads(perf.model_dump_json()),
        }
        rprint(json.dumps(output, indent=2))
    else:
        _render_dashboard(rollup, start_time, end_time)

    return 0


def export_command(
    *,
    ticket_id: str,
    output_format: str = "human",
    project_root: Path | None = None,
) -> int:
    """Export metrics summary to PM ticket as a comment.

    Args:
        ticket_id: Ticket ID to export metrics for
        output_format: Output format (human, json)
        project_root: Project root directory

    Returns:
        Exit code (0 = success, 1 = error)
    """
    root = project_root or Path.cwd()
    db_path = _resolve_db_path(root)

    if not db_path.exists():
        rprint("[red]No metrics database found.[/red]")
        return 1

    filter_ = MetricsFilter(ticket_id=ticket_id)

    with SQLiteStore(db_path) as store:
        events = store.query(filter_)

    if not events:
        rprint(f"[yellow]No events found for ticket {ticket_id}.[/yellow]")
        return 1

    rollup = cost_rollup(events)
    markdown = _generate_export_markdown(rollup, ticket_id)

    if output_format == "json":
        rprint(json.dumps({"ticket_id": ticket_id, "markdown": markdown}))
        return 0

    # Try to post to PM
    try:
        from imp.pm.models import PlaneConfig
        from imp.pm.plane import PlaneAdapter

        config = PlaneConfig.from_env()
        adapter = PlaneAdapter(config)
        adapter.add_comment(ticket_id, markdown)
        rprint(f"[green]Exported metrics to ticket {ticket_id}[/green]")
    except ImportError:
        rprint("[yellow]Plane SDK not installed. Install with: pip install impx[plane][/yellow]")
        rprint("\n[bold]Markdown summary:[/bold]\n")
        rprint(markdown)
    except Exception as e:
        rprint(f"[yellow]Could not post to PM: {e}[/yellow]")
        rprint("\n[bold]Markdown summary:[/bold]\n")
        rprint(markdown)

    return 0


def migrate_command(
    *,
    output_format: str = "human",
    project_root: Path | None = None,
) -> int:
    """Migrate JSONL metrics to SQLite.

    Args:
        output_format: Output format (human, json)
        project_root: Project root directory

    Returns:
        Exit code (0 = success, 1 = error)
    """
    root = project_root or Path.cwd()
    jsonl_path = root / ".imp" / "metrics.jsonl"
    db_path = _resolve_db_path(root)

    if db_path.exists():
        if output_format == "json":
            rprint(json.dumps({"status": "skipped", "reason": "database already exists"}))
        else:
            rprint("[yellow]SQLite database already exists. Skipping migration.[/yellow]")
        return 0

    if not jsonl_path.exists():
        if output_format == "json":
            rprint(json.dumps({"status": "skipped", "reason": "no JSONL file found"}))
        else:
            rprint("[yellow]No JSONL metrics file found to migrate.[/yellow]")
        return 0

    with SQLiteStore(db_path) as store:
        count = migrate_jsonl_to_sqlite(jsonl_path, store)

    if count > 0:
        migrated_path = jsonl_path.with_suffix(".jsonl.migrated")
        jsonl_path.rename(migrated_path)

    if output_format == "json":
        rprint(json.dumps({"status": "success", "events_migrated": count}))
    else:
        rprint(f"[green]Migrated {count} events from JSONL to SQLite.[/green]")

    return 0
