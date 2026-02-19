"""Integration tests for PM layer - full end-to-end workflows.

These tests cover:
- InterviewSpec → mapper → adapter → PlanResult (full workflow)
- Parent-child ticket hierarchy
- Traceability (source_spec_name, source_component_name)
- Error propagation from adapter
- Filter integration
- Priority propagation
- CLI integration (plan_command)

All adapter calls are MOCKED (no real Plane API).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.interview.models import InterviewSpec, SpecComponent
from imp.pm.base import PMError
from imp.pm.cli import plan_command
from imp.pm.mapper import spec_to_tickets
from imp.pm.models import (
    PlaneConfig,
    PlanResult,
    TicketFilter,
    TicketPriority,
    TicketRef,
    TicketStatus,
)
from imp.pm.plane import PlaneAdapter


class TestFullWorkflow:
    """Integration tests for full workflow: spec → mapper → adapter → result."""

    def test_full_workflow_spec_to_plan_result(self) -> None:
        """Test: InterviewSpec → mapper → adapter → PlanResult with parent + 3 components."""
        # Create InterviewSpec with 3 components
        spec = InterviewSpec(
            name="User Authentication System",
            problem_statement="Need secure user login",
            components=[
                SpecComponent(name="Login API", purpose="Handle user login requests"),
                SpecComponent(name="Session Manager", purpose="Manage user sessions"),
                SpecComponent(name="Password Hasher", purpose="Hash and verify passwords"),
            ],
            success_criteria=["Users can log in securely"],
        )

        # Map to tickets
        tickets = spec_to_tickets(spec, create_parent=True, default_priority=TicketPriority.HIGH)

        # Should have 4 tickets (1 parent + 3 components)
        assert len(tickets) == 4
        assert tickets[0].title == "User Authentication System"
        assert tickets[1].title == "Login API"
        assert tickets[2].title == "Session Manager"
        assert tickets[3].title == "Password Hasher"

        # Mock adapter to create tickets
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            # Mock create responses
            mock_client.work_items.create.side_effect = [
                {"id": "parent-id", "identifier": "AUTH-1"},
                {"id": "comp-1-id", "identifier": "AUTH-2"},
                {"id": "comp-2-id", "identifier": "AUTH-3"},
                {"id": "comp-3-id", "identifier": "AUTH-4"},
            ]

            adapter = PlaneAdapter(config)

            # Create parent ticket
            parent_ref = adapter.create_ticket(tickets[0])
            assert parent_ref.ticket_id == "parent-id"
            assert parent_ref.ticket_number == "AUTH-1"

            # Create component tickets with parent_id
            component_refs = []
            for ticket in tickets[1:]:
                child_ticket = ticket.model_copy(update={"parent_id": parent_ref.ticket_id})
                child_ref = adapter.create_ticket(child_ticket)
                component_refs.append(child_ref)

            # Build PlanResult
            result = PlanResult(
                spec_name=spec.name,
                parent_ticket=parent_ref,
                component_tickets=component_refs,
                total_tickets=4,
            )

            # Verify result
            assert result.spec_name == "User Authentication System"
            assert result.parent_ticket is not None
            assert result.parent_ticket.ticket_id == "parent-id"
            assert len(result.component_tickets) == 3
            assert result.total_tickets == 4
            assert result.success is True

    def test_workflow_without_parent_ticket(self) -> None:
        """Test: Workflow with create_parent=False (only component tickets)."""
        spec = InterviewSpec(
            name="Simple Feature",
            components=[
                SpecComponent(name="Task 1", purpose="Do thing 1"),
                SpecComponent(name="Task 2", purpose="Do thing 2"),
            ],
        )

        # Map without parent
        tickets = spec_to_tickets(spec, create_parent=False, default_priority=TicketPriority.LOW)

        # Should have 2 tickets (no parent)
        assert len(tickets) == 2
        assert tickets[0].title == "Task 1"
        assert tickets[1].title == "Task 2"

        # Mock adapter
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.work_items.create.side_effect = [
                {"id": "task-1-id", "identifier": "TASK-1"},
                {"id": "task-2-id", "identifier": "TASK-2"},
            ]

            adapter = PlaneAdapter(config)

            # Create component tickets (no parent)
            refs = [adapter.create_ticket(t) for t in tickets]

            result = PlanResult(
                spec_name=spec.name,
                parent_ticket=None,
                component_tickets=refs,
                total_tickets=len(refs),
            )

            assert result.parent_ticket is None
            assert len(result.component_tickets) == 2
            assert result.total_tickets == 2

    def test_parent_child_hierarchy(self) -> None:
        """Test: Parent ticket created first, then children get parent_id set."""
        spec = InterviewSpec(
            name="Feature X",
            components=[
                SpecComponent(name="Component A", purpose="Purpose A"),
            ],
        )

        tickets = spec_to_tickets(spec, create_parent=True)
        assert len(tickets) == 2

        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.work_items.create.side_effect = [
                {"id": "parent-123", "identifier": "FX-1"},
                {"id": "child-456", "identifier": "FX-2"},
            ]

            adapter = PlaneAdapter(config)

            # Create parent first
            parent_ref = adapter.create_ticket(tickets[0])
            assert parent_ref.ticket_id == "parent-123"

            # Create child with parent_id
            child_ticket = tickets[1].model_copy(update={"parent_id": parent_ref.ticket_id})
            assert child_ticket.parent_id == "parent-123"

            adapter.create_ticket(child_ticket)

            # Verify parent was set in create call
            calls = mock_client.work_items.create.call_args_list
            assert calls[1][1]["data"].parent == "parent-123"

    def test_traceability_round_trip(self) -> None:
        """Test: source_spec_name and source_component_name survive mapping."""
        spec = InterviewSpec(
            name="Traceability Test",
            components=[
                SpecComponent(name="Component Alpha", purpose="Test traceability"),
            ],
        )

        tickets = spec_to_tickets(spec, create_parent=True)

        # Parent ticket
        assert tickets[0].source_spec_name == "Traceability Test"
        assert tickets[0].source_component_name == ""

        # Component ticket
        assert tickets[1].source_spec_name == "Traceability Test"
        assert tickets[1].source_component_name == "Component Alpha"

    def test_empty_spec_no_components(self) -> None:
        """Test: Spec with no components (only parent ticket created)."""
        spec = InterviewSpec(
            name="Empty Spec",
            problem_statement="Just a shell",
            components=[],
        )

        tickets = spec_to_tickets(spec, create_parent=True)

        # Only parent ticket
        assert len(tickets) == 1
        assert tickets[0].title == "Empty Spec"

        # With create_parent=False, no tickets at all
        tickets_no_parent = spec_to_tickets(spec, create_parent=False)
        assert len(tickets_no_parent) == 0


class TestErrorPropagation:
    """Integration tests for error handling across mapper and adapter."""

    def test_adapter_failure_mid_create(self) -> None:
        """Test: Adapter succeeds for parent, fails on second component."""
        spec = InterviewSpec(
            name="Partial Failure Test",
            components=[
                SpecComponent(name="Good Component", purpose="Will succeed"),
                SpecComponent(name="Bad Component", purpose="Will fail"),
            ],
        )

        tickets = spec_to_tickets(spec, create_parent=True)
        assert len(tickets) == 3

        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            # Parent succeeds, first child succeeds, second child fails
            mock_client.work_items.create.side_effect = [
                {"id": "parent-id", "identifier": "P-1"},
                {"id": "child-1-id", "identifier": "P-2"},
                Exception("API error: quota exceeded"),
            ]

            adapter = PlaneAdapter(config)

            # Create parent
            parent_ref = adapter.create_ticket(tickets[0])
            assert parent_ref.ticket_id == "parent-id"

            # Create first child
            child_1 = tickets[1].model_copy(update={"parent_id": parent_ref.ticket_id})
            child_1_ref = adapter.create_ticket(child_1)
            assert child_1_ref.ticket_id == "child-1-id"

            # Create second child - should fail
            child_2 = tickets[2].model_copy(update={"parent_id": parent_ref.ticket_id})
            with pytest.raises(PMError, match="Failed to create ticket"):
                adapter.create_ticket(child_2)


class TestFilterIntegration:
    """Integration tests for ticket filtering."""

    def test_filter_by_status(self) -> None:
        """Test: List tickets with status filter."""
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            # Mock list response
            mock_client.work_items.list.return_value = [
                {
                    "id": "1",
                    "name": "Task 1",
                    "description_html": "",
                    "priority": "medium",
                    "parent": None,
                },
                {
                    "id": "2",
                    "name": "Task 2",
                    "description_html": "",
                    "priority": "medium",
                    "parent": None,
                },
            ]

            adapter = PlaneAdapter(config)

            # List with status filter (client-side filtering)
            filter_obj = TicketFilter(status=[TicketStatus.BACKLOG])
            tickets = adapter.list_tickets(filter_obj)

            # Both tickets have status BACKLOG (default)
            assert len(tickets) == 2

    def test_filter_by_priority(self) -> None:
        """Test: List tickets filtered by priority."""
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.work_items.list.return_value = [
                {
                    "id": "1",
                    "name": "High Priority",
                    "description_html": "",
                    "priority": "high",
                    "parent": None,
                },
                {
                    "id": "2",
                    "name": "Medium Priority",
                    "description_html": "",
                    "priority": "medium",
                    "parent": None,
                },
            ]

            adapter = PlaneAdapter(config)

            # Filter for high priority
            filter_obj = TicketFilter(priority=[TicketPriority.HIGH])
            tickets = adapter.list_tickets(filter_obj)

            assert len(tickets) == 1
            assert tickets[0].priority == TicketPriority.HIGH

    def test_filter_by_parent_id(self) -> None:
        """Test: List tickets filtered by parent_id."""
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.work_items.list.return_value = [
                {
                    "id": "child-1",
                    "name": "Child 1",
                    "description_html": "",
                    "priority": "medium",
                    "parent": "parent-123",
                },
                {
                    "id": "child-2",
                    "name": "Child 2",
                    "description_html": "",
                    "priority": "medium",
                    "parent": "parent-456",
                },
            ]

            adapter = PlaneAdapter(config)

            # Filter for children of parent-123
            filter_obj = TicketFilter(parent_id="parent-123")
            tickets = adapter.list_tickets(filter_obj)

            assert len(tickets) == 1
            assert tickets[0].parent_id == "parent-123"


class TestPriorityPropagation:
    """Integration tests for priority propagation through mapper to adapter."""

    def test_urgent_priority_end_to_end(self) -> None:
        """Test: URGENT priority set on spec flows through to all tickets."""
        spec = InterviewSpec(
            name="Critical Feature",
            components=[
                SpecComponent(name="Fix 1", purpose="Urgent fix"),
            ],
        )

        # Map with URGENT priority
        tickets = spec_to_tickets(spec, create_parent=True, default_priority=TicketPriority.URGENT)

        # All tickets should have URGENT priority
        assert tickets[0].priority == TicketPriority.URGENT
        assert tickets[1].priority == TicketPriority.URGENT

        # Verify adapter maps URGENT to int 4
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="test-ws",
            project_id="test-proj",
        )

        with patch("imp.pm.plane.PlaneClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.work_items.create.return_value = {
                "id": "urgent-id",
                "identifier": "URG-1",
            }

            adapter = PlaneAdapter(config)
            adapter.create_ticket(tickets[0])

            # Verify priority=4 was sent
            call_args = mock_client.work_items.create.call_args
            assert call_args[1]["data"].priority == "urgent"


class TestSpecRichContent:
    """Integration tests for specs with all fields populated."""

    def test_spec_with_all_fields(self) -> None:
        """Test: Spec with all fields populated generates rich ticket descriptions."""
        spec = InterviewSpec(
            name="Full Spec Test",
            problem_statement="We need a comprehensive solution",
            components=[
                SpecComponent(
                    name="Rich Component",
                    purpose="Demonstrate all fields",
                    inputs=["User input", "Config file"],
                    outputs=["Report", "Logs"],
                    edge_cases=["Empty input", "Malformed config"],
                    success_criteria=["All tests pass", "Performance under 100ms"],
                ),
            ],
            success_criteria=["System deployed", "Users happy"],
            out_of_scope=["Mobile app", "Internationalization"],
            constraints=["Must use Python 3.12+", "Budget < $10k"],
        )

        tickets = spec_to_tickets(spec, create_parent=True)

        # Parent ticket has 4 sections
        parent_desc = tickets[0].description
        assert "## Problem Statement" in parent_desc
        assert "## Success Criteria" in parent_desc
        assert "## Out of Scope" in parent_desc
        assert "## Constraints" in parent_desc
        assert "We need a comprehensive solution" in parent_desc
        assert "System deployed" in parent_desc
        assert "Mobile app" in parent_desc
        assert "Python 3.12+" in parent_desc

        # Component ticket has 5 sections
        comp_desc = tickets[1].description
        assert "## Purpose" in comp_desc
        assert "## Inputs" in comp_desc
        assert "## Outputs" in comp_desc
        assert "## Edge Cases" in comp_desc
        assert "## Definition of Done" in comp_desc
        assert "Demonstrate all fields" in comp_desc
        assert "User input" in comp_desc
        assert "Report" in comp_desc
        assert "Empty input" in comp_desc
        assert "All tests pass" in comp_desc


class TestPlanResultSerialization:
    """Integration tests for PlanResult JSON serialization."""

    def test_plan_result_json_round_trip(self) -> None:
        """Test: PlanResult → JSON → PlanResult preserves all data."""
        original = PlanResult(
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

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = PlanResult.model_validate_json(json_str)

        # Verify equality
        assert restored.spec_name == original.spec_name
        assert restored.parent_ticket == original.parent_ticket
        assert restored.component_tickets == original.component_tickets
        assert restored.total_tickets == original.total_tickets
        assert restored.success == original.success


class TestCLIIntegration:
    """Integration tests for plan_command CLI function."""

    def test_plan_command_end_to_end(self, tmp_path: Path) -> None:
        """Test: plan_command with real spec file, mocked adapter."""
        # Create spec file
        spec_file = tmp_path / "test_spec.json"
        spec_json = """
{
  "name": "CLI Test Feature",
  "problem_statement": "Test CLI integration",
  "components": [
    {
      "name": "Component 1",
      "purpose": "First component"
    }
  ]
}
"""
        spec_file.write_text(spec_json)

        # Mock PlaneConfig.from_env and PlaneAdapter
        with (
            patch("imp.pm.cli.PlaneConfig.from_env") as mock_config_from_env,
            patch("imp.pm.cli.PlaneAdapter") as MockAdapter,
        ):
            mock_config = PlaneConfig(
                api_key="test-key",
                workspace_slug="test-ws",
                project_id="test-proj",
            )
            mock_config_from_env.return_value = mock_config

            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter

            # Mock create_ticket responses
            mock_adapter.create_ticket.side_effect = [
                TicketRef(ticket_id="parent-id", ticket_number="CLI-1", url="http://test/CLI-1"),
                TicketRef(ticket_id="child-id", ticket_number="CLI-2", url="http://test/CLI-2"),
            ]

            # Run plan_command (use tmp_path as project_root to avoid stale receipts)
            exit_code = plan_command(
                spec_file=spec_file,
                provider="plane",
                create_parent=True,
                default_priority="medium",
                format="json",
                project_root=tmp_path,
            )

            # Verify success
            assert exit_code == 0

    def test_plan_command_invalid_file(self, tmp_path: Path) -> None:
        """Test: plan_command with non-existent file returns error."""
        bad_file = tmp_path / "does_not_exist.json"

        exit_code = plan_command(
            spec_file=bad_file,
            provider="plane",
            create_parent=True,
            default_priority="medium",
            format="json",
        )

        # Should return 1 (error)
        assert exit_code == 1
