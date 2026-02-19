"""Provider configuration models.

Defines per-provider configuration and per-role model roster.
Uses BaseModel (not BaseSettings) for simplicity — env var loading can come later.
"""

import os

from pydantic import BaseModel


def resolve_default_model() -> str:
    """Resolve the default AI model based on available credentials.

    Checks in order:
    1. ANTHROPIC_API_KEY set → "anthropic:claude-opus-4-6"
    2. claude-agent-sdk importable → "claude-agent-sdk"
    3. Neither → raise RuntimeError with clear instructions

    Returns:
        Full model string ready for PydanticAIProvider.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-opus-4-6"

    try:
        import claude_agent_sdk  # noqa: F401

        return "claude-agent-sdk"
    except ImportError:
        msg = (
            "No AI provider configured. Either:\n"
            "  1. Set ANTHROPIC_API_KEY environment variable, or\n"
            "  2. Install claude-agent-sdk: pip install impx[claude-sdk], or\n"
            "  3. Pass --model explicitly (e.g. --model claude-agent-sdk)"
        )
        raise RuntimeError(msg) from None


class ProviderConfig(BaseModel):
    """Configuration for a single AI provider/model.

    Covers common parameters across providers. Provider-specific config can be added
    via extra kwargs when needed.
    """

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    fallback_model: str | None = None
    max_tokens: int = 4096
    timeout_seconds: int = 120
    max_retries: int = 3
    temperature: float | None = None


class ModelRoster(BaseModel):
    """Per-role model assignment.

    Different agent roles have different performance/cost requirements:
    - interview: extract requirements from user (Sonnet)
    - coding: write code (Sonnet, reserved for managed executor)
    - review: critique and validate (Opus)
    - planning: high-level task decomposition (Opus)
    - context: cheap indexing and summarization (Haiku)
    """

    interview: ProviderConfig = ProviderConfig(model="claude-sonnet-4-5-20250929")
    coding: ProviderConfig = ProviderConfig(model="claude-sonnet-4-5-20250929")
    review: ProviderConfig = ProviderConfig(model="claude-opus-4-6")
    planning: ProviderConfig = ProviderConfig(model="claude-opus-4-6")
    context: ProviderConfig = ProviderConfig(model="claude-haiku-4-5-20251001")
