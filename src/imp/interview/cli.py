"""CLI commands for interview spec validation and import."""

import json
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from imp.interview.models import CompletenessResult, GapSeverity
from imp.interview.validator import validate_spec_file

console = Console()


def validate_command(
    spec_file: Path,
    format: str = "human",
) -> int:
    """Validate an interview spec file for completeness.

    Args:
        spec_file: Path to the spec JSON file.
        format: Output format: "human", "json", or "jsonl".

    Returns:
        Exit code (0 = complete, 1 = incomplete or error).
    """
    try:
        result = validate_spec_file(spec_file)

        if format == "json":
            _output_validate_json(result)
        elif format == "jsonl":
            print(result.model_dump_json())
        else:
            _output_validate_human(result, spec_file)

        return 0 if result.is_complete else 1

    except FileNotFoundError as e:
        if format == "human":
            console.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1
    except ValueError as e:
        if format == "human":
            console.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1


def import_command(
    spec_file: Path,
    output_dir: Path | None = None,
    format: str = "human",
) -> int:
    """Import a validated spec into the pipeline.

    Validates the spec first, then copies it to the output directory.

    Args:
        spec_file: Path to the spec JSON file.
        output_dir: Directory to import into (default: .imp/specs/).
        format: Output format: "human", "json", or "jsonl".

    Returns:
        Exit code (0 = imported, 1 = validation failed or error).
    """
    try:
        # Validate first
        result = validate_spec_file(spec_file)

        if not result.is_complete:
            if format == "human":
                console.print(
                    f"[red]Error:[/red] Spec is not complete enough to import "
                    f"(score: {result.score}/100, needs 80+)"
                )
                console.print("[yellow]Run `imp interview validate` to see gaps.[/yellow]")
            else:
                print(
                    json.dumps(
                        {
                            "error": "Spec not complete enough to import",
                            "score": result.score,
                            "threshold": 80,
                        }
                    )
                )
            return 1

        # Determine output directory
        target_dir = output_dir if output_dir else Path.cwd() / ".imp" / "specs"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy spec file
        target_path = target_dir / spec_file.name
        shutil.copy2(spec_file, target_path)

        if format == "human":
            console.print(
                Panel(
                    f"[green]✓ Spec imported successfully[/green]\n"
                    f"Score: {result.score}/100\n"
                    f"Location: {target_path}",
                    title="Import Result",
                    border_style="green",
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "imported": True,
                        "score": result.score,
                        "path": str(target_path),
                    }
                )
            )

        return 0

    except FileNotFoundError as e:
        if format == "human":
            console.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1
    except ValueError as e:
        if format == "human":
            console.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1


def _output_validate_json(result: CompletenessResult) -> None:
    """Output validation result as JSON."""
    print(result.model_dump_json(indent=2))


def _output_validate_human(result: CompletenessResult, spec_file: Path) -> None:
    """Output validation result in human-readable format."""
    # Header with score
    if result.is_complete:
        console.print(
            Panel(
                f"[green]✓ Spec is complete ({result.score}/100)[/green]",
                title=f"Spec Validation: {spec_file.name}",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]✗ Spec is incomplete ({result.score}/100, needs 80+)[/red]",
                title=f"Spec Validation: {spec_file.name}",
                border_style="red",
            )
        )

    # Gaps table
    if result.gap_count > 0:
        console.print(f"\n[bold]Found {result.gap_count} gap(s):[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Field", style="cyan")
        table.add_column("Severity", justify="center")
        table.add_column("Description")

        for gap in result.gaps:
            severity_style = (
                "red bold"
                if gap.severity == GapSeverity.CRITICAL
                else "yellow"
                if gap.severity == GapSeverity.IMPORTANT
                else "dim"
            )
            table.add_row(
                gap.field,
                f"[{severity_style}]{gap.severity.value}[/{severity_style}]",
                gap.description,
            )

        console.print(table)

        # Suggested questions for critical/important gaps
        important_gaps = [
            g for g in result.gaps if g.severity in (GapSeverity.CRITICAL, GapSeverity.IMPORTANT)
        ]
        if important_gaps:
            console.print("\n[bold]Suggested questions to fill gaps:[/bold]")
            for gap in important_gaps:
                if gap.suggested_questions:  # pragma: no branch
                    console.print(f"\n  [cyan]{gap.field}:[/cyan]")
                    for q in gap.suggested_questions:
                        console.print(f"    → {q}")
    else:
        console.print("\n[green]No gaps found. Spec is fully complete![/green]")

    # Suggestions (validator always generates at least one)
    if result.suggestions:  # pragma: no branch
        console.print()
        for suggestion in result.suggestions:
            console.print(f"[dim]💡 {suggestion}[/dim]")
