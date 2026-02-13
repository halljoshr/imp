"""Integration tests for claude-agent-sdk provider."""

import json
from unittest.mock import patch

import pytest

# Skip all tests if claude-agent-sdk not available
pytest.importorskip("claude_agent_sdk")

from imp.providers.pydantic_ai import PydanticAIProvider


class TestClaudeSDKIntegration:
    """Integration tests for full workflows with claude-agent-sdk."""

    @pytest.mark.asyncio
    async def test_end_to_end_invoke_workflow(self) -> None:
        """Complete workflow from provider creation to result."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Integration test response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create provider
            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=str,
                system_prompt="You are a helpful assistant",
            )

            # Invoke
            result = await provider.invoke("What is 2+2?")

            # Verify complete result
            assert isinstance(result.output, str)
            assert result.usage.input_tokens > 0
            assert result.usage.output_tokens > 0
            assert result.usage.cost_usd == 0.0  # No API cost
            assert result.duration_ms > 0
            assert result.model == "claude-code-cli"
            assert result.provider == "claude-agent-sdk"

    @pytest.mark.asyncio
    async def test_multiple_sequential_invokes(self) -> None:
        """Multiple sequential invokes accumulate usage correctly."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # Create a new iterator for each call
            def mock_iterator_factory():
                async def mock_iterator():
                    class MockMessage:
                        content = "Response"

                    yield MockMessage()

                return mock_iterator()

            mock_query.side_effect = lambda **kwargs: mock_iterator_factory()

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)

            # Make multiple invokes
            results = []
            for i in range(3):
                result = await provider.invoke(f"Request {i}")
                results.append(result)

            # Verify each result is independent
            for result in results:
                assert result.usage.requests == 1
                assert result.usage.input_tokens > 0
                assert result.usage.output_tokens > 0

            # Verify total usage
            total_input = sum(r.usage.input_tokens for r in results)
            total_output = sum(r.usage.output_tokens for r in results)
            assert total_input > 0
            assert total_output > 0

    @pytest.mark.asyncio
    async def test_error_recovery(self) -> None:
        """Provider handles SDK errors gracefully."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_error():
                raise RuntimeError("SDK connection error")
                yield  # Make it a generator

            mock_query.return_value = mock_error()

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)
            result = await provider.invoke("test prompt")

            # Should return error in response, not raise
            assert "Error from claude-agent-sdk" in result.output
            assert result.usage.requests == 1

    @pytest.mark.asyncio
    async def test_long_prompt_handling(self) -> None:
        """Handles long prompts with correct token estimation."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Long response " * 100

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)

            # Send long prompt
            long_prompt = "This is a test prompt " * 100
            result = await provider.invoke(long_prompt)

            # Token counts should reflect length
            assert result.usage.input_tokens > 100  # Long prompt
            assert result.usage.output_tokens > 100  # Long response

    @pytest.mark.asyncio
    async def test_custom_cli_path_integration(self) -> None:
        """Custom CLI path flows through to SDK."""
        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Import and create model directly with custom path
            from imp.providers.claude_sdk_model import ClaudeAgentSDKModel

            model = ClaudeAgentSDKModel(cli_path="/custom/claude/path")
            provider = PydanticAIProvider(model=model, output_type=str)

            await provider.invoke("test")

            # Verify CLI path was used
            mock_options.assert_called_once_with(cli_path="/custom/claude/path")

    @pytest.mark.asyncio
    async def test_pydantic_ai_provider_creates_sdk_model_with_structured_output(self) -> None:
        """PydanticAIProvider with BaseModel output_type creates SDK model correctly."""
        from imp.review.models import ReviewResult

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    # Return a valid ReviewResult JSON
                    content = """{
                        "passed": true,
                        "issues": [],
                        "validation_passed": true,
                        "duration_ms": 100
                    }"""

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create provider with Pydantic BaseModel output type
            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ReviewResult,  # Structured output type
                system_prompt="Review this code",
            )

            # Verify model was created
            assert provider._agent is not None
            # Model should be ClaudeAgentSDKModel
            from imp.providers.claude_sdk_model import ClaudeAgentSDKModel

            # Access the underlying model through the agent
            assert isinstance(provider._agent.model, ClaudeAgentSDKModel)

    @pytest.mark.asyncio
    async def test_structured_output_end_to_end_with_review_result(self) -> None:
        """Full flow: Pydantic AI → SDK model → mocked SDK → ReviewResult instance."""
        from imp.review.models import ReviewCategory, ReviewResult, ReviewSeverity

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    # Return a ReviewResult with one issue
                    content = (
                        '{"passed": false, "issues": ['
                        '{"path": "src/example.py", "line": 42, '
                        '"severity": "HIGH", "category": "bug", '
                        '"message": "Uncaught exception will crash", '
                        '"suggested_fix": "Add try/except", '
                        '"agent_prompt": "Fix the exception handling"}], '
                        '"handoff": {"agent_prompt": "Fix the issue", '
                        '"relevant_files": ["src/example.py"], "issues": ['
                        '{"path": "src/example.py", "line": 42, '
                        '"severity": "HIGH", "category": "bug", '
                        '"message": "Uncaught exception will crash", '
                        '"suggested_fix": "Add try/except", '
                        '"agent_prompt": "Fix the exception handling"}]}, '
                        '"validation_passed": true, "duration_ms": 200, '
                        '"model": "claude-code-cli", '
                        '"provider": "claude-agent-sdk"}'
                    )

                yield MockMessage()

            mock_query.return_value = mock_iterator()
            mock_options.return_value = None  # ClaudeAgentOptions instance

            # Create provider with ReviewResult output type
            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ReviewResult,
                system_prompt="Review this code",
            )

            # Invoke - should return ReviewResult instance
            result = await provider.invoke("Review src/example.py")

            # Verify result is properly structured
            assert isinstance(result.output, ReviewResult)
            assert result.output.passed is False
            assert len(result.output.issues) == 1
            assert result.output.issues[0].severity == ReviewSeverity.HIGH
            assert result.output.issues[0].category == ReviewCategory.BUG
            assert result.output.handoff is not None
            assert result.output.validation_passed is True

            # Verify usage tracking
            assert result.usage.input_tokens > 0
            assert result.usage.output_tokens > 0
            assert result.usage.cost_usd == 0.0  # No API cost

    @pytest.mark.asyncio
    async def test_structured_output_with_complex_nested_models(self) -> None:
        """Complex nested Pydantic models work through SDK."""
        from pydantic import BaseModel

        class NestedItem(BaseModel):
            """Nested model for testing."""

            name: str
            value: int

        class ComplexResult(BaseModel):
            """Complex model with nested structures."""

            items: list[NestedItem]
            metadata: dict[str, str]
            count: int

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = """{
                        "items": [
                            {"name": "item1", "value": 10},
                            {"name": "item2", "value": 20}
                        ],
                        "metadata": {"source": "test", "version": "1.0"},
                        "count": 2
                    }"""

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ComplexResult,
            )

            result = await provider.invoke("Generate test data")

            # Verify nested structure is properly parsed
            assert isinstance(result.output, ComplexResult)
            assert len(result.output.items) == 2
            assert result.output.items[0].name == "item1"
            assert result.output.items[0].value == 10
            assert result.output.metadata["source"] == "test"
            assert result.output.count == 2

    @pytest.mark.asyncio
    async def test_structured_output_error_propagation(self) -> None:
        """Errors from SDK properly propagate through to provider."""
        from imp.review.models import ReviewResult

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_error():
                raise RuntimeError("SDK failed to generate structured output")
                yield  # Make it a generator

            mock_query.return_value = mock_error()

            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ReviewResult,
            )

            # When SDK fails with structured output, Pydantic AI raises UnexpectedModelBehavior
            # after retrying (because the error string can't be parsed as ReviewResult)
            with pytest.raises(Exception) as exc_info:
                await provider.invoke("Review code")

            # Verify it's the expected exception type
            assert "Exceeded maximum retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fallback_when_sdk_not_available(self) -> None:
        """Provider falls back gracefully when claude-agent-sdk not installed."""
        from imp.review.models import ReviewResult

        # Patch CLAUDE_SDK_AVAILABLE to False to simulate SDK not installed
        with patch("imp.providers.claude_sdk_model.CLAUDE_SDK_AVAILABLE", False):
            # Attempting to create provider with claude-agent-sdk should raise ImportError
            with pytest.raises(ImportError) as exc_info:
                PydanticAIProvider(
                    model="claude-agent-sdk",
                    output_type=ReviewResult,
                )

            # Verify error message is helpful
            assert "claude-agent-sdk is not installed" in str(exc_info.value)
            assert "pip install impx[claude-sdk]" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_structured_output_with_invalid_json_response(self) -> None:
        """SDK returns invalid JSON - error is caught and reported."""
        from imp.review.models import ReviewResult

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    # Return invalid JSON (missing closing brace)
                    content = '{"passed": true, "issues": []'

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ReviewResult,
            )

            # This will fail during Pydantic parsing phase
            # The SDK returns the malformed JSON, but Pydantic AI should raise validation error
            with pytest.raises((json.JSONDecodeError, ValueError)):
                await provider.invoke("Review code")


class TestClaudeSDKWithMetrics:
    """Integration tests with metrics collection."""

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self) -> None:
        """Metrics can be collected from claude-agent-sdk results."""
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Metrics test"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            from imp.metrics import MetricsCollector

            provider = PydanticAIProvider(model="claude-agent-sdk", output_type=str)
            collector = MetricsCollector()

            # Invoke and collect metrics
            result = await provider.invoke("test prompt")
            collector.record_from_result(
                result, agent_role="test-role", operation="test", ticket_id="TEST-001"
            )

            # Verify metrics
            events = collector.get_events()
            assert len(events) == 1
            assert events[0].agent_role == "test-role"
            assert events[0].ticket_id == "TEST-001"
            assert events[0].usage.input_tokens > 0
            assert events[0].usage.cost_usd == 0.0  # No API cost
