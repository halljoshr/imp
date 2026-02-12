"""Tests for ClaudeAgentSDKModel implementation."""

from unittest.mock import patch

import pytest
from pydantic_ai.messages import TextPart
from pydantic_ai.models import ModelRequestParameters

# Skip all tests if claude-agent-sdk not available
pytest.importorskip("claude_agent_sdk")

from imp.providers.claude_sdk_model import ClaudeAgentSDKModel


class TestClaudeAgentSDKModel:
    """Test ClaudeAgentSDKModel custom model implementation."""

    def test_init_default_values(self) -> None:
        """Initialize with default model name and cli path."""
        model = ClaudeAgentSDKModel()
        assert model.model_name == "claude-code-cli"
        assert model.system == "claude-agent-sdk"
        assert model._cli_path is None

    def test_init_custom_values(self) -> None:
        """Initialize with custom model name and cli path."""
        model = ClaudeAgentSDKModel(model_name="custom-model", cli_path="/custom/path/claude")
        assert model.model_name == "custom-model"
        assert model._cli_path == "/custom/path/claude"

    def test_model_profile_capabilities(self) -> None:
        """Model profile declares correct capabilities."""
        model = ClaudeAgentSDKModel()
        # Access the profile through the Model superclass
        assert model.profile.supports_tools is False
        assert model.profile.supports_json_schema_output is False

    @pytest.mark.asyncio
    async def test_request_returns_model_response(self) -> None:
        """Request returns ModelResponse with correct structure."""
        model = ClaudeAgentSDKModel()

        # Mock the SDK query function
        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # Mock async iterator
            async def mock_iterator():
                class MockMessage:
                    content = "Test response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Mock _get_instructions and use empty messages list
            with patch.object(model, "_get_instructions", return_value=None):
                # Call request with minimal parameters
                response = await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Verify response structure
                assert len(response.parts) == 1
                assert isinstance(response.parts[0], TextPart)
                assert response.model_name == "claude-code-cli"
                assert response.usage.input_tokens > 0
                assert response.usage.output_tokens > 0

    @pytest.mark.asyncio
    async def test_request_includes_usage_details(self) -> None:
        """Request includes usage details with metadata."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # Mock async iterator
            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            with patch.object(model, "_get_instructions", return_value=None):
                response = await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Check usage details
                assert response.usage.details is not None
                assert "duration_ms" in response.usage.details
                assert "estimated" in response.usage.details
                assert (
                    response.usage.details["estimated"] == 1
                )  # 1 = True (details only accepts int)

    @pytest.mark.asyncio
    async def test_request_with_custom_cli_path(self) -> None:
        """Request uses custom CLI path when provided."""
        model = ClaudeAgentSDKModel(cli_path="/custom/claude")

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Verify ClaudeAgentOptions called with cli_path
                mock_options.assert_called_once_with(cli_path="/custom/claude")

    @pytest.mark.asyncio
    async def test_request_handles_sdk_error(self) -> None:
        """Request handles errors from SDK gracefully."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # Mock error in async iterator
            async def mock_error():
                raise RuntimeError("SDK error")
                yield  # Make it a generator

            mock_query.return_value = mock_error()

            with patch.object(model, "_get_instructions", return_value=None):
                response = await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Should return error message, not raise
                assert "Error from claude-agent-sdk" in response.parts[0].content

    def test_estimate_string_tokens_empty(self) -> None:
        """Token estimation handles empty string."""
        assert ClaudeAgentSDKModel._estimate_string_tokens("") == 0

    def test_estimate_string_tokens_single_word(self) -> None:
        """Token estimation for single word."""
        tokens = ClaudeAgentSDKModel._estimate_string_tokens("hello")
        assert tokens == 1

    def test_estimate_string_tokens_multiple_words(self) -> None:
        """Token estimation splits on word boundaries."""
        tokens = ClaudeAgentSDKModel._estimate_string_tokens("hello world test")
        assert tokens == 3

    def test_estimate_string_tokens_with_punctuation(self) -> None:
        """Token estimation handles punctuation."""
        tokens = ClaudeAgentSDKModel._estimate_string_tokens("Hello, world! How are you?")
        # "Hello", "world", "How", "are", "you" = 5 tokens
        assert tokens == 5

    def test_estimate_string_tokens_with_whitespace(self) -> None:
        """Token estimation handles extra whitespace."""
        tokens = ClaudeAgentSDKModel._estimate_string_tokens("  hello   world  ")
        assert tokens == 2

    def test_estimate_usage_includes_overhead(self) -> None:
        """Usage estimation includes 50 token overhead."""
        model = ClaudeAgentSDKModel()

        # Use empty messages list
        messages = []
        response_text = "response"

        usage = model._estimate_usage(messages, response_text)

        # Should have at least 50 tokens overhead
        assert usage.input_tokens == 50  # Just overhead for empty messages
        assert usage.output_tokens > 0

    @pytest.mark.asyncio
    async def test_estimate_usage_counts_response_tokens(self) -> None:
        """Usage estimation counts response tokens."""
        model = ClaudeAgentSDKModel()

        messages = []
        response_text = "one two three four five"  # 5 tokens

        usage = model._estimate_usage(messages, response_text)

        # Should estimate ~5 tokens for response
        assert usage.output_tokens == 5

    @pytest.mark.asyncio
    async def test_call_sdk_isolated_returns_text(self) -> None:
        """SDK call isolation returns concatenated text."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # Mock multiple chunks
            async def mock_iterator():
                class MockMessage:
                    def __init__(self, content):
                        self.content = content

                yield MockMessage("Hello ")
                yield MockMessage("world")

            mock_query.return_value = mock_iterator()

            result = await model._call_sdk_isolated("test prompt", None)
            assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_call_sdk_isolated_handles_string_chunks(self) -> None:
        """SDK call isolation handles raw string chunks."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                yield "chunk1"
                yield "chunk2"

            mock_query.return_value = mock_iterator()

            result = await model._call_sdk_isolated("test prompt", None)
            assert result == "chunk1chunk2"

    @pytest.mark.asyncio
    async def test_call_sdk_isolated_handles_other_types(self) -> None:
        """SDK call isolation handles other chunk types via str()."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class CustomChunk:
                    def __str__(self):
                        return "custom"

                yield CustomChunk()

            mock_query.return_value = mock_iterator()

            result = await model._call_sdk_isolated("test prompt", None)
            assert result == "custom"

    @pytest.mark.asyncio
    async def test_call_sdk_isolated_handles_exception(self) -> None:
        """SDK call isolation handles exceptions in outer context."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.asyncio.create_task") as mock_task:
            # Simulate exception in create_task
            mock_task.side_effect = RuntimeError("Task error")

            result = await model._call_sdk_isolated("test prompt", None)
            assert "Error calling claude-agent-sdk" in result

    @pytest.mark.asyncio
    async def test_request_with_messages_having_role_and_content(self) -> None:
        """Request formats messages with role and content attributes."""
        from unittest.mock import MagicMock

        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create mock message with role and content attributes
            mock_message = MagicMock()
            mock_message.role = "user"
            mock_message.content = "Test message"

            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[mock_message],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Verify query was called with formatted message
                call_args = mock_query.call_args
                assert call_args is not None
                prompt = call_args.kwargs.get("prompt", "")
                # The message formatting line should be covered
                assert "user: Test message" in prompt


class TestClaudeAgentSDKModelWithSystemPrompt:
    """Test handling of system prompts and message formatting."""

    @pytest.mark.asyncio
    async def test_request_builds_prompt_with_system(self) -> None:
        """Request builds prompt including system instructions."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Mock _get_instructions to return a system prompt
            with patch.object(model, "_get_instructions", return_value="System prompt"):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Verify query was called with prompt containing system instructions
                call_args = mock_query.call_args
                assert call_args is not None
                # Prompt is always passed as kwarg
                prompt = call_args.kwargs.get("prompt", "")
                assert "System: System prompt" in prompt

    @pytest.mark.asyncio
    async def test_request_builds_prompt_without_system(self) -> None:
        """Request builds prompt without system instructions when None."""
        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "Response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Mock _get_instructions to return None
            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=ModelRequestParameters(),
                )

                # Verify query was called without system instructions
                call_args = mock_query.call_args
                assert call_args is not None
                # Prompt is always passed as kwarg
                prompt = call_args.kwargs.get("prompt", "")
                assert "System:" not in prompt
