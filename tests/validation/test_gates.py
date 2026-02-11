"""Tests for validation gate runners."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from imp.validation.gates import GateRunner, run_gate
from imp.validation.models import GateType


class TestGateRunner:
    """Test GateRunner class."""

    def test_creation(self) -> None:
        """Can create GateRunner."""
        runner = GateRunner(
            gate_type=GateType.TEST,
            command="pytest tests/",
            cwd=Path("/tmp"),
        )
        assert runner.gate_type == GateType.TEST
        assert runner.command == "pytest tests/"
        assert runner.cwd == Path("/tmp")
        assert runner.timeout_seconds == 300  # Default
        assert runner.env is None  # Default

    def test_creation_with_custom_timeout(self) -> None:
        """Can create GateRunner with custom timeout."""
        runner = GateRunner(
            gate_type=GateType.LINT,
            command="ruff check",
            cwd=Path("/tmp"),
            timeout_seconds=60,
        )
        assert runner.timeout_seconds == 60

    def test_creation_with_env(self) -> None:
        """Can create GateRunner with environment variables."""
        env = {"CUSTOM_VAR": "value"}
        runner = GateRunner(
            gate_type=GateType.TYPE,
            command="mypy src/",
            cwd=Path("/tmp"),
            env=env,
        )
        assert runner.env == {"CUSTOM_VAR": "value"}

    @patch("subprocess.run")
    def test_run_success(self, mock_run: MagicMock) -> None:
        """Running successful gate returns passed result."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.TEST,
            command="pytest",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.gate_type == GateType.TEST
        assert result.passed is True
        assert result.command == "pytest"
        assert result.stdout == "All tests passed"
        assert result.stderr == ""
        assert result.duration_ms > 0

    @patch("subprocess.run")
    def test_run_failure(self, mock_run: MagicMock) -> None:
        """Running failed gate returns failed result."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="5 errors found",
        )

        runner = GateRunner(
            gate_type=GateType.LINT,
            command="ruff check",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.stderr == "5 errors found"

    @patch("subprocess.run")
    def test_run_with_timeout(self, mock_run: MagicMock) -> None:
        """Gate that times out returns failed result."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("pytest", 60)

        runner = GateRunner(
            gate_type=GateType.TEST,
            command="pytest",
            cwd=Path("/tmp"),
            timeout_seconds=60,
        )

        result = runner.run()

        assert result.passed is False
        assert "timeout" in result.message.lower()
        assert result.duration_ms >= 60000  # At least 60 seconds

    @patch("subprocess.run")
    def test_run_with_exception(self, mock_run: MagicMock) -> None:
        """Gate that raises exception returns failed result."""
        mock_run.side_effect = FileNotFoundError("command not found")

        runner = GateRunner(
            gate_type=GateType.TYPE,
            command="nonexistent-command",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert "error" in result.message.lower()

    @patch("subprocess.run")
    def test_run_captures_duration(self, mock_run: MagicMock) -> None:
        """Gate captures execution duration."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.TEST,
            command="pytest",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, int)

    @patch("subprocess.run")
    def test_run_passes_environment(self, mock_run: MagicMock) -> None:
        """Gate runner passes environment variables to subprocess."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        env = {"CUSTOM_VAR": "value"}
        runner = GateRunner(
            gate_type=GateType.TEST,
            command="pytest",
            cwd=Path("/tmp"),
            env=env,
        )

        runner.run()

        # Verify subprocess.run was called with environment
        call_kwargs = mock_run.call_args[1]
        assert "env" in call_kwargs


class TestRunGate:
    """Test run_gate function."""

    @patch("subprocess.run")
    def test_run_gate_test(self, mock_run: MagicMock) -> None:
        """Can run test gate via helper function."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="tests passed",
            stderr="",
        )

        result = run_gate(
            gate_type=GateType.TEST,
            command="pytest",
            cwd=Path("/tmp"),
        )

        assert result.gate_type == GateType.TEST
        assert result.passed is True

    @patch("subprocess.run")
    def test_run_gate_lint(self, mock_run: MagicMock) -> None:
        """Can run lint gate via helper function."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        result = run_gate(
            gate_type=GateType.LINT,
            command="ruff check",
            cwd=Path("/tmp"),
        )

        assert result.gate_type == GateType.LINT

    @patch("subprocess.run")
    def test_run_gate_with_kwargs(self, mock_run: MagicMock) -> None:
        """Can pass additional kwargs to run_gate."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        result = run_gate(
            gate_type=GateType.TYPE,
            command="mypy",
            cwd=Path("/tmp"),
            timeout_seconds=120,
            env={"VAR": "value"},
        )

        assert result.gate_type == GateType.TYPE


class TestFixableDetection:
    """Test fixable issue detection."""

    @patch("subprocess.run")
    def test_ruff_check_fixable(self, mock_run: MagicMock) -> None:
        """Ruff check errors are marked as fixable."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Found 5 errors (5 fixable)",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.LINT,
            command="ruff check src/",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.fixable is True

    @patch("subprocess.run")
    def test_ruff_format_fixable(self, mock_run: MagicMock) -> None:
        """Ruff format issues are marked as fixable."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Would reformat 3 files",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.FORMAT,
            command="ruff format --check src/",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.fixable is True

    @patch("subprocess.run")
    def test_mypy_not_fixable(self, mock_run: MagicMock) -> None:
        """Mypy errors are not automatically fixable."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Found 3 errors",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.TYPE,
            command="mypy src/",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.fixable is False

    @patch("subprocess.run")
    def test_prettier_fixable(self, mock_run: MagicMock) -> None:
        """Prettier format issues are marked as fixable."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Code style issues found in 2 files",
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.FORMAT,
            command="prettier --check .",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.fixable is True

    @patch("subprocess.run")
    def test_eslint_partially_fixable(self, mock_run: MagicMock) -> None:
        """ESLint errors may be partially fixable."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=(
                "10 problems (5 errors, 5 warnings)\n"
                "3 errors and 2 warnings potentially fixable with --fix"
            ),
            stderr="",
        )

        runner = GateRunner(
            gate_type=GateType.LINT,
            command="eslint .",
            cwd=Path("/tmp"),
        )

        result = runner.run()

        assert result.passed is False
        assert result.fixable is True
