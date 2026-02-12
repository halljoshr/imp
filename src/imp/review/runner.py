"""ReviewRunner — orchestrates two-pass code review.

Pass 1: Automated checks via ValidationRunner (imp check)
Pass 2: AI deep review with false positive prevention

From conversation 015: Simple ReviewHandoff model. NO three-tier system.
Build complexity when we hit the problem, not before.
"""

import time
from pathlib import Path

from imp.providers.base import AgentProvider
from imp.review.models import ReviewHandoff, ReviewIssue, ReviewResult, ReviewSeverity
from imp.validation.models import ValidationResult
from imp.validation.runner import ValidationRunner


class EscalationReport:
    """Report generated when circuit breaker triggers."""

    def __init__(self, ticket_id: str, attempts: int, failures: list[str]) -> None:
        """Initialize escalation report.

        Args:
            ticket_id: Ticket that exceeded retry limit
            attempts: Number of attempts made
            failures: List of failure reasons from each attempt
        """
        self.ticket_id = ticket_id
        self.attempts = attempts
        self.what_failed = failures


class ReviewRunner:
    """Orchestrates two-pass code review process."""

    def __init__(
        self,
        project_root: Path,
        provider: AgentProvider[ReviewResult, None] | None = None,
        max_retries: int = 3,
    ) -> None:
        """Initialize review runner.

        Args:
            project_root: Root directory of the project
            provider: AI provider for Pass 2 review (optional, required for Pass 2)
            max_retries: Maximum review attempts before escalation (circuit breaker)

        Raises:
            ValueError: If max_retries is not positive
        """
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")

        self.project_root = project_root
        self.provider = provider
        self.max_retries = max_retries

        # Circuit breaker state: ticket_id → (attempt_count, failure_reasons)
        self._attempts: dict[str, tuple[int, list[str]]] = {}

    async def run_pass_one(self, gate_types: list[str] | None = None) -> ValidationResult:
        """Run Pass 1: Automated validation checks.

        Args:
            gate_types: Optional list of specific gate types to run

        Returns:
            ValidationResult from running gates
        """
        runner = ValidationRunner(project_root=self.project_root)

        if gate_types:
            from imp.validation.models import GateType

            gates = [GateType(gt) for gt in gate_types]
            return runner.run_gates(gates)
        else:
            return runner.run_all()

    async def run_pass_two(self, changed_files: list[str]) -> ReviewResult:
        """Run Pass 2: AI deep review with false positive prevention.

        Args:
            changed_files: List of file paths that were changed

        Returns:
            ReviewResult from AI review

        Raises:
            ValueError: If provider is not configured
        """
        if self.provider is None:
            raise ValueError("AI provider required for Pass 2 review")

        start_time = time.time()

        # Build review prompt
        from imp.review.prompts import build_review_prompt

        user_prompt = build_review_prompt(changed_files)

        # Invoke AI provider (system_prompt and output_type already set at init)
        result = await self.provider.invoke(prompt=user_prompt)

        # Extract review result from agent output
        # The provider should return ReviewResult as output
        review_result = result.output

        # Set model/provider info
        duration_ms = int((time.time() - start_time) * 1000)

        # Create new result with provider metadata
        return ReviewResult(
            passed=review_result.passed,
            issues=review_result.issues,
            handoff=review_result.handoff,
            validation_passed=review_result.validation_passed,
            duration_ms=duration_ms,
            model=result.model,
            provider=result.provider,
        )

    async def run_full_review(
        self, changed_files: list[str], gate_types: list[str] | None = None
    ) -> ReviewResult:
        """Run full two-pass review: validation then AI review.

        Args:
            changed_files: List of file paths that were changed
            gate_types: Optional list of specific gate types to run in Pass 1

        Returns:
            ReviewResult with both validation and AI review outcomes
        """
        start_time = time.time()

        # Pass 1: Automated validation
        validation_result = await self.run_pass_one(gate_types=gate_types)

        # If validation fails, return early (don't run AI review on broken code)
        if not validation_result.passed:
            duration_ms = int((time.time() - start_time) * 1000)
            return ReviewResult(
                passed=False,
                issues=[],
                handoff=None,
                validation_passed=False,
                duration_ms=duration_ms,
            )

        # Pass 2: AI review (only if provider is configured)
        if self.provider is None:
            duration_ms = int((time.time() - start_time) * 1000)
            return ReviewResult(
                passed=True,
                issues=[],
                handoff=None,
                validation_passed=True,
                duration_ms=duration_ms,
            )

        # Run AI review
        ai_result = await self.run_pass_two(changed_files=changed_files)

        # Combine results
        duration_ms = int((time.time() - start_time) * 1000)
        return ReviewResult(
            passed=ai_result.passed and validation_result.passed,
            issues=ai_result.issues,
            handoff=ai_result.handoff,
            validation_passed=validation_result.passed,
            duration_ms=duration_ms,
            model=ai_result.model,
            provider=ai_result.provider,
        )

    async def run_with_fix(
        self,
        changed_files: list[str],
        ticket_id: str | None = None,
    ) -> ReviewResult:
        """Run review with auto-fix retry loop.

        If Pass 1 fails with fixable issues, attempts to fix them and re-review.
        Respects circuit breaker (max_retries).

        Args:
            changed_files: List of file paths that were changed
            ticket_id: Optional ticket ID for circuit breaker tracking

        Returns:
            ReviewResult from final attempt
        """
        attempt = 0

        while attempt < self.max_retries:
            # Run full review
            result = await self.run_full_review(changed_files=changed_files)

            # If passed, we're done
            if result.passed:
                return result

            # Track attempt if ticket_id provided
            if ticket_id:
                failure_reason = (
                    "Validation failed" if result.failed_validation else "AI review failed"
                )
                self.record_attempt(ticket_id, failure_reason=failure_reason)

            # If validation failed with fixable issues, try to fix
            if result.failed_validation:
                # Attempt auto-fix using ValidationRunner's built-in fix capability
                validation_runner = ValidationRunner(project_root=self.project_root)
                validation_runner.run_with_fix()

                # If still failing after fix attempt, increment and continue
                attempt += 1
                continue

            # No fixable issues or fix didn't work - stop
            break

        # Exhausted retries
        return result

    # Circuit breaker methods

    def record_attempt(self, ticket_id: str, failure_reason: str = "") -> None:
        """Record a review attempt for circuit breaker tracking.

        Args:
            ticket_id: Ticket being reviewed
            failure_reason: Optional reason for failure
        """
        if ticket_id not in self._attempts:
            self._attempts[ticket_id] = (0, [])

        count, reasons = self._attempts[ticket_id]
        self._attempts[ticket_id] = (count + 1, [*reasons, failure_reason])

    def get_attempt_count(self, ticket_id: str) -> int:
        """Get number of attempts for a ticket.

        Args:
            ticket_id: Ticket ID to check

        Returns:
            Number of review attempts
        """
        if ticket_id not in self._attempts:
            return 0
        return self._attempts[ticket_id][0]

    def should_escalate(self, ticket_id: str) -> bool:
        """Check if ticket should be escalated to human.

        Args:
            ticket_id: Ticket ID to check

        Returns:
            True if attempts >= max_retries
        """
        return self.get_attempt_count(ticket_id) >= self.max_retries

    def reset_attempts(self, ticket_id: str) -> None:
        """Reset circuit breaker for a ticket.

        Args:
            ticket_id: Ticket ID to reset
        """
        if ticket_id in self._attempts:
            del self._attempts[ticket_id]

    def generate_escalation_report(self, ticket_id: str) -> EscalationReport:
        """Generate escalation report for a ticket.

        Args:
            ticket_id: Ticket that exceeded retry limit

        Returns:
            EscalationReport with attempt details
        """
        count, reasons = self._attempts.get(ticket_id, (0, []))
        return EscalationReport(
            ticket_id=ticket_id,
            attempts=count,
            failures=reasons,
        )

    # Handoff generation

    def generate_handoff(self, issues: list[ReviewIssue]) -> ReviewHandoff | None:
        """Generate ReviewHandoff from issue list.

        Following false positive prevention: zero issues = ideal outcome.
        Only generate handoff when issues actually exist.

        Args:
            issues: List of review issues

        Returns:
            ReviewHandoff if issues exist, None otherwise
        """
        if not issues:
            return None

        # Extract unique file paths
        relevant_files = sorted(set(issue.path for issue in issues))

        # Sort issues by severity (HIGH → MEDIUM → LOW)
        sorted_issues = sorted(
            issues,
            key=lambda i: (
                0
                if i.severity == ReviewSeverity.HIGH
                else 1
                if i.severity == ReviewSeverity.MEDIUM
                else 2
            ),
        )

        # Build agent prompt prioritizing high-severity issues
        high_issues = [i for i in sorted_issues if i.severity == ReviewSeverity.HIGH]
        medium_issues = [i for i in sorted_issues if i.severity == ReviewSeverity.MEDIUM]
        low_issues = [i for i in sorted_issues if i.severity == ReviewSeverity.LOW]

        prompt_parts = []

        if high_issues:
            prompt_parts.append(f"CRITICAL: Fix {len(high_issues)} high-severity issue(s) first:")
            for issue in high_issues[:3]:  # Highlight top 3
                prompt_parts.append(f"  - {issue.path}:{issue.line}: {issue.message}")

        if medium_issues:
            prompt_parts.append(f"Then address {len(medium_issues)} medium-severity issue(s).")

        if low_issues:
            prompt_parts.append(
                f"Finally, consider {len(low_issues)} low-severity improvement(s)."
            )

        agent_prompt = "\n".join(prompt_parts)

        return ReviewHandoff(
            agent_prompt=agent_prompt,
            relevant_files=relevant_files,
            issues=sorted_issues,
        )
