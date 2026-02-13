#!/usr/bin/env python3
"""Smoke test for provider layer - validates real usage patterns.

This script tests the provider layer as a real user would use it:
- Imports modules like a developer would
- Creates providers and invokes them
- Validates cost calculation, model roster, configuration
- Uses real Pydantic AI (with TestModel to avoid API calls)

Run: python tests/smoke/smoke_test_provider.py
Exit code: 0 = pass, 1 = fail

This is NOT a pytest test. This is a smoke test that validates the module
works in the wild, not just in a test harness.
"""

import sys
from pathlib import Path

# Add src to path so we can import imp modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_imports():
    """Test: Can import all public APIs from imp.providers."""
    try:
        from imp.providers import (  # noqa: F401
            AgentProvider,
            AgentResult,
            ModelRoster,
            ProviderConfig,
            PydanticAIProvider,
            TokenUsage,
            calculate_cost,
        )

        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_create_provider():
    """Test: Can create provider instance with TestModel."""
    try:
        from pydantic_ai.models.test import TestModel

        from imp.providers import PydanticAIProvider

        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=str,
            system_prompt="You are a helpful assistant.",
        )
        print("✓ Provider instance created with TestModel")
        return provider
    except Exception as e:
        print(f"✗ Provider creation failed: {e}")
        return None


async def test_invoke_string_output(provider):
    """Test: Can invoke provider and get string output."""
    try:
        result = await provider.invoke("Say hello")

        # Validate result structure
        assert isinstance(result.output, str), "Output should be string"
        assert result.model == "test", "Model should be 'test'"
        assert result.provider == "test", "Provider should be 'test'"
        assert result.duration_ms >= 0, "Duration should be non-negative"

        # Validate usage
        assert result.usage.input_tokens >= 0, "Input tokens should be non-negative"
        assert result.usage.output_tokens >= 0, "Output tokens should be non-negative"
        assert result.usage.total_tokens >= 0, "Total tokens should be non-negative"
        assert result.usage.requests == 1, "Should have 1 request"

        print(f"✓ Provider invoked successfully (tokens: {result.usage.total_tokens})")
        return True
    except Exception as e:
        print(f"✗ Provider invoke failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_invoke_structured_output():
    """Test: Can invoke provider with structured Pydantic output."""
    try:
        from pydantic import BaseModel
        from pydantic_ai.models.test import TestModel

        from imp.providers import PydanticAIProvider

        class Question(BaseModel):
            text: str
            category: str

        provider = PydanticAIProvider(
            model=TestModel(), output_type=Question, system_prompt="Generate questions."
        )

        result = await provider.invoke("Generate a question about Python")

        assert isinstance(result.output, Question), "Output should be Question instance"
        assert hasattr(result.output, "text"), "Output should have 'text' field"
        assert hasattr(result.output, "category"), "Output should have 'category' field"

        print("✓ Structured output (Pydantic model) works")
        return True
    except Exception as e:
        print(f"✗ Structured output failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cost_calculation():
    """Test: Cost calculation works for Anthropic models."""
    try:
        from imp.providers import TokenUsage, calculate_cost

        # Test Sonnet pricing
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        expected = 10.50  # $3/1M input + $15/1M output
        assert abs(cost - expected) < 0.001, f"Expected ${expected}, got ${cost}"

        # Test Opus pricing
        cost = calculate_cost(usage, "claude-opus-4-6")
        expected = 52.50  # $15/1M input + $75/1M output
        assert abs(cost - expected) < 0.001, f"Expected ${expected}, got ${cost}"

        # Test Haiku pricing
        cost = calculate_cost(usage, "claude-haiku-4-5-20251001")
        expected = 2.80  # $0.80/1M input + $4/1M output
        assert abs(cost - expected) < 0.001, f"Expected ${expected}, got ${cost}"

        # Test unknown model returns 0
        cost = calculate_cost(usage, "unknown-model")
        assert cost == 0.0, "Unknown model should return 0.0"

        print("✓ Cost calculation accurate for all Anthropic models")
        return True
    except Exception as e:
        print(f"✗ Cost calculation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cache_cost_calculation():
    """Test: Cache cost calculation includes write/read multipliers."""
    try:
        from imp.providers import TokenUsage, calculate_cost

        usage = TokenUsage(
            input_tokens=100_000,
            output_tokens=50_000,
            cache_write_tokens=500_000,
            cache_read_tokens=1_000_000,
        )

        cost = calculate_cost(usage, "claude-sonnet-4-5-20250929")
        # Input: 100K * $3/1M = $0.30
        # Output: 50K * $15/1M = $0.75
        # Cache write: 500K * $3.75/1M = $1.875
        # Cache read: 1M * $0.30/1M = $0.30
        # Total: $3.225
        expected = 3.225
        assert abs(cost - expected) < 0.001, f"Expected ${expected}, got ${cost}"

        print("✓ Cache cost calculation (write 1.25x, read 0.1x) accurate")
        return True
    except Exception as e:
        print(f"✗ Cache cost calculation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_model_roster_configuration():
    """Test: ModelRoster provides per-role configuration."""
    try:
        from imp.providers import ModelRoster, ProviderConfig

        roster = ModelRoster()

        # Verify defaults
        assert roster.interview.model == "claude-sonnet-4-5-20250929"
        assert roster.review.model == "claude-opus-4-6"
        assert roster.planning.model == "claude-opus-4-6"
        assert roster.context.model == "claude-haiku-4-5-20251001"
        assert roster.coding.model == "claude-sonnet-4-5-20250929"

        # Verify override works
        custom_roster = ModelRoster(
            interview=ProviderConfig(model="claude-haiku-4-5-20251001", max_tokens=2048)
        )
        assert custom_roster.interview.model == "claude-haiku-4-5-20251001"
        assert custom_roster.interview.max_tokens == 2048

        print("✓ ModelRoster configuration (5 roles) working")
        return True
    except Exception as e:
        print(f"✗ ModelRoster configuration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_provider_config():
    """Test: ProviderConfig validation and defaults."""
    try:
        from imp.providers import ProviderConfig

        # Test defaults
        config = ProviderConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 120
        assert config.max_retries == 3
        assert config.temperature is None
        assert config.fallback_model is None

        # Test overrides
        config = ProviderConfig(
            provider="openai",
            model="gpt-4",
            max_tokens=8192,
            temperature=0.7,
            fallback_model="gpt-3.5-turbo",
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.max_tokens == 8192
        assert config.temperature == 0.7
        assert config.fallback_model == "gpt-3.5-turbo"

        print("✓ ProviderConfig defaults and overrides working")
        return True
    except Exception as e:
        print(f"✗ ProviderConfig test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_claude_sdk_integration():
    """Test: claude-agent-sdk integration (if installed)."""
    try:
        # Try to import claude-agent-sdk
        try:
            import claude_agent_sdk  # noqa: F401

            sdk_available = True
        except ImportError:
            sdk_available = False

        if not sdk_available:
            print("⊘ claude-agent-sdk not installed (skipping)")
            return True  # Not a failure, just not installed

        # If SDK is available, test it
        from unittest.mock import patch

        from imp.providers import PydanticAIProvider

        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = "SDK integration test response"

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create provider with claude-agent-sdk model
            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=str,
                system_prompt="Test system prompt",
            )

            result = await provider.invoke("Test prompt")

            # Validate result
            assert isinstance(result.output, str), "Output should be string"
            assert result.model == "claude-code-cli", "Model should be claude-code-cli"
            assert result.provider == "claude-agent-sdk", "Provider should be claude-agent-sdk"
            assert result.usage.cost_usd == 0.0, "Cost should be 0 (Max subscription)"

        print("✓ claude-agent-sdk integration working")
        return True
    except Exception as e:
        print(f"✗ claude-agent-sdk integration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_imp_review_with_claude_sdk():
    """Test: imp review with claude-agent-sdk model end-to-end.

    This validates the full pipeline:
    CLI → ReviewRunner → PydanticAIProvider → ClaudeAgentSDKModel → SDK → ReviewResult

    Tests structured output support for ReviewResult with claude-agent-sdk.
    """
    try:
        # Check if SDK is available
        try:
            import claude_agent_sdk  # noqa: F401

            sdk_available = True
        except ImportError:
            sdk_available = False

        if not sdk_available:
            print("⊘ claude-agent-sdk not installed (skipping review test)")
            return True  # Not a failure

        from pathlib import Path
        from unittest.mock import patch

        from imp.providers import PydanticAIProvider
        from imp.review.models import ReviewResult
        from imp.review.runner import ReviewRunner

        # Create a realistic ReviewResult JSON that SDK would return
        review_json = """{
            "passed": true,
            "issues": [],
            "handoff": null,
            "validation_passed": true,
            "duration_ms": 100
        }"""

        # Mock the SDK to return our JSON
        with patch("imp.providers.claude_sdk_model.query") as mock_query:

            async def mock_iterator():
                class MockMessage:
                    content = review_json

                yield MockMessage()

            mock_query.return_value = mock_iterator()

            # Create provider with ReviewResult output type
            provider = PydanticAIProvider(
                model="claude-agent-sdk",
                output_type=ReviewResult,
                system_prompt="You are a code reviewer.",
            )

            # Create ReviewRunner with the provider
            runner = ReviewRunner(
                project_root=Path("/tmp/test"),
                provider=provider,
            )

            # Run Pass 2 (AI review) directly to test structured output
            result = await runner.run_pass_two(changed_files=["test.py"])

            # Validate result structure
            assert isinstance(result, ReviewResult), "Output should be ReviewResult"
            assert result.passed is True, "Review should pass"
            assert result.issues == [], "Should have no issues"
            assert result.handoff is None, "Should have no handoff"
            assert result.validation_passed is True, "Validation should pass"
            assert result.model == "claude-code-cli", "Model should be claude-code-cli"
            assert result.provider == "claude-agent-sdk", "Provider should be claude-agent-sdk"

        print("✓ imp review --model claude-agent-sdk end-to-end working")
        return True
    except Exception as e:
        print(f"✗ imp review with claude-agent-sdk failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all smoke tests in sequence."""
    print("=" * 60)
    print("Provider Layer Smoke Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Imports
    results.append(test_imports())

    # Test 2: Provider creation
    provider = test_create_provider()
    results.append(provider is not None)

    # Test 3: String output
    if provider:
        results.append(await test_invoke_string_output(provider))

    # Test 4: Structured output
    results.append(await test_invoke_structured_output())

    # Test 5: Cost calculation
    results.append(test_cost_calculation())

    # Test 6: Cache cost calculation
    results.append(test_cache_cost_calculation())

    # Test 7: Model roster
    results.append(test_model_roster_configuration())

    # Test 8: Provider config
    results.append(test_provider_config())

    # Test 9: claude-agent-sdk integration
    results.append(await test_claude_sdk_integration())

    # Test 10: imp review with claude-agent-sdk
    results.append(await test_imp_review_with_claude_sdk())

    print()
    print("=" * 60)

    if all(results):
        print("🎉 All smoke tests passed!")
        print("=" * 60)
        return 0
    else:
        failed = len([r for r in results if not r])
        print(f"❌ {failed} smoke test(s) failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    import asyncio

    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
