#!/usr/bin/env python3
"""Smoke tests for imp.pm module - validates real usage patterns.

This script tests the PM layer as a real user would use it:
- Imports modules like a developer would
- Creates models and uses mapper
- Validates PlaneAdapter initialization
- Tests serialization/deserialization
- Validates enums and error handling

Run: uv run python tests/smoke/smoke_test_pm.py
Exit code: 0 = pass, 1 = fail

This is NOT a pytest test. This is a smoke test that validates the module
works in the wild, not just in a test harness.
"""

import sys
from pathlib import Path

# Add src to path so we can import imp modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

passed = 0
failed = 0


def smoke_test(name):
    """Decorator to run a smoke test and track pass/fail."""

    def decorator(fn):
        def wrapper():
            global passed, failed
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1

        return wrapper

    return decorator


@smoke_test("Import all public APIs from imp.pm")
def test_imports():
    """Test: Can import all public APIs from imp.pm."""
    from imp.pm import (  # noqa: F401
        PlaneAdapter,
        PlaneConfig,
        PlanResult,
        PMAdapter,
        PMError,
        Ticket,
        TicketFilter,
        TicketPriority,
        TicketRef,
        TicketSpec,
        TicketStatus,
        plan_command,
        spec_to_tickets,
    )


@smoke_test("Construct TicketSpec model")
def test_ticket_spec_construction():
    """Test: Can create TicketSpec with all fields."""
    from imp.pm import TicketPriority, TicketSpec

    spec = TicketSpec(
        title="Test Ticket",
        description="Test description",
        priority=TicketPriority.HIGH,
        parent_id="parent-123",
        labels=["bug", "urgent"],
        estimate_points=5,
        source_spec_name="Test Spec",
        source_component_name="Test Component",
    )

    assert spec.title == "Test Ticket"
    assert spec.priority == TicketPriority.HIGH
    assert spec.parent_id == "parent-123"
    assert len(spec.labels) == 2
    assert spec.estimate_points == 5


@smoke_test("Construct TicketRef model")
def test_ticket_ref_construction():
    """Test: Can create TicketRef."""
    from imp.pm import TicketRef

    ref = TicketRef(
        ticket_id="ticket-123",
        ticket_number="PROJ-42",
        url="http://example.com/PROJ-42",
    )

    assert ref.ticket_id == "ticket-123"
    assert ref.ticket_number == "PROJ-42"
    assert ref.url == "http://example.com/PROJ-42"


@smoke_test("Construct Ticket model")
def test_ticket_construction():
    """Test: Can create Ticket with full details."""
    from imp.pm import Ticket, TicketPriority, TicketStatus

    ticket = Ticket(
        ticket_id="ticket-456",
        title="Full Ticket",
        description="Full description",
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.IN_PROGRESS,
        parent_id="parent-789",
        labels=["feature"],
        estimate_points=8,
        assignee_id="user-123",
        url="http://example.com/ticket-456",
        source_spec_name="Spec Name",
        source_component_name="Component Name",
    )

    assert ticket.ticket_id == "ticket-456"
    assert ticket.status == TicketStatus.IN_PROGRESS
    assert ticket.priority == TicketPriority.MEDIUM


@smoke_test("Construct TicketFilter model")
def test_ticket_filter_construction():
    """Test: Can create TicketFilter."""
    from imp.pm import TicketFilter, TicketPriority, TicketStatus

    filter_obj = TicketFilter(
        status=[TicketStatus.TODO, TicketStatus.IN_PROGRESS],
        priority=[TicketPriority.HIGH, TicketPriority.URGENT],
        assignee_id="user-123",
        parent_id="parent-456",
    )

    assert len(filter_obj.status) == 2
    assert len(filter_obj.priority) == 2
    assert filter_obj.assignee_id == "user-123"


@smoke_test("Construct PlanResult model")
def test_plan_result_construction():
    """Test: Can create PlanResult."""
    from imp.pm import PlanResult, TicketRef

    result = PlanResult(
        spec_name="Test Spec",
        parent_ticket=TicketRef(
            ticket_id="parent-123",
            ticket_number="TEST-1",
            url="http://example.com/TEST-1",
        ),
        component_tickets=[
            TicketRef(
                ticket_id="child-456",
                ticket_number="TEST-2",
                url="http://example.com/TEST-2",
            ),
        ],
        total_tickets=2,
    )

    assert result.spec_name == "Test Spec"
    assert result.parent_ticket is not None
    assert len(result.component_tickets) == 1
    assert result.total_tickets == 2


@smoke_test("Construct PlaneConfig model")
def test_plane_config_construction():
    """Test: Can create PlaneConfig."""
    from imp.pm import PlaneConfig, TicketPriority

    config = PlaneConfig(
        api_key="test-key",
        base_url="http://localhost",
        workspace_slug="test-workspace",
        project_id="test-project",
        default_priority=TicketPriority.HIGH,
        rate_limit_delay=0.5,
    )

    assert config.api_key == "test-key"
    assert config.workspace_slug == "test-workspace"
    assert config.default_priority == TicketPriority.HIGH


@smoke_test("TicketStatus enum has expected values")
def test_ticket_status_enum():
    """Test: TicketStatus enum has all expected values."""
    from imp.pm import TicketStatus

    assert TicketStatus.BACKLOG == "backlog"
    assert TicketStatus.TODO == "todo"
    assert TicketStatus.IN_PROGRESS == "in_progress"
    assert TicketStatus.IN_REVIEW == "in_review"
    assert TicketStatus.DONE == "done"
    assert TicketStatus.CANCELLED == "cancelled"


@smoke_test("TicketPriority enum has expected values")
def test_ticket_priority_enum():
    """Test: TicketPriority enum has all expected values."""
    from imp.pm import TicketPriority

    assert TicketPriority.NONE == "none"
    assert TicketPriority.LOW == "low"
    assert TicketPriority.MEDIUM == "medium"
    assert TicketPriority.HIGH == "high"
    assert TicketPriority.URGENT == "urgent"


@smoke_test("TicketSpec JSON round-trip")
def test_ticket_spec_serialization():
    """Test: TicketSpec can be serialized and deserialized."""
    from imp.pm import TicketPriority, TicketSpec

    original = TicketSpec(
        title="Serialization Test",
        description="Test JSON serialization",
        priority=TicketPriority.MEDIUM,
    )

    # Serialize to JSON
    json_str = original.model_dump_json()

    # Deserialize back
    restored = TicketSpec.model_validate_json(json_str)

    assert restored.title == original.title
    assert restored.description == original.description
    assert restored.priority == original.priority


@smoke_test("PlanResult JSON round-trip")
def test_plan_result_serialization():
    """Test: PlanResult can be serialized and deserialized."""
    from imp.pm import PlanResult, TicketRef

    original = PlanResult(
        spec_name="Serialization Test",
        parent_ticket=TicketRef(
            ticket_id="p-1",
            ticket_number="TEST-1",
            url="http://test/TEST-1",
        ),
        component_tickets=[],
        total_tickets=1,
    )

    # Serialize
    json_str = original.model_dump_json()

    # Deserialize
    restored = PlanResult.model_validate_json(json_str)

    assert restored.spec_name == original.spec_name
    assert restored.parent_ticket == original.parent_ticket
    assert restored.total_tickets == original.total_tickets


@smoke_test("Map InterviewSpec to tickets")
def test_spec_to_tickets():
    """Test: spec_to_tickets transforms InterviewSpec to TicketSpec list."""
    from imp.interview.models import InterviewSpec, SpecComponent
    from imp.pm import TicketPriority, spec_to_tickets

    spec = InterviewSpec(
        name="Test Feature",
        problem_statement="Need to test mapping",
        components=[
            SpecComponent(name="Component 1", purpose="First component"),
            SpecComponent(name="Component 2", purpose="Second component"),
        ],
    )

    # Map to tickets with parent
    tickets = spec_to_tickets(spec, create_parent=True, default_priority=TicketPriority.HIGH)

    assert len(tickets) == 3  # 1 parent + 2 components
    assert tickets[0].title == "Test Feature"
    assert tickets[1].title == "Component 1"
    assert tickets[2].title == "Component 2"
    assert all(t.priority == TicketPriority.HIGH for t in tickets)


@smoke_test("PMAdapter ABC cannot be instantiated")
def test_pm_adapter_abstract():
    """Test: PMAdapter cannot be instantiated directly."""
    from imp.pm import PMAdapter

    try:
        PMAdapter()  # type: ignore
        raise AssertionError("PMAdapter should not be instantiable")
    except TypeError as e:
        assert "abstract" in str(e).lower()


@smoke_test("PMError can be raised and caught")
def test_pm_error():
    """Test: PMError can be raised and caught."""
    from imp.pm import PMError

    try:
        raise PMError("Test error message")
    except PMError as e:
        assert e.message == "Test error message"
        assert str(e) == "Test error message"


@smoke_test("PlaneAdapter import guard (no SDK required)")
def test_plane_adapter_import():
    """Test: PlaneAdapter module can be imported even if plane-sdk not installed."""
    try:
        from imp.pm import PlaneAdapter  # noqa: F401

        # Import should succeed even if plane-sdk is missing
        # The adapter will raise PMError when instantiated without SDK
    except ImportError as e:
        raise AssertionError("PlaneAdapter import should not fail even without plane-sdk") from e


@smoke_test("PlanResult.success property works")
def test_plan_result_success_property():
    """Test: PlanResult.success returns True when total_tickets > 0."""
    from imp.pm import PlanResult, TicketRef

    # Success case
    success_result = PlanResult(
        spec_name="Success Test",
        parent_ticket=TicketRef(
            ticket_id="p-1",
            ticket_number="TEST-1",
            url="http://test/TEST-1",
        ),
        component_tickets=[],
        total_tickets=1,
    )
    assert success_result.success is True

    # Failure case (no tickets)
    failure_result = PlanResult(
        spec_name="Failure Test",
        parent_ticket=None,
        component_tickets=[],
        total_tickets=0,
    )
    assert failure_result.success is False


if __name__ == "__main__":
    print("=" * 60)
    print("PM Module Smoke Tests")
    print("=" * 60)
    print()

    # Run all tests
    test_imports()
    test_ticket_spec_construction()
    test_ticket_ref_construction()
    test_ticket_construction()
    test_ticket_filter_construction()
    test_plan_result_construction()
    test_plane_config_construction()
    test_ticket_status_enum()
    test_ticket_priority_enum()
    test_ticket_spec_serialization()
    test_plan_result_serialization()
    test_spec_to_tickets()
    test_pm_adapter_abstract()
    test_pm_error()
    test_plane_adapter_import()
    test_plan_result_success_property()

    print()
    print("=" * 60)

    if failed == 0:
        print(f"✓ All {passed} smoke tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"✗ {failed} smoke test(s) failed, {passed} passed")
        print("=" * 60)
        sys.exit(1)
