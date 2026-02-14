"""Tests for PM base classes (ABC and errors).

Following three-tier TDD: write all tests BEFORE implementation.
Target: 100% branch coverage.
"""

import pytest

from imp.pm.base import PMAdapter, PMError
from imp.pm.models import Ticket, TicketFilter, TicketRef, TicketSpec, TicketStatus


class TestPMError:
    """Test PMError exception."""

    def test_creation_with_message(self) -> None:
        """Can create PMError with message."""
        error = PMError("Something went wrong")
        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"

    def test_is_exception(self) -> None:
        """PMError is a proper Exception."""
        error = PMError("Test error")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        """PMError can be raised and caught."""
        with pytest.raises(PMError) as exc_info:
            raise PMError("Test error message")
        assert exc_info.value.message == "Test error message"


class TestPMAdapter:
    """Test PMAdapter ABC."""

    def test_cannot_instantiate_directly(self) -> None:
        """PMAdapter cannot be instantiated directly (it's an ABC)."""
        with pytest.raises(TypeError):
            PMAdapter()  # type: ignore[abstract]

    def test_has_create_ticket_method(self) -> None:
        """PMAdapter has abstract create_ticket method."""
        assert hasattr(PMAdapter, "create_ticket")
        assert PMAdapter.create_ticket.__isabstractmethod__  # type: ignore[attr-defined]

    def test_has_get_ticket_method(self) -> None:
        """PMAdapter has abstract get_ticket method."""
        assert hasattr(PMAdapter, "get_ticket")
        assert PMAdapter.get_ticket.__isabstractmethod__  # type: ignore[attr-defined]

    def test_has_update_status_method(self) -> None:
        """PMAdapter has abstract update_status method."""
        assert hasattr(PMAdapter, "update_status")
        assert PMAdapter.update_status.__isabstractmethod__  # type: ignore[attr-defined]

    def test_has_add_comment_method(self) -> None:
        """PMAdapter has abstract add_comment method."""
        assert hasattr(PMAdapter, "add_comment")
        assert PMAdapter.add_comment.__isabstractmethod__  # type: ignore[attr-defined]

    def test_has_list_tickets_method(self) -> None:
        """PMAdapter has abstract list_tickets method."""
        assert hasattr(PMAdapter, "list_tickets")
        assert PMAdapter.list_tickets.__isabstractmethod__  # type: ignore[attr-defined]

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """A concrete implementation of PMAdapter can be instantiated."""

        class ConcretePMAdapter(PMAdapter):
            def create_ticket(self, spec: TicketSpec) -> TicketRef:
                return TicketRef(ticket_id="test-id")

            def get_ticket(self, ticket_id: str) -> Ticket:
                return Ticket(ticket_id=ticket_id, title="Test")

            def update_status(self, ticket_id: str, status: TicketStatus) -> None:
                pass

            def add_comment(self, ticket_id: str, comment: str) -> None:
                pass

            def list_tickets(self, filters: TicketFilter | None = None) -> list[Ticket]:
                return []

        adapter = ConcretePMAdapter()
        assert isinstance(adapter, PMAdapter)

    def test_concrete_subclass_methods_work(self) -> None:
        """Concrete implementation methods can be called."""

        class ConcretePMAdapter(PMAdapter):
            def create_ticket(self, spec: TicketSpec) -> TicketRef:
                return TicketRef(ticket_id=f"ticket-{spec.title}")

            def get_ticket(self, ticket_id: str) -> Ticket:
                return Ticket(ticket_id=ticket_id, title=f"Title for {ticket_id}")

            def update_status(self, ticket_id: str, status: TicketStatus) -> None:
                pass

            def add_comment(self, ticket_id: str, comment: str) -> None:
                pass

            def list_tickets(self, filters: TicketFilter | None = None) -> list[Ticket]:
                return [Ticket(ticket_id="id-1", title="Ticket 1")]

        adapter = ConcretePMAdapter()

        # Test create_ticket
        spec = TicketSpec(title="Test")
        ref = adapter.create_ticket(spec)
        assert ref.ticket_id == "ticket-Test"

        # Test get_ticket
        ticket = adapter.get_ticket("id-123")
        assert ticket.title == "Title for id-123"

        # Test list_tickets
        tickets = adapter.list_tickets()
        assert len(tickets) == 1
        assert tickets[0].ticket_id == "id-1"
