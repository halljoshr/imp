#!/usr/bin/env python3
"""Smoke test for interview layer - validates real usage patterns.

This script tests the interview module as a real user would use it:
- Imports modules like a developer would
- Creates InterviewSpec instances and validates them
- Tests JSON round-trips and file validation
- Uses real validator logic (deterministic, no AI)

Run: python tests/smoke/smoke_test_interview.py
Exit code: 0 = pass, 1 = fail

This is NOT a pytest test. This is a smoke test that validates the module
works in the wild, not just in a test harness.
"""

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

# Add src to path so we can import imp modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

passed = 0
failed = 0


def test(name: str, fn):
    """Execute a test and track pass/fail."""
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed += 1


def test_import_models():
    """Test: Can import all models from imp.interview.models."""
    from imp.interview.models import (  # noqa: F401
        CompletenessResult,
        GapSeverity,
        InterviewMetadata,
        InterviewMode,
        InterviewSpec,
        SpecComponent,
        SpecGap,
        StakeholderProfile,
    )


def test_import_validator():
    """Test: Can import validator functions."""
    from imp.interview.validator import (  # noqa: F401
        validate_spec,
        validate_spec_file,
    )


def test_construct_full_spec():
    """Test: Can construct a fully populated InterviewSpec."""
    from imp.interview.models import (
        InterviewMetadata,
        InterviewMode,
        InterviewSpec,
        SpecComponent,
        StakeholderProfile,
    )

    spec = InterviewSpec(
        name="Test Project",
        problem_statement="Users need a way to track tasks efficiently.",
        system_overview="A task tracking system with AI-powered suggestions.",
        components=[
            SpecComponent(
                name="Task Manager",
                purpose="Manage task lifecycle",
                inputs=["task title", "task description"],
                outputs=["created task", "task ID"],
                constraints=["max 1000 tasks per user"],
                edge_cases=["duplicate task names"],
                success_criteria=["tasks can be created and retrieved"],
            )
        ],
        success_criteria=["users can create and track tasks"],
        out_of_scope=["calendar integration"],
        constraints=["web-based only"],
        stakeholder_profile=StakeholderProfile(
            working_style="terminal-first",
            values=["efficiency", "simplicity"],
            pain_points=["complex UIs"],
            priorities=["speed over features"],
            technical_preferences=["Python", "CLI"],
        ),
        metadata=InterviewMetadata(
            interview_date=date.today(),
            mode=InterviewMode.DIRECT,
            completeness_score=95,
            domain="software-requirements",
            question_count=12,
        ),
    )

    # Validate structure
    assert spec.name == "Test Project"
    assert spec.component_count == 1
    assert spec.components[0].name == "Task Manager"
    assert spec.has_problem_statement
    assert spec.has_success_criteria
    assert spec.has_constraints
    assert spec.has_out_of_scope


def test_construct_minimal_spec():
    """Test: Can construct minimal InterviewSpec with defaults."""
    from imp.interview.models import InterviewSpec

    spec = InterviewSpec(name="Minimal Project")

    # Verify defaults
    assert spec.name == "Minimal Project"
    assert spec.problem_statement == ""
    assert spec.system_overview is None
    assert spec.component_count == 0
    assert len(spec.success_criteria) == 0
    assert len(spec.out_of_scope) == 0
    assert len(spec.constraints) == 0
    assert spec.stakeholder_profile is None
    assert spec.metadata is None


def test_validate_complete_spec():
    """Test: Validate a complete spec returns high score and is_complete=True."""
    from imp.interview.models import InterviewSpec, SpecComponent
    from imp.interview.validator import validate_spec

    spec = InterviewSpec(
        name="Complete Project",
        problem_statement="A real problem statement that's long enough to pass validation.",
        components=[
            SpecComponent(
                name="Component A",
                purpose="Does something useful",
                inputs=["data"],
                outputs=["result"],
                edge_cases=["empty input"],
                success_criteria=["result is correct"],
            )
        ],
        success_criteria=["system works end-to-end"],
        constraints=["must be fast"],
        out_of_scope=["mobile app"],
    )

    result = validate_spec(spec)

    # Should have high score and be complete
    assert result.score > 80, f"Expected score > 80, got {result.score}"
    assert result.is_complete, "Spec should be marked complete"
    assert isinstance(result.gaps, list)


def test_validate_empty_spec():
    """Test: Validate an empty spec returns low score with gaps."""
    from imp.interview.models import InterviewSpec
    from imp.interview.validator import validate_spec

    spec = InterviewSpec(name="Empty Project")

    result = validate_spec(spec)

    # Should have low score and not be complete
    assert result.score < 50, f"Expected score < 50, got {result.score}"
    assert not result.is_complete, "Empty spec should not be complete"
    assert len(result.gaps) > 0, "Should have identified gaps"
    assert result.gap_count > 0
    assert len(result.critical_gaps) > 0, "Should have critical gaps"


def test_json_round_trip():
    """Test: InterviewSpec can be serialized to JSON and back."""
    from imp.interview.models import InterviewSpec, SpecComponent

    original = InterviewSpec(
        name="Round Trip Test",
        problem_statement="Testing JSON serialization.",
        components=[
            SpecComponent(
                name="Test Component",
                purpose="Test serialization",
                inputs=["input"],
                outputs=["output"],
            )
        ],
    )

    # Serialize to JSON
    json_str = original.model_dump_json()
    data = json.loads(json_str)

    # Deserialize back
    restored = InterviewSpec.model_validate(data)

    # Verify equality
    assert restored.name == original.name
    assert restored.problem_statement == original.problem_statement
    assert restored.component_count == original.component_count
    assert restored.components[0].name == original.components[0].name
    assert restored.components[0].purpose == original.components[0].purpose
    assert restored.components[0].inputs == original.components[0].inputs
    assert restored.components[0].outputs == original.components[0].outputs


def test_file_validation():
    """Test: validate_spec_file can read and validate a spec from disk."""
    from imp.interview.models import InterviewSpec, SpecComponent
    from imp.interview.validator import validate_spec_file

    # Create a spec
    spec = InterviewSpec(
        name="File Test",
        problem_statement="Testing file-based validation workflow.",
        components=[
            SpecComponent(
                name="File Component",
                purpose="Test file validation",
                inputs=["file path"],
                outputs=["validation result"],
            )
        ],
    )

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(spec.model_dump_json())
        temp_path = Path(f.name)

    try:
        # Validate from file
        result = validate_spec_file(temp_path)

        # Should return a CompletenessResult
        assert hasattr(result, "score")
        assert hasattr(result, "gaps")
        assert hasattr(result, "suggestions")
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100
    finally:
        # Cleanup
        temp_path.unlink()


def test_spec_component_properties():
    """Test: SpecComponent property helpers work correctly."""
    from imp.interview.models import SpecComponent

    # Component with all fields
    full = SpecComponent(
        name="Full",
        purpose="Test",
        inputs=["a"],
        outputs=["b"],
        edge_cases=["c"],
        success_criteria=["d"],
    )
    assert full.has_inputs
    assert full.has_outputs
    assert full.has_edge_cases
    assert full.has_success_criteria

    # Component with minimal fields
    minimal = SpecComponent(name="Minimal", purpose="Test")
    assert not minimal.has_inputs
    assert not minimal.has_outputs
    assert not minimal.has_edge_cases
    assert not minimal.has_success_criteria


def test_completeness_result_properties():
    """Test: CompletenessResult property helpers work correctly."""
    from imp.interview.models import CompletenessResult, GapSeverity, SpecGap

    result = CompletenessResult(
        score=85,
        gaps=[
            SpecGap(
                field="test",
                severity=GapSeverity.CRITICAL,
                description="Critical gap",
            ),
            SpecGap(
                field="test2",
                severity=GapSeverity.IMPORTANT,
                description="Important gap",
            ),
            SpecGap(
                field="test3",
                severity=GapSeverity.MINOR,
                description="Minor gap",
            ),
        ],
    )

    assert result.is_complete  # score >= 80
    assert result.gap_count == 3
    assert len(result.critical_gaps) == 1
    assert len(result.important_gaps) == 1
    assert len(result.minor_gaps) == 1


def test_interview_mode_enum():
    """Test: InterviewMode enum values are correct."""
    from imp.interview.models import InterviewMode

    assert InterviewMode.DIRECT == "direct"
    assert InterviewMode.GAP_ANALYSIS == "gap_analysis"


def test_gap_severity_enum():
    """Test: GapSeverity enum values are correct."""
    from imp.interview.models import GapSeverity

    assert GapSeverity.CRITICAL == "critical"
    assert GapSeverity.IMPORTANT == "important"
    assert GapSeverity.MINOR == "minor"


def run_all_tests():
    """Run all smoke tests in sequence."""
    print("=" * 60)
    print("Interview Layer Smoke Tests")
    print("=" * 60)
    print()

    # Test 1: Import models
    test("Import models", test_import_models)

    # Test 2: Import validator
    test("Import validator", test_import_validator)

    # Test 3: Construct full spec
    test("Construct full InterviewSpec", test_construct_full_spec)

    # Test 4: Construct minimal spec
    test("Construct minimal InterviewSpec", test_construct_minimal_spec)

    # Test 5: Validate complete spec
    test("Validate complete spec", test_validate_complete_spec)

    # Test 6: Validate empty spec
    test("Validate empty spec", test_validate_empty_spec)

    # Test 7: JSON round-trip
    test("JSON round-trip", test_json_round_trip)

    # Test 8: File validation
    test("File validation", test_file_validation)

    # Test 9: SpecComponent properties
    test("SpecComponent properties", test_spec_component_properties)

    # Test 10: CompletenessResult properties
    test("CompletenessResult properties", test_completeness_result_properties)

    # Test 11: InterviewMode enum
    test("InterviewMode enum", test_interview_mode_enum)

    # Test 12: GapSeverity enum
    test("GapSeverity enum", test_gap_severity_enum)

    print()
    print("=" * 60)

    if failed == 0:
        print(f"🎉 All {passed} smoke tests passed!")
        print("=" * 60)
        return 0
    else:
        print(f"❌ {failed} smoke test(s) failed ({passed} passed)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
