"""Validation data models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GateType(StrEnum):
    """Validation gate types."""

    TEST = "test"
    LINT = "lint"
    TYPE = "type"
    FORMAT = "format"
    SECURITY = "security"


class GateResult(BaseModel):
    """Result from running a single validation gate.

    Records outcome, duration, and output from a validation command.
    """

    gate_type: GateType
    passed: bool
    message: str
    command: str
    duration_ms: int
    fixable: bool = False
    details: dict[str, object] | None = None
    stdout: str | None = None
    stderr: str | None = None

    model_config = ConfigDict(frozen=True)


class ValidationResult(BaseModel):
    """Aggregate result from running multiple validation gates.

    Contains all gate results with helper properties for filtering.
    """

    passed: bool
    gates: list[GateResult]
    total_duration_ms: int

    @property
    def failed_gates(self) -> list[GateResult]:
        """Get list of gates that failed."""
        return [g for g in self.gates if not g.passed]

    @property
    def fixable_gates(self) -> list[GateResult]:
        """Get list of gates that have fixable issues."""
        return [g for g in self.gates if not g.passed and g.fixable]

    @property
    def passed_gates(self) -> list[GateResult]:
        """Get list of gates that passed."""
        return [g for g in self.gates if g.passed]
