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
        assert model.profile.supports_json_schema_output is True

    def test_model_profile_supports_json_schema_output(self) -> None:
        """Model profile reports supports_json_schema_output=True after implementation."""
        model = ClaudeAgentSDKModel()
        # After implementation, this should be True
        # Currently expected to FAIL (TDD - test written before implementation)
        assert model.profile.supports_json_schema_output is True

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


class TestClaudeAgentSDKModelStructuredOutput:
    """Test JSON schema output support for structured data."""

    @pytest.mark.asyncio
    async def test_request_with_output_object_passes_schema_to_sdk(self) -> None:
        """Request with output_object passes output_format to ClaudeAgentOptions."""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            message: str
            score: int

        model = ClaudeAgentSDKModel()

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = '{"message": "test", "score": 42}'

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create request parameters with output_object
            params = ModelRequestParameters(output_object=TestSchema)

            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

                # Verify ClaudeAgentOptions was called with output_format
                assert mock_options.call_count == 1
                call_kwargs = mock_options.call_args.kwargs
                assert "output_format" in call_kwargs
                # Should be wrapped in Messages API structure
                assert isinstance(call_kwargs["output_format"], dict)
                assert call_kwargs["output_format"]["type"] == "json_schema"
                assert "schema" in call_kwargs["output_format"]
                assert "properties" in call_kwargs["output_format"]["schema"]

    @pytest.mark.asyncio
    async def test_request_with_output_object_returns_json_as_text(self) -> None:
        """Request with output_object extracts JSON from markdown wrapper."""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            message: str
            score: int

        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # SDK returns ResultMessage with structured_output (actual SDK behavior)
            async def mock_iterator():
                # Mock ResultMessage with structured_output
                class ResultMessage:
                    def __init__(self) -> None:
                        self.structured_output = {"message": "test", "score": 42}

                yield ResultMessage()

            mock_query.return_value = mock_iterator()

            params = ModelRequestParameters(output_object=TestSchema)

            with patch.object(model, "_get_instructions", return_value=None):
                response = await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

                # Expected to FAIL until implementation
                # Should return JSON string as TextPart
                assert len(response.parts) == 1
                assert isinstance(response.parts[0], TextPart)
                # Content should be valid JSON
                import json

                parsed = json.loads(response.parts[0].content)
                assert parsed["message"] == "test"
                assert parsed["score"] == 42

    @pytest.mark.asyncio
    async def test_request_with_output_object_invalid_json_raises(self) -> None:
        """Request with output_object raises ValueError when SDK returns invalid JSON."""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            message: str
            score: int

        model = ClaudeAgentSDKModel()

        with patch("imp.providers.claude_sdk_model.query") as mock_query:
            # SDK returns non-JSON text
            async def mock_iterator():
                class MockMessage:
                    content = "This is not JSON"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            params = ModelRequestParameters(output_object=TestSchema)

            with (
                patch.object(model, "_get_instructions", return_value=None),
                pytest.raises(ValueError, match="invalid JSON"),
            ):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

    @pytest.mark.asyncio
    async def test_request_without_output_object_works_normally(self) -> None:
        """Request without output_object continues to work (backward compatibility)."""
        model = ClaudeAgentSDKModel()

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = "Regular text response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Request WITHOUT output_object
            params = ModelRequestParameters()

            with patch.object(model, "_get_instructions", return_value=None):
                response = await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

                # Should work normally, returning text
                assert len(response.parts) == 1
                assert response.parts[0].content == "Regular text response"

                # ClaudeAgentOptions should NOT have output_format
                call_kwargs = mock_options.call_args.kwargs
                assert (
                    "output_format" not in call_kwargs or call_kwargs.get("output_format") is None
                )

    @pytest.mark.asyncio
    async def test_request_extracts_schema_from_basemodel(self) -> None:
        """Request correctly extracts JSON schema from Pydantic BaseModel."""
        from pydantic import BaseModel, Field

        class ComplexSchema(BaseModel):
            """A complex schema for testing."""

            name: str = Field(description="The name field")
            value: int = Field(ge=0, le=100, description="Value between 0-100")
            tags: list[str] = Field(default_factory=list)

        model = ClaudeAgentSDKModel()

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = '{"name": "test", "value": 50, "tags": []}'

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            params = ModelRequestParameters(output_object=ComplexSchema)

            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

                # Verify schema was extracted correctly
                call_kwargs = mock_options.call_args.kwargs
                output_format = call_kwargs["output_format"]

                # Should be wrapped in Messages API structure
                assert output_format["type"] == "json_schema"
                assert "schema" in output_format
                schema = output_format["schema"]

                # Should have proper JSON schema structure
                assert "type" in schema
                assert schema["type"] == "object"
                assert "properties" in schema
                assert "name" in schema["properties"]
                assert "value" in schema["properties"]
                assert "tags" in schema["properties"]
                # Should include field constraints/descriptions
                assert schema["properties"]["value"].get("minimum") == 0
                assert schema["properties"]["value"].get("maximum") == 100

    @pytest.mark.asyncio
    async def test_request_with_output_object_none_cli_path(self) -> None:
        """Request with output_object and no custom cli_path works correctly."""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            result: str

        model = ClaudeAgentSDKModel()  # No cli_path specified

        with (
            patch("imp.providers.claude_sdk_model.query") as mock_query,
            patch("imp.providers.claude_sdk_model.ClaudeAgentOptions") as mock_options,
        ):

            async def mock_iterator():
                class MockMessage:
                    content = '{"result": "success"}'

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            params = ModelRequestParameters(output_object=TestSchema)

            with patch.object(model, "_get_instructions", return_value=None):
                await model.request(
                    messages=[],
                    model_settings=None,
                    model_request_parameters=params,
                )

                # Expected to FAIL until implementation
                # Should still pass schema even without custom cli_path
                call_kwargs = mock_options.call_args.kwargs
                assert "output_format" in call_kwargs
                assert call_kwargs["cli_path"] is None


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
