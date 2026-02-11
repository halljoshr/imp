"""Tests for validation models."""

import pytest
from pydantic import ValidationError

from imp.validation.models import GateResult, GateType, ValidationResult


class TestGateType:
    """Test GateType enum."""

    def test_all_gate_types_defined(self) -> None:
        """All required gate types are available."""
        assert GateType.TEST == "test"
        assert GateType.LINT == "lint"
        assert GateType.TYPE == "type"
        assert GateType.FORMAT == "format"
        assert GateType.SECURITY == "security"

    def test_gate_types_are_strings(self) -> None:
        """Gate type values are strings for JSON serialization."""
        for gate in GateType:
            assert isinstance(gate.value, str)


class TestGateResult:
    """Test GateResult model."""

    def test_creation_success(self) -> None:
        """Can create successful GateResult."""
        result = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="All tests passed",
            command="pytest tests/",
            duration_ms=1500,
        )
        assert result.gate_type == GateType.TEST
        assert result.passed is True
        assert result.message == "All tests passed"
        assert result.command == "pytest tests/"
        assert result.duration_ms == 1500
        assert result.fixable is False  # Default
        assert result.details is None  # Default

    def test_creation_failure(self) -> None:
        """Can create failed GateResult."""
        result = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="5 linting errors found",
            command="ruff check src/",
            duration_ms=800,
            fixable=True,
            details={"errors": 5, "warnings": 2},
        )
        assert result.passed is False
        assert result.fixable is True
        assert result.details == {"errors": 5, "warnings": 2}

    def test_creation_with_output(self) -> None:
        """Can create GateResult with stdout/stderr."""
        result = GateResult(
            gate_type=GateType.TYPE,
            passed=False,
            message="Type errors found",
            command="mypy src/",
            duration_ms=2000,
            stdout="Found 3 errors in 2 files",
            stderr="",
        )
        assert result.stdout == "Found 3 errors in 2 files"
        assert result.stderr == ""

    def test_defaults(self) -> None:
        """Optional fields have sensible defaults."""
        result = GateResult(
            gate_type=GateType.SECURITY,
            passed=True,
            message="No security issues",
            command="bandit -r src/",
            duration_ms=500,
        )
        assert result.fixable is False
        assert result.details is None
        assert result.stdout is None
        assert result.stderr is None

    def test_immutability(self) -> None:
        """GateResult is frozen."""
        result = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="test",
            command="test",
            duration_ms=100,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]


class TestValidationResult:
    """Test ValidationResult model."""

    def test_creation_empty(self) -> None:
        """Can create ValidationResult with no gates."""
        result = ValidationResult(
            passed=True,
            gates=[],
            total_duration_ms=0,
        )
        assert result.passed is True
        assert len(result.gates) == 0
        assert result.total_duration_ms == 0

    def test_creation_all_passing(self) -> None:
        """ValidationResult with all gates passing."""
        gates = [
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
                message="Linting passed",
                command="ruff check",
                duration_ms=500,
            ),
        ]
        result = ValidationResult(
            passed=True,
            gates=gates,
            total_duration_ms=1500,
        )
        assert result.passed is True
        assert len(result.gates) == 2
        assert result.total_duration_ms == 1500

    def test_creation_with_failure(self) -> None:
        """ValidationResult with at least one gate failing."""
        gates = [
            GateResult(
                gate_type=GateType.TEST,
                passed=True,
                message="Tests passed",
                command="pytest",
                duration_ms=1000,
            ),
            GateResult(
                gate_type=GateType.TYPE,
                passed=False,
                message="Type errors",
                command="mypy",
                duration_ms=800,
            ),
        ]
        result = ValidationResult(
            passed=False,
            gates=gates,
            total_duration_ms=1800,
        )
        assert result.passed is False
        assert len(result.gates) == 2

    def test_failed_gates_property(self) -> None:
        """Can get list of failed gates."""
        gates = [
            GateResult(
                gate_type=GateType.TEST,
                passed=True,
                message="Tests passed",
                command="pytest",
                duration_ms=1000,
            ),
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
                duration_ms=800,
            ),
        ]
        result = ValidationResult(
            passed=False,
            gates=gates,
            total_duration_ms=2300,
        )

        failed = result.failed_gates
        assert len(failed) == 2
        assert failed[0].gate_type == GateType.LINT
        assert failed[1].gate_type == GateType.TYPE

    def test_fixable_gates_property(self) -> None:
        """Can get list of fixable gates."""
        gates = [
            GateResult(
                gate_type=GateType.LINT,
                passed=False,
                message="Lint errors",
                command="ruff check",
                duration_ms=500,
                fixable=True,
            ),
            GateResult(
                gate_type=GateType.FORMAT,
                passed=False,
                message="Format issues",
                command="ruff format --check",
                duration_ms=300,
                fixable=True,
            ),
            GateResult(
                gate_type=GateType.TYPE,
                passed=False,
                message="Type errors",
                command="mypy",
                duration_ms=800,
                fixable=False,
            ),
        ]
        result = ValidationResult(
            passed=False,
            gates=gates,
            total_duration_ms=1600,
        )

        fixable = result.fixable_gates
        assert len(fixable) == 2
        assert fixable[0].gate_type == GateType.LINT
        assert fixable[1].gate_type == GateType.FORMAT

    def test_passed_gates_property(self) -> None:
        """Can get list of passed gates."""
        gates = [
            GateResult(
                gate_type=GateType.TEST,
                passed=True,
                message="Tests passed",
                command="pytest",
                duration_ms=1000,
            ),
            GateResult(
                gate_type=GateType.LINT,
                passed=False,
                message="Lint errors",
                command="ruff check",
                duration_ms=500,
            ),
            GateResult(
                gate_type=GateType.SECURITY,
                passed=True,
                message="No security issues",
                command="bandit",
                duration_ms=600,
            ),
        ]
        result = ValidationResult(
            passed=False,
            gates=gates,
            total_duration_ms=2100,
        )

        passed = result.passed_gates
        assert len(passed) == 2
        assert passed[0].gate_type == GateType.TEST
        assert passed[1].gate_type == GateType.SECURITY

    def test_json_serialization(self) -> None:
        """ValidationResult can be serialized to JSON."""
        gates = [
            GateResult(
                gate_type=GateType.TEST,
                passed=True,
                message="Tests passed",
                command="pytest",
                duration_ms=1000,
            ),
        ]
        result = ValidationResult(
            passed=True,
            gates=gates,
            total_duration_ms=1000,
        )

        json_data = result.model_dump()
        assert json_data["passed"] is True
        assert len(json_data["gates"]) == 1
        assert json_data["gates"][0]["gate_type"] == "test"
