"""Spec completeness validator.

Deterministic scoring algorithm that evaluates an InterviewSpec for completeness.
No AI provider needed — pure logic with weighted criteria.

Scoring breakdown (0-100):
- problem_statement present and non-trivial: 15 points
- At least one component defined: 10 points
- Components have inputs defined: up to 15 points (proportional)
- Components have outputs defined: up to 15 points (proportional)
- Spec-level success criteria: 10 points
- Constraints identified: 5 points
- Edge cases covered (any component): 10 points
- Out of scope defined: 5 points
- Component-level success criteria: 10 points
- Stakeholder profile present: 5 points
"""

from __future__ import annotations

import json
from pathlib import Path

from imp.interview.models import (
    CompletenessResult,
    GapSeverity,
    InterviewSpec,
    SpecGap,
)

# Minimum length for a "non-trivial" problem statement
_MIN_PROBLEM_STATEMENT_LENGTH = 10


def validate_spec(spec: InterviewSpec) -> CompletenessResult:
    """Validate an InterviewSpec for completeness.

    Returns a CompletenessResult with a 0-100 score, identified gaps,
    and suggestions for improvement.
    """
    score = 0
    gaps: list[SpecGap] = []

    # --- problem_statement: 15 points ---
    if (
        spec.has_problem_statement
        and len(spec.problem_statement.strip()) >= _MIN_PROBLEM_STATEMENT_LENGTH
    ):
        score += 15
    else:
        gaps.append(
            SpecGap(
                field="problem_statement",
                severity=GapSeverity.CRITICAL,
                description="Problem statement is missing or too brief. "
                "Downstream modules need a clear problem definition.",
                suggested_questions=[
                    "Tell me about the specific situation that made you realize you need this.",
                    "Walk me through what happens today without this solution.",
                ],
            )
        )

    # --- At least one component: 10 points ---
    has_components = spec.component_count > 0
    if has_components:
        score += 10
    else:
        gaps.append(
            SpecGap(
                field="components",
                severity=GapSeverity.CRITICAL,
                description="No components defined. The spec needs at least one "
                "component with inputs and outputs for ticket generation.",
                suggested_questions=[
                    "What are the main pieces you need to build? Walk me through each one.",
                    "Tell me about the last time you broke a project into parts. "
                    "What were the pieces?",
                ],
            )
        )

    # --- Component inputs: up to 15 points (proportional) ---
    if has_components:
        ratio = len(spec.components_with_inputs) / spec.component_count
        score += round(15 * ratio)
        if ratio < 1.0:
            missing = [c.name for c in spec.components if not c.has_inputs]
            gaps.append(
                SpecGap(
                    field="component_inputs",
                    severity=GapSeverity.CRITICAL,
                    description=f"Components missing inputs: {', '.join(missing)}. "
                    "Each component needs defined inputs for implementation.",
                    suggested_questions=[
                        f"For the {missing[0]} component — what data does it need to do its job?",
                        "Walk me through exactly what information flows into this piece.",
                    ],
                )
            )

    # --- Component outputs: up to 15 points (proportional) ---
    if has_components:
        ratio = len(spec.components_with_outputs) / spec.component_count
        score += round(15 * ratio)
        if ratio < 1.0:
            missing = [c.name for c in spec.components if not c.has_outputs]
            gaps.append(
                SpecGap(
                    field="component_outputs",
                    severity=GapSeverity.CRITICAL,
                    description=f"Components missing outputs: {', '.join(missing)}. "
                    "Each component needs defined outputs for validation.",
                    suggested_questions=[
                        f"For the {missing[0]} component — what does it produce? "
                        "What does the result look like?",
                        "Describe what a successful output from this piece looks like.",
                    ],
                )
            )

    # --- Spec-level success criteria: 10 points ---
    if spec.has_success_criteria:
        score += 10
    else:
        gaps.append(
            SpecGap(
                field="success_criteria",
                severity=GapSeverity.IMPORTANT,
                description="No spec-level success criteria defined. "
                "How do we know the whole thing works?",
                suggested_questions=[
                    "Tell me about a time you shipped something and knew it was done. "
                    "What told you it was working?",
                    "If this works perfectly, what does that look like "
                    "from the user's perspective?",
                ],
            )
        )

    # --- Constraints: 5 points ---
    if spec.has_constraints:
        score += 5
    else:
        gaps.append(
            SpecGap(
                field="constraints",
                severity=GapSeverity.MINOR,
                description="No constraints identified. Technical, business, "
                "or compliance limits help scope the implementation.",
                suggested_questions=[
                    "Tell me about a time a technical limitation forced you "
                    "to change your approach. What was the constraint?",
                ],
            )
        )

    # --- Edge cases (any component): 10 points ---
    if has_components and len(spec.components_with_edge_cases) > 0:
        score += 10
    elif has_components:
        gaps.append(
            SpecGap(
                field="edge_cases",
                severity=GapSeverity.IMPORTANT,
                description="No edge cases documented in any component. "
                "Real-world stories reveal edge cases that specs miss.",
                suggested_questions=[
                    "Tell me about a time something like this broke in an unexpected way. "
                    "What happened?",
                    "Describe a situation where a similar feature didn't work as expected.",
                ],
            )
        )

    # --- Out of scope: 5 points ---
    if spec.has_out_of_scope:
        score += 5
    else:
        gaps.append(
            SpecGap(
                field="out_of_scope",
                severity=GapSeverity.MINOR,
                description="No out-of-scope items defined. Explicit exclusions "
                "prevent scope creep during implementation.",
                suggested_questions=[
                    "What are you explicitly NOT building in this version?",
                ],
            )
        )

    # --- Component-level success criteria: 10 points ---
    if has_components and len(spec.components_with_success_criteria) > 0:
        # Proportional to how many components have criteria
        ratio = len(spec.components_with_success_criteria) / spec.component_count
        score += round(10 * ratio)
        if ratio < 1.0:
            missing = [c.name for c in spec.components if not c.has_success_criteria]
            gaps.append(
                SpecGap(
                    field="component_success_criteria",
                    severity=GapSeverity.IMPORTANT,
                    description=f"Components missing success criteria: {', '.join(missing)}.",
                    suggested_questions=[
                        f"How do we know the {missing[0]} component is working correctly?",
                    ],
                )
            )
    elif has_components:
        gaps.append(
            SpecGap(
                field="component_success_criteria",
                severity=GapSeverity.IMPORTANT,
                description="No component-level success criteria defined anywhere.",
                suggested_questions=[
                    "For each piece, how do we know it's working? "
                    "What does a passing test look like?",
                ],
            )
        )

    # --- Stakeholder profile: 5 points ---
    if spec.stakeholder_profile is not None:
        score += 5
    else:
        gaps.append(
            SpecGap(
                field="stakeholder_profile",
                severity=GapSeverity.MINOR,
                description="No stakeholder profile captured. Understanding the "
                "stakeholder's working style helps tailor the implementation.",
                suggested_questions=[
                    "How do you typically work — terminal, IDE, or something else?",
                ],
            )
        )

    # Build suggestions from gaps
    suggestions: list[str] = []
    critical_count = len([g for g in gaps if g.severity == GapSeverity.CRITICAL])
    important_count = len([g for g in gaps if g.severity == GapSeverity.IMPORTANT])

    if critical_count > 0:
        suggestions.append(
            f"Address {critical_count} critical gap(s) before proceeding — "
            "these block downstream work."
        )
    if important_count > 0:
        suggestions.append(
            f"Consider filling {important_count} important gap(s) for a stronger spec."
        )
    if score >= 80 and len(gaps) > 0:
        suggestions.append(
            "Spec meets the completeness threshold but could be improved "
            "by addressing remaining gaps."
        )
    if score == 100:
        suggestions.append("Spec is fully complete. Ready for ticket generation.")

    # Clamp score to valid range
    score = max(0, min(100, score))

    return CompletenessResult(
        score=score,
        gaps=gaps,
        suggestions=suggestions,
    )


def validate_spec_file(path: Path) -> CompletenessResult:
    """Read a spec file (JSON) and validate it for completeness.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file contains invalid JSON or doesn't match the schema.
    """
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")

    text = path.read_text(encoding="utf-8")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in spec file: {e}") from e

    try:
        spec = InterviewSpec.model_validate(data)
    except Exception as e:
        raise ValueError(f"Spec file doesn't match InterviewSpec schema: {e}") from e

    return validate_spec(spec)
