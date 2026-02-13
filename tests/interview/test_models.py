"""Tests for interview spec schema models.

Following three-tier TDD: write all tests BEFORE implementation.
Target: 100% branch coverage.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from imp.interview.models import (
    CompletenessResult,
    GapSeverity,
    InterviewMetadata,
    InterviewMode,
    InterviewSpec,
    SpecComponent,
    SpecGap,
    StakeholderProfile,
)


class TestInterviewMode:
    """Test InterviewMode enum."""

    def test_direct_mode(self) -> None:
        """DIRECT mode is defined."""
        assert InterviewMode.DIRECT == "direct"

    def test_gap_analysis_mode(self) -> None:
        """GAP_ANALYSIS mode is defined."""
        assert InterviewMode.GAP_ANALYSIS == "gap_analysis"

    def test_modes_are_strings(self) -> None:
        """Mode values are strings for JSON serialization."""
        for mode in InterviewMode:
            assert isinstance(mode.value, str)


class TestGapSeverity:
    """Test GapSeverity enum."""

    def test_critical_severity(self) -> None:
        """CRITICAL severity is defined."""
        assert GapSeverity.CRITICAL == "critical"

    def test_important_severity(self) -> None:
        """IMPORTANT severity is defined."""
        assert GapSeverity.IMPORTANT == "important"

    def test_minor_severity(self) -> None:
        """MINOR severity is defined."""
        assert GapSeverity.MINOR == "minor"

    def test_severities_are_strings(self) -> None:
        """Severity values are strings for JSON serialization."""
        for severity in GapSeverity:
            assert isinstance(severity.value, str)


class TestSpecComponent:
    """Test SpecComponent model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create component with all fields populated."""
        component = SpecComponent(
            name="Authentication Service",
            purpose="Handle user login and session management",
            inputs=["username", "password", "session token"],
            outputs=["authenticated user object", "session cookie"],
            constraints=["Must support 2FA", "Session timeout after 30 minutes"],
            edge_cases=["Empty password", "Already logged in user"],
            success_criteria=[
                "User can log in successfully",
                "Session persists across page reloads",
            ],
        )
        assert component.name == "Authentication Service"
        assert component.purpose == "Handle user login and session management"
        assert len(component.inputs) == 3
        assert len(component.outputs) == 2
        assert len(component.constraints) == 2
        assert len(component.edge_cases) == 2
        assert len(component.success_criteria) == 2

    def test_creation_with_required_fields_only(self) -> None:
        """Can create component with only required fields (name and purpose)."""
        component = SpecComponent(
            name="Minimal Component",
            purpose="Does something useful",
        )
        assert component.name == "Minimal Component"
        assert component.purpose == "Does something useful"
        assert component.inputs == []
        assert component.outputs == []
        assert component.constraints == []
        assert component.edge_cases == []
        assert component.success_criteria == []

    def test_immutability(self) -> None:
        """SpecComponent is frozen."""
        component = SpecComponent(name="Test", purpose="Test purpose")
        with pytest.raises(ValidationError):
            component.name = "Changed"  # type: ignore[misc]

    def test_has_inputs_property_true(self) -> None:
        """has_inputs returns True when inputs are present."""
        component = SpecComponent(
            name="Test",
            purpose="Test",
            inputs=["input1"],
        )
        assert component.has_inputs is True

    def test_has_inputs_property_false(self) -> None:
        """has_inputs returns False when inputs are empty."""
        component = SpecComponent(name="Test", purpose="Test")
        assert component.has_inputs is False

    def test_has_outputs_property_true(self) -> None:
        """has_outputs returns True when outputs are present."""
        component = SpecComponent(
            name="Test",
            purpose="Test",
            outputs=["output1"],
        )
        assert component.has_outputs is True

    def test_has_outputs_property_false(self) -> None:
        """has_outputs returns False when outputs are empty."""
        component = SpecComponent(name="Test", purpose="Test")
        assert component.has_outputs is False

    def test_has_edge_cases_property_true(self) -> None:
        """has_edge_cases returns True when edge cases are present."""
        component = SpecComponent(
            name="Test",
            purpose="Test",
            edge_cases=["edge case 1"],
        )
        assert component.has_edge_cases is True

    def test_has_edge_cases_property_false(self) -> None:
        """has_edge_cases returns False when edge cases are empty."""
        component = SpecComponent(name="Test", purpose="Test")
        assert component.has_edge_cases is False

    def test_has_success_criteria_property_true(self) -> None:
        """has_success_criteria returns True when success criteria are present."""
        component = SpecComponent(
            name="Test",
            purpose="Test",
            success_criteria=["criterion 1"],
        )
        assert component.has_success_criteria is True

    def test_has_success_criteria_property_false(self) -> None:
        """has_success_criteria returns False when success criteria are empty."""
        component = SpecComponent(name="Test", purpose="Test")
        assert component.has_success_criteria is False

    def test_json_serialization_round_trip(self) -> None:
        """SpecComponent can be serialized to JSON and back."""
        component = SpecComponent(
            name="Test Component",
            purpose="Testing serialization",
            inputs=["input1", "input2"],
            outputs=["output1"],
        )
        data = component.model_dump()
        restored = SpecComponent.model_validate(data)
        assert restored.name == component.name
        assert restored.purpose == component.purpose
        assert restored.inputs == component.inputs
        assert restored.outputs == component.outputs


class TestStakeholderProfile:
    """Test StakeholderProfile model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create profile with all fields populated."""
        profile = StakeholderProfile(
            working_style="Terminal-first, IDE-based development",
            values=["efficiency", "quality", "maintainability"],
            pain_points=["Re-explaining errors to AI", "Context loss"],
            priorities=["Minimal typing", "High autonomy"],
            technical_preferences=["Python", "TypeScript", "TDD"],
        )
        assert profile.working_style == "Terminal-first, IDE-based development"
        assert len(profile.values) == 3
        assert len(profile.pain_points) == 2
        assert len(profile.priorities) == 2
        assert len(profile.technical_preferences) == 3

    def test_creation_with_no_fields(self) -> None:
        """Can create profile with no fields (all optional/defaults)."""
        profile = StakeholderProfile()
        assert profile.working_style is None
        assert profile.values == []
        assert profile.pain_points == []
        assert profile.priorities == []
        assert profile.technical_preferences == []

    def test_immutability(self) -> None:
        """StakeholderProfile is frozen."""
        profile = StakeholderProfile()
        with pytest.raises(ValidationError):
            profile.working_style = "Changed"  # type: ignore[misc]

    def test_json_serialization_round_trip(self) -> None:
        """StakeholderProfile can be serialized to JSON and back."""
        profile = StakeholderProfile(
            working_style="CLI-focused",
            values=["speed", "accuracy"],
        )
        data = profile.model_dump()
        restored = StakeholderProfile.model_validate(data)
        assert restored.working_style == profile.working_style
        assert restored.values == profile.values


class TestInterviewMetadata:
    """Test InterviewMetadata model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create metadata with all fields populated."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=85,
            domain="software-requirements",
            question_count=42,
        )
        assert metadata.interview_date == date(2026, 2, 13)
        assert metadata.mode == InterviewMode.DIRECT
        assert metadata.completeness_score == 85
        assert metadata.domain == "software-requirements"
        assert metadata.question_count == 42

    def test_optional_domain_defaults_to_none(self) -> None:
        """domain field defaults to None when not provided."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.GAP_ANALYSIS,
            completeness_score=75,
            question_count=10,
        )
        assert metadata.domain is None

    def test_completeness_score_validation_zero_valid(self) -> None:
        """completeness_score of 0 is valid."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=0,
            question_count=0,
        )
        assert metadata.completeness_score == 0

    def test_completeness_score_validation_hundred_valid(self) -> None:
        """completeness_score of 100 is valid."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=100,
            question_count=50,
        )
        assert metadata.completeness_score == 100

    def test_completeness_score_validation_negative_raises(self) -> None:
        """completeness_score of -1 raises ValidationError."""
        with pytest.raises(ValidationError):
            InterviewMetadata(
                interview_date=date(2026, 2, 13),
                mode=InterviewMode.DIRECT,
                completeness_score=-1,
                question_count=10,
            )

    def test_completeness_score_validation_over_hundred_raises(self) -> None:
        """completeness_score of 101 raises ValidationError."""
        with pytest.raises(ValidationError):
            InterviewMetadata(
                interview_date=date(2026, 2, 13),
                mode=InterviewMode.DIRECT,
                completeness_score=101,
                question_count=10,
            )

    def test_question_count_validation_zero_valid(self) -> None:
        """question_count of 0 is valid."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=50,
            question_count=0,
        )
        assert metadata.question_count == 0

    def test_question_count_validation_negative_raises(self) -> None:
        """question_count negative value raises ValidationError."""
        with pytest.raises(ValidationError):
            InterviewMetadata(
                interview_date=date(2026, 2, 13),
                mode=InterviewMode.DIRECT,
                completeness_score=50,
                question_count=-1,
            )

    def test_immutability(self) -> None:
        """InterviewMetadata is frozen."""
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=80,
            question_count=20,
        )
        with pytest.raises(ValidationError):
            metadata.completeness_score = 90  # type: ignore[misc]


class TestInterviewSpec:
    """Test InterviewSpec model."""

    def test_creation_with_all_fields_populated(self) -> None:
        """Can create spec with all fields populated."""
        component = SpecComponent(name="Component 1", purpose="Purpose 1")
        profile = StakeholderProfile(working_style="Terminal-first")
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=90,
            question_count=30,
        )
        spec = InterviewSpec(
            name="Test Project",
            problem_statement="Building a workflow automation tool",
            system_overview="AI-powered engineering workflow system",
            components=[component],
            success_criteria=["System works end-to-end"],
            out_of_scope=["Mobile app support"],
            constraints=["Must be open source"],
            stakeholder_profile=profile,
            metadata=metadata,
        )
        assert spec.name == "Test Project"
        assert spec.problem_statement == "Building a workflow automation tool"
        assert spec.system_overview == "AI-powered engineering workflow system"
        assert len(spec.components) == 1
        assert len(spec.success_criteria) == 1
        assert len(spec.out_of_scope) == 1
        assert len(spec.constraints) == 1
        assert spec.stakeholder_profile is not None
        assert spec.metadata is not None

    def test_creation_with_only_name(self) -> None:
        """Can create spec with only name (minimal - everything else has defaults)."""
        spec = InterviewSpec(name="Minimal Spec")
        assert spec.name == "Minimal Spec"
        assert spec.problem_statement == ""
        assert spec.system_overview is None
        assert spec.components == []
        assert spec.success_criteria == []
        assert spec.out_of_scope == []
        assert spec.constraints == []
        assert spec.stakeholder_profile is None
        assert spec.metadata is None

    def test_component_count_property(self) -> None:
        """component_count returns the number of components."""
        comp1 = SpecComponent(name="C1", purpose="P1")
        comp2 = SpecComponent(name="C2", purpose="P2")
        spec = InterviewSpec(name="Test", components=[comp1, comp2])
        assert spec.component_count == 2

        spec_empty = InterviewSpec(name="Test")
        assert spec_empty.component_count == 0

    def test_components_with_inputs_property(self) -> None:
        """components_with_inputs filters correctly."""
        comp_with_inputs = SpecComponent(name="C1", purpose="P1", inputs=["input1"])
        comp_without_inputs = SpecComponent(name="C2", purpose="P2")
        spec = InterviewSpec(name="Test", components=[comp_with_inputs, comp_without_inputs])
        result = spec.components_with_inputs
        assert len(result) == 1
        assert result[0].name == "C1"

    def test_components_with_outputs_property(self) -> None:
        """components_with_outputs filters correctly."""
        comp_with_outputs = SpecComponent(name="C1", purpose="P1", outputs=["output1"])
        comp_without_outputs = SpecComponent(name="C2", purpose="P2")
        spec = InterviewSpec(name="Test", components=[comp_with_outputs, comp_without_outputs])
        result = spec.components_with_outputs
        assert len(result) == 1
        assert result[0].name == "C1"

    def test_components_with_edge_cases_property(self) -> None:
        """components_with_edge_cases filters correctly."""
        comp_with_edges = SpecComponent(name="C1", purpose="P1", edge_cases=["edge1"])
        comp_without_edges = SpecComponent(name="C2", purpose="P2")
        spec = InterviewSpec(name="Test", components=[comp_with_edges, comp_without_edges])
        result = spec.components_with_edge_cases
        assert len(result) == 1
        assert result[0].name == "C1"

    def test_components_with_success_criteria_property(self) -> None:
        """components_with_success_criteria filters correctly."""
        comp_with_criteria = SpecComponent(
            name="C1", purpose="P1", success_criteria=["criterion1"]
        )
        comp_without_criteria = SpecComponent(name="C2", purpose="P2")
        spec = InterviewSpec(name="Test", components=[comp_with_criteria, comp_without_criteria])
        result = spec.components_with_success_criteria
        assert len(result) == 1
        assert result[0].name == "C1"

    def test_has_problem_statement_property_true(self) -> None:
        """has_problem_statement returns True when non-empty."""
        spec = InterviewSpec(name="Test", problem_statement="Real problem here")
        assert spec.has_problem_statement is True

    def test_has_problem_statement_property_false_empty_string(self) -> None:
        """has_problem_statement returns False when empty string."""
        spec = InterviewSpec(name="Test", problem_statement="")
        assert spec.has_problem_statement is False

    def test_has_problem_statement_property_false_whitespace(self) -> None:
        """has_problem_statement returns False when only whitespace."""
        spec = InterviewSpec(name="Test", problem_statement="   \n  \t  ")
        assert spec.has_problem_statement is False

    def test_has_success_criteria_property_true(self) -> None:
        """has_success_criteria returns True when success criteria defined."""
        spec = InterviewSpec(name="Test", success_criteria=["criterion1"])
        assert spec.has_success_criteria is True

    def test_has_success_criteria_property_false(self) -> None:
        """has_success_criteria returns False when success criteria empty."""
        spec = InterviewSpec(name="Test")
        assert spec.has_success_criteria is False

    def test_has_constraints_property_true(self) -> None:
        """has_constraints returns True when constraints identified."""
        spec = InterviewSpec(name="Test", constraints=["constraint1"])
        assert spec.has_constraints is True

    def test_has_constraints_property_false(self) -> None:
        """has_constraints returns False when constraints empty."""
        spec = InterviewSpec(name="Test")
        assert spec.has_constraints is False

    def test_has_out_of_scope_property_true(self) -> None:
        """has_out_of_scope returns True when out-of-scope items defined."""
        spec = InterviewSpec(name="Test", out_of_scope=["feature X"])
        assert spec.has_out_of_scope is True

    def test_has_out_of_scope_property_false(self) -> None:
        """has_out_of_scope returns False when out-of-scope items empty."""
        spec = InterviewSpec(name="Test")
        assert spec.has_out_of_scope is False

    def test_json_serialization_round_trip_with_nested_models(self) -> None:
        """InterviewSpec can be serialized to JSON and back with nested models."""
        component = SpecComponent(
            name="Auth",
            purpose="Authentication",
            inputs=["username", "password"],
        )
        profile = StakeholderProfile(working_style="CLI", values=["speed"])
        metadata = InterviewMetadata(
            interview_date=date(2026, 2, 13),
            mode=InterviewMode.DIRECT,
            completeness_score=85,
            question_count=25,
        )
        spec = InterviewSpec(
            name="Test Project",
            problem_statement="Solve auth problems",
            components=[component],
            success_criteria=["All tests pass"],
            stakeholder_profile=profile,
            metadata=metadata,
        )
        data = spec.model_dump()
        restored = InterviewSpec.model_validate(data)
        assert restored.name == spec.name
        assert restored.problem_statement == spec.problem_statement
        assert len(restored.components) == 1
        assert restored.components[0].name == "Auth"
        assert restored.stakeholder_profile is not None
        assert restored.stakeholder_profile.working_style == "CLI"
        assert restored.metadata is not None
        assert restored.metadata.completeness_score == 85


class TestSpecGap:
    """Test SpecGap model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create gap with all fields."""
        gap = SpecGap(
            field="problem_statement",
            severity=GapSeverity.CRITICAL,
            description="Problem statement is missing - blocks downstream work",
            suggested_questions=[
                "Tell me about a time when this problem caused you frustration",
                "What would the ideal outcome look like?",
            ],
        )
        assert gap.field == "problem_statement"
        assert gap.severity == GapSeverity.CRITICAL
        assert gap.description == "Problem statement is missing - blocks downstream work"
        assert len(gap.suggested_questions) == 2

    def test_immutability(self) -> None:
        """SpecGap is frozen."""
        gap = SpecGap(
            field="test",
            severity=GapSeverity.MINOR,
            description="test description",
        )
        with pytest.raises(ValidationError):
            gap.severity = GapSeverity.CRITICAL  # type: ignore[misc]

    def test_suggested_questions_defaults_to_empty_list(self) -> None:
        """suggested_questions defaults to empty list."""
        gap = SpecGap(
            field="constraints",
            severity=GapSeverity.MINOR,
            description="No constraints identified",
        )
        assert gap.suggested_questions == []


class TestCompletenessResult:
    """Test CompletenessResult model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create result with all fields."""
        gap1 = SpecGap(
            field="problem_statement",
            severity=GapSeverity.CRITICAL,
            description="Missing problem statement",
        )
        gap2 = SpecGap(
            field="success_criteria",
            severity=GapSeverity.IMPORTANT,
            description="Success criteria incomplete",
        )
        result = CompletenessResult(
            score=65,
            gaps=[gap1, gap2],
            suggestions=["Add more detail to components", "Define edge cases"],
        )
        assert result.score == 65
        assert len(result.gaps) == 2
        assert len(result.suggestions) == 2

    def test_is_complete_property_score_80(self) -> None:
        """is_complete returns True when score is 80."""
        result = CompletenessResult(score=80)
        assert result.is_complete is True

    def test_is_complete_property_score_79(self) -> None:
        """is_complete returns False when score is 79."""
        result = CompletenessResult(score=79)
        assert result.is_complete is False

    def test_is_complete_property_score_100(self) -> None:
        """is_complete returns True when score is 100."""
        result = CompletenessResult(score=100)
        assert result.is_complete is True

    def test_is_complete_property_score_0(self) -> None:
        """is_complete returns False when score is 0."""
        result = CompletenessResult(score=0)
        assert result.is_complete is False

    def test_critical_gaps_property(self) -> None:
        """critical_gaps property filters correctly."""
        gap_critical1 = SpecGap(field="f1", severity=GapSeverity.CRITICAL, description="desc1")
        gap_critical2 = SpecGap(field="f2", severity=GapSeverity.CRITICAL, description="desc2")
        gap_important = SpecGap(field="f3", severity=GapSeverity.IMPORTANT, description="desc3")
        gap_minor = SpecGap(field="f4", severity=GapSeverity.MINOR, description="desc4")
        result = CompletenessResult(
            score=50,
            gaps=[gap_critical1, gap_important, gap_critical2, gap_minor],
        )
        critical = result.critical_gaps
        assert len(critical) == 2
        assert all(g.severity == GapSeverity.CRITICAL for g in critical)

    def test_important_gaps_property(self) -> None:
        """important_gaps property filters correctly."""
        gap_critical = SpecGap(field="f1", severity=GapSeverity.CRITICAL, description="desc1")
        gap_important1 = SpecGap(field="f2", severity=GapSeverity.IMPORTANT, description="desc2")
        gap_important2 = SpecGap(field="f3", severity=GapSeverity.IMPORTANT, description="desc3")
        gap_minor = SpecGap(field="f4", severity=GapSeverity.MINOR, description="desc4")
        result = CompletenessResult(
            score=60,
            gaps=[gap_critical, gap_important1, gap_important2, gap_minor],
        )
        important = result.important_gaps
        assert len(important) == 2
        assert all(g.severity == GapSeverity.IMPORTANT for g in important)

    def test_minor_gaps_property(self) -> None:
        """minor_gaps property filters correctly."""
        gap_critical = SpecGap(field="f1", severity=GapSeverity.CRITICAL, description="desc1")
        gap_important = SpecGap(field="f2", severity=GapSeverity.IMPORTANT, description="desc2")
        gap_minor1 = SpecGap(field="f3", severity=GapSeverity.MINOR, description="desc3")
        gap_minor2 = SpecGap(field="f4", severity=GapSeverity.MINOR, description="desc4")
        result = CompletenessResult(
            score=70,
            gaps=[gap_critical, gap_important, gap_minor1, gap_minor2],
        )
        minor = result.minor_gaps
        assert len(minor) == 2
        assert all(g.severity == GapSeverity.MINOR for g in minor)

    def test_gap_count_property(self) -> None:
        """gap_count returns total number of gaps."""
        gap1 = SpecGap(field="f1", severity=GapSeverity.CRITICAL, description="desc1")
        gap2 = SpecGap(field="f2", severity=GapSeverity.IMPORTANT, description="desc2")
        gap3 = SpecGap(field="f3", severity=GapSeverity.MINOR, description="desc3")
        result = CompletenessResult(score=50, gaps=[gap1, gap2, gap3])
        assert result.gap_count == 3

        result_empty = CompletenessResult(score=100)
        assert result_empty.gap_count == 0

    def test_score_validation_zero_valid(self) -> None:
        """score of 0 is valid."""
        result = CompletenessResult(score=0)
        assert result.score == 0

    def test_score_validation_hundred_valid(self) -> None:
        """score of 100 is valid."""
        result = CompletenessResult(score=100)
        assert result.score == 100

    def test_score_validation_negative_raises(self) -> None:
        """score of -1 raises ValidationError."""
        with pytest.raises(ValidationError):
            CompletenessResult(score=-1)

    def test_score_validation_over_hundred_raises(self) -> None:
        """score of 101 raises ValidationError."""
        with pytest.raises(ValidationError):
            CompletenessResult(score=101)

    def test_empty_gaps_list(self) -> None:
        """Can create result with empty gaps list."""
        result = CompletenessResult(score=100, gaps=[])
        assert result.gaps == []
        assert result.gap_count == 0
        assert result.critical_gaps == []
        assert result.important_gaps == []
        assert result.minor_gaps == []
