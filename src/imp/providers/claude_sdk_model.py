"""Custom Pydantic AI model for claude-agent-sdk integration.

This module provides a Pydantic AI compatible model wrapper around claude-agent-sdk,
allowing Max subscription usage through the standard provider abstraction.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

try:
    from claude_agent_sdk import ClaudeAgentOptions, query

    CLAUDE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    CLAUDE_SDK_AVAILABLE = False
    # Graceful degradation - module can be imported but will raise when used
    ClaudeAgentOptions = None  # type: ignore
    query = None  # type: ignore


@dataclass(init=False)
class ClaudeAgentSDKModel(Model):
    """Custom Pydantic AI model that wraps claude-agent-sdk.

    This allows using Claude Max subscription quota through Pydantic AI's
    abstraction layer, maintaining usage tracking and provider consistency.

    Supports structured output via claude-agent-sdk's output_format parameter.

    Note: claude-agent-sdk must be installed separately:
        pip install claude-agent-sdk>=0.1.35
    """

    _model_name: str
    _cli_path: str | None

    def __init__(
        self,
        model_name: str = "claude-code-cli",
        cli_path: str | None = None,
    ):
        """Initialize the claude-agent-sdk model.

        Args:
            model_name: Display name for the model (default: claude-code-cli)
            cli_path: Optional path to Claude Code CLI binary
        """
        if not CLAUDE_SDK_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "claude-agent-sdk is not installed. Install with: pip install impx[claude-sdk]"
            )

        self._model_name = model_name
        self._cli_path = cli_path

        # Define model capabilities
        profile = ModelProfile(
            supports_tools=False,  # SDK has its own tool system (not using for now)
            supports_json_schema_output=True,  # Native JSON schema via output_format
            default_structured_output_mode="native",  # Use native JSON schema by default
        )

        super().__init__(profile=profile)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a request to claude-agent-sdk.

        This is the core method that Pydantic AI calls to get completions.

        Args:
            messages: List of conversation messages
            model_settings: Optional model settings
            model_request_parameters: Request parameters (includes instructions)

        Returns:
            ModelResponse with completion text and usage estimates
        """
        # Check for structured output request BEFORE prepare_request
        # (prepare_request may clear it for some model types)
        output_object = model_request_parameters.output_object

        # REQUIRED: Always call prepare_request first (merges settings, validates)
        model_settings, model_request_parameters = self.prepare_request(
            model_settings, model_request_parameters
        )

        # Extract system prompt if present
        instructions = self._get_instructions(messages, model_request_parameters)

        # Build the prompt for claude-agent-sdk
        full_prompt = self._build_prompt(messages, instructions)

        # Track timing
        start = time.monotonic()

        # Configure SDK options
        if output_object is not None:
            # Structured output mode - extract and pass JSON schema
            # output_object can be either a Pydantic BaseModel class or OutputObjectDefinition
            if hasattr(output_object, "model_json_schema"):
                # Pydantic BaseModel class - extract schema
                schema = output_object.model_json_schema()
            else:
                # OutputObjectDefinition - schema already extracted
                schema = output_object.json_schema
            # Wrap schema in Messages API structure (required by SDK)
            # SDK expects: {"type": "json_schema", "schema": {actual_schema}}
            output_format = {"type": "json_schema", "schema": schema}
            options = ClaudeAgentOptions(cli_path=self._cli_path, output_format=output_format)
        else:
            # Text completion mode
            options = ClaudeAgentOptions(cli_path=self._cli_path)

        # Make the request via claude-agent-sdk
        # NOTE: Isolate the SDK call to avoid async context manager conflicts
        result_text = await self._call_sdk_isolated(full_prompt, options)

        # Calculate duration
        duration_ms = int((time.monotonic() - start) * 1000)

        # FALLBACK: SDK may wrap structured output in markdown in some cases.
        # Extract JSON from markdown wrapper if present.
        # NOTE: SDK normally returns structured_output directly (see _call_sdk_isolated)
        if (
            output_object is not None and result_text and not result_text.startswith("Error")
        ):  # pragma: no cover
            # Check for markdown JSON wrapper: ```json\n{...}\n```
            if result_text.strip().startswith("```json"):  # pragma: no cover
                # Extract JSON from markdown code block
                match = re.search(r"```json\s*\n(.*?)\n```", result_text, re.DOTALL)
                if match:  # pragma: no cover
                    result_text = match.group(1).strip()

            # Validate extracted JSON
            try:
                json.loads(result_text)  # Validate JSON syntax
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"claude-agent-sdk returned invalid JSON for structured output: {e}"
                ) from e

        # Estimate token usage (SDK doesn't expose real counts)
        usage = self._estimate_usage(messages, result_text)

        # Add duration to usage details (details only accepts int values)
        usage.details["duration_ms"] = duration_ms
        usage.details["estimated"] = 1  # 1 = True (details only accepts int)

        # Return ModelResponse
        return ModelResponse(
            parts=[TextPart(content=result_text)],
            model_name=self._model_name,
            usage=usage,
        )

    @property
    def model_name(self) -> str:
        """The model name for display/logging."""
        return self._model_name

    @property
    def system(self) -> str:
        """The provider identifier (used for OpenTelemetry, metrics)."""
        return "claude-agent-sdk"

    def _build_prompt(self, messages: list[ModelMessage], instructions: str | None) -> str:
        """Build full prompt string from messages and instructions.

        Extracted for testability and clarity.

        Args:
            messages: List of conversation messages
            instructions: Optional system instructions

        Returns:
            Full prompt string for claude-agent-sdk
        """
        prompt_parts = []

        # Add system prompt if present
        if instructions:
            prompt_parts.append(f"System: {instructions}")

        # Add message history
        for msg in messages:
            if hasattr(msg, "role") and hasattr(msg, "content"):
                prompt_parts.append(f"{msg.role}: {msg.content}")

        return "\n\n".join(prompt_parts)

    async def _call_sdk_isolated(self, prompt: str, options: ClaudeAgentOptions | None) -> str:
        """Call claude-agent-sdk in an isolated async context.

        This avoids cancel scope conflicts between claude-agent-sdk's anyio
        task groups and Pydantic AI's pydantic-graph task management.

        Args:
            prompt: The full prompt to send
            options: Optional SDK configuration

        Returns:
            The concatenated response text
        """

        async def _consume_stream() -> str:
            """Consume the SDK stream in a separate task."""
            chunks: list[str] = []
            result_message = None
            try:
                async for chunk in query(prompt=prompt, options=options):
                    # Check for ResultMessage with structured_output
                    if type(chunk).__name__ == "ResultMessage":
                        result_message = chunk
                    # Extract text content from different chunk types
                    elif hasattr(chunk, "content"):
                        # AssistantMessage, SystemMessage, etc.
                        chunks.append(str(chunk.content))
                    elif isinstance(chunk, str):
                        chunks.append(chunk)
                    else:
                        # StreamEvent or other types
                        chunks.append(str(chunk))
            except Exception as e:
                return f"Error from claude-agent-sdk: {e}"

            # If structured output is available, return it as JSON
            if (
                result_message
                and hasattr(result_message, "structured_output")
                and result_message.structured_output is not None
            ):
                return json.dumps(result_message.structured_output)

            return "".join(chunks)

        # Run in a separate task to isolate the async context
        try:
            result = await asyncio.create_task(_consume_stream())
            return result
        except Exception as e:
            return f"Error calling claude-agent-sdk: {e}"

    @staticmethod
    def _estimate_string_tokens(text: str) -> int:
        """Estimate tokens using word-boundary splitting.

        This matches the approach in pydantic_ai.models.test._estimate_string_tokens
        which splits on whitespace and punctuation to approximate tokenization.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        # Split on word boundaries (whitespace, punctuation)
        tokens = re.split(r"\W+", text.strip())
        return len([t for t in tokens if t])  # Filter empty strings

    def _estimate_usage(self, messages: list[ModelMessage], response_text: str) -> RequestUsage:
        """Estimate token usage for request and response.

        Uses same approach as Pydantic AI's TestModel:
        - ~50 token overhead for the API call
        - Word-boundary splitting for token estimation

        Args:
            messages: Input messages
            response_text: Response text

        Returns:
            RequestUsage with estimated token counts
        """
        # Start with API call overhead (same as TestModel)
        input_tokens = 50

        # Estimate tokens from messages
        for msg in messages:
            # Messages are complex objects - estimate from string representation
            msg_str = str(msg)
            input_tokens += self._estimate_string_tokens(msg_str)

        # Estimate output tokens
        output_tokens = self._estimate_string_tokens(response_text)

        return RequestUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
