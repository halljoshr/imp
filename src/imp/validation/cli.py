"""CLI commands for validation."""

import json
from pathlib import Path

import rich

from imp.validation.models import GateType, ValidationResult
from imp.validation.runner import ValidationRunner


def check_command(
    project_root: Path,
    gates: list[str] | None = None,
    fix: bool = False,
    format: str = "human",
) -> int:
    """Run validation checks on a project.

    Args:
        project_root: Root directory of the project
        gates: Optional list of specific gates to run (all if None)
        fix: If True, attempt to auto-fix issues
        format: Output format: "human", "json", or "jsonl"

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        # Validate project root exists
        if not project_root.exists():
            if format == "human":
                rich.print(f"[red]Error:[/red] Project root does not exist: {project_root}")
            else:
                print(json.dumps({"error": f"Project root does not exist: {project_root}"}))
            return 1

        # Parse gate types if specified
        gate_types = None
        if gates:
            try:
                gate_types = [GateType(gate) for gate in gates]
            except ValueError as e:
                if format == "human":
                    rich.print(f"[red]Error:[/red] Invalid gate name: {e}")
                else:
                    print(json.dumps({"error": f"Invalid gate name: {e}"}))
                return 1

        # Create runner
        runner = ValidationRunner(project_root=project_root)

        # Run validation
        if fix:
            result = runner.run_with_fix(gate_types)
        elif gate_types:
            result = runner.run_gates(gate_types)
        else:
            result = runner.run_all()

        # Output results
        _output_result(result, format)

        # Return exit code
        return 0 if result.passed else 1

    except Exception as e:
        if format == "human":
            rich.print(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1


def _output_result(result: ValidationResult, format: str) -> None:
    """Output validation result in specified format.

    Args:
        result: ValidationResult to output
        format: Output format ("human", "json", or "jsonl")
    """
    if format == "json":
        print(json.dumps(result.model_dump(), indent=2))

    elif format == "jsonl":
        # Output one JSON object per gate
        for gate in result.gates:
            print(json.dumps(gate.model_dump()))

        # Output summary
        summary = {
            "passed": result.passed,
            "total_duration_ms": result.total_duration_ms,
            "total_gates": len(result.gates),
        }
        print(json.dumps(summary))

    else:  # human
        # Header
        if result.passed:
            rich.print("\n[green]✓ All validation checks passed[/green]\n")
        else:
            rich.print("\n[red]✗ Validation checks failed[/red]\n")

        # Gate results
        for gate in result.gates:
            status = "[green]✓[/green]" if gate.passed else "[red]✗[/red]"
            duration_s = gate.duration_ms / 1000

            rich.print(f"{status} {gate.gate_type}: {gate.message} ({duration_s:.2f}s)")

            # Show fixable hint for failed gates
            if not gate.passed and gate.fixable:
                rich.print("  [yellow]→ Can be auto-fixed with --fix[/yellow]")

        # Summary
        total_s = result.total_duration_ms / 1000
        rich.print(f"\n[dim]Total: {len(result.gates)} gates in {total_s:.2f}s[/dim]")

        # Fixable summary
        if result.fixable_gates:
            count = len(result.fixable_gates)
            rich.print(f"[yellow]{count} issues can be fixed with: imp check --fix[/yellow]")

        rich.print("")
