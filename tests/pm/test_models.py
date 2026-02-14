"""Tests for PM models.

Following three-tier TDD: write all tests BEFORE implementation.
Target: 100% branch coverage.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from imp.pm.models import (
    PlaneConfig,
    PlanResult,
    Ticket,
    TicketFilter,
    TicketPriority,
    TicketRef,
    TicketSpec,
    TicketStatus,
)


class TestTicketStatus:
    """Test TicketStatus enum."""

    def test_backlog_status(self) -> None:
        """BACKLOG status is defined."""
        assert TicketStatus.BACKLOG == "backlog"

    def test_todo_status(self) -> None:
        """TODO status is defined."""
        assert TicketStatus.TODO == "todo"

    def test_in_progress_status(self) -> None:
        """IN_PROGRESS status is defined."""
        assert TicketStatus.IN_PROGRESS == "in_progress"

    def test_in_review_status(self) -> None:
        """IN_REVIEW status is defined."""
        assert TicketStatus.IN_REVIEW == "in_review"

    def test_done_status(self) -> None:
        """DONE status is defined."""
        assert TicketStatus.DONE == "done"

    def test_cancelled_status(self) -> None:
        """CANCELLED status is defined."""
        assert TicketStatus.CANCELLED == "cancelled"

    def test_statuses_are_strings(self) -> None:
        """Status values are strings for JSON serialization."""
        for status in TicketStatus:
            assert isinstance(status.value, str)


class TestTicketPriority:
    """Test TicketPriority enum."""

    def test_none_priority(self) -> None:
        """NONE priority is defined."""
        assert TicketPriority.NONE == "none"

    def test_low_priority(self) -> None:
        """LOW priority is defined."""
        assert TicketPriority.LOW == "low"

    def test_medium_priority(self) -> None:
        """MEDIUM priority is defined."""
        assert TicketPriority.MEDIUM == "medium"

    def test_high_priority(self) -> None:
        """HIGH priority is defined."""
        assert TicketPriority.HIGH == "high"

    def test_urgent_priority(self) -> None:
        """URGENT priority is defined."""
        assert TicketPriority.URGENT == "urgent"

    def test_priorities_are_strings(self) -> None:
        """Priority values are strings for JSON serialization."""
        for priority in TicketPriority:
            assert isinstance(priority.value, str)


class TestPlaneConfig:
    """Test PlaneConfig model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create config with all fields."""
        config = PlaneConfig(
            api_key="test-key-123",
            base_url="https://plane.example.com",
            workspace_slug="my-workspace",
            project_id="proj-456",
            default_priority=TicketPriority.HIGH,
            rate_limit_delay=2.5,
        )
        assert config.api_key == "test-key-123"
        assert config.base_url == "https://plane.example.com"
        assert config.workspace_slug == "my-workspace"
        assert config.project_id == "proj-456"
        assert config.default_priority == TicketPriority.HIGH
        assert config.rate_limit_delay == 2.5

    def test_creation_with_required_fields_only(self) -> None:
        """Can create config with only required fields (defaults apply)."""
        config = PlaneConfig(
            api_key="test-key",
            workspace_slug="workspace",
            project_id="project",
        )
        assert config.api_key == "test-key"
        assert config.base_url == "http://localhost"
        assert config.workspace_slug == "workspace"
        assert config.project_id == "project"
        assert config.default_priority == TicketPriority.MEDIUM
        assert config.rate_limit_delay == 1.0

    def test_mutable(self) -> None:
        """PlaneConfig is mutable (not frozen)."""
        config = PlaneConfig(
            api_key="test",
            workspace_slug="workspace",
            project_id="project",
        )
        config.base_url = "https://new-url.com"
        assert config.base_url == "https://new-url.com"

    def test_from_env_with_all_vars(self) -> None:
        """from_env loads config from environment variables."""
        env = {
            "PLANE_API_KEY": "env-key-123",
            "PLANE_BASE_URL": "https://plane.env.com",
            "PLANE_WORKSPACE_SLUG": "env-workspace",
            "PLANE_PROJECT_ID": "env-project-789",
        }
        with patch.dict(os.environ, env, clear=False):
            config = PlaneConfig.from_env()
            assert config.api_key == "env-key-123"
            assert config.base_url == "https://plane.env.com"
            assert config.workspace_slug == "env-workspace"
            assert config.project_id == "env-project-789"

    def test_from_env_with_minimal_vars(self) -> None:
        """from_env works with minimal required env vars (base_url defaults)."""
        env = {
            "PLANE_API_KEY": "env-key",
            "PLANE_WORKSPACE_SLUG": "env-workspace",
            "PLANE_PROJECT_ID": "env-project",
        }
        with patch.dict(os.environ, env, clear=True):
            config = PlaneConfig.from_env()
            assert config.api_key == "env-key"
            assert config.base_url == "http://localhost"
            assert config.workspace_slug == "env-workspace"
            assert config.project_id == "env-project"

    def test_from_env_missing_api_key_raises(self) -> None:
        """from_env raises ValueError when PLANE_API_KEY is missing."""
        env = {
            "PLANE_WORKSPACE_SLUG": "workspace",
            "PLANE_PROJECT_ID": "project",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="PLANE_API_KEY"),
        ):
            PlaneConfig.from_env()

    def test_from_env_missing_workspace_slug_raises(self) -> None:
        """from_env raises ValueError when PLANE_WORKSPACE_SLUG is missing."""
        env = {
            "PLANE_API_KEY": "key",
            "PLANE_PROJECT_ID": "project",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="PLANE_WORKSPACE_SLUG"),
        ):
            PlaneConfig.from_env()

    def test_from_env_missing_project_id_raises(self) -> None:
        """from_env raises ValueError when PLANE_PROJECT_ID is missing."""
        env = {
            "PLANE_API_KEY": "key",
            "PLANE_WORKSPACE_SLUG": "workspace",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="PLANE_PROJECT_ID"),
        ):
            PlaneConfig.from_env()

    def test_from_env_empty_api_key_raises(self) -> None:
        """from_env raises ValueError when PLANE_API_KEY is empty string."""
        env = {
            "PLANE_API_KEY": "",
            "PLANE_WORKSPACE_SLUG": "workspace",
            "PLANE_PROJECT_ID": "project",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="PLANE_API_KEY"),
        ):
            PlaneConfig.from_env()


class TestTicketSpec:
    """Test TicketSpec model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create spec with all fields."""
        spec = TicketSpec(
            title="Implement authentication",
            description="Add OAuth2 authentication flow",
            priority=TicketPriority.HIGH,
            parent_id="parent-123",
            labels=["auth", "security"],
            estimate_points=8,
            source_spec_name="Auth Feature Spec",
            source_component_name="OAuth2 Component",
        )
        assert spec.title == "Implement authentication"
        assert spec.description == "Add OAuth2 authentication flow"
        assert spec.priority == TicketPriority.HIGH
        assert spec.parent_id == "parent-123"
        assert spec.labels == ["auth", "security"]
        assert spec.estimate_points == 8
        assert spec.source_spec_name == "Auth Feature Spec"
        assert spec.source_component_name == "OAuth2 Component"

    def test_creation_with_title_only(self) -> None:
        """Can create spec with only title (minimal required)."""
        spec = TicketSpec(title="Simple ticket")
        assert spec.title == "Simple ticket"
        assert spec.description == ""
        assert spec.priority == TicketPriority.NONE
        assert spec.parent_id is None
        assert spec.labels == []
        assert spec.estimate_points is None
        assert spec.source_spec_name == ""
        assert spec.source_component_name == ""

    def test_immutability(self) -> None:
        """TicketSpec is frozen."""
        spec = TicketSpec(title="Test")
        with pytest.raises(ValidationError):
            spec.title = "Changed"  # type: ignore[misc]

    def test_json_serialization_round_trip(self) -> None:
        """TicketSpec can be serialized to JSON and back."""
        spec = TicketSpec(
            title="Test ticket",
            description="Test description",
            priority=TicketPriority.MEDIUM,
            labels=["test", "example"],
        )
        data = spec.model_dump()
        restored = TicketSpec.model_validate(data)
        assert restored.title == spec.title
        assert restored.description == spec.description
        assert restored.priority == spec.priority
        assert restored.labels == spec.labels


class TestTicketRef:
    """Test TicketRef model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create ref with all fields."""
        ref = TicketRef(
            ticket_id="ticket-123",
            ticket_number="IMP-42",
            url="https://plane.example.com/workspace/project/issues/IMP-42",
        )
        assert ref.ticket_id == "ticket-123"
        assert ref.ticket_number == "IMP-42"
        assert ref.url == "https://plane.example.com/workspace/project/issues/IMP-42"

    def test_creation_with_ticket_id_only(self) -> None:
        """Can create ref with only ticket_id (minimal required)."""
        ref = TicketRef(ticket_id="ticket-456")
        assert ref.ticket_id == "ticket-456"
        assert ref.ticket_number == ""
        assert ref.url == ""

    def test_immutability(self) -> None:
        """TicketRef is frozen."""
        ref = TicketRef(ticket_id="test-id")
        with pytest.raises(ValidationError):
            ref.ticket_id = "changed"  # type: ignore[misc]

    def test_json_serialization_round_trip(self) -> None:
        """TicketRef can be serialized to JSON and back."""
        ref = TicketRef(
            ticket_id="id-123",
            ticket_number="NUM-1",
            url="https://example.com",
        )
        data = ref.model_dump()
        restored = TicketRef.model_validate(data)
        assert restored.ticket_id == ref.ticket_id
        assert restored.ticket_number == ref.ticket_number
        assert restored.url == ref.url


class TestTicket:
    """Test Ticket model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create ticket with all fields."""
        ticket = Ticket(
            ticket_id="ticket-789",
            title="Fix bug in login",
            description="Users cannot log in with 2FA",
            priority=TicketPriority.URGENT,
            status=TicketStatus.IN_PROGRESS,
            parent_id="parent-456",
            labels=["bug", "auth", "2fa"],
            estimate_points=5,
            assignee_id="user-123",
            url="https://plane.example.com/issues/789",
            source_spec_name="Auth Spec",
            source_component_name="Login Component",
        )
        assert ticket.ticket_id == "ticket-789"
        assert ticket.title == "Fix bug in login"
        assert ticket.description == "Users cannot log in with 2FA"
        assert ticket.priority == TicketPriority.URGENT
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.parent_id == "parent-456"
        assert ticket.labels == ["bug", "auth", "2fa"]
        assert ticket.estimate_points == 5
        assert ticket.assignee_id == "user-123"
        assert ticket.url == "https://plane.example.com/issues/789"
        assert ticket.source_spec_name == "Auth Spec"
        assert ticket.source_component_name == "Login Component"

    def test_creation_with_minimal_fields(self) -> None:
        """Can create ticket with only ticket_id and title (minimal required)."""
        ticket = Ticket(ticket_id="id-1", title="Minimal ticket")
        assert ticket.ticket_id == "id-1"
        assert ticket.title == "Minimal ticket"
        assert ticket.description == ""
        assert ticket.priority == TicketPriority.NONE
        assert ticket.status == TicketStatus.BACKLOG
        assert ticket.parent_id is None
        assert ticket.labels == []
        assert ticket.estimate_points is None
        assert ticket.assignee_id is None
        assert ticket.url == ""
        assert ticket.source_spec_name == ""
        assert ticket.source_component_name == ""

    def test_immutability(self) -> None:
        """Ticket is frozen."""
        ticket = Ticket(ticket_id="test-id", title="Test")
        with pytest.raises(ValidationError):
            ticket.status = TicketStatus.DONE  # type: ignore[misc]

    def test_json_serialization_round_trip(self) -> None:
        """Ticket can be serialized to JSON and back."""
        ticket = Ticket(
            ticket_id="id-999",
            title="Test ticket",
            description="Description here",
            priority=TicketPriority.LOW,
            status=TicketStatus.TODO,
            labels=["test"],
        )
        data = ticket.model_dump()
        restored = Ticket.model_validate(data)
        assert restored.ticket_id == ticket.ticket_id
        assert restored.title == ticket.title
        assert restored.description == ticket.description
        assert restored.priority == ticket.priority
        assert restored.status == ticket.status
        assert restored.labels == ticket.labels


class TestTicketFilter:
    """Test TicketFilter model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create filter with all fields."""
        filter_obj = TicketFilter(
            status=[TicketStatus.TODO, TicketStatus.IN_PROGRESS],
            priority=[TicketPriority.HIGH, TicketPriority.URGENT],
            assignee_id="user-456",
            parent_id="parent-789",
        )
        assert filter_obj.status == [TicketStatus.TODO, TicketStatus.IN_PROGRESS]
        assert filter_obj.priority == [TicketPriority.HIGH, TicketPriority.URGENT]
        assert filter_obj.assignee_id == "user-456"
        assert filter_obj.parent_id == "parent-789"

    def test_creation_with_no_fields(self) -> None:
        """Can create filter with no fields (all optional/defaults)."""
        filter_obj = TicketFilter()
        assert filter_obj.status == []
        assert filter_obj.priority == []
        assert filter_obj.assignee_id is None
        assert filter_obj.parent_id is None

    def test_mutable(self) -> None:
        """TicketFilter is mutable (not frozen)."""
        filter_obj = TicketFilter()
        filter_obj.assignee_id = "new-user"
        assert filter_obj.assignee_id == "new-user"

    def test_json_serialization_round_trip(self) -> None:
        """TicketFilter can be serialized to JSON and back."""
        filter_obj = TicketFilter(
            status=[TicketStatus.DONE],
            priority=[TicketPriority.MEDIUM],
            assignee_id="user-123",
        )
        data = filter_obj.model_dump()
        restored = TicketFilter.model_validate(data)
        assert restored.status == filter_obj.status
        assert restored.priority == filter_obj.priority
        assert restored.assignee_id == filter_obj.assignee_id


class TestPlanResult:
    """Test PlanResult model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create result with all fields."""
        parent_ref = TicketRef(
            ticket_id="parent-123",
            ticket_number="IMP-1",
            url="https://example.com/IMP-1",
        )
        component_ref1 = TicketRef(ticket_id="comp-1", ticket_number="IMP-2")
        component_ref2 = TicketRef(ticket_id="comp-2", ticket_number="IMP-3")
        result = PlanResult(
            spec_name="Auth Feature Spec",
            parent_ticket=parent_ref,
            component_tickets=[component_ref1, component_ref2],
            total_tickets=3,
        )
        assert result.spec_name == "Auth Feature Spec"
        assert result.parent_ticket is not None
        assert result.parent_ticket.ticket_id == "parent-123"
        assert len(result.component_tickets) == 2
        assert result.total_tickets == 3

    def test_creation_with_minimal_fields(self) -> None:
        """Can create result with only spec_name (minimal required)."""
        result = PlanResult(spec_name="Minimal Spec")
        assert result.spec_name == "Minimal Spec"
        assert result.parent_ticket is None
        assert result.component_tickets == []
        assert result.total_tickets == 0

    def test_success_property_true(self) -> None:
        """success returns True when total_tickets > 0."""
        result = PlanResult(spec_name="Test", total_tickets=1)
        assert result.success is True

    def test_success_property_false(self) -> None:
        """success returns False when total_tickets is 0."""
        result = PlanResult(spec_name="Test", total_tickets=0)
        assert result.success is False

    def test_immutability(self) -> None:
        """PlanResult is frozen."""
        result = PlanResult(spec_name="Test", total_tickets=5)
        with pytest.raises(ValidationError):
            result.total_tickets = 10  # type: ignore[misc]

    def test_json_serialization_round_trip(self) -> None:
        """PlanResult can be serialized to JSON and back."""
        parent = TicketRef(ticket_id="parent-id", ticket_number="NUM-1")
        comp1 = TicketRef(ticket_id="comp-1")
        result = PlanResult(
            spec_name="Test Spec",
            parent_ticket=parent,
            component_tickets=[comp1],
            total_tickets=2,
        )
        data = result.model_dump()
        restored = PlanResult.model_validate(data)
        assert restored.spec_name == result.spec_name
        assert restored.parent_ticket is not None
        assert restored.parent_ticket.ticket_id == "parent-id"
        assert len(restored.component_tickets) == 1
        assert restored.total_tickets == 2
