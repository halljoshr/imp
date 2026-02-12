"""Pydantic AI provider implementation.

Wraps Pydantic AI Agent for standardized usage tracking, cost calculation, and timing.
Supports both standard Pydantic AI providers and claude-agent-sdk integration.
"""

import time
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.test import TestModel

from imp.providers.base import AgentProvider, AgentResult, TokenUsage
from imp.providers.pricing import calculate_cost

# Import claude-agent-sdk model if available
try:
    from imp.providers.claude_sdk_model import ClaudeAgentSDKModel

    CLAUDE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    CLAUDE_SDK_AVAILABLE = False
    ClaudeAgentSDKModel = None  # type: ignore


class PydanticAIProvider[OutputT, DepsT](AgentProvider[OutputT, DepsT]):
    """Pydantic AI implementation of AgentProvider.

    Wraps Pydantic AI Agent to provide standardized usage tracking, cost calculation,
    and performance metrics.

    Supports:
    - Standard Pydantic AI providers (18+ models via shorthand notation)
    - claude-agent-sdk integration (Max subscription usage)

    Example:
        # Standard provider (API key required)
        provider = PydanticAIProvider(
            model="anthropic:claude-opus-4-6",
            output_type=str
        )

        # claude-agent-sdk (Max subscription, no API key)
        provider = PydanticAIProvider(
            model="claude-agent-sdk",
            output_type=str
        )
    """

    def __init__(
        self,
        model: Model | KnownModelName | TestModel | str,
        output_type: type[OutputT],
        system_prompt: str = "",
    ) -> None:
        """Initialize provider with model and output type.

        Args:
            model: Pydantic AI model (Model, shorthand string, TestModel, or "claude-agent-sdk")
            output_type: Type of structured output (str, BaseModel subclass, etc.)
            system_prompt: Optional system prompt for the agent

        Raises:
            ImportError: If model="claude-agent-sdk" but SDK not installed
        """
        # Detect claude-agent-sdk model string
        if isinstance(model, str) and model == "claude-agent-sdk":
            if not CLAUDE_SDK_AVAILABLE:  # pragma: no cover
                raise ImportError(
                    "claude-agent-sdk is not installed. Install with: pip install impx[claude-sdk]"
                )
            # Create ClaudeAgentSDKModel instance
            model = ClaudeAgentSDKModel()

        self._agent: Agent[DepsT, OutputT] = Agent(
            model=model, output_type=output_type, system_prompt=system_prompt
        )

        # Extract model and provider names for result metadata
        self._model_name, self._provider_name = self._parse_model_name(model)

    def _parse_model_name(
        self, model: Model | KnownModelName | TestModel | str
    ) -> tuple[str, str]:
        """Extract model name and provider from model identifier.

        Args:
            model: Model specification

        Returns:
            Tuple of (model_name, provider_name)
        """
        # Handle ClaudeAgentSDKModel
        if CLAUDE_SDK_AVAILABLE and isinstance(model, ClaudeAgentSDKModel):
            return (model.model_name, model.system)

        if isinstance(model, TestModel):
            return ("test", "test")

        if isinstance(model, str):
            # Handle shorthand like "anthropic:claude-sonnet-4-5"
            if ":" in model:
                provider, model_name = model.split(":", 1)
                return (model_name, provider)
            # Plain string model name
            return (model, "unknown")

        # Model object - use string representation
        model_str = str(model)
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
            return (model_name, provider)
        return (model_str, "unknown")

    async def invoke(
        self,
        prompt: str,
        dependencies: DepsT | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AgentResult[OutputT]:
        """Invoke the agent with a prompt.

        Args:
            prompt: User prompt
            dependencies: Optional dependencies for agent
            system_prompt: Optional system prompt override (not used, agent set at init)
            **kwargs: Additional arguments (passed to agent.run)

        Returns:
            AgentResult with output, usage, cost, and timing
        """
        start = time.monotonic()
        if dependencies is not None:
            result = await self._agent.run(prompt, deps=dependencies, **kwargs)
        else:
            result = await self._agent.run(prompt, **kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Map Pydantic AI RunUsage to our TokenUsage
        run_usage = result.usage()
        usage = TokenUsage(
            input_tokens=run_usage.input_tokens or 0,
            output_tokens=run_usage.output_tokens or 0,
            total_tokens=run_usage.total_tokens or 0,
            cache_read_tokens=0,  # Not exposed by Pydantic AI's usage() method
            cache_write_tokens=0,  # Not exposed by Pydantic AI's usage() method
            requests=1,
            tool_calls=0,  # Not tracked in current implementation
            cost_usd=calculate_cost(
                TokenUsage(
                    input_tokens=run_usage.input_tokens or 0,
                    output_tokens=run_usage.output_tokens or 0,
                ),
                self._model_name,
            ),
        )

        return AgentResult(
            output=result.output,
            usage=usage,
            model=self._model_name,
            provider=self._provider_name,
            duration_ms=duration_ms,
        )
