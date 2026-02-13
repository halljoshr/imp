"""Unit tests for the spec completeness validator.

100% branch coverage required. Tests all scoring components, gap detection,
and file validation logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from imp.interview.models import (
    GapSeverity,
    InterviewSpec,
    SpecComponent,
    StakeholderProfile,
)
from imp.interview.validator import validate_spec, validate_spec_file


class TestValidateSpec:
    """Tests for validate_spec function with 100% branch coverage."""

    def test_perfect_spec(self) -> None:
        """Perfect spec with all fields populated scores 100, no gaps, is_complete=True."""
        spec = InterviewSpec(
            name="Test Project",
            problem_statement=(
                "This is a detailed problem statement that meets the minimum length requirement"
            ),
            components=[
                SpecComponent(
                    name="Component A",
                    purpose="Does something important",
                    inputs=["user input", "config data"],
                    outputs=["processed result", "status code"],
                    edge_cases=["empty input", "malformed data"],
                    success_criteria=["output is valid", "no errors"],
                ),
                SpecComponent(
                    name="Component B",
                    purpose="Does another important thing",
                    inputs=["component A output"],
                    outputs=["final result"],
                    edge_cases=["network timeout"],
                    success_criteria=["result is correct"],
                ),
            ],
            success_criteria=["end-to-end test passes", "user is satisfied"],
            constraints=["must run in < 1s", "Python 3.12+"],
            out_of_scope=["mobile app", "offline mode"],
            stakeholder_profile=StakeholderProfile(
                working_style="terminal-first",
                values=["efficiency"],
                pain_points=["manual steps"],
            ),
        )

        result = validate_spec(spec)

        assert result.score == 100
        assert result.is_complete is True
        assert len(result.gaps) == 0
        assert "fully complete" in " ".join(result.suggestions)

    def test_empty_minimal_spec(self) -> None:
        """Empty/minimal spec scores 0, has CRITICAL gaps for problem_statement and components."""
        spec = InterviewSpec(name="test")

        result = validate_spec(spec)

        assert result.score == 0
        assert result.is_complete is False

        # Should have CRITICAL gaps for problem_statement and components
        critical_fields = {g.field for g in result.critical_gaps}
        assert "problem_statement" in critical_fields
        assert "components" in critical_fields

        # Check that critical gap message is in suggestions
        assert any("critical gap" in s for s in result.suggestions)

    def test_problem_statement_empty(self) -> None:
        """Empty problem statement scores 0 points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="",
            components=[
                SpecComponent(
                    name="comp",
                    purpose="test",
                    inputs=["input"],
                    outputs=["output"],
                )
            ],
        )

        result = validate_spec(spec)

        # Should get points for components (10) + inputs (15) + outputs (15) = 40
        assert result.score == 40
        gap = next(g for g in result.gaps if g.field == "problem_statement")
        assert gap.severity == GapSeverity.CRITICAL

    def test_problem_statement_too_short(self) -> None:
        """Problem statement < 10 chars scores 0 points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="fix bug",  # 7 chars
            components=[
                SpecComponent(
                    name="comp",
                    purpose="test",
                    inputs=["input"],
                    outputs=["output"],
                )
            ],
        )

        result = validate_spec(spec)

        # Should get points for components (10) + inputs (15) + outputs (15) = 40
        assert result.score == 40
        gap = next(g for g in result.gaps if g.field == "problem_statement")
        assert gap.severity == GapSeverity.CRITICAL

    def test_problem_statement_sufficient(self) -> None:
        """Problem statement >= 10 chars scores 15 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="fix the auth bug",  # 16 chars
        )

        result = validate_spec(spec)

        # 15 points for problem statement, 0 for everything else
        # Will still have CRITICAL gap for components
        assert result.score == 15
        problem_gaps = [g for g in result.gaps if g.field == "problem_statement"]
        assert len(problem_gaps) == 0

    def test_component_existence_no_components(self) -> None:
        """0 components scores 0 points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
        )

        result = validate_spec(spec)

        # 15 points for problem statement only
        assert result.score == 15
        gap = next(g for g in result.gaps if g.field == "components")
        assert gap.severity == GapSeverity.CRITICAL

    def test_component_existence_with_components(self) -> None:
        """At least 1 component scores 10 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[SpecComponent(name="comp", purpose="test")],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (component existence) = 25
        assert result.score == 25
        component_gaps = [g for g in result.gaps if g.field == "components"]
        assert len(component_gaps) == 0

    def test_component_inputs_all_have_inputs(self) -> None:
        """All components with inputs scores 15 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    inputs=["input2"],
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 15 (all inputs) = 40
        assert result.score == 40
        input_gaps = [g for g in result.gaps if g.field == "component_inputs"]
        assert len(input_gaps) == 0

    def test_component_inputs_partial(self) -> None:
        """Partial components with inputs scores proportional points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    # No inputs
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + round(15 * 0.5) = 15 + 10 + 8 = 33
        assert result.score == 33
        gap = next(g for g in result.gaps if g.field == "component_inputs")
        assert gap.severity == GapSeverity.CRITICAL
        assert "comp2" in gap.description

    def test_component_inputs_none_have_inputs(self) -> None:
        """No components with inputs scores 0 points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(name="comp1", purpose="test"),
                SpecComponent(name="comp2", purpose="test"),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 0 (inputs) = 25
        assert result.score == 25
        gap = next(g for g in result.gaps if g.field == "component_inputs")
        assert gap.severity == GapSeverity.CRITICAL
        assert "comp1" in gap.description
        assert "comp2" in gap.description

    def test_component_outputs_all_have_outputs(self) -> None:
        """All components with outputs scores 15 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    outputs=["output1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    outputs=["output2"],
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 15 (all outputs) = 40
        assert result.score == 40
        output_gaps = [g for g in result.gaps if g.field == "component_outputs"]
        assert len(output_gaps) == 0

    def test_component_outputs_partial(self) -> None:
        """Partial components with outputs scores proportional points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    outputs=["output1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    # No outputs
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + round(15 * 0.5) = 15 + 10 + 8 = 33
        assert result.score == 33
        gap = next(g for g in result.gaps if g.field == "component_outputs")
        assert gap.severity == GapSeverity.CRITICAL
        assert "comp2" in gap.description

    def test_component_outputs_none_have_outputs(self) -> None:
        """No components with outputs scores 0 points, creates CRITICAL gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(name="comp1", purpose="test"),
                SpecComponent(name="comp2", purpose="test"),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 0 (outputs) = 25
        assert result.score == 25
        gap = next(g for g in result.gaps if g.field == "component_outputs")
        assert gap.severity == GapSeverity.CRITICAL
        assert "comp1" in gap.description
        assert "comp2" in gap.description

    def test_spec_level_success_criteria_present(self) -> None:
        """Spec-level success criteria present scores 10 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            success_criteria=["criterion 1", "criterion 2"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (success_criteria) = 25
        assert result.score == 25
        criteria_gaps = [g for g in result.gaps if g.field == "success_criteria"]
        assert len(criteria_gaps) == 0

    def test_spec_level_success_criteria_empty(self) -> None:
        """No spec-level success criteria scores 0 points, creates IMPORTANT gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
        )

        result = validate_spec(spec)

        # 15 (problem) only
        assert result.score == 15
        gap = next(g for g in result.gaps if g.field == "success_criteria")
        assert gap.severity == GapSeverity.IMPORTANT

    def test_constraints_present(self) -> None:
        """Constraints present scores 5 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            constraints=["constraint 1"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 5 (constraints) = 20
        assert result.score == 20
        constraint_gaps = [g for g in result.gaps if g.field == "constraints"]
        assert len(constraint_gaps) == 0

    def test_constraints_empty(self) -> None:
        """No constraints scores 0 points, creates MINOR gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
        )

        result = validate_spec(spec)

        # 15 (problem) only
        assert result.score == 15
        gap = next(g for g in result.gaps if g.field == "constraints")
        assert gap.severity == GapSeverity.MINOR

    def test_edge_cases_present(self) -> None:
        """At least one component with edge cases scores 10 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    edge_cases=["edge case 1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    # No edge cases
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 10 (edge cases) = 35
        assert result.score == 35
        edge_gaps = [g for g in result.gaps if g.field == "edge_cases"]
        assert len(edge_gaps) == 0

    def test_edge_cases_none_when_components_exist(self) -> None:
        """No edge cases when components exist scores 0 points, creates IMPORTANT gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(name="comp1", purpose="test"),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) = 25
        assert result.score == 25
        gap = next(g for g in result.gaps if g.field == "edge_cases")
        assert gap.severity == GapSeverity.IMPORTANT

    def test_edge_cases_no_gap_when_no_components(self) -> None:
        """No edge case gap when no components exist (component gap covers this)."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[],  # No components
        )

        result = validate_spec(spec)

        # Should not have edge_cases gap, only components gap
        edge_gaps = [g for g in result.gaps if g.field == "edge_cases"]
        assert len(edge_gaps) == 0

    def test_out_of_scope_present(self) -> None:
        """Out of scope present scores 5 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            out_of_scope=["mobile app"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 5 (out_of_scope) = 20
        assert result.score == 20
        oos_gaps = [g for g in result.gaps if g.field == "out_of_scope"]
        assert len(oos_gaps) == 0

    def test_out_of_scope_empty(self) -> None:
        """No out of scope scores 0 points, creates MINOR gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
        )

        result = validate_spec(spec)

        # 15 (problem) only
        assert result.score == 15
        gap = next(g for g in result.gaps if g.field == "out_of_scope")
        assert gap.severity == GapSeverity.MINOR

    def test_component_success_criteria_all_have_criteria(self) -> None:
        """All components with success criteria scores 10 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    success_criteria=["criterion 1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    success_criteria=["criterion 2"],
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 10 (component criteria) = 35
        assert result.score == 35
        criteria_gaps = [g for g in result.gaps if g.field == "component_success_criteria"]
        assert len(criteria_gaps) == 0

    def test_component_success_criteria_partial(self) -> None:
        """Partial success criteria scores proportional points with IMPORTANT gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    success_criteria=["criterion 1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    # No success criteria
                ),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + round(10 * 0.5) = 15 + 10 + 5 = 30
        assert result.score == 30
        gap = next(g for g in result.gaps if g.field == "component_success_criteria")
        assert gap.severity == GapSeverity.IMPORTANT
        assert "comp2" in gap.description

    def test_component_success_criteria_none_have_criteria(self) -> None:
        """No components with success criteria scores 0 points, creates IMPORTANT gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(name="comp1", purpose="test"),
                SpecComponent(name="comp2", purpose="test"),
            ],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 0 (component criteria) = 25
        assert result.score == 25
        gap = next(g for g in result.gaps if g.field == "component_success_criteria")
        assert gap.severity == GapSeverity.IMPORTANT

    def test_stakeholder_profile_present(self) -> None:
        """Stakeholder profile present scores 5 points, no gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            stakeholder_profile=StakeholderProfile(working_style="terminal-first"),
        )

        result = validate_spec(spec)

        # 15 (problem) + 5 (stakeholder) = 20
        assert result.score == 20
        stakeholder_gaps = [g for g in result.gaps if g.field == "stakeholder_profile"]
        assert len(stakeholder_gaps) == 0

    def test_stakeholder_profile_none(self) -> None:
        """No stakeholder profile scores 0 points, creates MINOR gap."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            stakeholder_profile=None,
        )

        result = validate_spec(spec)

        # 15 (problem) only
        assert result.score == 15
        gap = next(g for g in result.gaps if g.field == "stakeholder_profile")
        assert gap.severity == GapSeverity.MINOR

    def test_boundary_score_exactly_80(self) -> None:
        """Score exactly 80 results in is_complete=True."""
        # Build a spec that scores exactly 80:
        # problem_statement (15) + components (10) + inputs (15) + outputs (15) +
        # success_criteria (10) + constraints (5) + edge_cases (10) = 80
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                ),
            ],
            success_criteria=["criterion 1"],
            constraints=["constraint 1"],
        )

        result = validate_spec(spec)

        assert result.score == 80
        assert result.is_complete is True

    def test_boundary_score_79(self) -> None:
        """Score 79 results in is_complete=False."""
        # Build a spec that scores 79:
        # problem_statement (15) + components (10) + inputs (15) + outputs (15) +
        # success_criteria (10) + edge_cases (10) + out_of_scope (5) - 1 = 79
        # We'll omit constraints (5 points) to get 75, then need to add 4 more
        # Actually, let's use: 15 + 10 + 15 + 15 + 10 + 10 + 5 - 1 = 79
        # Easier: partial component criteria for 4 points
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    inputs=["input2"],
                    outputs=["output2"],
                ),
            ],
            success_criteria=["criterion 1"],
            out_of_scope=["mobile"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 15 (inputs) + 15 (outputs) +
        # 10 (success) + 5 (out_of_scope) + 10 (edge cases) = 80
        # Wait, that's 80. Need to tweak.
        # Let's recalculate: remove out_of_scope to get 75
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                ),
            ],
            success_criteria=["criterion 1"],
            # No constraints (0), no out_of_scope (0), no stakeholder (0)
            # 15 + 10 + 15 + 15 + 10 + 10 = 75
            # Add constraints to get 80, or add stakeholder to get 80
            # To get 79, add partial component criteria
            # Actually easier: use 3 components with 2/3 having success criteria
            # round(10 * 2/3) = round(6.67) = 7 points
        )

        # Restart with cleaner approach for 79:
        # 15 (problem) + 10 (components) + 15 (inputs) + 15 (outputs) +
        # 10 (success) + 5 (constraints) + 10 (edge) = 80
        # To get 79, remove constraints = 75, add stakeholder = 80. Not helpful.
        # Instead: use partial component success criteria
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                    success_criteria=["criterion 1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    inputs=["input2"],
                    outputs=["output2"],
                    success_criteria=["criterion 2"],
                ),
                SpecComponent(
                    name="comp3",
                    purpose="test",
                    inputs=["input3"],
                    outputs=["output3"],
                    # No success criteria
                ),
            ],
            success_criteria=["overall criterion"],
            constraints=["constraint 1"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 15 (inputs) + 15 (outputs) +
        # 10 (success) + 5 (constraints) + 10 (edge) + round(10 * 2/3) =
        # 15 + 10 + 15 + 15 + 10 + 5 + 10 + 7 = 87
        # That's too high. Let me recalculate more carefully.

        # Simpler approach: start with 80, remove 1 point
        # 80 - constraints (5) = 75, add stakeholder (5) = 80
        # To get 79: 75 + round(10 * 0.4) = 75 + 4 = 79
        # Need 2/5 components with success criteria
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                    success_criteria=["criterion 1"],
                ),
                SpecComponent(
                    name="comp2",
                    purpose="test",
                    inputs=["input2"],
                    outputs=["output2"],
                    success_criteria=["criterion 2"],
                ),
                SpecComponent(
                    name="comp3",
                    purpose="test",
                    inputs=["input3"],
                    outputs=["output3"],
                ),
                SpecComponent(
                    name="comp4",
                    purpose="test",
                    inputs=["input4"],
                    outputs=["output4"],
                ),
                SpecComponent(
                    name="comp5",
                    purpose="test",
                    inputs=["input5"],
                    outputs=["output5"],
                ),
            ],
            success_criteria=["overall criterion"],
        )

        result = validate_spec(spec)

        # 15 (problem) + 10 (components) + 15 (inputs) + 15 (outputs) +
        # 10 (success) + 10 (edge) + round(10 * 0.4) =
        # 15 + 10 + 15 + 15 + 10 + 10 + 4 = 79
        assert result.score == 79
        assert result.is_complete is False

    def test_suggestions_critical_gaps(self) -> None:
        """Suggestions include critical gap message when critical gaps exist."""
        spec = InterviewSpec(name="test")  # No problem statement, no components

        result = validate_spec(spec)

        assert any("critical gap" in s for s in result.suggestions)

    def test_suggestions_important_gaps(self) -> None:
        """Suggestions include important gap message when important gaps exist."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input"],
                    outputs=["output"],
                )
            ],
            # No success criteria = IMPORTANT gap
        )

        result = validate_spec(spec)

        assert any("important gap" in s for s in result.suggestions)

    def test_suggestions_meets_threshold_with_gaps(self) -> None:
        """Suggestions include 'meets threshold' message when score >= 80 but gaps remain."""
        spec = InterviewSpec(
            name="test",
            problem_statement="sufficient problem statement",
            components=[
                SpecComponent(
                    name="comp1",
                    purpose="test",
                    inputs=["input1"],
                    outputs=["output1"],
                    edge_cases=["edge1"],
                ),
            ],
            success_criteria=["criterion 1"],
            constraints=["constraint 1"],
            # Score = 80, but missing out_of_scope, stakeholder, component criteria = gaps
        )

        result = validate_spec(spec)

        assert result.score == 80
        assert len(result.gaps) > 0
        assert any("meets the completeness threshold" in s for s in result.suggestions)

    def test_gap_severity_filtering(self) -> None:
        """CompletenessResult properties filter gaps by severity."""
        spec = InterviewSpec(
            name="test",
            # Missing problem statement = CRITICAL
            # Missing components = CRITICAL
            # Missing success_criteria = IMPORTANT
            # Missing constraints = MINOR
            # Missing out_of_scope = MINOR
            # Missing stakeholder = MINOR
        )

        result = validate_spec(spec)

        assert len(result.critical_gaps) == 2  # problem_statement, components
        assert len(result.important_gaps) == 1  # success_criteria
        assert len(result.minor_gaps) == 3  # constraints, out_of_scope, stakeholder


class TestValidateSpecFile:
    """Tests for validate_spec_file function."""

    def test_valid_json_file(self, tmp_path: Path) -> None:
        """Valid JSON file is loaded and validated correctly."""
        spec = InterviewSpec(
            name="Test Project",
            problem_statement="This is a test problem statement that is sufficiently long",
            components=[
                SpecComponent(
                    name="Component A",
                    purpose="Test component",
                    inputs=["input1"],
                    outputs=["output1"],
                )
            ],
        )

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

        result = validate_spec_file(spec_file)

        # Should match what validate_spec would return
        assert result.score > 0
        assert isinstance(result.score, int)

    def test_non_existent_file(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        spec_file = tmp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError, match="Spec file not found"):
            validate_spec_file(spec_file)

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON raises ValueError with 'Invalid JSON' message."""
        spec_file = tmp_path / "invalid.json"
        spec_file.write_text("{ this is not valid JSON }", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid JSON"):
            validate_spec_file(spec_file)

    def test_valid_json_wrong_schema(self, tmp_path: Path) -> None:
        """Valid JSON but wrong schema raises ValueError with 'doesn't match' message."""
        spec_file = tmp_path / "wrong_schema.json"
        spec_file.write_text(
            json.dumps({"wrong_field": "value", "not_a_spec": True}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="doesn't match"):
            validate_spec_file(spec_file)
