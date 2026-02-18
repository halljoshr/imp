"""PM CLI command — generate PM tickets from interview specs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError
from rich import print as rprint
from rich.table import Table

from imp.interview.models import InterviewSpec
from imp.pm.base import PMError
from imp.pm.mapper import spec_to_tickets
from imp.pm.models import PlaneConfig, PlanResult, TicketPriority, TicketRef
from imp.pm.plane import PlaneAdapter


def _receipt_path(project_root: Path, spec_content: str) -> Path:
    """Get the receipt file path for a spec based on content hash."""
    spec_hash = hashlib.sha256(spec_content.encode()).hexdigest()[:12]
    return project_root / ".imp" / "plans" / f"{spec_hash}.json"


def _write_receipt(receipt_file: Path, result: PlanResult) -> None:
    """Write a plan receipt after successful ticket creation."""
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(result.model_dump_json(indent=2))


def plan_command(
    spec_file: Path,
    provider: str = "plane",
    create_parent: bool = True,
    default_priority: str = "medium",
    format: str = "human",
    project_root: Path | None = None,
    force: bool = False,
) -> int:
    """Generate PM tickets from an interview spec file.

    Args:
        spec_file: Path to the interview spec JSON file.
        provider: PM provider (default: plane).
        create_parent: If True, create parent epic ticket.
        default_priority: Default ticket priority.
        format: Output format (human, json, jsonl).
        project_root: Project root for .imp/ directory (default: cwd).
        force: If True, bypass duplicate check.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = project_root or Path.cwd()

    # 1. Load and validate spec file
    if not spec_file.exists():
        rprint(f"[red]Error:[/red] File not found: {spec_file}")
        return 1

    try:
        spec_content = spec_file.read_text()
        spec_json = json.loads(spec_content)
    except json.JSONDecodeError as e:
        rprint(f"[red]Error:[/red] Invalid JSON: {e}")
        return 1

    try:
        spec = InterviewSpec.model_validate(spec_json)
    except ValidationError as e:
        rprint(f"[red]Error:[/red] Invalid spec: {e}")
        return 1

    # 1b. Check for existing plan receipt
    receipt_file = _receipt_path(root, spec_content)
    if not force and receipt_file.exists():
        existing = json.loads(receipt_file.read_text())
        rprint(
            f"[red]Error:[/red] Spec already planned — "
            f"{existing['total_tickets']} tickets created for "
            f"[bold]{existing['spec_name']}[/bold]"
        )
        rprint(f"\nReceipt: {receipt_file}")
        rprint("Use [bold]--force[/bold] to create tickets again.")
        return 1

    # 2. Map priority string to enum
    try:
        priority = TicketPriority(default_priority)
    except ValueError:
        rprint(f"[red]Error:[/red] Invalid priority: {default_priority}")
        return 1

    # 3. Transform spec to tickets
    tickets = spec_to_tickets(spec, create_parent, priority)

    # 4. Initialize adapter
    if provider == "plane":
        try:
            config = PlaneConfig.from_env()
        except ValueError as e:
            rprint(f"[red]Error:[/red] {e}")
            rprint("\n[yellow]Setup instructions:[/yellow]")
            rprint("  export PLANE_API_KEY=<your-api-key>")
            rprint("  export PLANE_WORKSPACE_SLUG=<your-workspace-slug>")
            rprint("  export PLANE_PROJECT_ID=<your-project-id>")
            rprint("  export PLANE_BASE_URL=<base-url>  # optional, defaults to http://localhost")
            return 1

        try:
            adapter = PlaneAdapter(config)
        except PMError as e:
            rprint(f"[red]Error:[/red] {e}")
            rprint("\n[yellow]Install instructions:[/yellow]")
            rprint("  uv add plane-sdk")
            return 1
    else:
        rprint(f"[red]Error:[/red] Unknown provider: {provider}")
        return 1

    # 5. Create tickets
    ticket_refs: list[TicketRef] = []
    parent_ref: TicketRef | None = None

    try:
        if create_parent and tickets:
            # Create parent ticket first
            parent_spec = tickets[0]
            parent_ref = adapter.create_ticket(parent_spec)
            ticket_refs.append(parent_ref)

            # Create component tickets with parent_id set
            for ticket_spec in tickets[1:]:
                # Use model_copy since TicketSpec is frozen
                child_spec = ticket_spec.model_copy(update={"parent_id": parent_ref.ticket_id})
                child_ref = adapter.create_ticket(child_spec)
                ticket_refs.append(child_ref)
        else:
            # Create component tickets without parent
            for ticket_spec in tickets:
                ref = adapter.create_ticket(ticket_spec)
                ticket_refs.append(ref)
    except PMError as e:
        rprint(f"[red]Error:[/red] {e}")
        return 1

    # 6. Build PlanResult
    component_refs = ticket_refs[1:] if create_parent else ticket_refs
    result = PlanResult(
        spec_name=spec.name,
        parent_ticket=parent_ref,
        component_tickets=component_refs,
        total_tickets=len(ticket_refs),
    )

    # 7. Write plan receipt
    _write_receipt(receipt_file, result)

    # 8. Output in requested format
    if format == "json":
        print(result.model_dump_json(indent=2))
    elif format == "jsonl":
        # Output one line per ticket as it was created
        for ref in ticket_refs:
            print(
                json.dumps(
                    {
                        "ticket_id": ref.ticket_id,
                        "ticket_number": ref.ticket_number,
                        "url": ref.url,
                    }
                )
            )
    elif format == "human":
        _print_human_output(result, create_parent)
    else:
        rprint(f"[red]Error:[/red] Unknown format: {format}")
        return 1

    return 0


def _print_human_output(result: PlanResult, create_parent: bool) -> None:
    """Print human-readable output as a Rich table."""
    table = Table(title=f"Plan: {result.spec_name}")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Ticket ID", style="green")
    table.add_column("URL", style="blue")

    # Add parent ticket first (bold)
    if create_parent and result.parent_ticket:
        table.add_row(
            "1",
            f"[bold]{result.spec_name}[/bold]",
            result.parent_ticket.ticket_number,
            result.parent_ticket.url,
        )

    # Add component tickets
    for i, ref in enumerate(result.component_tickets, start=2 if create_parent else 1):
        table.add_row(
            str(i),
            "",  # Title not available in TicketRef
            ref.ticket_number,
            ref.url,
        )

    rprint(table)
    rprint(f"\n[green]✓[/green] Created {result.total_tickets} tickets")
