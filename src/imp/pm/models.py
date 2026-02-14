"""PM integration models — tickets, configs, and results."""

from __future__ import annotations

import os
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(StrEnum):
    """Ticket status values."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class TicketPriority(StrEnum):
    """Ticket priority values."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PlaneConfig(BaseModel):
    """Configuration for Plane PM integration."""

    api_key: str
    base_url: str = "http://localhost"
    workspace_slug: str
    project_id: str
    default_priority: TicketPriority = TicketPriority.MEDIUM
    rate_limit_delay: float = 1.0

    @classmethod
    def from_env(cls) -> PlaneConfig:
        """Load config from environment variables.

        Raises:
            ValueError: If required environment variables are missing or empty.
        """
        api_key = os.environ.get("PLANE_API_KEY", "")
        base_url = os.environ.get("PLANE_BASE_URL", "http://localhost")
        workspace_slug = os.environ.get("PLANE_WORKSPACE_SLUG", "")
        project_id = os.environ.get("PLANE_PROJECT_ID", "")

        if not api_key:
            raise ValueError("PLANE_API_KEY environment variable is required")
        if not workspace_slug:
            raise ValueError("PLANE_WORKSPACE_SLUG environment variable is required")
        if not project_id:
            raise ValueError("PLANE_PROJECT_ID environment variable is required")

        return cls(
            api_key=api_key,
            base_url=base_url,
            workspace_slug=workspace_slug,
            project_id=project_id,
        )


class TicketSpec(BaseModel):
    """Specification for creating a ticket."""

    title: str
    description: str = ""
    priority: TicketPriority = TicketPriority.NONE
    parent_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    estimate_points: int | None = None
    source_spec_name: str = ""
    source_component_name: str = ""

    model_config = ConfigDict(frozen=True)


class TicketRef(BaseModel):
    """Reference to a created ticket (minimal info)."""

    ticket_id: str
    ticket_number: str = ""
    url: str = ""

    model_config = ConfigDict(frozen=True)


class Ticket(BaseModel):
    """Full ticket details."""

    ticket_id: str
    title: str
    description: str = ""
    priority: TicketPriority = TicketPriority.NONE
    status: TicketStatus = TicketStatus.BACKLOG
    parent_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    estimate_points: int | None = None
    assignee_id: str | None = None
    url: str = ""
    source_spec_name: str = ""
    source_component_name: str = ""

    model_config = ConfigDict(frozen=True)


class TicketFilter(BaseModel):
    """Filter criteria for listing tickets."""

    status: list[TicketStatus] = Field(default_factory=list)
    priority: list[TicketPriority] = Field(default_factory=list)
    assignee_id: str | None = None
    parent_id: str | None = None


class PlanResult(BaseModel):
    """Result of ticket generation from a spec."""

    spec_name: str
    parent_ticket: TicketRef | None = None
    component_tickets: list[TicketRef] = Field(default_factory=list)
    total_tickets: int = 0

    model_config = ConfigDict(frozen=True)

    @property
    def success(self) -> bool:
        """Check if ticket generation was successful (at least one ticket created)."""
        return self.total_tickets > 0
