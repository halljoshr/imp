"""Imp providers — AI provider abstraction layer."""

from imp.providers.base import AgentProvider, AgentResult, TokenUsage
from imp.providers.config import ModelRoster, ProviderConfig
from imp.providers.pricing import calculate_cost
from imp.providers.pydantic_ai import PydanticAIProvider

__all__ = [
    "AgentProvider",
    "AgentResult",
    "ModelRoster",
    "ProviderConfig",
    "PydanticAIProvider",
    "TokenUsage",
    "calculate_cost",
]

# Optional export: ClaudeAgentSDKModel (requires claude-agent-sdk)
try:
    from imp.providers.claude_sdk_model import ClaudeAgentSDKModel  # noqa: F401

    __all__.append("ClaudeAgentSDKModel")
except ImportError:  # pragma: no cover
    # claude-agent-sdk not installed - gracefully skip
    pass
