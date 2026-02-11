"""Gate runners for executing validation commands."""

import subprocess
import time
from pathlib import Path

from imp.validation.models import GateResult, GateType


class GateRunner:
    """Runs a validation gate and captures results."""

    def __init__(
        self,
        gate_type: GateType,
        command: str,
        cwd: Path,
        timeout_seconds: int = 300,
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialize gate runner.

        Args:
            gate_type: Type of validation gate
            command: Command to execute
            cwd: Working directory for command execution
            timeout_seconds: Command timeout in seconds (default: 300)
            env: Optional environment variables
        """
        self.gate_type = gate_type
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self.env = env

    def run(self) -> GateResult:
        """Execute the gate and return result.

        Returns:
            GateResult with execution outcome
        """
        start_time = time.time()

        try:
            # Prepare environment
            import os

            run_env = os.environ.copy()
            if self.env:
                run_env.update(self.env)

            # Execute command
            result = subprocess.run(
                self.command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=run_env,
            )

            duration_ms = max(1, int((time.time() - start_time) * 1000))

            # Determine if passed
            passed = result.returncode == 0

            # Determine if fixable based on command and output
            fixable = self._is_fixable(result.stdout, result.stderr)

            # Generate message - use stderr or stdout if available
            if passed:
                message = result.stdout.strip() if result.stdout else f"{self.gate_type} passed"
            else:
                # Use stderr if present, otherwise stdout, otherwise generic message
                if result.stderr.strip():
                    message = result.stderr.strip()
                elif result.stdout.strip():
                    message = result.stdout.strip()
                else:
                    message = f"{self.gate_type} failed"

            return GateResult(
                gate_type=self.gate_type,
                passed=passed,
                message=message,
                command=self.command,
                duration_ms=duration_ms,
                fixable=fixable,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        except subprocess.TimeoutExpired:
            duration_ms = max(
                int((time.time() - start_time) * 1000), int(self.timeout_seconds * 1000)
            )
            return GateResult(
                gate_type=self.gate_type,
                passed=False,
                message=f"{self.gate_type} timeout after {self.timeout_seconds}s",
                command=self.command,
                duration_ms=duration_ms,
                fixable=False,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return GateResult(
                gate_type=self.gate_type,
                passed=False,
                message=f"{self.gate_type} error: {e}",
                command=self.command,
                duration_ms=duration_ms,
                fixable=False,
            )

    def _is_fixable(self, stdout: str, stderr: str) -> bool:
        """Determine if gate issues are automatically fixable.

        Args:
            stdout: Command standard output
            stderr: Command standard error

        Returns:
            True if issues can be auto-fixed
        """
        output = (stdout + stderr).lower()

        # Ruff check/format are fixable
        if "ruff check" in self.command.lower():
            return True
        if "ruff format" in self.command.lower() and "--check" in self.command.lower():
            return True

        # Prettier is fixable
        if "prettier" in self.command.lower() and "--check" in self.command.lower():
            return True

        # ESLint is partially fixable
        if "eslint" in self.command.lower() and ("fixable" in output or "--fix" in output):
            return True

        # Type checking is generally not auto-fixable
        if self.gate_type == GateType.TYPE:
            return False

        # Tests are not auto-fixable
        if self.gate_type == GateType.TEST:
            return False

        # Default to False for unknown commands
        return False


def run_gate(
    gate_type: GateType,
    command: str,
    cwd: Path,
    timeout_seconds: int = 300,
    env: dict[str, str] | None = None,
) -> GateResult:
    """Helper function to run a gate.

    Args:
        gate_type: Type of validation gate
        command: Command to execute
        cwd: Working directory
        timeout_seconds: Command timeout in seconds
        env: Optional environment variables

    Returns:
        GateResult from gate execution
    """
    runner = GateRunner(
        gate_type=gate_type,
        command=command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    return runner.run()
