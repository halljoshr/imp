"""Custom Pydantic AI model for claude-agent-sdk integration.

This module provides a Pydantic AI compatible model wrapper around claude-agent-sdk,
allowing Max subscription usage through the standard provider abstraction.
"""

from __future__ import annotations

import asyncio
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
        # NOTE: claude-agent-sdk has built-in tools, but we're using it as a
        # simple completion model through Pydantic AI
        profile = ModelProfile(
            supports_tools=False,  # SDK has its own tool system
            supports_json_schema_output=False,  # No native structured output
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
        # REQUIRED: Always call prepare_request first (merges settings, validates)
        model_settings, model_request_parameters = self.prepare_request(
            model_settings, model_request_parameters
        )

        # Extract system prompt if present
        instructions = self._get_instructions(messages, model_request_parameters)

        # Build the prompt for claude-agent-sdk
        # NOTE: SDK expects a single string prompt, not chat messages
        prompt_parts = []

        # Add system prompt if present
        if instructions:
            prompt_parts.append(f"System: {instructions}")

        # Add message history
        for msg in messages:
            if hasattr(msg, "role") and hasattr(msg, "content"):
                prompt_parts.append(f"{msg.role}: {msg.content}")

        full_prompt = "\n\n".join(prompt_parts)

        # Track timing
        start = time.monotonic()

        # Configure SDK options
        options = ClaudeAgentOptions(cli_path=self._cli_path) if self._cli_path else None

        # Make the request via claude-agent-sdk
        # NOTE: Isolate the SDK call to avoid async context manager conflicts
        result_text = await self._call_sdk_isolated(full_prompt, options)

        # Calculate duration
        duration_ms = int((time.monotonic() - start) * 1000)

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
            try:
                async for chunk in query(prompt=prompt, options=options):
                    # Extract text content from different chunk types
                    if hasattr(chunk, "content"):
                        # AssistantMessage, SystemMessage, etc.
                        chunks.append(str(chunk.content))
                    elif isinstance(chunk, str):
                        chunks.append(chunk)
                    else:
                        # StreamEvent or other types
                        chunks.append(str(chunk))
            except Exception as e:
                return f"Error from claude-agent-sdk: {e}"
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
