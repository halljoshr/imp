"""Validation runner for orchestrating multiple gates."""

import concurrent.futures
from pathlib import Path

from imp.validation.detector import ToolchainConfig, detect_toolchain
from imp.validation.gates import GateRunner
from imp.validation.models import GateResult, GateType, ValidationResult


class ValidationRunner:
    """Orchestrates validation gate execution."""

    def __init__(
        self,
        project_root: Path,
        toolchain: ToolchainConfig | None = None,
    ) -> None:
        """Initialize validation runner.

        Args:
            project_root: Root directory of the project
            toolchain: Optional explicit toolchain config (auto-detected if None)
        """
        self.project_root = project_root
        self.toolchain = toolchain or detect_toolchain(project_root)

    def available_gates(self) -> list[str]:
        """Get list of available validation gates.

        Returns:
            List of gate type strings
        """
        return self.toolchain.available_gates()

    def run_gate(self, gate_type: GateType) -> GateResult:
        """Run a single validation gate.

        Args:
            gate_type: Type of gate to run

        Returns:
            GateResult from execution

        Raises:
            ValueError: If gate type is not available
        """
        # Get command for gate type
        command = self._get_gate_command(gate_type)

        if not command:
            raise ValueError(f"Gate {gate_type} is not configured for this project")

        # Run gate
        runner = GateRunner(
            gate_type=gate_type,
            command=command,
            cwd=self.project_root,
        )

        try:
            return runner.run()
        except Exception as e:
            # Handle unexpected exceptions from gate runner
            from imp.validation.models import GateResult

            return GateResult(
                gate_type=gate_type,
                passed=False,
                message=f"{gate_type} error: {e}",
                command=command,
                duration_ms=0,
                fixable=False,
            )

    def run_all(self, parallel: bool = False) -> ValidationResult:
        """Run all available validation gates.

        Args:
            parallel: If True, run gates in parallel

        Returns:
            ValidationResult with all gate outcomes
        """
        available = self.available_gates()
        gate_types = [GateType(gate) for gate in available]

        if not gate_types:
            # No gates available
            return ValidationResult(
                passed=True,
                gates=[],
                total_duration_ms=0,
            )

        if parallel:
            return self._run_parallel(gate_types)
        else:
            return self._run_sequential(gate_types)

    def run_gates(self, gate_types: list[GateType]) -> ValidationResult:
        """Run specific validation gates.

        Args:
            gate_types: List of gate types to run

        Returns:
            ValidationResult with specified gate outcomes
        """
        return self._run_sequential(gate_types)

    def run_with_fix(self, gate_types: list[GateType] | None = None) -> ValidationResult:
        """Run gates, attempt auto-fix, then re-validate.

        Args:
            gate_types: Optional list of specific gates (all if None)

        Returns:
            ValidationResult after fix attempts
        """
        from imp.validation.fixer import apply_fix

        # Step 1: Run initial validation
        initial_result = self.run_gates(gate_types) if gate_types else self.run_all()

        # Step 2: Apply fixes to fixable gates
        for gate in initial_result.fixable_gates:
            apply_fix(gate, cwd=self.project_root)

        # Step 3: Re-run validation
        if gate_types:
            return self.run_gates(gate_types)
        else:
            return self.run_all()

    def get_fix_command(self, gate_type: GateType) -> str | None:
        """Get fix command for a gate type.

        Args:
            gate_type: Gate type to get fix command for

        Returns:
            Fix command string or None if not fixable
        """
        command = self._get_gate_command(gate_type)

        if not command:
            return None

        # Transform check command to fix command
        if "ruff check" in command:
            if "--fix" not in command:
                return command + " --fix"
            return command

        if "ruff format" in command:
            if "--check" in command:
                return command.replace(" --check", "")
            # Already a fix command
            return command

        if "prettier" in command and "--check" in command:
            return command.replace("--check", "--write")

        if "eslint" in command:
            if "--fix" not in command:
                return command + " --fix"
            return command

        # Type checking and tests are not auto-fixable
        if gate_type in (GateType.TYPE, GateType.TEST):
            return None

        return None

    def _get_gate_command(self, gate_type: GateType) -> str | None:
        """Get command for a gate type.

        Args:
            gate_type: Gate type

        Returns:
            Command string or None
        """
        if gate_type == GateType.TEST:
            return self.toolchain.test_command
        elif gate_type == GateType.LINT:
            return self.toolchain.lint_command
        elif gate_type == GateType.TYPE:
            return self.toolchain.type_command
        elif gate_type == GateType.FORMAT:
            return self.toolchain.format_command
        elif gate_type == GateType.SECURITY:
            return self.toolchain.security_command
        return None

    def _run_sequential(self, gate_types: list[GateType]) -> ValidationResult:
        """Run gates sequentially.

        Args:
            gate_types: List of gate types to run

        Returns:
            ValidationResult with all outcomes
        """
        results: list[GateResult] = []
        total_duration = 0

        for gate_type in gate_types:
            try:
                result = self.run_gate(gate_type)
                results.append(result)
                total_duration += result.duration_ms
            except ValueError:
                # Gate not available - skip
                continue

        # Determine overall pass/fail
        passed = all(r.passed for r in results)

        return ValidationResult(
            passed=passed,
            gates=results,
            total_duration_ms=total_duration,
        )

    def _run_parallel(self, gate_types: list[GateType]) -> ValidationResult:
        """Run gates in parallel.

        Args:
            gate_types: List of gate types to run

        Returns:
            ValidationResult with all outcomes
        """
        results: list[GateResult] = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all gates
            futures = []
            for gate_type in gate_types:
                command = self._get_gate_command(gate_type)
                if command:
                    runner = GateRunner(
                        gate_type=gate_type,
                        command=command,
                        cwd=self.project_root,
                    )
                    future = executor.submit(runner.run)
                    futures.append(future)

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception:
                    # Skip failed gate
                    continue

        # Calculate total duration (parallel, so use max not sum)
        total_duration = max((r.duration_ms for r in results), default=0)

        # Determine overall pass/fail
        passed = all(r.passed for r in results)

        return ValidationResult(
            passed=passed,
            gates=results,
            total_duration_ms=total_duration,
        )
