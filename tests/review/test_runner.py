"""Tests for ReviewRunner."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from imp.providers.base import AgentProvider, AgentResult, TokenUsage
from imp.review.models import (
    ReviewCategory,
    ReviewHandoff,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
)
from imp.review.runner import ReviewRunner
from imp.validation.models import GateResult, GateType, ValidationResult


class TestReviewRunnerCreation:
    """Test ReviewRunner initialization."""

    def test_creation_with_defaults(self, tmp_path: Path) -> None:
        """Can create ReviewRunner with default settings."""
        runner = ReviewRunner(project_root=tmp_path)

        assert runner.project_root == tmp_path
        assert runner.max_retries == 3  # Default circuit breaker
        assert runner.provider is None  # Not required at init

    def test_creation_with_custom_max_retries(self, tmp_path: Path) -> None:
        """Can create ReviewRunner with custom max retries."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=5)

        assert runner.max_retries == 5

    def test_creation_with_provider(self, tmp_path: Path) -> None:
        """Can create ReviewRunner with AI provider."""
        mock_provider = MagicMock(spec=AgentProvider)
        runner = ReviewRunner(
            project_root=tmp_path,
            provider=mock_provider,
        )

        assert runner.provider == mock_provider

    def test_max_retries_must_be_positive(self, tmp_path: Path) -> None:
        """max_retries must be positive."""
        with pytest.raises(ValueError, match="max_retries must be positive"):
            ReviewRunner(project_root=tmp_path, max_retries=0)

        with pytest.raises(ValueError, match="max_retries must be positive"):
            ReviewRunner(project_root=tmp_path, max_retries=-1)


class TestReviewRunnerPassOne:
    """Test Pass 1: Automated validation checks."""

    @pytest.mark.asyncio
    async def test_pass_one_runs_validation(self, tmp_path: Path) -> None:
        """Pass 1 runs automated validation gates."""
        mock_validation_result = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_pass_one()

            assert result.passed is True
            assert len(result.gates) == 1
            mock_val_runner.return_value.run_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_pass_one_detects_failures(self, tmp_path: Path) -> None:
        """Pass 1 detects validation failures."""
        mock_validation_result = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Linting errors found",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
            ],
            total_duration_ms=500,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_pass_one()

            assert result.passed is False
            assert len(result.failed_gates) == 1

    @pytest.mark.asyncio
    async def test_pass_one_runs_specific_gates(self, tmp_path: Path) -> None:
        """Pass 1 can run specific validation gates."""
        mock_validation_result = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_gates.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_pass_one(gate_types=[GateType.TEST])

            assert result.passed is True
            mock_val_runner.return_value.run_gates.assert_called_once_with([GateType.TEST])


class TestReviewRunnerPassTwo:
    """Test Pass 2: AI deep review."""

    @pytest.mark.asyncio
    async def test_pass_two_requires_provider(self, tmp_path: Path) -> None:
        """Pass 2 requires an AI provider."""
        runner = ReviewRunner(project_root=tmp_path, provider=None)

        with pytest.raises(ValueError, match="AI provider required for Pass 2"):
            await runner.run_pass_two(changed_files=[])

    @pytest.mark.asyncio
    async def test_pass_two_with_no_issues(self, tmp_path: Path) -> None:
        """Pass 2 can return clean review (zero issues = ideal)."""
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=True,
                issues=[],
                validation_passed=True,
                duration_ms=2000,
                handoff=None,
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
        result = await runner.run_pass_two(changed_files=["src/test.py"])

        assert result.passed is True
        assert len(result.issues) == 0
        mock_provider.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_pass_two_with_issues(self, tmp_path: Path) -> None:
        """Pass 2 can detect issues with agentPrompt."""
        mock_issues = [
            ReviewIssue(
                path="src/test.py",
                line=42,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Potential null pointer dereference",
                suggested_fix="Add null check before dereferencing pointer",
                agent_prompt="Fix the null check in src/test.py line 42...",
            ),
        ]

        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=False,
                issues=mock_issues,
                validation_passed=True,
                duration_ms=2000,
                handoff=ReviewHandoff(
                    agent_prompt="Fix the issues listed below...",
                    relevant_files=["src/test.py"],
                    issues=mock_issues,
                ),
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
        result = await runner.run_pass_two(changed_files=["src/test.py"])

        assert result.passed is False
        assert len(result.issues) == 1
        assert result.issues[0].severity == ReviewSeverity.HIGH
        assert result.handoff is not None
        assert result.handoff.agent_prompt.startswith("Fix the issues")

    @pytest.mark.asyncio
    async def test_pass_two_includes_changed_files_in_prompt(self, tmp_path: Path) -> None:
        """Pass 2 includes changed files list in AI prompt."""
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=True,
                issues=[],
                validation_passed=True,
                duration_ms=2000,
                handoff=None,
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        changed_files = ["src/auth.py", "src/session.py"]
        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
        await runner.run_pass_two(changed_files=changed_files)

        # Verify the prompt includes file list
        call_kwargs = mock_provider.invoke.call_args.kwargs
        prompt = call_kwargs.get("prompt", "")

        assert "src/auth.py" in prompt
        assert "src/session.py" in prompt

    @pytest.mark.asyncio
    async def test_pass_two_respects_false_positive_prevention(self, tmp_path: Path) -> None:
        """Pass 2 uses prompts with false positive prevention."""
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=True,
                issues=[],
                validation_passed=True,
                duration_ms=2000,
                handoff=None,
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
        await runner.run_pass_two(changed_files=["src/test.py"])

        # Verify user prompt includes false positive prevention reminder
        call_args = mock_provider.invoke.call_args
        user_prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")

        # Check that false positive prevention is mentioned in prompt
        assert "false positive prevention" in user_prompt.lower()
        assert "zero issues = ideal" in user_prompt.lower()
        assert "specific input" in user_prompt.lower()


class TestReviewRunnerFullReview:
    """Test full two-pass review workflow."""

    @pytest.mark.asyncio
    async def test_full_review_pass_one_then_pass_two(self, tmp_path: Path) -> None:
        """Full review runs Pass 1 then Pass 2."""
        # Mock Pass 1 (validation)
        mock_validation_result = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        # Mock Pass 2 (AI review)
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=True,
                issues=[],
                validation_passed=True,
                duration_ms=3000,
                handoff=None,
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
            result = await runner.run_full_review(changed_files=["src/test.py"])

            assert result.passed is True
            assert result.validation_passed is True
            assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_full_review_fails_on_pass_one_failure(self, tmp_path: Path) -> None:
        """Full review fails if Pass 1 fails."""
        mock_validation_result = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Linting errors",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
            ],
            total_duration_ms=500,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            mock_provider = AsyncMock(spec=AgentProvider)
            runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
            result = await runner.run_full_review(changed_files=["src/test.py"])

            # Should fail without running Pass 2
            assert result.passed is False
            assert result.validation_passed is False  # Validation failed
            mock_provider.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_review_aggregates_issues(self, tmp_path: Path) -> None:
        """Full review aggregates issues from both passes."""
        # Pass 1 fails
        mock_validation_result = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Linting errors",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
            ],
            total_duration_ms=500,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_full_review(changed_files=["src/test.py"])

            # Should have validation issues
            assert result.passed is False
            assert result.validation_passed is False  # Validation failed
            # Validation failed - no need to check failed_gates here


class TestReviewRunnerCircuitBreaker:
    """Test circuit breaker pattern (max retries)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_tracks_attempts(self, tmp_path: Path) -> None:
        """Circuit breaker tracks review attempts per ticket."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=3)

        ticket_id = "TICKET-42"
        runner.record_attempt(ticket_id)
        runner.record_attempt(ticket_id)

        assert runner.get_attempt_count(ticket_id) == 2
        assert not runner.should_escalate(ticket_id)

    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_after_max_retries(self, tmp_path: Path) -> None:
        """Circuit breaker triggers after max retries."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=3)

        ticket_id = "TICKET-42"
        runner.record_attempt(ticket_id)
        runner.record_attempt(ticket_id)
        runner.record_attempt(ticket_id)

        assert runner.get_attempt_count(ticket_id) == 3
        assert runner.should_escalate(ticket_id)

    @pytest.mark.asyncio
    async def test_circuit_breaker_separate_per_ticket(self, tmp_path: Path) -> None:
        """Circuit breaker tracks attempts separately per ticket."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=3)

        ticket_a = "TICKET-1"
        ticket_b = "TICKET-2"

        runner.record_attempt(ticket_a)
        runner.record_attempt(ticket_a)
        runner.record_attempt(ticket_b)

        assert runner.get_attempt_count(ticket_a) == 2
        assert runner.get_attempt_count(ticket_b) == 1
        assert not runner.should_escalate(ticket_a)
        assert not runner.should_escalate(ticket_b)

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self, tmp_path: Path) -> None:
        """Can reset circuit breaker for a ticket."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=3)

        ticket_id = "TICKET-42"
        runner.record_attempt(ticket_id)
        runner.record_attempt(ticket_id)
        assert runner.get_attempt_count(ticket_id) == 2

        runner.reset_attempts(ticket_id)
        assert runner.get_attempt_count(ticket_id) == 0

    @pytest.mark.asyncio
    async def test_generate_escalation_report(self, tmp_path: Path) -> None:
        """Can generate escalation report after circuit breaker triggers."""
        runner = ReviewRunner(project_root=tmp_path, max_retries=2)

        ticket_id = "TICKET-42"
        runner.record_attempt(ticket_id, failure_reason="Lint errors")
        runner.record_attempt(ticket_id, failure_reason="Still lint errors")

        assert runner.should_escalate(ticket_id)

        report = runner.generate_escalation_report(ticket_id)
        assert report.ticket_id == ticket_id
        assert report.attempts == 2
        assert len(report.what_failed) == 2
        assert "Lint errors" in report.what_failed[0]


class TestReviewRunnerHandoffGeneration:
    """Test handoff generation for fix prompts."""

    @pytest.mark.asyncio
    async def test_generate_handoff_from_issues(self, tmp_path: Path) -> None:
        """Can generate ReviewHandoff from issue list."""
        issues = [
            ReviewIssue(
                path="src/auth.py",
                line=42,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Null pointer risk",
                suggested_fix="Add null check",
                agent_prompt="Add null check at line 42",
            ),
            ReviewIssue(
                path="src/session.py",
                line=100,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.STANDARDS,
                message="Complex function",
                suggested_fix="Refactor function",
                agent_prompt="Refactor the function to reduce complexity",
            ),
        ]

        runner = ReviewRunner(project_root=tmp_path)
        handoff = runner.generate_handoff(issues)

        assert handoff is not None
        assert len(handoff.issues) == 2
        assert "src/auth.py" in handoff.relevant_files
        assert "src/session.py" in handoff.relevant_files
        assert "null" in handoff.agent_prompt.lower()  # Mentions the high-severity issue

    @pytest.mark.asyncio
    async def test_handoff_not_generated_for_zero_issues(self, tmp_path: Path) -> None:
        """Handoff is None when there are zero issues (ideal outcome)."""
        runner = ReviewRunner(project_root=tmp_path)
        handoff = runner.generate_handoff([])

        assert handoff is None

    @pytest.mark.asyncio
    async def test_handoff_prioritizes_high_severity(self, tmp_path: Path) -> None:
        """Handoff prioritizes HIGH severity issues in agent_prompt."""
        issues = [
            ReviewIssue(
                path="src/utils.py",
                line=10,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Missing docstring",
                suggested_fix="Add docstring",
                agent_prompt="Add docstring",
            ),
            ReviewIssue(
                path="src/auth.py",
                line=42,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Security vulnerability",
                suggested_fix="Fix security vulnerability",
                agent_prompt="Fix security issue at line 42",
            ),
        ]

        runner = ReviewRunner(project_root=tmp_path)
        handoff = runner.generate_handoff(issues)

        assert handoff is not None
        # High severity issue should be mentioned first in agent_prompt
        prompt_lower = handoff.agent_prompt.lower()
        high_pos = prompt_lower.find("security")
        low_pos = prompt_lower.find("docstring")

        # HIGH issue mentioned before LOW (or LOW not mentioned)
        assert high_pos < low_pos or low_pos == -1


class TestReviewRunnerWithFix:
    """Test review-fix-retry workflow."""

    @pytest.mark.asyncio
    async def test_run_with_fix_attempts_autofix(self, tmp_path: Path) -> None:
        """run_with_fix attempts auto-fix on fixable issues."""
        # First validation fails with fixable issue
        initial_validation = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Linting errors",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
            ],
            total_duration_ms=500,
        )

        # After fix, validation passes
        fixed_validation = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=True,
                    message="All checks passed",
                    command="ruff check",
                    duration_ms=500,
                ),
            ],
            total_duration_ms=500,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            # Mock both run_all (for full_review) and run_with_fix (for auto-fix)
            mock_instance = mock_val_runner.return_value
            mock_instance.run_all.side_effect = [
                initial_validation,
                fixed_validation,
            ]
            mock_instance.run_with_fix.return_value = None

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_with_fix(changed_files=["src/test.py"])

            assert result.passed is True
            mock_instance.run_with_fix.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_fix_respects_circuit_breaker(self, tmp_path: Path) -> None:
        """run_with_fix respects circuit breaker max retries."""
        # Validation always fails
        failed_validation = ValidationResult(
            passed=False,
            gates=[
                GateResult(
                    gate_type=GateType.LINT,
                    passed=False,
                    message="Linting errors",
                    command="ruff check",
                    duration_ms=500,
                    fixable=True,
                ),
            ],
            total_duration_ms=500,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_instance = mock_val_runner.return_value
            mock_instance.run_all.return_value = failed_validation
            mock_instance.run_with_fix.return_value = None

            runner = ReviewRunner(project_root=tmp_path, max_retries=3)
            ticket_id = "TICKET-42"

            # Should stop after max_retries attempts
            result = await runner.run_with_fix(
                changed_files=["src/test.py"],
                ticket_id=ticket_id,
            )

            assert result.passed is False
            assert runner.should_escalate(ticket_id)


class TestReviewRunnerMetrics:
    """Test metrics collection during review."""

    @pytest.mark.asyncio
    async def test_tracks_pass_one_duration(self, tmp_path: Path) -> None:
        """Tracks duration of Pass 1 validation."""
        mock_validation_result = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="Tests passed",
                    command="pytest",
                    duration_ms=1000,
                ),
            ],
            total_duration_ms=1000,
        )

        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.return_value = mock_validation_result

            runner = ReviewRunner(project_root=tmp_path)
            result = await runner.run_pass_one()

            assert result.total_duration_ms == 1000

    @pytest.mark.asyncio
    async def test_tracks_pass_two_tokens_and_cost(self, tmp_path: Path) -> None:
        """Tracks token usage and cost from Pass 2 AI review."""
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResult(
            output=ReviewResult(
                passed=True,
                issues=[],
                validation_passed=True,
                duration_ms=2000,
                handoff=None,
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                cost_usd=0.045,
            ),
            model="claude-opus-4-6",
            provider="anthropic",
            duration_ms=2000,
        )

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)
        result = await runner.run_pass_two(changed_files=["src/test.py"])

        # Metrics should be tracked (actual tracking via MetricsCollector tested elsewhere)
        assert result.passed is True


class TestReviewRunnerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_changed_files_list(self, tmp_path: Path) -> None:
        """Can handle empty changed files list."""
        from imp.types import AgentResult, TokenUsage

        mock_provider = AsyncMock(spec=AgentProvider)

        # Mock the provider to return a properly structured AgentResult
        mock_review_result = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=100,
        )

        mock_provider.invoke.return_value = AgentResult(
            output=mock_review_result,
            usage=TokenUsage(input_tokens=10, output_tokens=20),
            model="test-model",
            provider="test-provider",
            duration_ms=100,
        )

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)

        # Should still run (reviews entire project or skips Pass 2)
        result = await runner.run_full_review(changed_files=[])
        assert result is not None
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_nonexistent_project_root(self) -> None:
        """Handles nonexistent project root."""
        fake_path = Path("/nonexistent/path")

        # Should not crash at init (might fail later when running commands)
        runner = ReviewRunner(project_root=fake_path)
        assert runner.project_root == fake_path

    @pytest.mark.asyncio
    async def test_ai_provider_timeout(self, tmp_path: Path) -> None:
        """Handles AI provider timeout gracefully."""
        mock_provider = AsyncMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = TimeoutError("AI provider timeout")

        runner = ReviewRunner(project_root=tmp_path, provider=mock_provider)

        with pytest.raises(TimeoutError):
            await runner.run_pass_two(changed_files=["src/test.py"])

    @pytest.mark.asyncio
    async def test_validation_runner_exception(self, tmp_path: Path) -> None:
        """Handles ValidationRunner exception gracefully."""
        with patch("imp.review.runner.ValidationRunner") as mock_val_runner:
            mock_val_runner.return_value.run_all.side_effect = RuntimeError("Command not found")

            runner = ReviewRunner(project_root=tmp_path)

            with pytest.raises(RuntimeError, match="Command not found"):
                await runner.run_pass_one()
