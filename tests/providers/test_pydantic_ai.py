"""Tests for Pydantic AI provider implementation."""

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from imp.providers.pydantic_ai import PydanticAIProvider


class DummyOutput(BaseModel):
    """Dummy output model for testing."""

    message: str


class TestPydanticAIProvider:
    """Test PydanticAIProvider with TestModel."""

    async def test_invoke_returns_agent_result(self) -> None:
        """Invoke returns AgentResult with correct structure."""
        provider = PydanticAIProvider(
            model=TestModel(), output_type=str, system_prompt="Test system prompt"
        )
        result = await provider.invoke("test prompt")

        assert isinstance(result.output, str)
        assert result.model == "test"
        assert result.provider == "test"
        assert result.duration_ms >= 0
        assert result.usage.total_tokens >= 0

    async def test_usage_has_token_counts(self) -> None:
        """Usage contains token counts from TestModel."""
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt")

        # TestModel generates token counts
        usage = result.usage
        assert usage.requests == 1
        assert isinstance(usage.input_tokens, int)
        assert isinstance(usage.output_tokens, int)
        assert isinstance(usage.total_tokens, int)

    async def test_cost_calculated(self) -> None:
        """Cost is calculated for known models."""
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt")
        # TestModel returns 'test' as model name, which isn't in our pricing table
        # so cost should be 0.0
        assert result.usage.cost_usd == 0.0

    async def test_duration_tracked(self) -> None:
        """Duration is tracked in milliseconds."""
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt")

        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    async def test_model_name_from_shorthand(self) -> None:
        """Extract model name from provider shorthand."""
        # Test the parsing logic directly without creating agent
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        model_name, provider_name = provider._parse_model_name("anthropic:claude-opus-4-6")
        assert model_name == "claude-opus-4-6"
        assert provider_name == "anthropic"

    async def test_model_name_from_plain_string(self) -> None:
        """Handle plain model string without provider prefix."""
        # Test the parsing logic directly without creating agent
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        model_name, provider_name = provider._parse_model_name("claude-sonnet-4-5-20250929")
        assert model_name == "claude-sonnet-4-5-20250929"
        assert provider_name == "unknown"

    async def test_model_name_from_test_model(self) -> None:
        """TestModel uses 'test' as name and provider."""
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        assert provider._model_name == "test"
        assert provider._provider_name == "test"

    async def test_system_prompt_default(self) -> None:
        """System prompt defaults to empty string."""
        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt")
        assert isinstance(result.output, str)

    async def test_system_prompt_override(self) -> None:
        """System prompt can be overridden in constructor."""
        provider = PydanticAIProvider(
            model=TestModel(), output_type=str, system_prompt="Custom system prompt"
        )
        result = await provider.invoke("test prompt")
        assert isinstance(result.output, str)

    async def test_structured_output(self) -> None:
        """Works with structured Pydantic output."""
        provider = PydanticAIProvider(model=TestModel(), output_type=DummyOutput)
        result = await provider.invoke("test prompt")

        assert isinstance(result.output, DummyOutput)
        assert hasattr(result.output, "message")

    async def test_dependencies_passed(self) -> None:
        """Dependencies can be passed to invoke."""

        class Deps:
            value: int = 42

        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        result = await provider.invoke("test prompt", dependencies=Deps())
        assert isinstance(result.output, str)

    async def test_model_object_with_colon_in_repr(self) -> None:
        """Handle Model objects with colon in string representation."""

        # Create a mock Model-like object with a __str__ that includes ":"
        class MockModel:
            def __str__(self) -> str:
                return "openai:gpt-4"

        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        model_name, provider_name = provider._parse_model_name(MockModel())
        assert model_name == "gpt-4"
        assert provider_name == "openai"

    async def test_model_object_without_colon_in_repr(self) -> None:
        """Handle Model objects without colon in string representation."""

        # Create a mock Model-like object with a __str__ without ":"
        class MockModel:
            def __str__(self) -> str:
                return "some-model"

        provider = PydanticAIProvider(model=TestModel(), output_type=str)
        model_name, provider_name = provider._parse_model_name(MockModel())
        assert model_name == "some-model"
        assert provider_name == "unknown"
