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


interview_app = typer.Typer(help="Run the interview agent.")
app.add_typer(interview_app, name="interview")


@interview_app.callback(invoke_without_command=True)
def interview() -> None:
    _not_implemented("interview")


review_app = typer.Typer(help="Run code review.")
app.add_typer(review_app, name="review")


@review_app.callback(invoke_without_command=True)
def review() -> None:
    _not_implemented("review")


metrics_app = typer.Typer(help="View and manage metrics.")
app.add_typer(metrics_app, name="metrics")


@metrics_app.callback(invoke_without_command=True)
def metrics() -> None:
    _not_implemented("metrics")
