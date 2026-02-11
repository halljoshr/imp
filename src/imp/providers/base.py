"""Core provider abstractions.

This module defines the base types for agent invocations:
- TokenUsage: token counts and costs
- AgentResult: structured output from agent invocations
- AgentProvider: abstract base class for all provider implementations

No pydantic-ai dependency here — pure foundation layer.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class TokenUsage(BaseModel):
    """Token usage and cost tracking.

    Maps directly to Pydantic AI RunUsage. Same shape for direct calls and managed executor.
    All token counts default to 0 for easy initialization.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    requests: int = 1
    tool_calls: int = 0
    cost_usd: float | None = None

    model_config = ConfigDict(frozen=True)


class AgentResult[OutputT](BaseModel):
    """Result from an agent invocation.

    Generic over output type to support both structured (BaseModel) and unstructured (str)
    outputs.
    """

    output: OutputT
    usage: TokenUsage
    model: str
    provider: str
    duration_ms: int


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
