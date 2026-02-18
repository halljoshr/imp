"""Tests for PM CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.pm.models import PlaneConfig, TicketPriority, TicketRef

# --- Test Fixtures ---


def _write_spec(tmp_path: Path, spec_dict: dict) -> Path:
    """Helper to write a spec dict to a temp JSON file."""
    p = tmp_path / "test_spec.json"
    p.write_text(json.dumps(spec_dict))
    return p


MINIMAL_SPEC = {
    "name": "Test Project",
    "problem_statement": "Test problem",
    "components": [
        {"name": "Component A", "purpose": "Does A things"},
        {"name": "Component B", "purpose": "Does B things"},
    ],
}


# --- Happy Path Tests ---


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_with_parent_success(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command with create_parent=True creates 3 tickets (parent + 2 components)."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    # Write spec file
    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    # Execute
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )

    # Verify
    assert exit_code == 0
    assert mock_adapter.create_ticket.call_count == 3


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_without_parent_success(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command with create_parent=False creates 2 tickets (components only)."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    # Write spec file
    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    # Execute
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=False,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )

    # Verify
    assert exit_code == 0
    assert mock_adapter.create_ticket.call_count == 2


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_sets_parent_id_on_child_tickets(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that child tickets have parent_id set to the parent ticket's ID."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    parent_ref = TicketRef(
        ticket_id="parent-123", ticket_number="IMP-1", url="http://localhost/t-1"
    )
    child1_ref = TicketRef(ticket_id="child-1", ticket_number="IMP-2", url="http://localhost/t-2")
    child2_ref = TicketRef(ticket_id="child-2", ticket_number="IMP-3", url="http://localhost/t-3")
    mock_adapter.create_ticket.side_effect = [parent_ref, child1_ref, child2_ref]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    # Write spec file
    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    # Execute
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )

    # Verify exit code
    assert exit_code == 0

    # Verify parent ticket created first
    first_call_spec = mock_adapter.create_ticket.call_args_list[0][0][0]
    assert first_call_spec.parent_id is None

    # Verify child tickets have parent_id set
    second_call_spec = mock_adapter.create_ticket.call_args_list[1][0][0]
    assert second_call_spec.parent_id == "parent-123"

    third_call_spec = mock_adapter.create_ticket.call_args_list[2][0][0]
    assert third_call_spec.parent_id == "parent-123"


# --- Error Handling Tests ---


def test_plan_command_file_not_found() -> None:
    """Test plan_command exits 1 when spec file doesn't exist."""
    from imp.pm.cli import plan_command

    exit_code = plan_command(
        spec_file=Path("/nonexistent/file.json"),
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


def test_plan_command_invalid_json(tmp_path: Path) -> None:
    """Test plan_command exits 1 on invalid JSON."""
    from imp.pm.cli import plan_command

    # Write invalid JSON
    spec_file = tmp_path / "invalid.json"
    spec_file.write_text("{invalid json content")

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


def test_plan_command_invalid_spec(tmp_path: Path) -> None:
    """Test plan_command exits 1 on invalid spec (missing required field)."""
    from imp.pm.cli import plan_command

    # Write spec missing required 'name' field
    invalid_spec = {"components": []}
    spec_file = _write_spec(tmp_path, invalid_spec)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


def test_plan_command_invalid_priority(tmp_path: Path) -> None:
    """Test plan_command exits 1 with invalid priority string."""
    from imp.pm.cli import plan_command

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="invalid-priority",
        format="json",
    )

    assert exit_code == 1


def test_plan_command_unknown_provider(tmp_path: Path) -> None:
    """Test plan_command exits 1 with unknown provider."""
    from imp.pm.cli import plan_command

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="unknown-provider",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_adapter_init_failure_missing_env(
    mock_from_env: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command exits 1 when adapter init fails due to missing env vars."""
    from imp.pm.cli import plan_command

    # Mock from_env to raise ValueError (missing env vars)
    mock_from_env.side_effect = ValueError("PLANE_API_KEY environment variable is required")

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_adapter_create_ticket_failure(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command exits 1 when adapter.create_ticket raises PMError."""
    from imp.pm.base import PMError
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = PMError("API error: failed to create ticket")
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
    )

    assert exit_code == 1


# --- Output Format Tests ---


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_json_output_valid(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test plan_command with json format outputs valid JSON."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )

    assert exit_code == 0

    # Capture and parse stdout
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    # Verify structure
    assert output["spec_name"] == "Test Project"
    assert output["total_tickets"] == 3
    assert output["parent_ticket"]["ticket_id"] == "t-1"
    assert len(output["component_tickets"]) == 2


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_human_output_runs_without_error(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command with human format runs without error."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=False,
        default_priority="medium",
        format="human",
        project_root=tmp_path,
    )

    assert exit_code == 0


# --- Priority Tests ---


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_custom_priority_propagates(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that custom priority propagates to created tickets."""
    from imp.pm.cli import plan_command

    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="urgent",
        format="json",
        project_root=tmp_path,
    )

    assert exit_code == 0

    # Verify priority on created ticket
    first_call_spec = mock_adapter.create_ticket.call_args_list[0][0][0]
    assert first_call_spec.priority == TicketPriority.URGENT


# --- Idempotency Tests ---


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_writes_receipt(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command writes a receipt file after successful creation."""
    from imp.pm.cli import plan_command

    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )

    assert exit_code == 0

    # Verify receipt was written
    receipt_dir = tmp_path / ".imp" / "plans"
    assert receipt_dir.exists()
    receipts = list(receipt_dir.glob("*.json"))
    assert len(receipts) == 1

    # Verify receipt contains plan result
    receipt_data = json.loads(receipts[0].read_text())
    assert receipt_data["spec_name"] == "Test Project"
    assert receipt_data["total_tickets"] == 3


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_blocks_duplicate(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command exits 1 when spec was already planned."""
    from imp.pm.cli import plan_command

    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    # First run succeeds
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )
    assert exit_code == 0

    # Second run blocked
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )
    assert exit_code == 1
    assert mock_adapter.create_ticket.call_count == 3  # Only from first run


@patch("imp.pm.cli.PlaneAdapter")
@patch("imp.pm.cli.PlaneConfig.from_env")
def test_plan_command_force_overrides_duplicate_check(
    mock_from_env: MagicMock,
    mock_adapter_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Test plan_command with force=True bypasses duplicate check."""
    from imp.pm.cli import plan_command

    mock_adapter = MagicMock()
    mock_adapter.create_ticket.side_effect = [
        TicketRef(ticket_id="t-1", ticket_number="IMP-1", url="http://localhost/t-1"),
        TicketRef(ticket_id="t-2", ticket_number="IMP-2", url="http://localhost/t-2"),
        TicketRef(ticket_id="t-3", ticket_number="IMP-3", url="http://localhost/t-3"),
        TicketRef(ticket_id="t-4", ticket_number="IMP-4", url="http://localhost/t-4"),
        TicketRef(ticket_id="t-5", ticket_number="IMP-5", url="http://localhost/t-5"),
        TicketRef(ticket_id="t-6", ticket_number="IMP-6", url="http://localhost/t-6"),
    ]
    mock_adapter_cls.return_value = mock_adapter
    mock_from_env.return_value = PlaneConfig(
        api_key="test-key", workspace_slug="ws", project_id="proj"
    )

    spec_file = _write_spec(tmp_path, MINIMAL_SPEC)

    # First run
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
    )
    assert exit_code == 0

    # Second run with force
    exit_code = plan_command(
        spec_file=spec_file,
        provider="plane",
        create_parent=True,
        default_priority="medium",
        format="json",
        project_root=tmp_path,
        force=True,
    )
    assert exit_code == 0
    assert mock_adapter.create_ticket.call_count == 6  # Both runs created tickets
