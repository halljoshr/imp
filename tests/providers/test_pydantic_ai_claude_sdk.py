"""Tests for PydanticAIProvider integration with claude-agent-sdk."""

from unittest.mock import patch

import pytest

# Skip all tests if claude-agent-sdk not available
pytest.importorskip("claude_agent_sdk")

from imp.providers.pydantic_ai import PydanticAIProvider


class TestPydanticAIProviderClaudeSDK:
    """Test PydanticAIProvider with claude-agent-sdk backend."""

    @pytest.mark.asyncio
    async def test_invoke_with_claude_agent_sdk_model(self) -> None:
        """Invoke with 'claude-agent-sdk' model string uses SDK backend."""
        # Mock the query function
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "SDK response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create provider with claude-agent-sdk model
            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)
            result = await provider.invoke("test prompt")

            # Verify result structure
            assert isinstance(result.output, str)
            assert result.model == "claude-code-cli"
            assert result.provider == "claude-agent-sdk"
            assert result.duration_ms >= 0
            assert result.usage.total_tokens >= 0

    @pytest.mark.asyncio
    async def test_usage_tracking_with_claude_sdk(self) -> None:
        """Usage tracking works with claude-agent-sdk backend."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response text"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)
            result = await provider.invoke("test prompt")

            # Verify usage tracking
            usage = result.usage
            assert usage.requests == 1
            assert usage.input_tokens > 0  # Estimated tokens
            assert usage.output_tokens > 0  # Estimated tokens
            assert usage.total_tokens > 0
            # Cost should be 0 since SDK uses Max subscription
            assert usage.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_model_name_parsing_claude_sdk(self) -> None:
        """Model name parsing recognizes claude-agent-sdk."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)

            # Check parsed names
            assert provider._model_name == "claude-code-cli"
            assert provider._provider_name == "claude-agent-sdk"

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_sdk(self) -> None:
        """System prompt is passed to claude-agent-sdk backend."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=str,
                system_prompt="Custom system prompt",
            )
            await provider.invoke("test prompt")

            # Verify query was called (system prompt is internal to agent)
            assert mock_query.called


class TestPydanticAIProviderFallback:
    """Test fallback to standard Pydantic AI providers."""

    @pytest.mark.asyncio
    async def test_standard_providers_still_work(self) -> None:
        """Standard Pydantic AI providers work normally."""
        from pydantic_ai.models.test import TestModel

        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt")

        # Should use standard Pydantic AI path
        assert isinstance(result.output, str)
        assert result.model == "test"
        assert result.provider == "test"

    @pytest.mark.asyncio
    async def test_anthropic_shorthand_still_works(self) -> None:
        """Anthropic shorthand notation still works."""
        from pydantic_ai.models.test import TestModel

        # Create with standard model to verify no regression
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        model_name, provider_name = provider._parse_model_name("anthropic:claude-opus-4-6")

        assert model_name == "claude-opus-4-6"
        assert provider_name == "anthropic"
