"""Core provider abstractions.

This module defines provider-specific types and abstractions:
- AgentProvider: abstract base class for all provider implementations

Foundational types (TokenUsage, AgentResult) have been moved to imp.types
and are re-exported here for backward compatibility.
"""

from abc import ABC, abstractmethod

# Re-export foundational types from imp.types for backward compatibility
from imp.types import AgentResult, TokenUsage

__all__ = ["AgentProvider", "AgentResult", "TokenUsage"]


class AgentProvider[OutputT, DepsT](ABC):
    """Abstract base class for all agent providers.

    Generic over:
    - OutputT: type of agent output (str, BaseModel subclass, etc.)
    - DepsT: type of dependencies passed to agent (or None)
    """

    @abstractmethod
    async def invoke(
        self,
        prompt: str,
        dependencies: DepsT | None = None,
        system_prompt: str | None = None,
        **kwargs: object,
    ) -> AgentResult[OutputT]:
        """Invoke the agent with a prompt.

        Args:
            prompt: User prompt to send to the agent
            dependencies: Optional dependencies to pass to agent runtime
            system_prompt: Optional system prompt override
            **kwargs: Additional provider-specific arguments

        Returns:
            AgentResult with typed output, usage stats, and metadata
        """
        ...
