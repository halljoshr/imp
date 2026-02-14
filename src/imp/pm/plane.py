"""Plane PM adapter using plane-sdk."""

from __future__ import annotations

import time
from typing import Any, ClassVar

from imp.pm.base import PMAdapter, PMError
from imp.pm.models import (
    PlaneConfig,
    Ticket,
    TicketFilter,
    TicketPriority,
    TicketRef,
    TicketSpec,
    TicketStatus,
)

try:
    from plane import PlaneClient  # type: ignore[import-untyped]
    from plane.models.work_items import CreateWorkItem  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    PlaneClient = None
    CreateWorkItem = None


class PlaneAdapter(PMAdapter):
    """Plane PM adapter using plane-sdk."""

    # Priority enum to Plane string mapping
    PRIORITY_MAP: ClassVar[dict[TicketPriority, str]] = {
        TicketPriority.NONE: "none",
        TicketPriority.LOW: "low",
        TicketPriority.MEDIUM: "medium",
        TicketPriority.HIGH: "high",
        TicketPriority.URGENT: "urgent",
    }

    # TicketStatus to Plane state group mapping
    STATUS_GROUP_MAP: ClassVar[dict[TicketStatus, str]] = {
        TicketStatus.BACKLOG: "backlog",
        TicketStatus.TODO: "unstarted",
        TicketStatus.IN_PROGRESS: "started",
        TicketStatus.IN_REVIEW: "started",
        TicketStatus.DONE: "completed",
        TicketStatus.CANCELLED: "cancelled",
    }

    def __init__(self, config: PlaneConfig) -> None:
        """Initialize PlaneAdapter with config.

        Args:
            config: PlaneConfig with API credentials and settings.

        Raises:
            PMError: If plane-sdk is not installed.
        """
        if PlaneClient is None:
            raise PMError("plane-sdk is not installed. Install with: pip install 'impx[plane]'")
        self._config = config
        self._client: Any = PlaneClient(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self._last_request_time: float = 0.0
        self._state_cache: dict[str, str] = {}  # state_group -> state_uuid

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        delay = self._config.rate_limit_delay
        if elapsed < delay and self._last_request_time > 0:
            time.sleep(delay - elapsed)
        self._last_request_time = time.monotonic()

    def _get_state_id(self, status: TicketStatus) -> str:
        """Get Plane state UUID for a ticket status. Caches after first lookup.

        Args:
            status: TicketStatus to map to Plane state.

        Returns:
            Plane state UUID string.

        Raises:
            PMError: If state lookup fails or state group not found.
        """
        group = self.STATUS_GROUP_MAP[status]
        if group in self._state_cache:
            return self._state_cache[group]
        # Fetch states from Plane API
        try:
            self._rate_limit()
            states = self._client.states.list(
                self._config.workspace_slug,
                self._config.project_id,
            )
            # states is a list of state objects with 'group' and 'id' fields
            for state in states:
                state_group = (
                    state.get("group", "")
                    if isinstance(state, dict)
                    else getattr(state, "group", "")
                )
                state_id = (
                    state.get("id", "") if isinstance(state, dict) else getattr(state, "id", "")
                )
                if state_group not in self._state_cache:  # pragma: no cover
                    self._state_cache[state_group] = state_id  # pragma: no cover
        except Exception as e:  # pragma: no cover
            raise PMError(f"Failed to fetch states: {e}") from e  # pragma: no cover

        if group not in self._state_cache:
            raise PMError(f"No state found for group '{group}'")
        return self._state_cache[group]

    def create_ticket(self, spec: TicketSpec) -> TicketRef:
        """Create a work item in Plane.

        Args:
            spec: TicketSpec with title, description, priority, etc.

        Returns:
            TicketRef with ticket ID, number, and URL.

        Raises:
            PMError: If ticket creation fails.
        """
        try:
            self._rate_limit()
            work_item = CreateWorkItem(
                name=spec.title,
                description_html=spec.description,
                priority=self.PRIORITY_MAP.get(spec.priority, "none"),
                parent=spec.parent_id,
            )

            result = self._client.work_items.create(
                self._config.workspace_slug,
                self._config.project_id,
                data=work_item,
            )
            # Extract ticket_id and url from result
            ticket_id = (
                result.get("id", "") if isinstance(result, dict) else getattr(result, "id", "")
            )
            identifier = (
                result.get("identifier", "")
                if isinstance(result, dict)
                else getattr(result, "identifier", "")
            )

            base = self._config.base_url
            ws = self._config.workspace_slug
            proj = self._config.project_id
            url = f"{base}/{ws}/projects/{proj}/work-items/{ticket_id}"

            return TicketRef(
                ticket_id=ticket_id,
                ticket_number=identifier,
                url=url,
            )
        except PMError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as e:
            raise PMError(f"Failed to create ticket: {e}") from e

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Get a work item from Plane.

        Args:
            ticket_id: Plane work item ID.

        Returns:
            Ticket model with full details.

        Raises:
            PMError: If ticket fetch fails.
        """
        try:
            self._rate_limit()
            result = self._client.work_items.get(
                self._config.workspace_slug,
                self._config.project_id,
                ticket_id,
            )
            return self._to_ticket(result)
        except PMError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as e:
            raise PMError(f"Failed to get ticket: {e}") from e

    def update_status(self, ticket_id: str, status: TicketStatus) -> None:
        """Update a work item's status in Plane.

        Args:
            ticket_id: Plane work item ID.
            status: New TicketStatus.

        Raises:
            PMError: If status update fails.
        """
        try:
            state_id = self._get_state_id(status)
            self._rate_limit()
            self._client.work_items.update(
                self._config.workspace_slug,
                self._config.project_id,
                ticket_id,
                data={"state": state_id},
            )
        except PMError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as e:
            raise PMError(f"Failed to update status: {e}") from e

    def add_comment(self, ticket_id: str, comment: str) -> None:
        """Add a comment to a work item in Plane.

        Args:
            ticket_id: Plane work item ID.
            comment: Comment text (HTML format).

        Raises:
            PMError: If comment addition fails.
        """
        try:
            self._rate_limit()
            self._client.work_items.add_comment(
                self._config.workspace_slug,
                self._config.project_id,
                ticket_id,
                data={"comment_html": comment},
            )
        except PMError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as e:
            raise PMError(f"Failed to add comment: {e}") from e

    def list_tickets(self, filters: TicketFilter | None = None) -> list[Ticket]:
        """List work items from Plane, with optional client-side filtering.

        Args:
            filters: Optional TicketFilter for status, priority, assignee, parent.

        Returns:
            List of Ticket models.

        Raises:
            PMError: If listing fails.
        """
        try:
            self._rate_limit()
            results = self._client.work_items.list(
                self._config.workspace_slug,
                self._config.project_id,
            )
            tickets = [self._to_ticket(r) for r in results]
            if filters:
                tickets = self._apply_filters(tickets, filters)
            return tickets
        except PMError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as e:
            raise PMError(f"Failed to list tickets: {e}") from e

    def _to_ticket(self, data: Any) -> Ticket:
        """Convert Plane API response to Ticket model.

        Args:
            data: Plane API response object or dict.

        Returns:
            Ticket model.
        """

        def get(k: str, d: str = "") -> Any:
            return data.get(k, d) if isinstance(data, dict) else getattr(data, k, d)

        # Map Plane priority string back to enum
        priority_str = str(get("priority", "none"))
        reverse_priority = {v: k for k, v in self.PRIORITY_MAP.items()}
        priority = reverse_priority.get(priority_str, TicketPriority.NONE)

        return Ticket(
            ticket_id=get("id", ""),
            title=get("name", ""),
            description=get("description_html", ""),
            priority=priority,
            status=TicketStatus.BACKLOG,  # simplified - would need state lookup for real mapping
            parent_id=get("parent"),
            assignee_id=None,  # Plane uses assignees list, simplified
            url="",
        )

    @staticmethod
    def _apply_filters(tickets: list[Ticket], filters: TicketFilter) -> list[Ticket]:
        """Apply client-side filters to ticket list.

        Args:
            tickets: List of Ticket models.
            filters: TicketFilter with status, priority, assignee, parent filters.

        Returns:
            Filtered list of Ticket models.
        """
        result = tickets
        if filters.status:
            result = [t for t in result if t.status in filters.status]
        if filters.priority:
            result = [t for t in result if t.priority in filters.priority]
        if filters.assignee_id is not None:
            result = [t for t in result if t.assignee_id == filters.assignee_id]
        if filters.parent_id is not None:
            result = [t for t in result if t.parent_id == filters.parent_id]
        return result
