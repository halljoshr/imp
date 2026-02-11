"""Tests for validation CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from imp.validation.cli import check_command
from imp.validation.models import GateResult, GateType, ValidationResult


class TestCheckCommand:
    """Test imp check CLI command."""

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_all_passing(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check with all gates passing returns 0."""
        mock_run_all.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        exit_code = check_command(
            project_root=tmp_path,
            gates=None,  # Run all
            fix=False,
            format="human",
        )

        assert exit_code == 0

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_with_failure(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check with failures returns 1."""
        mock_run_all.return_value = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Lint errors",
                    command="ruff check",
                    duration_ms=500,
                ),
            ],
            total_duration_ms=500,
        )

        exit_code = check_command(
            project_root=tmp_path,
            gates=None,
            fix=False,
            format="human",
        )

        assert exit_code == 1

    @patch("imp.validation.runner.ValidationRunner.run_gates")
    def test_check_specific_gates(self, mock_run_gates: MagicMock, tmp_path: Path) -> None:
        """imp check with specific gates runs only those."""
        mock_run_gates.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        check_command(
            project_root=tmp_path,
            gates=["test", "lint"],
            fix=False,
            format="human",
        )

        mock_run_gates.assert_called_once()
        # Should pass [GateType.TEST, GateType.LINT] to run_gates
        call_args = mock_run_gates.call_args[0]
        assert GateType.TEST in call_args[0]
        assert GateType.LINT in call_args[0]

    @patch("imp.validation.runner.ValidationRunner.run_with_fix")
    def test_check_with_fix_flag(self, mock_run_fix: MagicMock, tmp_path: Path) -> None:
        """imp check --fix runs fix mode."""
        mock_run_fix.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=True,
                    message="Fixed and validated",
                    command="ruff check",
                    duration_ms=800,
                ),
            ],
            total_duration_ms=800,
        )

        exit_code = check_command(
            project_root=tmp_path,
            gates=None,
            fix=True,
            format="human",
        )

        mock_run_fix.assert_called_once()
        assert exit_code == 0

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_json_output(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check --format json outputs valid JSON."""
        mock_run_all.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        with patch("builtins.print") as mock_print:
            check_command(
                project_root=tmp_path,
                gates=None,
                fix=False,
                format="json",
            )

            # Should print valid JSON
            assert mock_print.called
            output = mock_print.call_args[0][0]
            data = json.loads(output)
            assert data["passed"] is True
            assert len(data["gates"]) == 1

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_jsonl_output(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check --format jsonl outputs JSONL stream."""
        mock_run_all.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
                GateResult(
                    gate_type=GateType.LINT,
                    passed=True,
                    message="Lint passed",
                    command="ruff check",
                    duration_ms=500,
                ),
            ],
            total_duration_ms=1500,
        )

        with patch("builtins.print") as mock_print:
            check_command(
                project_root=tmp_path,
                gates=None,
                fix=False,
                format="jsonl",
            )

            # Should print JSONL (one JSON object per line)
            assert mock_print.call_count >= 2  # At least one per gate

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_human_output(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check --format human outputs Rich-formatted text."""
        mock_run_all.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        with patch("rich.print") as mock_rprint:
            check_command(
                project_root=tmp_path,
                gates=None,
                fix=False,
                format="human",
            )

            # Should use rich.print for human-readable output
            assert mock_rprint.called

    def test_check_invalid_gate_name(self, tmp_path: Path) -> None:
        """imp check with invalid gate name returns error."""
        exit_code = check_command(
            project_root=tmp_path,
            gates=["invalid-gate"],
            fix=False,
            format="human",
        )

        # Should return error exit code
        assert exit_code != 0

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_shows_fixable_info(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check output indicates which issues are fixable."""
        mock_run_all.return_value = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Lint errors",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
                GateResult(
                    gate_type=GateType.TYPE,
                    passed=False,
                    message="Type errors",
                    command="mypy",
                    duration_ms=1000,
                    fixable=False,
                ),
            ],
            total_duration_ms=1500,
        )

        with patch("rich.print") as mock_rprint:
            check_command(
                project_root=tmp_path,
                gates=None,
                fix=False,
                format="human",
            )

            # Output should mention fixable issues
            output = " ".join(str(call[0][0]) for call in mock_rprint.call_args_list)
            assert "fixable" in output.lower() or "--fix" in output.lower()

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_shows_duration(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check output shows execution duration."""
        mock_run_all.return_value = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1234,
                ),
            ],
            total_duration_ms=1234,
        )

        with patch("rich.print") as mock_rprint:
            check_command(
                project_root=tmp_path,
                gates=None,
                fix=False,
                format="human",
            )

            # Output should show duration
            output = " ".join(str(call[0][0]) for call in mock_rprint.call_args_list)
            # Duration might be shown in ms or seconds
            assert "1234" in output or "1.23" in output or "1.2" in output


class TestCheckCommandEdgeCases:
    """Test edge cases for check command."""

    def test_check_empty_project(self, tmp_path: Path) -> None:
        """imp check on empty project handles gracefully."""
        check_command(
            project_root=tmp_path,
            gates=None,
            fix=False,
            format="human",
        )

        # Should handle empty project gracefully
        # Exit code depends on whether no gates = success or failure

    def test_check_nonexistent_path(self) -> None:
        """imp check on nonexistent path returns error."""
        exit_code = check_command(
            project_root=Path("/nonexistent/path"),
            gates=None,
            fix=False,
            format="human",
        )

        assert exit_code != 0

    @patch("imp.validation.runner.ValidationRunner.run_all")
    def test_check_handles_exception(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """imp check handles unexpected exceptions gracefully."""
        mock_run_all.side_effect = RuntimeError("Unexpected error")

        exit_code = check_command(
            project_root=tmp_path,
            gates=None,
            fix=False,
            format="human",
        )

        assert exit_code != 0
