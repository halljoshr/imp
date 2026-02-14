"""Map InterviewSpec to PM tickets."""

from __future__ import annotations

from imp.interview.models import InterviewSpec, SpecComponent
from imp.pm.models import TicketPriority, TicketSpec


def spec_to_tickets(
    spec: InterviewSpec,
    create_parent: bool = True,
    default_priority: TicketPriority = TicketPriority.MEDIUM,
) -> list[TicketSpec]:
    """Transform an InterviewSpec into a list of TicketSpec objects.

    Args:
        spec: The interview spec to transform.
        create_parent: If True, create a parent ticket for the spec.
        default_priority: Default priority for all tickets.

    Returns:
        List of TicketSpec objects (parent first if create_parent=True, then components).
    """
    tickets: list[TicketSpec] = []

    # Create parent ticket if requested
    if create_parent:
        parent_ticket = _create_parent_ticket(spec, default_priority)
        tickets.append(parent_ticket)

    # Create component tickets
    for component in spec.components:
        component_ticket = _create_component_ticket(component, spec.name, default_priority)
        tickets.append(component_ticket)

    return tickets


def _create_parent_ticket(spec: InterviewSpec, default_priority: TicketPriority) -> TicketSpec:
    """Create the parent ticket for a spec."""
    # Build description with 4 sections
    sections = []

    # Problem Statement
    sections.append("## Problem Statement\n")
    if spec.problem_statement and spec.problem_statement.strip():
        sections.append(f"{spec.problem_statement.strip()}\n")
    else:
        sections.append("None specified.\n")

    # Success Criteria
    sections.append("\n## Success Criteria\n")
    if spec.success_criteria:
        for criterion in spec.success_criteria:
            sections.append(f"- {criterion}\n")
    else:
        sections.append("None specified.\n")

    # Out of Scope
    sections.append("\n## Out of Scope\n")
    if spec.out_of_scope:
        for item in spec.out_of_scope:
            sections.append(f"- {item}\n")
    else:
        sections.append("None specified.\n")

    # Constraints
    sections.append("\n## Constraints\n")
    if spec.constraints:
        for constraint in spec.constraints:
            sections.append(f"- {constraint}\n")
    else:
        sections.append("None specified.\n")

    description = "".join(sections)

    return TicketSpec(
        title=spec.name,
        description=description,
        priority=default_priority,
        source_spec_name=spec.name,
        source_component_name="",
    )


def _create_component_ticket(
    component: SpecComponent, spec_name: str, default_priority: TicketPriority
) -> TicketSpec:
    """Create a ticket for a spec component."""
    # Build description with 5 sections
    sections = []

    # Purpose
    sections.append("## Purpose\n")
    sections.append(f"{component.purpose}\n")

    # Inputs
    sections.append("\n## Inputs\n")
    if component.inputs:
        for input_item in component.inputs:
            sections.append(f"- {input_item}\n")
    else:
        sections.append("None specified.\n")

    # Outputs
    sections.append("\n## Outputs\n")
    if component.outputs:
        for output_item in component.outputs:
            sections.append(f"- {output_item}\n")
    else:
        sections.append("None specified.\n")

    # Edge Cases
    sections.append("\n## Edge Cases\n")
    if component.edge_cases:
        for edge_case in component.edge_cases:
            sections.append(f"- {edge_case}\n")
    else:
        sections.append("None specified.\n")

    # Definition of Done
    sections.append("\n## Definition of Done\n")
    if component.success_criteria:
        for criterion in component.success_criteria:
            sections.append(f"- {criterion}\n")
    else:
        sections.append("None specified.\n")

    description = "".join(sections)

    return TicketSpec(
        title=component.name,
        description=description,
        priority=default_priority,
        source_spec_name=spec_name,
        source_component_name=component.name,
    )
