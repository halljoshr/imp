"""Tests for provider configuration models."""

import os
import sys
import types
from unittest.mock import patch

import pytest

from imp.providers.config import ModelRoster, ProviderConfig, resolve_default_model


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


class TestResolveDefaultModel:
    """Test resolve_default_model auto-detection."""

    def test_anthropic_api_key_returns_anthropic_model(self) -> None:
        """When ANTHROPIC_API_KEY is set, returns anthropic:claude-opus-4-6."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}):
            result = resolve_default_model()
        assert result == "anthropic:claude-opus-4-6"

    def test_no_api_key_with_sdk_returns_claude_agent_sdk(self) -> None:
        """When no API key but SDK importable, returns claude-agent-sdk."""
        old_val = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            fake_sdk = types.ModuleType("claude_agent_sdk")
            with patch.dict(sys.modules, {"claude_agent_sdk": fake_sdk}):
                result = resolve_default_model()
            assert result == "claude-agent-sdk"
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_val

    def test_api_key_takes_priority_over_sdk(self) -> None:
        """API key is preferred even when SDK is available."""
        fake_sdk = types.ModuleType("claude_agent_sdk")
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-456"}),
            patch.dict(sys.modules, {"claude_agent_sdk": fake_sdk}),
        ):
            result = resolve_default_model()
        assert result == "anthropic:claude-opus-4-6"

    def test_empty_api_key_is_not_set(self) -> None:
        """Empty string ANTHROPIC_API_KEY is treated as not set."""
        old_val = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            os.environ["ANTHROPIC_API_KEY"] = ""
            fake_sdk = types.ModuleType("claude_agent_sdk")
            with patch.dict(sys.modules, {"claude_agent_sdk": fake_sdk}):
                result = resolve_default_model()
            # Empty string is falsy, so should fall through to SDK check
            assert result == "claude-agent-sdk"
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_val
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_no_api_key_no_sdk_raises_runtime_error(self) -> None:
        """When no API key and no SDK, raises RuntimeError with instructions."""
        old_val = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with (
                patch.dict(sys.modules, {"claude_agent_sdk": None}),
                pytest.raises(RuntimeError, match="No AI provider configured"),
            ):
                resolve_default_model()
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_val

    def test_error_message_includes_instructions(self) -> None:
        """Error message tells user what to do."""
        old_val = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with (
                patch.dict(sys.modules, {"claude_agent_sdk": None}),
                pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY") as exc_info,
            ):
                resolve_default_model()
            assert "--model" in str(exc_info.value)
            assert "claude-agent-sdk" in str(exc_info.value)
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_val
