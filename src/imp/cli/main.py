"""Imp CLI application."""

from enum import StrEnum
from typing import Annotated

import typer
from rich import print as rprint

import imp as imp_pkg


class OutputFormat(StrEnum):
    """Output format for CLI commands."""

    human = "human"
    json = "json"
    jsonl = "jsonl"


app = typer.Typer(
    name="imp",
    help="AI-powered engineering workflow framework.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        rprint(f"imp {imp_pkg.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.human,
) -> None:
    """Imp — AI-powered engineering workflow framework."""


def _not_implemented(name: str) -> None:
    rprint(f"[yellow]imp {name}[/yellow] is not implemented yet.")
    raise typer.Exit(1)


# --- Subcommand groups ---

init_app = typer.Typer(help="Initialize imp in a project.")
app.add_typer(init_app, name="init")


@init_app.callback(invoke_without_command=True)
def init() -> None:
    _not_implemented("init")


check_app = typer.Typer(help="Run validation checks.")
app.add_typer(check_app, name="check")


@check_app.callback(invoke_without_command=True)
def check(
    gates: Annotated[
        list[str] | None,
        typer.Option("--gates", "-g", help="Specific gates to run (all if not specified)"),
    ] = None,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to auto-fix issues"),
    ] = False,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Run validation checks on the project."""
    from pathlib import Path

    from imp.validation.cli import check_command

    # Determine project root
    root = Path(project_root) if project_root else Path.cwd()

    # Run validation
    exit_code = check_command(
        project_root=root,
        gates=gates,
        fix=fix,
        format=format.value,
    )

    raise typer.Exit(exit_code)


interview_app = typer.Typer(help="Interview spec validation and import.")
app.add_typer(interview_app, name="interview")


@interview_app.callback(invoke_without_command=True)
def interview(ctx: typer.Context) -> None:
    """Interview spec validation and import tools."""
    if ctx.invoked_subcommand is None:
        rprint("Use [bold]imp interview validate[/bold] or [bold]imp interview import[/bold].")
        rprint("Run [bold]imp interview --help[/bold] for details.")
        raise typer.Exit(0)


@interview_app.command("validate")
def interview_validate(
    spec_file: Annotated[
        str,
        typer.Argument(help="Path to the spec JSON file to validate"),
    ],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
) -> None:
    """Validate an interview spec file for completeness."""
    from pathlib import Path

    from imp.interview.cli import validate_command

    exit_code = validate_command(
        spec_file=Path(spec_file),
        format=format.value,
    )
    raise typer.Exit(exit_code)


@interview_app.command("import")
def interview_import(
    spec_file: Annotated[
        str,
        typer.Argument(help="Path to the spec JSON file to import"),
    ],
    output_dir: Annotated[
        str | None,
        typer.Option("--output-dir", "-o", help="Directory to import into"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
) -> None:
    """Import a validated spec into the pipeline."""
    from pathlib import Path

    from imp.interview.cli import import_command

    exit_code = import_command(
        spec_file=Path(spec_file),
        output_dir=Path(output_dir) if output_dir else None,
        format=format.value,
    )
    raise typer.Exit(exit_code)


review_app = typer.Typer(help="Run code review.")
app.add_typer(review_app, name="review")


@review_app.callback(invoke_without_command=True)
def review(
    files: Annotated[
        list[str] | None,
        typer.Argument(help="Files to review (all changed files if not specified)"),
    ] = None,
    provider: Annotated[
        str,
        typer.Option("--provider", help="AI provider (default: anthropic)"),
    ] = "anthropic",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="AI model (default: claude-opus-4-6)"),
    ] = "claude-opus-4-6",
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Run AI code review on the project."""
    from pathlib import Path

    from imp.review.cli import review_command

    # Determine project root
    root = Path(project_root) if project_root else Path.cwd()

    # Run review
    exit_code = review_command(
        project_root=root,
        changed_files=files,
        provider=provider,
        model=model,
        format=format.value,
    )

    raise typer.Exit(exit_code)


@app.command("plan")
def plan(
    spec_file: Annotated[
        str,
        typer.Argument(help="Path to the interview spec JSON file"),
    ],
    provider: Annotated[
        str,
        typer.Option("--provider", help="PM provider (default: plane)"),
    ] = "plane",
    parent: Annotated[
        bool,
        typer.Option("--parent/--no-parent", help="Create parent epic ticket"),
    ] = True,
    priority: Annotated[
        str,
        typer.Option("--priority", help="Default ticket priority"),
    ] = "medium",
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
) -> None:
    """Generate PM tickets from an interview spec."""
    from pathlib import Path

    from imp.pm.cli import plan_command

    exit_code = plan_command(
        spec_file=Path(spec_file),
        provider=provider,
        create_parent=parent,
        default_priority=priority,
        format=format.value,
    )
    raise typer.Exit(exit_code)


metrics_app = typer.Typer(help="View and manage metrics.")
app.add_typer(metrics_app, name="metrics")


@metrics_app.callback(invoke_without_command=True)
def metrics() -> None:
    _not_implemented("metrics")
