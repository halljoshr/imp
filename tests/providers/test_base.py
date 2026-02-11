"""Tests for base provider abstractions."""

import pytest
from pydantic import BaseModel, ValidationError

from imp.providers.base import AgentProvider, AgentResult, TokenUsage


class DummyOutput(BaseModel):
    """Dummy output model for testing."""

    message: str


class ConcreteProvider(AgentProvider[str, None]):
    """Concrete implementation for testing abstract provider."""

    async def invoke(
        self,
        prompt: str,
        dependencies: None = None,
        system_prompt: str | None = None,
        **kwargs: object,
    ) -> AgentResult[str]:
        """Dummy implementation."""
        return AgentResult(
            output="test",
            usage=TokenUsage(),
            model="test-model",
            provider="test",
            duration_ms=100,
        )


class TestTokenUsage:
    """Test TokenUsage model."""

    def test_creation_with_defaults(self) -> None:
        """All fields have defaults, can create with no args."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0
        assert usage.requests == 1
        assert usage.tool_calls == 0
        assert usage.cost_usd is None

    def test_creation_with_all_fields(self) -> None:
        """Can populate all fields."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cache_read_tokens=20,
            cache_write_tokens=10,
            requests=2,
            tool_calls=3,
            cost_usd=0.025,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cache_read_tokens == 20
        assert usage.cache_write_tokens == 10
        assert usage.requests == 2
        assert usage.tool_calls == 3
        assert usage.cost_usd == 0.025

    def test_immutability(self) -> None:
        """TokenUsage is frozen."""
        usage = TokenUsage(input_tokens=100)
        with pytest.raises(ValidationError):
            usage.input_tokens = 200  # type: ignore[misc]


class TestAgentResult:
    """Test AgentResult model."""

    def test_with_str_output(self) -> None:
        """AgentResult works with str output."""
        usage = TokenUsage(input_tokens=50, output_tokens=25)
        result = AgentResult(
            output="Hello world",
            usage=usage,
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
            duration_ms=1250,
        )
        assert result.output == "Hello world"
        assert result.usage.input_tokens == 50
        assert result.model == "claude-sonnet-4-5-20250929"
        assert result.provider == "anthropic"
        assert result.duration_ms == 1250

    def test_with_basemodel_output(self) -> None:
        """AgentResult works with BaseModel output."""
        usage = TokenUsage(output_tokens=30)
        output = DummyOutput(message="structured output")
        result = AgentResult(
            output=output,
            usage=usage,
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )
        assert isinstance(result.output, DummyOutput)
        assert result.output.message == "structured output"
        assert result.usage.output_tokens == 30


class TestAgentProvider:
    """Test AgentProvider abstract base class."""

    def test_is_abstract(self) -> None:
        """Cannot instantiate AgentProvider directly."""
        with pytest.raises(TypeError):
            AgentProvider()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        """Can create and use concrete subclass."""
        provider = ConcreteProvider()
        assert isinstance(provider, AgentProvider)

    async def test_concrete_invoke(self) -> None:
        """Concrete provider invoke works."""
        provider = ConcreteProvider()
        result = await provider.invoke("test prompt")
        assert result.output == "test"
        assert result.model == "test-model"
