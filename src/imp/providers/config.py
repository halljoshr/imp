"""Provider configuration models.

Defines per-provider configuration and per-role model roster.
Uses BaseModel (not BaseSettings) for simplicity — env var loading can come later.
"""

from pydantic import BaseModel


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
