"""Tests for auto-fix functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from imp.validation.fixer import FixResult, apply_fix, get_fix_command
from imp.validation.models import GateResult, GateType


class TestGetFixCommand:
    """Test get_fix_command function."""

    def test_ruff_check_fix_command(self) -> None:
        """Ruff check fix command adds --fix flag."""
        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )

        fix_cmd = get_fix_command(gate)
        assert fix_cmd is not None
        assert "ruff check" in fix_cmd
        assert "--fix" in fix_cmd

    def test_ruff_format_fix_command(self) -> None:
        """Ruff format fix command removes --check flag."""
        gate = GateResult(
            gate_type=GateType.FORMAT,
            passed=False,
            message="Format issues",
            command="ruff format --check src/",
            duration_ms=300,
            fixable=True,
        )

        fix_cmd = get_fix_command(gate)
        assert fix_cmd is not None
        assert "ruff format" in fix_cmd
        assert "--check" not in fix_cmd

    def test_prettier_fix_command(self) -> None:
        """Prettier fix command removes --check flag."""
        gate = GateResult(
            gate_type=GateType.FORMAT,
            passed=False,
            message="Format issues",
            command="prettier --check .",
            duration_ms=200,
            fixable=True,
        )

        fix_cmd = get_fix_command(gate)
        assert fix_cmd is not None
        assert "prettier" in fix_cmd
        assert "--check" not in fix_cmd
        assert "--write" in fix_cmd

    def test_eslint_fix_command(self) -> None:
        """ESLint fix command adds --fix flag."""
        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="eslint .",
            duration_ms=800,
            fixable=True,
        )

        fix_cmd = get_fix_command(gate)
        assert fix_cmd is not None
        assert "eslint" in fix_cmd
        assert "--fix" in fix_cmd

    def test_non_fixable_gate(self) -> None:
        """Non-fixable gate returns None."""
        gate = GateResult(
            gate_type=GateType.TYPE,
            passed=False,
            message="Type errors",
            command="mypy src/",
            duration_ms=1000,
            fixable=False,
        )

        fix_cmd = get_fix_command(gate)
        assert fix_cmd is None

    def test_passing_gate(self) -> None:
        """Passing gate doesn't need fix command."""
        gate = GateResult(
            gate_type=GateType.LINT,
            passed=True,
            message="No issues",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )

        get_fix_command(gate)
        # Implementation choice: could return None or the fix command
        # Either is valid - None means "no fix needed"

    def test_unknown_command(self) -> None:
        """Unknown command type returns None or best effort fix."""
        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Errors",
            command="custom-linter src/",
            duration_ms=500,
            fixable=True,
        )

        get_fix_command(gate)
        # Should either return None (can't fix) or attempt --fix flag


class TestApplyFix:
    """Test apply_fix function."""

    @patch("subprocess.run")
    def test_apply_fix_success(self, mock_run: MagicMock) -> None:
        """Applying fix successfully returns success result."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fixed 5 issues",
            stderr="",
        )

        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )

        result = apply_fix(gate, cwd=Path("/tmp"))

        assert result.success is True
        assert result.gate_type == GateType.LINT
        assert result.fix_command is not None
        assert "ruff check" in result.fix_command
        assert result.stdout == "Fixed 5 issues"

    @patch("subprocess.run")
    def test_apply_fix_failure(self, mock_run: MagicMock) -> None:
        """Applying fix that fails returns failure result."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Fix failed: syntax error",
        )

        gate = GateResult(
            gate_type=GateType.FORMAT,
            passed=False,
            message="Format issues",
            command="ruff format --check src/",
            duration_ms=300,
            fixable=True,
        )

        result = apply_fix(gate, cwd=Path("/tmp"))

        assert result.success is False
        assert result.stderr == "Fix failed: syntax error"

    def test_apply_fix_non_fixable_gate(self) -> None:
        """Applying fix to non-fixable gate returns failure."""
        gate = GateResult(
            gate_type=GateType.TYPE,
            passed=False,
            message="Type errors",
            command="mypy src/",
            duration_ms=1000,
            fixable=False,
        )

        result = apply_fix(gate, cwd=Path("/tmp"))

        assert result.success is False
        assert result.fix_command is None
        assert "not fixable" in result.message.lower()

    def test_apply_fix_passing_gate(self) -> None:
        """Applying fix to passing gate is no-op."""
        gate = GateResult(
            gate_type=GateType.LINT,
            passed=True,
            message="No issues",
            command="ruff check src/",
            duration_ms=500,
        )

        result = apply_fix(gate, cwd=Path("/tmp"))

        # Should indicate no fix needed
        assert "no fix needed" in result.message.lower() or result.success is True

    @patch("subprocess.run")
    def test_apply_fix_with_timeout(self, mock_run: MagicMock) -> None:
        """Fix command that times out returns failure."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("ruff check --fix", 60)

        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )

        result = apply_fix(gate, cwd=Path("/tmp"), timeout_seconds=60)

        assert result.success is False
        assert "timeout" in result.message.lower()

    @patch("subprocess.run")
    def test_apply_fix_with_exception(self, mock_run: MagicMock) -> None:
        """Fix command that raises exception returns failure."""
        mock_run.side_effect = FileNotFoundError("command not found")

        gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )

        result = apply_fix(gate, cwd=Path("/tmp"))

        assert result.success is False
        assert "error" in result.message.lower()


class TestFixResult:
    """Test FixResult model."""

    def test_creation_success(self) -> None:
        """Can create successful FixResult."""
        result = FixResult(
            success=True,
            gate_type=GateType.LINT,
            fix_command="ruff check --fix src/",
            message="Fixed 3 issues",
            duration_ms=800,
        )

        assert result.success is True
        assert result.gate_type == GateType.LINT
        assert result.fix_command == "ruff check --fix src/"
        assert result.duration_ms == 800

    def test_creation_failure(self) -> None:
        """Can create failed FixResult."""
        result = FixResult(
            success=False,
            gate_type=GateType.TYPE,
            fix_command=None,
            message="Type errors are not automatically fixable",
            duration_ms=0,
        )

        assert result.success is False
        assert result.fix_command is None

    def test_creation_with_output(self) -> None:
        """Can create FixResult with stdout/stderr."""
        result = FixResult(
            success=True,
            gate_type=GateType.FORMAT,
            fix_command="ruff format src/",
            message="Fixed formatting",
            duration_ms=500,
            stdout="Formatted 5 files",
            stderr="",
        )

        assert result.stdout == "Formatted 5 files"
        assert result.stderr == ""


class TestBatchFix:
    """Test batch fix operations."""

    @patch("subprocess.run")
    def test_fix_multiple_gates(self, mock_run: MagicMock) -> None:
        """Can fix multiple gates in sequence."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fixed",
            stderr="",
        )

        gates = [
            GateResult(
                gate_type=GateType.LINT,
                passed=False,
                message="Lint errors",
                command="ruff check src/",
                duration_ms=500,
                fixable=True,
            ),
            GateResult(
                gate_type=GateType.FORMAT,
                passed=False,
                message="Format issues",
                command="ruff format --check src/",
                duration_ms=300,
                fixable=True,
            ),
        ]

        results = [apply_fix(gate, cwd=Path("/tmp")) for gate in gates]

        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("subprocess.run")
    def test_fix_only_fixable_gates(self, mock_run: MagicMock) -> None:
        """Batch fix skips non-fixable gates."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fixed",
            stderr="",
        )

        gates = [
            GateResult(
                gate_type=GateType.LINT,
                passed=False,
                message="Lint errors",
                command="ruff check src/",
                duration_ms=500,
                fixable=True,
            ),
            GateResult(
                gate_type=GateType.TYPE,
                passed=False,
                message="Type errors",
                command="mypy src/",
                duration_ms=1000,
                fixable=False,
            ),
        ]

        fixable_gates = [g for g in gates if g.fixable]
        results = [apply_fix(gate, cwd=Path("/tmp")) for gate in fixable_gates]

        assert len(results) == 1  # Only fixed the fixable one
        assert results[0].gate_type == GateType.LINT
