"""Imp CLI application."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

import typer
from rich import print as rprint

import imp as imp_pkg

if TYPE_CHECKING:
    from imp.context.summarizer import InvokeFn


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
    from dotenv import load_dotenv

    load_dotenv()


def _not_implemented(name: str) -> None:
    rprint(f"[yellow]imp {name}[/yellow] is not implemented yet.")
    raise typer.Exit(1)


# --- Subcommand groups ---


@app.command("init")
def init(
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    summarize: Annotated[
        bool,
        typer.Option("--summarize", help="Run AI summarization (L3) on modules"),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="AI model for summarization"),
    ] = None,
) -> None:
    """Initialize project indexes for context-efficient navigation."""
    from pathlib import Path

    from imp.context.cli import init_command

    root = Path(project_root) if project_root else Path.cwd()

    # Build invoke_fn from model if summarize is requested
    invoke_fn = None
    if summarize and model:
        invoke_fn = _build_invoke_fn(model)

    exit_code = init_command(
        root=root,
        format=format.value,
        summarize=summarize,
        model=model,
        invoke_fn=invoke_fn,
    )
    raise typer.Exit(exit_code)


def _build_invoke_fn(model: str) -> InvokeFn:
    """Build an InvokeFn from model string using PydanticAIProvider.

    Args:
        model: Model string (e.g., "anthropic:claude-haiku-4-5")

    Returns:
        Async callable: prompt -> (purpose_string, TokenUsage)
    """
    from typing import cast

    from pydantic_ai.models import KnownModelName

    from imp.providers.pydantic_ai import PydanticAIProvider
    from imp.types import TokenUsage

    provider: PydanticAIProvider[str, None] = PydanticAIProvider(
        model=cast(KnownModelName, model),
        output_type=str,
        system_prompt="You are a concise code summarizer. Respond with 2-3 sentences only.",
    )

    async def invoke_fn(prompt: str) -> tuple[str, TokenUsage]:
        result = await provider.invoke(prompt)
        return result.output, result.usage

    return invoke_fn


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
    force: Annotated[
        bool,
        typer.Option("--force", help="Force re-creation even if already planned"),
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
    """Generate PM tickets from an interview spec."""
    from pathlib import Path

    from imp.pm.cli import plan_command

    root = Path(project_root) if project_root else Path.cwd()
    exit_code = plan_command(
        spec_file=Path(spec_file),
        provider=provider,
        create_parent=parent,
        default_priority=priority,
        format=format.value,
        project_root=root,
        force=force,
    )
    raise typer.Exit(exit_code)


code_app = typer.Typer(help="Managed code execution sessions.")
app.add_typer(code_app, name="code")


@code_app.callback(invoke_without_command=True)
def code(ctx: typer.Context) -> None:
    """Managed code execution: start, done, list, clean sessions."""
    if ctx.invoked_subcommand is None:
        rprint(
            "Use [bold]imp code start[/bold], [bold]done[/bold],"
            " [bold]list[/bold], or [bold]clean[/bold]."
        )
        rprint("Run [bold]imp code --help[/bold] for details.")
        raise typer.Exit(0)


@code_app.command("start")
def code_start(
    ticket_id: Annotated[
        str,
        typer.Argument(help="Ticket ID (e.g. IMP-5)"),
    ],
    title: Annotated[
        str,
        typer.Argument(help="Ticket title"),
    ],
    description: Annotated[
        str,
        typer.Option("--description", "-d", help="Ticket description"),
    ] = "",
    base_branch: Annotated[
        str,
        typer.Option("--base-branch", "-b", help="Base branch for the worktree"),
    ] = "main",
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Start a new managed executor session for a ticket."""
    from pathlib import Path

    from imp.executor.cli import start_command

    root = Path(project_root) if project_root else None
    exit_code = start_command(
        ticket_id=ticket_id,
        title=title,
        description=description,
        base_branch=base_branch,
        project_root=root,
    )
    raise typer.Exit(exit_code)


@code_app.command("done")
def code_done(
    ticket_id: Annotated[
        str,
        typer.Argument(help="Ticket ID to complete"),
    ],
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Run the completion pipeline for a ticket session."""
    from pathlib import Path

    from imp.executor.cli import done_command

    root = Path(project_root) if project_root else None
    exit_code = done_command(ticket_id=ticket_id, project_root=root)
    raise typer.Exit(exit_code)


@code_app.command("list")
def code_list(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """List all executor sessions."""
    from pathlib import Path

    from imp.executor.cli import list_command

    root = Path(project_root) if project_root else None
    exit_code = list_command(project_root=root, format=format.value)
    raise typer.Exit(exit_code)


@code_app.command("clean")
def code_clean(
    force: Annotated[
        bool,
        typer.Option("--force", help="Also remove active sessions"),
    ] = False,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Remove completed and escalated session worktrees."""
    from pathlib import Path

    from imp.executor.cli import clean_command

    root = Path(project_root) if project_root else None
    exit_code = clean_command(force=force, project_root=root)
    raise typer.Exit(exit_code)


metrics_app = typer.Typer(help="View and manage metrics.")
app.add_typer(metrics_app, name="metrics")


@metrics_app.callback(invoke_without_command=True)
def metrics(
    ctx: typer.Context,
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Filter by ticket ID"),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Filter by agent role"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Filter by model name"),
    ] = None,
    session: Annotated[
        str | None,
        typer.Option("--session", "-s", help="Filter by session ID"),
    ] = None,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to show"),
    ] = 7,
    date_range: Annotated[
        str | None,
        typer.Option("--range", "-r", help="Date range (YYYY-MM-DD:YYYY-MM-DD)"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """View metrics dashboard."""
    if ctx.invoked_subcommand is not None:
        return

    from pathlib import Path

    from imp.cli.metrics_cli import metrics_command

    root = Path(project_root) if project_root else Path.cwd()
    exit_code = metrics_command(
        ticket=ticket,
        agent=agent,
        model=model,
        session=session,
        days=days,
        date_range=date_range,
        output_format=format.value,
        project_root=root,
    )
    raise typer.Exit(exit_code)


@metrics_app.command("export")
def metrics_export(
    ticket_id: Annotated[
        str,
        typer.Argument(help="Ticket ID to export metrics for"),
    ],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Export metrics summary to a PM ticket."""
    from pathlib import Path

    from imp.cli.metrics_cli import export_command

    root = Path(project_root) if project_root else Path.cwd()
    exit_code = export_command(
        ticket_id=ticket_id,
        output_format=format.value,
        project_root=root,
    )
    raise typer.Exit(exit_code)


@metrics_app.command("migrate")
def metrics_migrate(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.human,
    project_root: Annotated[
        str | None,
        typer.Option("--project-root", "-p", help="Project root directory"),
    ] = None,
) -> None:
    """Migrate JSONL metrics to SQLite."""
    from pathlib import Path

    from imp.cli.metrics_cli import migrate_command

    root = Path(project_root) if project_root else Path.cwd()
    exit_code = migrate_command(
        output_format=format.value,
        project_root=root,
    )
    raise typer.Exit(exit_code)
