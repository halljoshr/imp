"""Interview spec schema models.

The spec schema is the contract — whatever interview method produces the spec,
the output must conform to these models. `imp interview validate` enforces this.
The skill is swappable, the schema is not.

Architecture decided in conversation 021: portable skill + spec schema + validation.
Imp owns the schema and validation, not the conversation.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InterviewMode(StrEnum):
    """Interview operating modes.

    DIRECT: Stakeholder available for conversation, requirements discovery.
    GAP_ANALYSIS: Existing spec provided, identify gaps and generate questions.
    """

    DIRECT = "direct"
    GAP_ANALYSIS = "gap_analysis"


class GapSeverity(StrEnum):
    """Severity of a gap found during spec validation.

    CRITICAL: Missing information that blocks downstream work entirely.
    IMPORTANT: Significant gap that will cause problems but doesn't block.
    MINOR: Nice-to-have information, not strictly required.
    """

    CRITICAL = "critical"
    IMPORTANT = "important"
    MINOR = "minor"


class SpecComponent(BaseModel):
    """A single component or feature in the spec.

    The atomic unit of a requirements specification. Each component must define
    at minimum a name and purpose. Inputs and outputs drive downstream ticket
    generation and validation criteria.
    """

    name: str = Field(description="Component or feature name")
    purpose: str = Field(description="What this component does and why it exists")
    inputs: list[str] = Field(
        default_factory=list,
        description="What data/information this component needs",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="What this component produces",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Technical or business constraints on this component",
    )
    edge_cases: list[str] = Field(
        default_factory=list,
        description="Edge cases discovered through interview stories",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="How we know this component works correctly",
    )

    model_config = ConfigDict(frozen=True)

    @property
    def has_inputs(self) -> bool:
        """Check if inputs are defined."""
        return len(self.inputs) > 0

    @property
    def has_outputs(self) -> bool:
        """Check if outputs are defined."""
        return len(self.outputs) > 0

    @property
    def has_edge_cases(self) -> bool:
        """Check if edge cases are documented."""
        return len(self.edge_cases) > 0

    @property
    def has_success_criteria(self) -> bool:
        """Check if success criteria are defined."""
        return len(self.success_criteria) > 0


class StakeholderProfile(BaseModel):
    """Lightweight stakeholder profile built during the interview.

    Extracted from responses, not asked directly. Used to adapt question
    phrasing and connect requirements to stakeholder values.
    """

    working_style: str | None = Field(
        default=None,
        description="How the stakeholder works (terminal-first, IDE-based, etc.)",
    )
    values: list[str] = Field(
        default_factory=list,
        description="What the stakeholder values (efficiency, quality, cost, etc.)",
    )
    pain_points: list[str] = Field(
        default_factory=list,
        description="What frustrates the stakeholder most",
    )
    priorities: list[str] = Field(
        default_factory=list,
        description="What matters most vs. least",
    )
    technical_preferences: list[str] = Field(
        default_factory=list,
        description="Preferred languages, tools, patterns",
    )

    model_config = ConfigDict(frozen=True)


class InterviewMetadata(BaseModel):
    """Metadata about the interview that produced this spec."""

    interview_date: date = Field(description="Date the interview was conducted")
    mode: InterviewMode = Field(description="Interview mode used (direct or gap_analysis)")
    completeness_score: int = Field(
        ge=0,
        le=100,
        description="Completeness score at conclusion (0-100)",
    )
    domain: str | None = Field(
        default=None,
        description="Domain library used (e.g., 'software-requirements')",
    )
    question_count: int = Field(
        ge=0,
        description="Number of questions asked during the interview",
    )

    model_config = ConfigDict(frozen=True)


class InterviewSpec(BaseModel):
    """The full structured spec output from an interview.

    This is THE contract — all downstream modules (PM tickets, review criteria,
    coding agent specs) consume this schema. Whatever interview method produced it,
    the output must conform to this shape.

    Validated by `imp interview validate`. Imported by `imp interview import`.
    """

    name: str = Field(description="Project or feature name")
    problem_statement: str = Field(
        default="",
        description="Core problem being solved, ideally from interview stories",
    )
    system_overview: str | None = Field(
        default=None,
        description="High-level description of the system or feature",
    )
    components: list[SpecComponent] = Field(
        default_factory=list,
        description="Components/features that make up the spec",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Spec-level success criteria (how we know the whole thing works)",
    )
    out_of_scope: list[str] = Field(
        default_factory=list,
        description="What's explicitly excluded from this spec",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Technical, business, or compliance constraints",
    )
    stakeholder_profile: StakeholderProfile | None = Field(
        default=None,
        description="Profile of the stakeholder built during interview",
    )
    metadata: InterviewMetadata | None = Field(
        default=None,
        description="Metadata about the interview process",
    )

    @property
    def component_count(self) -> int:
        """Number of components in the spec."""
        return len(self.components)

    @property
    def components_with_inputs(self) -> list[SpecComponent]:
        """Components that have inputs defined."""
        return [c for c in self.components if c.has_inputs]

    @property
    def components_with_outputs(self) -> list[SpecComponent]:
        """Components that have outputs defined."""
        return [c for c in self.components if c.has_outputs]

    @property
    def components_with_edge_cases(self) -> list[SpecComponent]:
        """Components that have edge cases documented."""
        return [c for c in self.components if c.has_edge_cases]

    @property
    def components_with_success_criteria(self) -> list[SpecComponent]:
        """Components that have success criteria defined."""
        return [c for c in self.components if c.has_success_criteria]

    @property
    def has_problem_statement(self) -> bool:
        """Check if a meaningful problem statement is defined."""
        return len(self.problem_statement.strip()) > 0

    @property
    def has_success_criteria(self) -> bool:
        """Check if spec-level success criteria are defined."""
        return len(self.success_criteria) > 0

    @property
    def has_constraints(self) -> bool:
        """Check if constraints are identified."""
        return len(self.constraints) > 0

    @property
    def has_out_of_scope(self) -> bool:
        """Check if out-of-scope items are defined."""
        return len(self.out_of_scope) > 0


class SpecGap(BaseModel):
    """A specific gap identified during spec validation.

    Each gap includes suggested story-based questions to fill it,
    following the Teresa Torres methodology.
    """

    field: str = Field(description="Which field or area is missing/weak")
    severity: GapSeverity = Field(description="How critical this gap is")
    description: str = Field(description="What's missing and why it matters")
    suggested_questions: list[str] = Field(
        default_factory=list,
        description="Story-based questions to fill this gap",
    )

    model_config = ConfigDict(frozen=True)


class CompletenessResult(BaseModel):
    """Output of spec validation — completeness score and identified gaps.

    Score is 0-100 based on weighted criteria. A spec is considered complete
    enough to proceed when score >= 80.
    """

    score: int = Field(ge=0, le=100, description="Completeness score (0-100)")
    gaps: list[SpecGap] = Field(
        default_factory=list,
        description="Identified gaps in the spec",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="General suggestions for improving the spec",
    )

    @property
    def is_complete(self) -> bool:
        """Check if the spec is complete enough to proceed (score >= 80)."""
        return self.score >= 80

    @property
    def critical_gaps(self) -> list[SpecGap]:
        """Get critical gaps that block downstream work."""
        return [g for g in self.gaps if g.severity == GapSeverity.CRITICAL]

    @property
    def important_gaps(self) -> list[SpecGap]:
        """Get important gaps that will cause problems."""
        return [g for g in self.gaps if g.severity == GapSeverity.IMPORTANT]

    @property
    def minor_gaps(self) -> list[SpecGap]:
        """Get minor nice-to-have gaps."""
        return [g for g in self.gaps if g.severity == GapSeverity.MINOR]

    @property
    def gap_count(self) -> int:
        """Total number of gaps found."""
        return len(self.gaps)
