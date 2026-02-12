"""Integration tests for claude-agent-sdk provider."""

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
