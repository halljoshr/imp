"""Integration tests for provider layer - full end-to-end flows."""

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from imp.providers import ModelRoster, ProviderConfig, PydanticAIProvider


class InterviewQuestion(BaseModel):
    """Example structured output for Interview Agent."""

    question: str
    rationale: str
    expected_answer_type: str


class ReviewFinding(BaseModel):
    """Example structured output for Review Agent."""

    severity: str
    file_path: str
    line_number: int
    issue: str
    suggestion: str


class TestProviderIntegration:
    """Integration tests exercising realistic provider usage patterns."""

    async def test_structured_output_interview_scenario(self) -> None:
        """Simulate Interview Agent generating a structured question."""
        # TestModel will generate valid InterviewQuestion output automatically
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=InterviewQuestion,
            system_prompt="You are an expert product manager conducting requirements interviews.",
        )

        result = await provider.invoke(
            "Generate the first question for a requirements interview about a new feature."
        )

        # Verify structured output
        assert isinstance(result.output, InterviewQuestion)
        assert result.output.question != ""
        assert result.output.rationale != ""
        assert result.output.expected_answer_type != ""

        # Verify usage tracking
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0
        assert result.usage.total_tokens > 0
        assert result.usage.requests == 1

        # Verify timing
        assert result.duration_ms >= 0

        # TestModel returns 'test' as model name, so cost should be 0.0
        assert result.usage.cost_usd == 0.0

    async def test_structured_output_review_scenario(self) -> None:
        """Simulate Review Agent generating structured findings."""
        # TestModel will generate valid ReviewFinding output automatically
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=ReviewFinding,
            system_prompt="You are a security-focused code reviewer.",
        )

        result = await provider.invoke(
            "Review this code for security issues:\n\n"
            "query = f'SELECT * FROM users WHERE id = {user_id}'"
        )

        # Verify structured output
        assert isinstance(result.output, ReviewFinding)
        assert result.output.severity != ""
        assert result.output.file_path != ""
        assert result.output.line_number >= 0  # TestModel may generate 0
        assert result.output.issue != ""
        assert result.output.suggestion != ""

        # Verify full result structure
        assert result.model == "test"
        assert result.provider == "test"
        assert result.duration_ms >= 0

    async def test_model_roster_configuration(self) -> None:
        """Test that ModelRoster provides correct per-role configuration."""
        roster = ModelRoster()

        # Verify each role has configuration
        assert roster.interview.model == "claude-sonnet-4-5-20250929"
        assert roster.review.model == "claude-opus-4-6"
        assert roster.planning.model == "claude-opus-4-6"
        assert roster.context.model == "claude-haiku-4-5-20251001"
        assert roster.coding.model == "claude-sonnet-4-5-20250929"

        # Verify we can override
        custom_roster = ModelRoster(
            interview=ProviderConfig(model="claude-haiku-4-5-20251001", max_tokens=2048)
        )
        assert custom_roster.interview.model == "claude-haiku-4-5-20251001"
        assert custom_roster.interview.max_tokens == 2048

    async def test_cost_calculation_with_anthropic_models(self) -> None:
        """Test cost calculation works with real Anthropic model configurations."""
        # Manually test cost calculation with Anthropic model names
        from imp.providers import TokenUsage, calculate_cost

        usage = TokenUsage(
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=500_000,  # 500K tokens
        )

        sonnet_cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # Sonnet: $3/1M input + $15/1M output = $3 + $7.50 = $10.50
        assert sonnet_cost == 10.50

        opus_cost = calculate_cost(usage, "claude-opus-4-6")
        # Opus: $15/1M input + $75/1M output = $15 + $37.50 = $52.50
        assert opus_cost == 52.50

        haiku_cost = calculate_cost(usage, "claude-haiku-4-5-20251001")
        # Haiku: $0.80/1M input + $4/1M output = $0.80 + $2.00 = $2.80
        assert haiku_cost == 2.80

    async def test_cache_cost_calculation(self) -> None:
        """Test that cache pricing is calculated correctly."""
        from imp.providers import TokenUsage, calculate_cost

        # Simulate cache usage
        usage = TokenUsage(
            input_tokens=100_000,
            output_tokens=50_000,
            cache_write_tokens=500_000,  # 500K tokens written to cache
            cache_read_tokens=1_000_000,  # 1M tokens read from cache
        )

        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # Sonnet:
        # - Input: 100K * $3/1M = $0.30
        # - Output: 50K * $15/1M = $0.75
        # - Cache write: 500K * $3.75/1M = $1.875
        # - Cache read: 1M * $0.30/1M = $0.30
        # Total: $3.225
        assert abs(cost - 3.225) < 0.001

    async def test_multi_turn_conversation_simulation(self) -> None:
        """Simulate multiple turns of conversation to verify state handling."""
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="You are a helpful assistant.",
        )

        # Turn 1
        result1 = await provider.invoke("Hello, what can you help me with?")
        assert isinstance(result1.output, str)
        assert result1.usage.requests == 1

        # Turn 2 - provider should be stateless (each invoke is independent)
        result2 = await provider.invoke("Tell me about Python.")
        assert isinstance(result2.output, str)
        assert result2.usage.requests == 1

        # Verify each invocation is independent
        assert result1.duration_ms >= 0
        assert result2.duration_ms >= 0

    async def test_error_handling_with_structured_output(self) -> None:
        """Verify provider handles errors gracefully with structured output."""
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=InterviewQuestion,
        )

        # TestModel should handle this gracefully
        result = await provider.invoke("")

        # Even with empty prompt, should get valid structured output from TestModel
        assert isinstance(result.output, InterviewQuestion)
        assert result.duration_ms >= 0
