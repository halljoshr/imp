"""Auto-fix functionality for validation gates."""

import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from imp.validation.models import GateResult, GateType


class FixResult(BaseModel):
    """Result from attempting to auto-fix a gate."""

    success: bool
    gate_type: GateType
    fix_command: str | None
    message: str
    duration_ms: int
    stdout: str | None = None
    stderr: str | None = None

    model_config = ConfigDict(frozen=True)


def get_fix_command(gate: GateResult) -> str | None:
    """Get fix command for a gate result.

    Args:
        gate: Gate result to get fix command for

    Returns:
        Fix command string or None if not fixable
    """
    # Can't fix if already passing or not marked as fixable
    if gate.passed:
        return None

    if not gate.fixable:
        return None

    command = gate.command

    # Transform check commands to fix commands
    if "ruff check" in command:
        if "--fix" not in command:
            return command + " --fix"
        return command

    if "ruff format" in command and "--check" in command:
        return command.replace(" --check", "")

    if "prettier" in command and "--check" in command:
        return command.replace("--check", "--write")

    if "eslint" in command:
        if "--fix" not in command:
            return command + " --fix"
        return command

    # Unknown or non-fixable command
    return None


def apply_fix(
    gate: GateResult,
    cwd: Path,
    timeout_seconds: int = 300,
) -> FixResult:
    """Apply auto-fix to a gate result.

    Args:
        gate: Gate result to fix
        cwd: Working directory for command execution
        timeout_seconds: Command timeout in seconds

    Returns:
        FixResult with fix outcome
    """
    # Check if gate needs fixing
    if gate.passed:
        return FixResult(
            success=True,
            gate_type=gate.gate_type,
            fix_command=None,
            message="No fix needed - gate already passing",
            duration_ms=0,
        )

    # Check if gate is fixable
    if not gate.fixable:
        return FixResult(
            success=False,
            gate_type=gate.gate_type,
            fix_command=None,
            message=f"{gate.gate_type} is not fixable",
            duration_ms=0,
        )

    # Get fix command
    fix_command = get_fix_command(gate)

    if not fix_command:
        return FixResult(
            success=False,
            gate_type=gate.gate_type,
            fix_command=None,
            message=f"No fix command available for {gate.gate_type}",
            duration_ms=0,
        )

    # Execute fix command
    start_time = time.time()

    try:
        result = subprocess.run(
            fix_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        duration_ms = max(1, int((time.time() - start_time) * 1000))

        # Success if return code is 0
        success = result.returncode == 0

        if success:
            message = f"Successfully fixed {gate.gate_type}"
        else:
            message = f"Fix command failed for {gate.gate_type}"

        return FixResult(
            success=success,
            gate_type=gate.gate_type,
            fix_command=fix_command,
            message=message,
            duration_ms=duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    except subprocess.TimeoutExpired:
        duration_ms = max(int((time.time() - start_time) * 1000), int(timeout_seconds * 1000))
        return FixResult(
            success=False,
            gate_type=gate.gate_type,
            fix_command=fix_command,
            message=f"Fix command timeout after {timeout_seconds}s",
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return FixResult(
            success=False,
            gate_type=gate.gate_type,
            fix_command=fix_command,
            message=f"Error running fix command: {e}",
            duration_ms=duration_ms,
        )
