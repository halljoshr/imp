"""Tests for provider configuration models."""

from imp.providers.config import ModelRoster, ProviderConfig


class TestProviderConfig:
    """Test ProviderConfig model."""

    def test_defaults(self) -> None:
        """All fields have sensible defaults."""
        config = ProviderConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.fallback_model is None
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 120
        assert config.max_retries == 3
        assert config.temperature is None

    def test_all_fields_override(self) -> None:
        """Can override all fields."""
        config = ProviderConfig(
            provider="openai",
            model="gpt-5.2",
            fallback_model="gpt-4o",
            max_tokens=8192,
            timeout_seconds=60,
            max_retries=5,
            temperature=0.7,
        )
        assert config.provider == "openai"
        assert config.model == "gpt-5.2"
        assert config.fallback_model == "gpt-4o"
        assert config.max_tokens == 8192
        assert config.timeout_seconds == 60
        assert config.max_retries == 5
        assert config.temperature == 0.7

    def test_partial_override(self) -> None:
        """Can override only some fields."""
        config = ProviderConfig(model="claude-opus-4-6", temperature=0.5)
        assert config.model == "claude-opus-4-6"
        assert config.temperature == 0.5
        assert config.provider == "anthropic"  # default preserved
        assert config.max_tokens == 4096  # default preserved


class TestModelRoster:
    """Test ModelRoster model."""

    def test_defaults(self) -> None:
        """All roles have defaults."""
        roster = ModelRoster()
        assert roster.interview.model == "claude-sonnet-4-5-20250929"
        assert roster.coding.model == "claude-sonnet-4-5-20250929"
        assert roster.review.model == "claude-opus-4-6"
        assert roster.planning.model == "claude-opus-4-6"
        assert roster.context.model == "claude-haiku-4-5-20251001"

    def test_override_individual_role(self) -> None:
        """Can override individual role configs."""
        custom_interview = ProviderConfig(model="claude-opus-4-6", temperature=0.9)
        roster = ModelRoster(interview=custom_interview)
        assert roster.interview.model == "claude-opus-4-6"
        assert roster.interview.temperature == 0.9
        # Other roles keep defaults
        assert roster.coding.model == "claude-sonnet-4-5-20250929"
        assert roster.review.model == "claude-opus-4-6"

    def test_override_multiple_roles(self) -> None:
        """Can override multiple roles."""
        roster = ModelRoster(
            coding=ProviderConfig(model="gpt-5.2", provider="openai"),
            context=ProviderConfig(model="claude-sonnet-4-5-20250929"),
        )
        assert roster.coding.model == "gpt-5.2"
        assert roster.coding.provider == "openai"
        assert roster.context.model == "claude-sonnet-4-5-20250929"
        # Unchanged roles
        assert roster.interview.model == "claude-sonnet-4-5-20250929"

    def test_coding_role_exists(self) -> None:
        """Coding role exists for managed executor."""
        roster = ModelRoster()
        assert hasattr(roster, "coding")
        assert isinstance(roster.coding, ProviderConfig)
