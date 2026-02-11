"""Cost calculation for token usage.

Prices are per 1M tokens, based on Anthropic's pricing as of January 2025.
Cache pricing: write = 1.25x input, read = 0.1x input.
"""

from typing import Protocol


class UsageProtocol(Protocol):
    """Protocol for token usage to avoid circular imports with base.py."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


# Prices per 1M tokens (USD)
PROVIDER_PRICES: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,  # 1.25x input
        "cache_read": 1.50,  # 0.1x input
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,  # 1.25x input
        "cache_read": 0.30,  # 0.1x input
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,  # 1.25x input
        "cache_read": 0.08,  # 0.1x input
    },
}


def calculate_cost(usage: UsageProtocol, model: str) -> float:
    """Calculate cost in USD for the given usage and model.

    Args:
        usage: Token usage counts (input, output, cache read/write)
        model: Model identifier (e.g., "claude-sonnet-4-5-20250929")

    Returns:
        Total cost in USD. Returns 0.0 for unknown models or zero tokens.
    """
    if model not in PROVIDER_PRICES:
        return 0.0

    prices = PROVIDER_PRICES[model]

    # Calculate cost per token type (prices are per 1M tokens)
    input_cost = (usage.input_tokens / 1_000_000) * prices["input"]
    output_cost = (usage.output_tokens / 1_000_000) * prices["output"]
    cache_write_cost = (usage.cache_write_tokens / 1_000_000) * prices["cache_write"]
    cache_read_cost = (usage.cache_read_tokens / 1_000_000) * prices["cache_read"]

    return input_cost + output_cost + cache_write_cost + cache_read_cost
