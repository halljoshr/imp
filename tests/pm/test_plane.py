"""Tests for PlaneAdapter — Plane PM integration.

All tests mock the plane-sdk module since it's not installed in dev environment.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from imp.pm.base import PMError
from imp.pm.models import (
    PlaneConfig,
    Ticket,
    TicketFilter,
    TicketPriority,
    TicketRef,
    TicketSpec,
    TicketStatus,
)


def make_config() -> PlaneConfig:
    """Factory for test PlaneConfig."""
    return PlaneConfig(
        api_key="test-key",
        base_url="http://localhost",
        workspace_slug="test-ws",
        project_id="proj-123",
        rate_limit_delay=0.0,  # disable rate limiting in tests
    )


@pytest.fixture
def mock_plane_client():
    """Mock the plane-sdk PlaneClient for tests."""
    mock_client = MagicMock()
    with patch("imp.pm.plane.PlaneClient", mock_client):
        yield mock_client


# ============================================================================
# Import Guard Tests
# ============================================================================


def test_import_guard_when_plane_sdk_not_installed():
    """PlaneAdapter raises PMError when plane-sdk is not installed."""
    with patch("imp.pm.plane.PlaneClient", None):
        from imp.pm.plane import PlaneAdapter

        with pytest.raises(PMError, match="plane-sdk is not installed"):
            PlaneAdapter(make_config())


def test_import_guard_when_plane_sdk_available(mock_plane_client):
    """PlaneAdapter initializes when plane-sdk is available."""
    from imp.pm.plane import PlaneAdapter

    adapter = PlaneAdapter(make_config())
    assert adapter is not None
    mock_plane_client.assert_called_once_with(
        base_url="http://localhost",
        api_key="test-key",
    )


# ============================================================================
# create_ticket Tests
# ============================================================================


def test_create_ticket_minimal_spec(mock_plane_client):
    """create_ticket sends correct CreateWorkItem for minimal spec."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {
        "id": "ticket-123",
        "identifier": "PROJ-42",
    }

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test ticket", description="Test description")
    result = adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    work_item = call_args[1]["data"]
    assert work_item.name == "Test ticket"
    assert work_item.description_html == "Test description"
    assert work_item.priority == "none"
    assert result.ticket_id == "ticket-123"
    assert result.ticket_number == "PROJ-42"
    assert result.url == "http://localhost/test-ws/projects/proj-123/work-items/ticket-123"


def test_create_ticket_with_parent_id(mock_plane_client):
    """create_ticket includes parent_id when set."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {
        "id": "child-123",
        "identifier": "PROJ-43",
    }

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Child ticket", parent_id="parent-456")
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    work_item = call_args[1]["data"]
    assert work_item.parent == "parent-456"


def test_create_ticket_priority_none(mock_plane_client):
    """create_ticket maps TicketPriority.NONE to 'none'."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test", priority=TicketPriority.NONE)
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    assert call_args[1]["data"].priority == "none"


def test_create_ticket_priority_low(mock_plane_client):
    """create_ticket maps TicketPriority.LOW to 'low'."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test", priority=TicketPriority.LOW)
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    assert call_args[1]["data"].priority == "low"


def test_create_ticket_priority_medium(mock_plane_client):
    """create_ticket maps TicketPriority.MEDIUM to 'medium'."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test", priority=TicketPriority.MEDIUM)
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    assert call_args[1]["data"].priority == "medium"


def test_create_ticket_priority_high(mock_plane_client):
    """create_ticket maps TicketPriority.HIGH to 'high'."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test", priority=TicketPriority.HIGH)
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    assert call_args[1]["data"].priority == "high"


def test_create_ticket_priority_urgent(mock_plane_client):
    """create_ticket maps TicketPriority.URGENT to 'urgent'."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test", priority=TicketPriority.URGENT)
    adapter.create_ticket(spec)

    call_args = mock_instance.work_items.create.call_args
    assert call_args[1]["data"].priority == "urgent"


def test_create_ticket_returns_ticket_ref(mock_plane_client):
    """create_ticket returns TicketRef with id and url."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {
        "id": "abc-123",
        "identifier": "PRJ-99",
    }

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test")
    result = adapter.create_ticket(spec)

    assert isinstance(result, TicketRef)
    assert result.ticket_id == "abc-123"
    assert result.ticket_number == "PRJ-99"
    assert "abc-123" in result.url


def test_create_ticket_wraps_sdk_exception(mock_plane_client):
    """create_ticket wraps SDK exceptions as PMError."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.side_effect = Exception("API error")

    adapter = PlaneAdapter(make_config())
    spec = TicketSpec(title="Test")

    with pytest.raises(PMError, match="Failed to create ticket: API error"):
        adapter.create_ticket(spec)


# ============================================================================
# get_ticket Tests
# ============================================================================


def test_get_ticket_returns_ticket_model(mock_plane_client):
    """get_ticket fetches ticket and maps to Ticket model."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.get.return_value = {
        "id": "ticket-456",
        "name": "Test Ticket",
        "description_html": "<p>Description</p>",
        "priority": "medium",
        "parent": None,
    }

    adapter = PlaneAdapter(make_config())
    result = adapter.get_ticket("ticket-456")

    assert isinstance(result, Ticket)
    assert result.ticket_id == "ticket-456"
    assert result.title == "Test Ticket"
    assert result.description == "<p>Description</p>"
    assert result.priority == TicketPriority.MEDIUM


def test_get_ticket_wraps_sdk_exception(mock_plane_client):
    """get_ticket wraps SDK exceptions as PMError."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.get.side_effect = Exception("Not found")

    adapter = PlaneAdapter(make_config())

    with pytest.raises(PMError, match="Failed to get ticket: Not found"):
        adapter.get_ticket("ticket-123")


# ============================================================================
# update_status Tests
# ============================================================================


def test_update_status_fetches_states_and_updates(mock_plane_client):
    """update_status fetches states, then updates ticket."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.states.list.return_value = [
        {"group": "backlog", "id": "state-backlog"},
        {"group": "started", "id": "state-started"},
    ]
    mock_instance.work_items.update.return_value = {}

    adapter = PlaneAdapter(make_config())
    adapter.update_status("ticket-123", TicketStatus.IN_PROGRESS)

    mock_instance.states.list.assert_called_once_with("test-ws", "proj-123")
    mock_instance.work_items.update.assert_called_once_with(
        "test-ws",
        "proj-123",
        "ticket-123",
        data={"state": "state-started"},
    )


def test_update_status_uses_cached_state_on_second_call(mock_plane_client):
    """update_status uses cached state on second call (no re-fetch)."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.states.list.return_value = [
        {"group": "started", "id": "state-started"},
    ]
    mock_instance.work_items.update.return_value = {}

    adapter = PlaneAdapter(make_config())
    adapter.update_status("ticket-1", TicketStatus.IN_PROGRESS)
    adapter.update_status("ticket-2", TicketStatus.IN_PROGRESS)

    # states.list should only be called once
    assert mock_instance.states.list.call_count == 1
    # update should be called twice
    assert mock_instance.work_items.update.call_count == 2


def test_update_status_wraps_sdk_exception(mock_plane_client):
    """update_status wraps SDK exceptions as PMError."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.states.list.return_value = [{"group": "started", "id": "s1"}]
    mock_instance.work_items.update.side_effect = Exception("Update failed")

    adapter = PlaneAdapter(make_config())

    with pytest.raises(PMError, match="Failed to update status: Update failed"):
        adapter.update_status("ticket-123", TicketStatus.IN_PROGRESS)


def test_update_status_raises_when_state_not_found(mock_plane_client):
    """update_status raises PMError when state group not found."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.states.list.return_value = []

    adapter = PlaneAdapter(make_config())

    with pytest.raises(PMError, match="No state found for group"):
        adapter.update_status("ticket-123", TicketStatus.IN_PROGRESS)


# ============================================================================
# add_comment Tests
# ============================================================================


def test_add_comment_sends_comment(mock_plane_client):
    """add_comment sends comment with correct payload."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.add_comment.return_value = {}

    adapter = PlaneAdapter(make_config())
    adapter.add_comment("ticket-123", "This is a comment")

    mock_instance.work_items.add_comment.assert_called_once_with(
        "test-ws",
        "proj-123",
        "ticket-123",
        data={"comment_html": "This is a comment"},
    )


def test_add_comment_wraps_sdk_exception(mock_plane_client):
    """add_comment wraps SDK exceptions as PMError."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.add_comment.side_effect = Exception("Comment failed")

    adapter = PlaneAdapter(make_config())

    with pytest.raises(PMError, match="Failed to add comment: Comment failed"):
        adapter.add_comment("ticket-123", "Comment")


# ============================================================================
# list_tickets Tests
# ============================================================================


def test_list_tickets_no_filter(mock_plane_client):
    """list_tickets returns all tickets when no filter provided."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.return_value = [
        {"id": "t1", "name": "Ticket 1", "description_html": "", "priority": 0, "parent": None},
        {"id": "t2", "name": "Ticket 2", "description_html": "", "priority": 1, "parent": None},
    ]

    adapter = PlaneAdapter(make_config())
    result = adapter.list_tickets()

    assert len(result) == 2
    assert result[0].ticket_id == "t1"
    assert result[1].ticket_id == "t2"


def test_list_tickets_with_status_filter(mock_plane_client):
    """list_tickets applies status filter client-side."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.return_value = [
        {"id": "t1", "name": "T1", "description_html": "", "priority": 0, "parent": None},
        {"id": "t2", "name": "T2", "description_html": "", "priority": 0, "parent": None},
    ]

    adapter = PlaneAdapter(make_config())
    # Mock _to_ticket to set different statuses
    with patch.object(adapter, "_to_ticket") as mock_to_ticket:
        mock_to_ticket.side_effect = [
            Ticket(ticket_id="t1", title="T1", status=TicketStatus.BACKLOG, url=""),
            Ticket(ticket_id="t2", title="T2", status=TicketStatus.TODO, url=""),
        ]
        filter_obj = TicketFilter(status=[TicketStatus.TODO])
        result = adapter.list_tickets(filter_obj)

    assert len(result) == 1
    assert result[0].ticket_id == "t2"


def test_list_tickets_with_priority_filter(mock_plane_client):
    """list_tickets applies priority filter client-side."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.return_value = [
        {"id": "t1", "name": "T1", "description_html": "", "priority": 1, "parent": None},
        {"id": "t2", "name": "T2", "description_html": "", "priority": 3, "parent": None},
    ]

    adapter = PlaneAdapter(make_config())
    with patch.object(adapter, "_to_ticket") as mock_to_ticket:
        mock_to_ticket.side_effect = [
            Ticket(ticket_id="t1", title="T1", priority=TicketPriority.LOW, url=""),
            Ticket(ticket_id="t2", title="T2", priority=TicketPriority.HIGH, url=""),
        ]
        filter_obj = TicketFilter(priority=[TicketPriority.HIGH])
        result = adapter.list_tickets(filter_obj)

    assert len(result) == 1
    assert result[0].ticket_id == "t2"


def test_list_tickets_with_assignee_filter(mock_plane_client):
    """list_tickets applies assignee filter client-side."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.return_value = [
        {"id": "t1", "name": "T1", "description_html": "", "priority": 0, "parent": None},
        {"id": "t2", "name": "T2", "description_html": "", "priority": 0, "parent": None},
    ]

    adapter = PlaneAdapter(make_config())
    with patch.object(adapter, "_to_ticket") as mock_to_ticket:
        mock_to_ticket.side_effect = [
            Ticket(ticket_id="t1", title="T1", assignee_id="user-1", url=""),
            Ticket(ticket_id="t2", title="T2", assignee_id="user-2", url=""),
        ]
        filter_obj = TicketFilter(assignee_id="user-1")
        result = adapter.list_tickets(filter_obj)

    assert len(result) == 1
    assert result[0].ticket_id == "t1"


def test_list_tickets_with_parent_filter(mock_plane_client):
    """list_tickets applies parent filter client-side."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.return_value = [
        {"id": "t1", "name": "T1", "description_html": "", "priority": 0, "parent": None},
        {"id": "t2", "name": "T2", "description_html": "", "priority": 0, "parent": "parent-123"},
    ]

    adapter = PlaneAdapter(make_config())
    with patch.object(adapter, "_to_ticket") as mock_to_ticket:
        mock_to_ticket.side_effect = [
            Ticket(ticket_id="t1", title="T1", parent_id=None, url=""),
            Ticket(ticket_id="t2", title="T2", parent_id="parent-123", url=""),
        ]
        filter_obj = TicketFilter(parent_id="parent-123")
        result = adapter.list_tickets(filter_obj)

    assert len(result) == 1
    assert result[0].ticket_id == "t2"


def test_list_tickets_wraps_sdk_exception(mock_plane_client):
    """list_tickets wraps SDK exceptions as PMError."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.list.side_effect = Exception("List failed")

    adapter = PlaneAdapter(make_config())

    with pytest.raises(PMError, match="Failed to list tickets: List failed"):
        adapter.list_tickets()


# ============================================================================
# Rate Limiting Tests
# ============================================================================


def test_rate_limit_sleeps_when_requests_too_fast(mock_plane_client):
    """Rate limiter sleeps when requests are too fast."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    config = make_config()
    config.rate_limit_delay = 1.0  # enable rate limiting

    with (
        patch("imp.pm.plane.time.sleep") as mock_sleep,
        patch("imp.pm.plane.time.monotonic") as mock_time,
    ):
        # _rate_limit calls monotonic twice: once at start, once at end
        # First request: [start=0.0, end=0.1]
        # Second request: [start=0.5, sleep happens, end=1.0]
        mock_time.side_effect = [0.0, 0.1, 0.5, 1.0]

        adapter = PlaneAdapter(config)
        spec = TicketSpec(title="Test")
        adapter.create_ticket(spec)
        adapter.create_ticket(spec)

        # Should sleep once
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert 0.5 < sleep_duration < 0.7  # approximately 0.6s (1.0 - 0.4)


def test_rate_limit_no_sleep_when_enough_time_passed(mock_plane_client):
    """Rate limiter does not sleep when enough time has passed."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    config = make_config()
    config.rate_limit_delay = 1.0

    with (
        patch("imp.pm.plane.time.sleep") as mock_sleep,
        patch("imp.pm.plane.time.monotonic") as mock_time,
    ):
        # First request at t=0, second at t=2.0 (no sleep needed)
        mock_time.side_effect = [0.0, 0.0, 2.0, 2.0]

        adapter = PlaneAdapter(config)
        spec = TicketSpec(title="Test")
        adapter.create_ticket(spec)
        adapter.create_ticket(spec)

        # Should not sleep
        mock_sleep.assert_not_called()


def test_rate_limit_no_sleep_on_first_request(mock_plane_client):
    """Rate limiter does not sleep on first request."""
    from imp.pm.plane import PlaneAdapter

    mock_instance = mock_plane_client.return_value
    mock_instance.work_items.create.return_value = {"id": "t1", "identifier": "T1"}

    config = make_config()
    config.rate_limit_delay = 1.0

    with patch("imp.pm.plane.time.sleep") as mock_sleep:
        adapter = PlaneAdapter(config)
        spec = TicketSpec(title="Test")
        adapter.create_ticket(spec)

        # Should not sleep on first request
        mock_sleep.assert_not_called()
