"""Tests for cost calculation."""

from imp.providers.base import TokenUsage
from imp.providers.pricing import PROVIDER_PRICES, calculate_cost


class TestProviderPrices:
    """Test PROVIDER_PRICES constant."""

    def test_has_opus_4_6(self) -> None:
        """Opus 4.6 pricing exists."""
        assert "claude-opus-4-6" in PROVIDER_PRICES
        prices = PROVIDER_PRICES["claude-opus-4-6"]
        assert prices["input"] == 15.00
        assert prices["output"] == 75.00
        assert prices["cache_write"] == 18.75
        assert prices["cache_read"] == 1.50

    def test_has_sonnet_4_5(self) -> None:
        """Sonnet 4.5 pricing exists."""
        assert "claude-sonnet-4-5-20250929" in PROVIDER_PRICES
        prices = PROVIDER_PRICES["claude-sonnet-4-5-20250929"]
        assert prices["input"] == 3.00
        assert prices["output"] == 15.00
        assert prices["cache_write"] == 3.75
        assert prices["cache_read"] == 0.30

    def test_has_haiku_4_5(self) -> None:
        """Haiku 4.5 pricing exists."""
        assert "claude-haiku-4-5-20251001" in PROVIDER_PRICES
        prices = PROVIDER_PRICES["claude-haiku-4-5-20251001"]
        assert prices["input"] == 0.80
        assert prices["output"] == 4.00
        assert prices["cache_write"] == 1.00
        assert prices["cache_read"] == 0.08


class TestCalculateCost:
    """Test calculate_cost function."""

    def test_opus_cost(self) -> None:
        """Calculate cost for Opus 4.6."""
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
        cost = calculate_cost(usage, "claude-opus-4-6")
        # (1M * 15.00) + (0.5M * 75.00) = 15 + 37.5 = 52.5
        assert cost == 52.50

    def test_sonnet_cost(self) -> None:
        """Calculate cost for Sonnet 4.5."""
        usage = TokenUsage(input_tokens=2_000_000, output_tokens=1_000_000)
        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # (2M * 3.00) + (1M * 15.00) = 6 + 15 = 21
        assert cost == 21.00

    def test_haiku_cost(self) -> None:
        """Calculate cost for Haiku 4.5."""
        usage = TokenUsage(input_tokens=5_000_000, output_tokens=2_000_000)
        cost = calculate_cost(usage, "claude-haiku-4-5-20251001")
        # (5M * 0.80) + (2M * 4.00) = 4 + 8 = 12
        assert cost == 12.00

    def test_cache_write_cost(self) -> None:
        """Cache writes cost 1.25x input."""
        usage = TokenUsage(cache_write_tokens=1_000_000)
        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # 1M * 3.75 = 3.75
        assert cost == 3.75

    def test_cache_read_cost(self) -> None:
        """Cache reads cost 0.1x input."""
        usage = TokenUsage(cache_read_tokens=10_000_000)
        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # 10M * 0.30 = 3.00
        assert cost == 3.00

    def test_mixed_costs(self) -> None:
        """All token types together."""
        usage = TokenUsage(
            input_tokens=1_000_000,
            output_tokens=500_000,
            cache_write_tokens=200_000,
            cache_read_tokens=5_000_000,
        )
        cost = calculate_cost(usage, "claude-opus-4-6")
        # (1M * 15) + (0.5M * 75) + (0.2M * 18.75) + (5M * 1.50)
        # = 15 + 37.5 + 3.75 + 7.5 = 63.75
        assert cost == 63.75

    def test_unknown_model_returns_zero(self) -> None:
        """Unknown model returns 0.0."""
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
        cost = calculate_cost(usage, "unknown-model")
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self) -> None:
        """Zero tokens returns 0.0."""
        usage = TokenUsage()
        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        assert cost == 0.0
