"""Imp validation — code and output validation checks.

Public API for validation module.
"""

from imp.validation.cli import check_command
from imp.validation.detector import ProjectType, ToolchainConfig, detect_toolchain
from imp.validation.fixer import FixResult, apply_fix, get_fix_command
from imp.validation.gates import GateRunner, run_gate
from imp.validation.models import GateResult, GateType, ValidationResult
from imp.validation.runner import ValidationRunner

__all__ = [
    "FixResult",
    "GateResult",
    "GateRunner",
    "GateType",
    "ProjectType",
    "ToolchainConfig",
    "ValidationResult",
    "ValidationRunner",
    "apply_fix",
    "check_command",
    "detect_toolchain",
    "get_fix_command",
    "run_gate",
]
