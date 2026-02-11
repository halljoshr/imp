"""Tests for ValidationRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.validation.detector import ProjectType, ToolchainConfig
from imp.validation.models import GateResult, GateType, ValidationResult
from imp.validation.runner import ValidationRunner


class TestValidationRunner:
    """Test ValidationRunner class."""

    def test_creation_with_auto_detect(self, tmp_path: Path) -> None:
        """Can create ValidationRunner with auto-detection."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        runner = ValidationRunner(project_root=tmp_path)
        assert runner.project_root == tmp_path
        assert runner.toolchain is not None
        assert runner.toolchain.project_type == ProjectType.PYTHON

    def test_creation_with_explicit_toolchain(self, tmp_path: Path) -> None:
        """Can create ValidationRunner with explicit toolchain config."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        assert runner.toolchain == toolchain

    def test_available_gates(self, tmp_path: Path) -> None:
        """available_gates returns gates from toolchain."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        gates = runner.available_gates()
        assert "test" in gates
        assert "lint" in gates
        assert "type" in gates
        assert "format" not in gates  # Not configured

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_single_gate(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Can run single validation gate."""
        mock_run.return_value = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="Tests passed",
            command="pytest",
            duration_ms=1000,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_gate(GateType.TEST)

        assert result.gate_type == GateType.TEST
        assert result.passed is True
        mock_run.assert_called_once()

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_all_gates(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Can run all available validation gates."""
        # Mock will be called multiple times, return success each time
        mock_run.return_value = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="Passed",
            command="test",
            duration_ms=500,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        assert isinstance(result, ValidationResult)
        assert len(result.gates) == 3  # test, lint, type
        assert result.passed is True
        assert mock_run.call_count == 3

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_all_with_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """run_all detects failures and returns failed result."""

        def side_effect(*args: object, **kwargs: object) -> GateResult:
            # First call (test) passes, second call (lint) fails
            if mock_run.call_count == 1:
                return GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                )
            else:
                return GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Lint errors",
                    command="ruff check",
                    duration_ms=500,
                )

        mock_run.side_effect = side_effect

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        assert result.passed is False
        assert len(result.gates) == 2
        assert len(result.failed_gates) == 1
        assert result.failed_gates[0].gate_type == GateType.LINT

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_specific_gates(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Can run specific subset of gates."""
        mock_run.return_value = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="Passed",
            command="test",
            duration_ms=500,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_gates([GateType.TEST, GateType.TYPE])

        assert len(result.gates) == 2
        assert mock_run.call_count == 2

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_with_fix_mode(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Can run gates in fix mode."""
        # First run finds issues
        mock_run.return_value = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check",
            duration_ms=500,
            fixable=True,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            lint_command="ruff check",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_with_fix([GateType.LINT])

        # Should attempt fix for fixable gates
        assert len(result.gates) >= 1
        # Implementation should run fix command then re-validate

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_gate_not_available(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Running unavailable gate raises error or returns failed result."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            # No security command configured
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        # Should either raise ValueError or return failed GateResult
        with pytest.raises(ValueError):
            runner.run_gate(GateType.SECURITY)

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_calculates_total_duration(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """run_all calculates total duration correctly."""

        def side_effect(*args: object, **kwargs: object) -> GateResult:
            durations = [1000, 500, 800]
            idx = mock_run.call_count - 1
            return GateResult(
                gate_type=GateType.TEST,
                passed=True,
                message="Passed",
                command="test",
                duration_ms=durations[idx],
            )

        mock_run.side_effect = side_effect

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        assert result.total_duration_ms == 2300  # 1000 + 500 + 800

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_empty_gate_list(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Running empty gate list returns empty result."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            # No commands configured
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        assert len(result.gates) == 0
        assert result.passed is True  # No failures = pass
        assert result.total_duration_ms == 0

    @patch("imp.validation.gates.GateRunner.run")
    def test_run_parallel_mode(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Can run gates in parallel mode for speed."""
        mock_run.return_value = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="Passed",
            command="test",
            duration_ms=1000,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all(parallel=True)

        assert len(result.gates) == 3
        # In parallel mode, should still run all gates

    def test_get_fix_command(self, tmp_path: Path) -> None:
        """Can get fix command for fixable gate types."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            lint_command="ruff check",
            format_command="ruff format",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        # Lint gate: ruff check -> ruff check --fix
        lint_fix = runner.get_fix_command(GateType.LINT)
        assert "ruff check" in lint_fix
        assert "--fix" in lint_fix

        # Format gate: ruff format --check -> ruff format
        format_fix = runner.get_fix_command(GateType.FORMAT)
        assert "ruff format" in format_fix
        assert "--check" not in format_fix

    def test_get_fix_command_not_fixable(self, tmp_path: Path) -> None:
        """get_fix_command returns None for non-fixable gates."""
        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        # Type checking is not auto-fixable
        fix_cmd = runner.get_fix_command(GateType.TYPE)
        assert fix_cmd is None


class TestValidationRunnerEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_project_root(self) -> None:
        """Creating runner with nonexistent path handles gracefully."""
        runner = ValidationRunner(project_root=Path("/nonexistent/path"))
        assert runner.toolchain.project_type == ProjectType.UNKNOWN

    @patch("imp.validation.gates.GateRunner.run")
    def test_gate_timeout_handling(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Runner handles gate timeouts gracefully."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("pytest", 60)

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        # Should have failed result for timeout
        assert result.passed is False
        assert len(result.gates) >= 1

    @patch("imp.validation.gates.GateRunner.run")
    def test_multiple_failures(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Runner handles multiple gate failures."""
        mock_run.return_value = GateResult(
            gate_type=GateType.TEST,
            passed=False,
            message="Failed",
            command="test",
            duration_ms=100,
        )

        toolchain = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )

        runner = ValidationRunner(
            project_root=tmp_path,
            toolchain=toolchain,
        )

        result = runner.run_all()

        assert result.passed is False
        assert len(result.failed_gates) == 3  # All gates failed
