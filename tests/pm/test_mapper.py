"""Unit tests for spec-to-tickets mapper."""

from __future__ import annotations

from imp.interview.models import InterviewSpec, SpecComponent
from imp.pm.mapper import spec_to_tickets
from imp.pm.models import TicketPriority


def test_empty_spec_with_parent() -> None:
    """Empty spec with create_parent=True should create 1 parent ticket."""
    spec = InterviewSpec(name="Test Project")
    tickets = spec_to_tickets(spec, create_parent=True)
    assert len(tickets) == 1
    assert tickets[0].title == "Test Project"


def test_empty_spec_without_parent() -> None:
    """Empty spec with create_parent=False should create 0 tickets."""
    spec = InterviewSpec(name="Test Project")
    tickets = spec_to_tickets(spec, create_parent=False)
    assert len(tickets) == 0


def test_one_component_with_parent() -> None:
    """Spec with 1 component and create_parent=True should create 2 tickets."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    assert len(tickets) == 2
    assert tickets[0].title == "Test Project"
    assert tickets[1].title == "Component A"


def test_one_component_without_parent() -> None:
    """Spec with 1 component and create_parent=False should create 1 ticket."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)
    assert len(tickets) == 1
    assert tickets[0].title == "Component A"


def test_three_components_with_parent() -> None:
    """Spec with 3 components should create 4 tickets (parent + 3 components)."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
            SpecComponent(name="Component B", purpose="Does B things"),
            SpecComponent(name="Component C", purpose="Does C things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    assert len(tickets) == 4
    assert tickets[0].title == "Test Project"
    assert tickets[1].title == "Component A"
    assert tickets[2].title == "Component B"
    assert tickets[3].title == "Component C"


def test_custom_default_priority() -> None:
    """Custom default_priority should propagate to all tickets."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True, default_priority=TicketPriority.URGENT)
    assert all(t.priority == TicketPriority.URGENT for t in tickets)


def test_parent_ticket_title() -> None:
    """Parent ticket title should match spec.name."""
    spec = InterviewSpec(name="My Awesome Project")
    tickets = spec_to_tickets(spec, create_parent=True)
    assert tickets[0].title == "My Awesome Project"


def test_parent_ticket_description_has_all_sections() -> None:
    """Parent ticket description should contain all 4 Markdown sections."""
    spec = InterviewSpec(
        name="Test Project",
        problem_statement="We need to solve X",
        success_criteria=["Criterion 1", "Criterion 2"],
        out_of_scope=["Thing A", "Thing B"],
        constraints=["Constraint 1"],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    desc = tickets[0].description

    assert "## Problem Statement" in desc
    assert "We need to solve X" in desc
    assert "## Success Criteria" in desc
    assert "- Criterion 1" in desc
    assert "- Criterion 2" in desc
    assert "## Out of Scope" in desc
    assert "- Thing A" in desc
    assert "- Thing B" in desc
    assert "## Constraints" in desc
    assert "- Constraint 1" in desc


def test_component_ticket_title() -> None:
    """Component ticket title should match component.name."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Auth Module", purpose="Handles authentication"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)
    assert tickets[0].title == "Auth Module"


def test_component_ticket_description_has_all_sections() -> None:
    """Component ticket description should contain all 5 Markdown sections."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(
                name="Auth Module",
                purpose="Handles authentication",
                inputs=["Username", "Password"],
                outputs=["JWT Token"],
                edge_cases=["Empty username", "Invalid password"],
                success_criteria=["Can login", "Can logout"],
            ),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)
    desc = tickets[0].description

    assert "## Purpose" in desc
    assert "Handles authentication" in desc
    assert "## Inputs" in desc
    assert "- Username" in desc
    assert "- Password" in desc
    assert "## Outputs" in desc
    assert "- JWT Token" in desc
    assert "## Edge Cases" in desc
    assert "- Empty username" in desc
    assert "- Invalid password" in desc
    assert "## Definition of Done" in desc
    assert "- Can login" in desc
    assert "- Can logout" in desc


def test_traceability_source_spec_name_on_all_tickets() -> None:
    """source_spec_name should be set on all tickets."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    assert all(t.source_spec_name == "Test Project" for t in tickets)


def test_traceability_parent_has_empty_component_name() -> None:
    """Parent ticket should have empty source_component_name."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    parent_ticket = tickets[0]
    assert parent_ticket.source_component_name == ""


def test_traceability_component_has_component_name() -> None:
    """Component ticket should have source_component_name = component.name."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True)
    component_ticket = tickets[1]
    assert component_ticket.source_component_name == "Component A"


def test_component_with_all_fields_populated() -> None:
    """Component with all fields populated should have all sections with content."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(
                name="Full Component",
                purpose="Does everything",
                inputs=["Input A", "Input B"],
                outputs=["Output X", "Output Y"],
                edge_cases=["Edge case 1", "Edge case 2"],
                success_criteria=["Success 1", "Success 2"],
            ),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)
    desc = tickets[0].description

    # All sections should have actual content (not "None specified.")
    assert "- Input A" in desc
    assert "- Input B" in desc
    assert "- Output X" in desc
    assert "- Output Y" in desc
    assert "- Edge case 1" in desc
    assert "- Edge case 2" in desc
    assert "- Success 1" in desc
    assert "- Success 2" in desc
    assert "None specified." not in desc


def test_component_with_minimal_fields() -> None:
    """Component with only name + purpose should show 'None specified.' for empty sections."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Minimal Component", purpose="Does minimal things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)
    desc = tickets[0].description

    assert "## Purpose" in desc
    assert "Does minimal things" in desc
    assert "## Inputs" in desc
    assert "None specified." in desc
    # Count "None specified." (should be 4: inputs, outputs, edge_cases, success_criteria)
    assert desc.count("None specified.") == 4


def test_parent_empty_problem_statement() -> None:
    """Parent with empty problem statement should show 'None specified.'"""
    spec = InterviewSpec(name="Test Project", problem_statement="")
    tickets = spec_to_tickets(spec, create_parent=True)
    desc = tickets[0].description

    assert "## Problem Statement" in desc
    assert "None specified." in desc


def test_parent_empty_success_criteria() -> None:
    """Parent with empty success criteria should show 'None specified.'"""
    spec = InterviewSpec(name="Test Project", success_criteria=[])
    tickets = spec_to_tickets(spec, create_parent=True)
    desc = tickets[0].description

    assert "## Success Criteria" in desc
    assert "None specified." in desc


def test_multiple_components_preserve_order() -> None:
    """Multiple components should preserve order in output tickets."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="First", purpose="First component"),
            SpecComponent(name="Second", purpose="Second component"),
            SpecComponent(name="Third", purpose="Third component"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=False)

    assert len(tickets) == 3
    assert tickets[0].title == "First"
    assert tickets[1].title == "Second"
    assert tickets[2].title == "Third"


def test_urgent_priority_all_tickets() -> None:
    """TicketPriority.URGENT as default should propagate to all tickets."""
    spec = InterviewSpec(
        name="Test Project",
        components=[
            SpecComponent(name="Component A", purpose="Does A things"),
            SpecComponent(name="Component B", purpose="Does B things"),
        ],
    )
    tickets = spec_to_tickets(spec, create_parent=True, default_priority=TicketPriority.URGENT)

    assert len(tickets) == 3
    assert all(t.priority == TicketPriority.URGENT for t in tickets)
