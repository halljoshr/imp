"""Review data models.

Simple ReviewHandoff model with 3 fields:
- agent_prompt: AI-to-AI handoff instructions
- relevant_files: Files needing attention
- issues: Structured issue list

Following the Linus critique from conversation 015: build the simplest version
that proves the core idea. NO three-tier handoff system. Single JSON file per review.
Build handoff complexity when we hit the problem, not before.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewSeverity(StrEnum):
    """Severity levels for review issues.

    From code-review research (ai-reviewer.mjs):
    - HIGH: bugs, security vulnerabilities
    - MEDIUM: logic errors, performance issues
    - LOW: standards violations, code quality
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReviewCategory(StrEnum):
    """Categories of review issues.

    Based on design-doc.md §10 review types and ai-reviewer.mjs priorities.
    """

    BUG = "bug"  # Confirmed bugs that WILL cause incorrect behavior
    SECURITY = "security"  # Injection, XSS, exposed secrets, missing auth
    PERFORMANCE = "performance"  # N+1 queries, unnecessary work
    STANDARDS = "standards"  # DRY violations, style inconsistencies
    SPEC_COMPLIANCE = "spec_compliance"  # Output vs acceptance criteria


class ReviewIssue(BaseModel):
    """A single issue found during code review.

    From ai-reviewer.mjs: Every issue includes an agentPrompt — a detailed prompt
    a coding agent can pick up directly to verify and fix the issue. This turns
    review into a pipeline, not a handoff.

    False Positive Prevention (mandatory 5-point self-check):
    1. Can I name a SPECIFIC input that triggers a runtime failure? (If no → SKIP)
    2. Does the code already handle this? Look for try/catch, null checks, validation.
       (If yes → SKIP)
    3. Have I read the FULL function body, not just the signature? (If no → read it first)
    4. Is this a style preference or design opinion? (If yes → SKIP)
    5. Am I using speculative language ("may", "might", "could")? (If yes → SKIP)

    Zero issues = ideal outcome. Never invent issues to appear thorough.
    """

    path: str = Field(description="Exact file path where the issue was found")
    line: int = Field(description="Line number where the issue occurs")
    severity: ReviewSeverity = Field(
        description=(
            "Issue severity: HIGH (bugs/security), MEDIUM (logic/performance), LOW (standards)"
        )
    )
    category: ReviewCategory = Field(
        description="Issue category: bug, security, performance, standards, spec_compliance"
    )
    message: str = Field(
        description="One-sentence description of a CONFIRMED issue (not potential). "
        "Must quote problematic code with backticks and state what WILL break."
    )
    suggested_fix: str = Field(
        description=(
            "Concrete description of how to fix the issue. Include corrected code if helpful."
        )
    )
    agent_prompt: str = Field(
        description=(
            "Multi-sentence explanation for an AI agent. Include: "
            "(1) the file and line, (2) what the code currently does wrong, "
            "(3) what the correct behavior should be, "
            "(4) why the current code produces incorrect results. "
            "Must be detailed enough for a coding agent to locate, verify, and fix independently."
        )
    )

    model_config = ConfigDict(frozen=True)


class ReviewHandoff(BaseModel):
    """Handoff state for the review process.

    Simple 3-field model per conversation 015. NO three-tier system.
    Build complexity when we hit the problem in production, not before.

    This is the contract between reviewer and coding agent.
    """

    agent_prompt: str = Field(
        description="High-level AI-to-AI handoff instructions. "
        "Summary of what needs to be fixed and priority order."
    )
    relevant_files: list[str] = Field(
        description="Files that need attention (paths relative to repo root)"
    )
    issues: list[ReviewIssue] = Field(
        description="Structured list of issues found, sorted by severity then category"
    )

    @property
    def high_severity_issues(self) -> list[ReviewIssue]:
        """Get list of high-severity issues."""
        return [i for i in self.issues if i.severity == ReviewSeverity.HIGH]

    @property
    def medium_severity_issues(self) -> list[ReviewIssue]:
        """Get list of medium-severity issues."""
        return [i for i in self.issues if i.severity == ReviewSeverity.MEDIUM]

    @property
    def low_severity_issues(self) -> list[ReviewIssue]:
        """Get list of low-severity issues."""
        return [i for i in self.issues if i.severity == ReviewSeverity.LOW]

    @property
    def by_category(self) -> dict[ReviewCategory, list[ReviewIssue]]:
        """Group issues by category."""
        result: dict[ReviewCategory, list[ReviewIssue]] = {cat: [] for cat in ReviewCategory}
        for issue in self.issues:
            result[issue.category].append(issue)
        return result


class ReviewResult(BaseModel):
    """Result from running a code review.

    Pass/fail determined by presence of HIGH severity issues and validation result.
    Issues at MEDIUM/LOW may be warnings that don't block.
    """

    passed: bool = Field(description="True if no HIGH severity issues found and validation passed")
    issues: list[ReviewIssue] = Field(
        description="All issues found, sorted by severity (HIGH → MEDIUM → LOW)"
    )
    handoff: ReviewHandoff | None = Field(
        default=None,
        description="Handoff state if issues were found, None if review passed cleanly",
    )
    validation_passed: bool = Field(
        description="True if automated validation (imp check) passed before AI review"
    )
    duration_ms: int = Field(description="Total review duration in milliseconds")
    model: str | None = Field(
        default=None, description="AI model used for review (e.g., 'claude-opus-4-6')"
    )
    provider: str | None = Field(
        default=None, description="AI provider used for review (e.g., 'anthropic')"
    )

    @property
    def failed_validation(self) -> bool:
        """Check if validation failed (should block AI review)."""
        return not self.validation_passed

    @property
    def high_severity_count(self) -> int:
        """Count of high-severity issues."""
        return len([i for i in self.issues if i.severity == ReviewSeverity.HIGH])

    @property
    def medium_severity_count(self) -> int:
        """Count of medium-severity issues."""
        return len([i for i in self.issues if i.severity == ReviewSeverity.MEDIUM])

    @property
    def low_severity_count(self) -> int:
        """Count of low-severity issues."""
        return len([i for i in self.issues if i.severity == ReviewSeverity.LOW])

    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.issues)

    @property
    def by_category(self) -> dict[ReviewCategory, list[ReviewIssue]]:
        """Group issues by category."""
        result: dict[ReviewCategory, list[ReviewIssue]] = {cat: [] for cat in ReviewCategory}
        for issue in self.issues:
            result[issue.category].append(issue)
        return result
