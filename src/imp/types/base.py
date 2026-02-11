"""Foundational types for agent invocations.

These types are shared across all modules and form the core vocabulary of the system:
- TokenUsage: token counts and costs
- AgentResult: structured output from agent invocations

These types have no dependencies on other imp modules (pure foundation layer).
"""

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
