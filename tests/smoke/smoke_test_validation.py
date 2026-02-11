#!/usr/bin/env python3
"""Smoke test for validation module.

This is a standalone script that validates the validation module works
in the wild, not just in test harnesses.

Run with: uv run python tests/smoke/smoke_test_validation.py

Exit codes:
- 0: All smoke tests passed
- 1: At least one smoke test failed
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def test_imports() -> None:
    """Test that all validation modules can be imported."""
    print("Testing imports...")

    try:
        from imp.validation.cli import check_command  # noqa: F401
        from imp.validation.detector import (  # noqa: F401
            ProjectType,
            ToolchainConfig,
            detect_toolchain,
        )
        from imp.validation.fixer import FixResult, apply_fix, get_fix_command  # noqa: F401
        from imp.validation.gates import GateRunner, run_gate  # noqa: F401
        from imp.validation.models import GateResult, GateType, ValidationResult  # noqa: F401
        from imp.validation.runner import ValidationRunner  # noqa: F401

        print("✓ All validation modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_models() -> None:
    """Test that validation models work correctly."""
    print("\nTesting models...")

    try:
        from imp.validation.models import GateResult, GateType, ValidationResult

        # Test GateType enum
        assert GateType.TEST == "test"
        assert GateType.LINT == "lint"
        assert GateType.TYPE == "type"
        assert GateType.FORMAT == "format"
        assert GateType.SECURITY == "security"

        # Test GateResult creation
        gate_result = GateResult(
            gate_type=GateType.TEST,
            passed=True,
            message="Tests passed",
            command="pytest",
            duration_ms=1000,
        )
        assert gate_result.passed is True
        assert gate_result.gate_type == GateType.TEST

        # Test ValidationResult creation
        validation_result = ValidationResult(
            passed=True,
            gates=[gate_result],
            total_duration_ms=1000,
        )
        assert validation_result.passed is True
        assert len(validation_result.gates) == 1
        assert len(validation_result.passed_gates) == 1
        assert len(validation_result.failed_gates) == 0

        # Test ValidationResult with failure
        failed_gate = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check",
            duration_ms=500,
            fixable=True,
        )
        failed_result = ValidationResult(
            passed=False,
            gates=[gate_result, failed_gate],
            total_duration_ms=1500,
        )
        assert failed_result.passed is False
        assert len(failed_result.failed_gates) == 1
        assert len(failed_result.fixable_gates) == 1

        # Test JSON serialization
        json_data = validation_result.model_dump()
        assert json_data["passed"] is True
        assert len(json_data["gates"]) == 1

        print("✓ Models work correctly")
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        return False


def test_detector() -> None:
    """Test that toolchain detection works."""
    print("\nTesting detector...")

    try:
        from imp.validation.detector import (
            ProjectType,
            ToolchainConfig,
            detect_toolchain,
        )

        # Test ProjectType enum
        assert ProjectType.PYTHON == "python"
        assert ProjectType.TYPESCRIPT == "typescript"
        assert ProjectType.MIXED == "mixed"
        assert ProjectType.UNKNOWN == "unknown"

        # Test ToolchainConfig creation
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
        )
        assert config.project_type == ProjectType.PYTHON
        assert config.test_command == "pytest"

        # Test available_gates
        gates = config.available_gates()
        assert "test" in gates
        assert "lint" in gates
        assert "type" in gates

        # Test detect_toolchain with temp directory
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create pyproject.toml
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text("""
[project]
name = "test-project"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
""")

            # Detect toolchain
            detected = detect_toolchain(tmp_path)
            assert detected.project_type == ProjectType.PYTHON
            assert detected.test_command is not None
            assert detected.lint_command is not None

        # Test detect_toolchain with nonexistent path
        nonexistent = detect_toolchain(Path("/nonexistent/path"))
        assert nonexistent.project_type == ProjectType.UNKNOWN

        print("✓ Detector works correctly")
        return True
    except Exception as e:
        print(f"✗ Detector test failed: {e}")
        return False


def test_gates() -> None:
    """Test that gate runners work."""
    print("\nTesting gates...")

    try:
        from imp.validation.gates import GateRunner, run_gate
        from imp.validation.models import GateType

        # Test GateRunner creation
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            runner = GateRunner(
                gate_type=GateType.TEST,
                command="echo 'test'",
                cwd=tmp_path,
            )
            assert runner.gate_type == GateType.TEST
            assert runner.command == "echo 'test'"
            assert runner.cwd == tmp_path

            # Test run_gate helper
            result = run_gate(
                gate_type=GateType.TEST,
                command="echo 'success'",
                cwd=tmp_path,
            )
            assert result.gate_type == GateType.TEST
            # Should pass since echo returns 0
            assert result.passed is True

        print("✓ Gates work correctly")
        return True
    except Exception as e:
        print(f"✗ Gates test failed: {e}")
        return False


def test_runner() -> None:
    """Test that ValidationRunner works."""
    print("\nTesting runner...")

    try:
        from imp.validation.detector import ProjectType, ToolchainConfig
        from imp.validation.models import GateType
        from imp.validation.runner import ValidationRunner

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create runner with minimal toolchain
            toolchain = ToolchainConfig(
                project_type=ProjectType.PYTHON,
                test_command="echo 'test passed'",
            )

            runner = ValidationRunner(
                project_root=tmp_path,
                toolchain=toolchain,
            )

            assert runner.project_root == tmp_path
            assert runner.toolchain == toolchain

            # Test available_gates
            gates = runner.available_gates()
            assert "test" in gates

            # Test get_fix_command
            runner.get_fix_command(GateType.LINT)
            # May return None if lint not configured

        print("✓ Runner works correctly")
        return True
    except Exception as e:
        print(f"✗ Runner test failed: {e}")
        return False


def test_fixer() -> None:
    """Test that fixer works."""
    print("\nTesting fixer...")

    try:
        from imp.validation.fixer import FixResult, get_fix_command
        from imp.validation.models import GateResult, GateType

        # Test FixResult creation
        fix_result = FixResult(
            success=True,
            gate_type=GateType.LINT,
            fix_command="ruff check --fix src/",
            message="Fixed 3 issues",
            duration_ms=500,
        )
        assert fix_result.success is True
        assert fix_result.gate_type == GateType.LINT

        # Test get_fix_command
        gate_result = GateResult(
            gate_type=GateType.LINT,
            passed=False,
            message="Lint errors",
            command="ruff check src/",
            duration_ms=500,
            fixable=True,
        )
        fix_cmd = get_fix_command(gate_result)
        assert fix_cmd is not None
        assert "ruff check" in fix_cmd

        # Test non-fixable gate
        type_gate = GateResult(
            gate_type=GateType.TYPE,
            passed=False,
            message="Type errors",
            command="mypy src/",
            duration_ms=1000,
            fixable=False,
        )
        type_fix = get_fix_command(type_gate)
        assert type_fix is None

        print("✓ Fixer works correctly")
        return True
    except Exception as e:
        print(f"✗ Fixer test failed: {e}")
        return False


def test_cli() -> None:
    """Test that CLI command exists and is importable."""
    print("\nTesting CLI...")

    try:
        from imp.validation.cli import check_command

        # Just verify it's callable
        assert callable(check_command)

        print("✓ CLI command imported successfully")
        return True
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False


def test_real_detection() -> None:
    """Test detection on the actual Imp project."""
    print("\nTesting real project detection...")

    try:
        from imp.validation.detector import detect_toolchain

        # Find the imp project root
        imp_root = Path(__file__).parent.parent.parent
        assert (imp_root / "pyproject.toml").exists()

        # Detect Imp's toolchain
        toolchain = detect_toolchain(imp_root)

        # Verify detection worked
        assert toolchain.test_command is not None
        assert "pytest" in toolchain.test_command
        assert toolchain.lint_command is not None
        assert "ruff" in toolchain.lint_command
        assert toolchain.type_command is not None
        assert "mypy" in toolchain.type_command

        print("✓ Real project detection works")
        print(f"  Detected project type: {toolchain.project_type}")
        print(f"  Test command: {toolchain.test_command}")
        print(f"  Lint command: {toolchain.lint_command}")
        print(f"  Type command: {toolchain.type_command}")
        return True
    except Exception as e:
        print(f"✗ Real detection test failed: {e}")
        return False


def main() -> int:
    """Run all smoke tests."""
    print("=" * 60)
    print("Validation Module Smoke Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_models,
        test_detector,
        test_gates,
        test_runner,
        test_fixer,
        test_cli,
        test_real_detection,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All smoke tests passed!")
        return 0
    else:
        print("\n❌ Some smoke tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
