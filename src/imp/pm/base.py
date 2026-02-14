"""PM base classes — abstract adapter and errors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from imp.pm.models import Ticket, TicketFilter, TicketRef, TicketSpec, TicketStatus


class PMError(Exception):
    """PM integration error."""

    def __init__(self, message: str) -> None:
        """Initialize PMError with a message."""
        self.message = message
        super().__init__(message)


class PMAdapter(ABC):
    """Abstract base class for PM system adapters (Plane, Linear, etc.)."""

    @abstractmethod
    def create_ticket(self, spec: TicketSpec) -> TicketRef:
        """Create a ticket and return a reference to it."""
        ...

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> Ticket:
        """Fetch full ticket details by ID."""
        ...

    @abstractmethod
    def update_status(self, ticket_id: str, status: TicketStatus) -> None:
        """Update ticket status."""
        ...

    @abstractmethod
    def add_comment(self, ticket_id: str, comment: str) -> None:
        """Add a comment to a ticket."""
        ...

    @abstractmethod
    def list_tickets(self, filters: TicketFilter | None = None) -> list[Ticket]:
        """List tickets, optionally filtered."""
        ...
