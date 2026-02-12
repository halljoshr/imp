"""CLI commands for code review."""

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from imp.providers.pydantic_ai import PydanticAIProvider
from imp.review.models import ReviewResult, ReviewSeverity
from imp.review.runner import ReviewRunner

console = Console()


def review_command(
    project_root: Path,
    changed_files: list[str] | None = None,
    provider: str = "anthropic",
    model: str = "claude-opus-4-6",
    format: str = "human",
) -> int:
    """Run code review on a project.

    Args:
        project_root: Root directory of the project
        changed_files: Optional list of files to review (all if None)
        provider: AI provider to use (default: anthropic)
        model: AI model to use (default: claude-opus-4-6)
        format: Output format: "human", "json", or "jsonl"

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        # Validate project root exists
        if not project_root.exists():
            if format == "human":
                console.print(f"[red]Error:[/red] Project root does not exist: {project_root}")
            else:
                print(json.dumps({"error": f"Project root does not exist: {project_root}"}))
            return 1

        # Create AI provider with review system prompt
        from typing import cast

        from pydantic_ai.models import KnownModelName

        from imp.review.prompts import get_system_prompt

        model_str = f"{provider}:{model}"
        ai_provider: PydanticAIProvider[ReviewResult, None] = PydanticAIProvider(
            model=cast(KnownModelName, model_str),
            output_type=ReviewResult,
            system_prompt=get_system_prompt(),
        )

        # Create runner
        runner = ReviewRunner(
            project_root=project_root,
            provider=ai_provider,
        )

        # Run review
        files = changed_files or []
        result = asyncio.run(runner.run_full_review(changed_files=files))

        # Output result
        if format == "json":
            _output_json(result)
        elif format == "jsonl":
            _output_jsonl(result)
        else:
            _output_human(result)

        return 0 if result.passed else 1

    except KeyboardInterrupt:
        if format == "human":
            console.print("\n[yellow]Review cancelled by user[/yellow]")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        if format == "human":
            console.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1


def _output_json(result: ReviewResult) -> None:
    """Output result as JSON."""
    print(result.model_dump_json(indent=2))


def _output_jsonl(result: ReviewResult) -> None:
    """Output result as JSONL."""
    print(result.model_dump_json())


def _output_human(result: ReviewResult) -> None:
    """Output result in human-readable format."""
    # Header
    if result.passed:
        console.print(
            Panel(
                "[green]✓ Review passed[/green]",
                title="Code Review Result",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[red]✗ Review failed[/red]",
                title="Code Review Result",
                border_style="red",
            )
        )

    # Validation status
    if result.validation_passed:
        console.print("✓ [green]Automated validation passed[/green]")
    else:
        console.print("✗ [red]Automated validation failed[/red]")
        console.print("[yellow]→ Run `imp check --fix` to auto-fix validation issues[/yellow]")

    # Issue summary
    if result.total_issues > 0:
        console.print(f"\n[bold]Found {result.total_issues} issue(s):[/bold]")
        console.print(
            f"  • {result.high_severity_count} HIGH severity"
            + (" [red](blocking)[/red]" if result.high_severity_count > 0 else "")
        )
        console.print(f"  • {result.medium_severity_count} MEDIUM severity")
        console.print(f"  • {result.low_severity_count} LOW severity")

        # Issues table
        table = Table(show_header=True, header_style="bold")
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right", style="magenta")
        table.add_column("Severity", justify="center")
        table.add_column("Category", style="yellow")
        table.add_column("Message")

        for issue in result.issues:
            severity_style = (
                "red bold"
                if issue.severity == ReviewSeverity.HIGH
                else "yellow"
                if issue.severity == ReviewSeverity.MEDIUM
                else "dim"
            )
            table.add_row(
                issue.path,
                str(issue.line),
                f"[{severity_style}]{issue.severity.value}[/{severity_style}]",
                issue.category.value,
                issue.message,
            )

        console.print()
        console.print(table)

        # Suggested fixes
        if result.high_severity_count > 0:
            console.print("\n[bold red]High-severity issues must be fixed:[/bold red]")
            for issue in [i for i in result.issues if i.severity == ReviewSeverity.HIGH]:
                console.print(f"\n[cyan]{issue.path}:{issue.line}[/cyan]")
                console.print(f"  [red]✗[/red] {issue.message}")
                console.print(f"  [green]✓[/green] {issue.suggested_fix}")

    else:
        console.print("\n[green]No issues found. Code looks good![/green]")

    # Duration
    console.print(f"\n[dim]Review completed in {result.duration_ms / 1000:.2f}s[/dim]")
    if result.model:
        console.print(f"[dim]Model: {result.model}[/dim]")
