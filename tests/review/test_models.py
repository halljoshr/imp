"""Tests for review models.

Following three-tier TDD: write all tests BEFORE implementation.
Target: 100% branch coverage.
"""

import pytest
from pydantic import ValidationError

from imp.review.models import (
    ReviewCategory,
    ReviewHandoff,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
)


class TestReviewSeverity:
    """Test ReviewSeverity enum."""

    def test_all_severities_defined(self) -> None:
        """All severity levels are available."""
        assert ReviewSeverity.HIGH == "HIGH"
        assert ReviewSeverity.MEDIUM == "MEDIUM"
        assert ReviewSeverity.LOW == "LOW"

    def test_severities_are_strings(self) -> None:
        """Severity values are strings for JSON serialization."""
        for severity in ReviewSeverity:
            assert isinstance(severity.value, str)


class TestReviewCategory:
    """Test ReviewCategory enum."""

    def test_all_categories_defined(self) -> None:
        """All review categories are available."""
        assert ReviewCategory.BUG == "bug"
        assert ReviewCategory.SECURITY == "security"
        assert ReviewCategory.PERFORMANCE == "performance"
        assert ReviewCategory.STANDARDS == "standards"
        assert ReviewCategory.SPEC_COMPLIANCE == "spec_compliance"

    def test_categories_are_strings(self) -> None:
        """Category values are strings for JSON serialization."""
        for category in ReviewCategory:
            assert isinstance(category.value, str)


class TestReviewIssue:
    """Test ReviewIssue model."""

    def test_creation_high_severity_bug(self) -> None:
        """Can create high-severity bug issue."""
        issue = ReviewIssue(
            path="src/auth/session.py",
            line=42,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Null pointer dereference: `user.profile.email` accessed without null check",
            suggested_fix="Add null check: `if user.profile is None: return None`",
            agent_prompt=(
                "File: src/auth/session.py, Line 42. "
                "The code attempts to access `user.profile.email` but does not check if "
                "`user.profile` is None first. If a user has no profile, this will raise "
                "AttributeError. Add a null check before accessing nested attributes."
            ),
        )
        assert issue.path == "src/auth/session.py"
        assert issue.line == 42
        assert issue.severity == ReviewSeverity.HIGH
        assert issue.category == ReviewCategory.BUG
        assert "Null pointer dereference" in issue.message
        assert issue.suggested_fix.startswith("Add null check")
        assert "src/auth/session.py" in issue.agent_prompt

    def test_creation_security_issue(self) -> None:
        """Can create security vulnerability issue."""
        issue = ReviewIssue(
            path="api/routes/search.py",
            line=15,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.SECURITY,
            message="SQL injection: query parameter `q` is concatenated into SQL without escaping",
            suggested_fix=(
                "Use parameterized query: "
                "`cursor.execute('SELECT * FROM items WHERE name = ?', (q,))`"
            ),
            agent_prompt=(
                "File: api/routes/search.py, Line 15. "
                "The search query parameter is directly concatenated into a SQL string, "
                "allowing SQL injection. An attacker could pass `' OR '1'='1` to bypass "
                "filtering. Use parameterized queries or an ORM to prevent injection."
            ),
        )
        assert issue.severity == ReviewSeverity.HIGH
        assert issue.category == ReviewCategory.SECURITY
        assert "SQL injection" in issue.message

    def test_creation_performance_issue(self) -> None:
        """Can create performance issue."""
        issue = ReviewIssue(
            path="db/queries.py",
            line=89,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.PERFORMANCE,
            message="N+1 query: loop calls `get_user(id)` for each item instead of batch fetching",
            suggested_fix=(
                "Replace loop with single query: `users = User.objects.filter(id__in=user_ids)`"
            ),
            agent_prompt=(
                "File: db/queries.py, Line 89. "
                "The code loops through items and calls `get_user()` for each one, resulting "
                "in N+1 database queries. If there are 100 items, this makes 101 queries. "
                "Collect all user IDs first, then fetch users in a single batch query."
            ),
        )
        assert issue.severity == ReviewSeverity.MEDIUM
        assert issue.category == ReviewCategory.PERFORMANCE
        assert "N+1 query" in issue.message

    def test_creation_standards_violation(self) -> None:
        """Can create standards violation issue."""
        issue = ReviewIssue(
            path="ui/components/Button.tsx",
            line=23,
            severity=ReviewSeverity.LOW,
            category=ReviewCategory.STANDARDS,
            message="Inline style used: `style={{ color: 'red' }}` instead of Tailwind classes",
            suggested_fix="Replace with Tailwind: `className='text-red-500'`",
            agent_prompt=(
                "File: ui/components/Button.tsx, Line 23. "
                "This project uses Tailwind CSS for styling, but this component uses inline "
                "styles which bypass the design system. Replace `style={{ color: 'red' }}` "
                "with the Tailwind class `text-red-500` to maintain consistency."
            ),
        )
        assert issue.severity == ReviewSeverity.LOW
        assert issue.category == ReviewCategory.STANDARDS
        assert "Inline style" in issue.message

    def test_creation_spec_compliance_issue(self) -> None:
        """Can create spec compliance issue."""
        issue = ReviewIssue(
            path="services/payment.py",
            line=67,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.SPEC_COMPLIANCE,
            message=(
                "Missing acceptance criteria: function does not validate `amount > 0` as required"
            ),
            suggested_fix=(
                "Add validation at function start: "
                "`if amount <= 0: raise ValueError('Amount must be positive')`"
            ),
            agent_prompt=(
                "File: services/payment.py, Line 67. "
                "The ticket's acceptance criteria state that payment amount must be validated "
                "as positive, but this function accepts any amount without checking. Add a "
                "guard clause to raise an error if amount <= 0."
            ),
        )
        assert issue.category == ReviewCategory.SPEC_COMPLIANCE
        assert "acceptance criteria" in issue.message

    def test_immutability(self) -> None:
        """ReviewIssue is frozen."""
        issue = ReviewIssue(
            path="test.py",
            line=1,
            severity=ReviewSeverity.LOW,
            category=ReviewCategory.STANDARDS,
            message="test",
            suggested_fix="fix",
            agent_prompt="prompt",
        )
        with pytest.raises(ValidationError):
            issue.severity = ReviewSeverity.HIGH  # type: ignore[misc]

    def test_required_fields(self) -> None:
        """All fields are required."""
        with pytest.raises(ValidationError):
            ReviewIssue(  # type: ignore[call-arg]
                path="test.py",
                line=1,
                # missing severity
                category=ReviewCategory.BUG,
                message="test",
                suggested_fix="fix",
                agent_prompt="prompt",
            )

    def test_json_serialization(self) -> None:
        """ReviewIssue can be serialized to JSON."""
        issue = ReviewIssue(
            path="test.py",
            line=10,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.BUG,
            message="test message",
            suggested_fix="test fix",
            agent_prompt="test prompt",
        )
        data = issue.model_dump()
        assert data["path"] == "test.py"
        assert data["line"] == 10
        assert data["severity"] == "MEDIUM"
        assert data["category"] == "bug"


class TestReviewHandoff:
    """Test ReviewHandoff model."""

    def test_creation_with_issues(self) -> None:
        """Can create handoff with issues."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug 1",
                suggested_fix="Fix 1",
                agent_prompt="Prompt 1",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Bug 2",
                suggested_fix="Fix 2",
                agent_prompt="Prompt 2",
            ),
        ]
        handoff = ReviewHandoff(
            agent_prompt=(
                "Fix the high-severity bug in a.py first, then address performance in b.py"
            ),
            relevant_files=["a.py", "b.py"],
            issues=issues,
        )
        assert handoff.agent_prompt.startswith("Fix the high-severity")
        assert handoff.relevant_files == ["a.py", "b.py"]
        assert len(handoff.issues) == 2

    def test_creation_empty_issues(self) -> None:
        """Can create handoff with no issues (clean review)."""
        handoff = ReviewHandoff(
            agent_prompt="No issues found. Code looks good.",
            relevant_files=[],
            issues=[],
        )
        assert handoff.agent_prompt == "No issues found. Code looks good."
        assert handoff.relevant_files == []
        assert handoff.issues == []

    def test_high_severity_issues_property(self) -> None:
        """high_severity_issues property filters correctly."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="High",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.BUG,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="High",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        handoff = ReviewHandoff(
            agent_prompt="test",
            relevant_files=["a.py", "b.py", "c.py"],
            issues=issues,
        )
        high = handoff.high_severity_issues
        assert len(high) == 2
        assert all(i.severity == ReviewSeverity.HIGH for i in high)

    def test_medium_severity_issues_property(self) -> None:
        """medium_severity_issues property filters correctly."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="High",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        handoff = ReviewHandoff(
            agent_prompt="test",
            relevant_files=["a.py", "b.py"],
            issues=issues,
        )
        medium = handoff.medium_severity_issues
        assert len(medium) == 1
        assert medium[0].severity == ReviewSeverity.MEDIUM

    def test_low_severity_issues_property(self) -> None:
        """low_severity_issues property filters correctly."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Low",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.BUG,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        handoff = ReviewHandoff(
            agent_prompt="test",
            relevant_files=["a.py", "b.py"],
            issues=issues,
        )
        low = handoff.low_severity_issues
        assert len(low) == 1
        assert low[0].severity == ReviewSeverity.LOW

    def test_by_category_property(self) -> None:
        """by_category property groups issues correctly."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug 1",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.BUG,
                message="Bug 2",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="Security",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        handoff = ReviewHandoff(
            agent_prompt="test",
            relevant_files=["a.py", "b.py", "c.py"],
            issues=issues,
        )
        by_cat = handoff.by_category
        assert len(by_cat[ReviewCategory.BUG]) == 2
        assert len(by_cat[ReviewCategory.SECURITY]) == 1
        assert len(by_cat[ReviewCategory.PERFORMANCE]) == 0

    def test_by_category_empty(self) -> None:
        """by_category works with no issues."""
        handoff = ReviewHandoff(
            agent_prompt="test",
            relevant_files=[],
            issues=[],
        )
        by_cat = handoff.by_category
        assert all(len(issues) == 0 for issues in by_cat.values())

    def test_json_serialization(self) -> None:
        """ReviewHandoff can be serialized to JSON."""
        issues = [
            ReviewIssue(
                path="test.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="test",
                suggested_fix="fix",
                agent_prompt="prompt",
            )
        ]
        handoff = ReviewHandoff(
            agent_prompt="Test prompt",
            relevant_files=["test.py"],
            issues=issues,
        )
        data = handoff.model_dump()
        assert data["agent_prompt"] == "Test prompt"
        assert data["relevant_files"] == ["test.py"]
        assert len(data["issues"]) == 1


class TestReviewResult:
    """Test ReviewResult model."""

    def test_creation_passed_no_issues(self) -> None:
        """Can create passed result with no issues."""
        result = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=5000,
        )
        assert result.passed is True
        assert result.issues == []
        assert result.handoff is None
        assert result.validation_passed is True
        assert result.duration_ms == 5000
        assert result.model is None
        assert result.provider is None

    def test_creation_failed_with_issues(self) -> None:
        """Can create failed result with issues and handoff."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            )
        ]
        handoff = ReviewHandoff(
            agent_prompt="Fix the bug in a.py",
            relevant_files=["a.py"],
            issues=issues,
        )
        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=handoff,
            validation_passed=True,
            duration_ms=8000,
            model="claude-opus-4-6",
            provider="anthropic",
        )
        assert result.passed is False
        assert len(result.issues) == 1
        assert result.handoff is not None
        assert result.model == "claude-opus-4-6"
        assert result.provider == "anthropic"

    def test_creation_validation_failed(self) -> None:
        """Can create result when validation failed."""
        result = ReviewResult(
            passed=False,
            issues=[],
            handoff=None,
            validation_passed=False,
            duration_ms=2000,
        )
        assert result.passed is False
        assert result.validation_passed is False
        assert result.failed_validation is True

    def test_failed_validation_property(self) -> None:
        """failed_validation property returns correct value."""
        result_passed = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )
        assert result_passed.failed_validation is False

        result_failed = ReviewResult(
            passed=False,
            issues=[],
            handoff=None,
            validation_passed=False,
            duration_ms=1000,
        )
        assert result_failed.failed_validation is True

    def test_severity_count_properties(self) -> None:
        """Severity count properties return correct counts."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="High 1",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="High 2",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="d.py",
                line=4,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Low",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )
        assert result.high_severity_count == 2
        assert result.medium_severity_count == 1
        assert result.low_severity_count == 1
        assert result.total_issues == 4

    def test_total_issues_property(self) -> None:
        """total_issues property returns correct count."""
        result_empty = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )
        assert result_empty.total_issues == 0

        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Issue",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            )
        ]
        result_one = ReviewResult(
            passed=True,
            issues=issues,
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )
        assert result_one.total_issues == 1

    def test_by_category_property(self) -> None:
        """by_category property groups issues correctly."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug 1",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.BUG,
                message="Bug 2",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="Security",
                suggested_fix="Fix",
                agent_prompt="Prompt",
            ),
        ]
        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )
        by_cat = result.by_category
        assert len(by_cat[ReviewCategory.BUG]) == 2
        assert len(by_cat[ReviewCategory.SECURITY]) == 1
        assert len(by_cat[ReviewCategory.PERFORMANCE]) == 0

    def test_json_serialization(self) -> None:
        """ReviewResult can be serialized to JSON."""
        issues = [
            ReviewIssue(
                path="test.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="test",
                suggested_fix="fix",
                agent_prompt="prompt",
            )
        ]
        handoff = ReviewHandoff(
            agent_prompt="Fix the bug",
            relevant_files=["test.py"],
            issues=issues,
        )
        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=handoff,
            validation_passed=True,
            duration_ms=5000,
            model="claude-opus-4-6",
            provider="anthropic",
        )
        data = result.model_dump()
        assert data["passed"] is False
        assert len(data["issues"]) == 1
        assert data["handoff"] is not None
        assert data["model"] == "claude-opus-4-6"
        assert data["provider"] == "anthropic"

    def test_optional_fields(self) -> None:
        """Optional fields can be omitted."""
        result = ReviewResult(
            passed=True,
            issues=[],
            validation_passed=True,
            duration_ms=1000,
        )
        assert result.handoff is None
        assert result.model is None
        assert result.provider is None
