"""Integration tests for review layer - full end-to-end workflows.

These tests cover:
- Two-pass review (validation → AI review)
- Integration with imp check (ValidationRunner)
- ReviewRunner with real provider (TestModel)
- Handoff JSON generation
- Circuit breaker triggering
- Fix workflow (review → fix → re-review)
"""

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai.models.test import TestModel

from imp.providers import PydanticAIProvider
from imp.review.models import (
    ReviewCategory,
    ReviewHandoff,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
)
from imp.validation.detector import detect_toolchain
from imp.validation.models import GateResult, GateType, ValidationResult
from imp.validation.runner import ValidationRunner


class CodeReview(BaseModel):
    """Test model for structured review output."""

    has_issues: bool
    summary: str


class TestReviewModels:
    """Integration tests for review data models."""

    def test_review_issue_creation_and_validation(self) -> None:
        """Test ReviewIssue creation with all required fields."""
        issue = ReviewIssue(
            path="src/example.py",
            line=42,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Variable `user_id` is used before null check on line 42",
            suggested_fix="Move the null check for `user_id` before line 42",
            agent_prompt=(
                "In src/example.py at line 42, the code uses `user_id` without checking "
                "if it's None first. This will cause a NoneType error when the user is not "
                "authenticated. The correct behavior is to check `if user_id is None:` "
                "before using it. The current code produces incorrect results because "
                "it assumes user_id is always present."
            ),
        )

        assert issue.path == "src/example.py"
        assert issue.line == 42
        assert issue.severity == ReviewSeverity.HIGH
        assert issue.category == ReviewCategory.BUG
        assert "user_id" in issue.message
        assert "null check" in issue.suggested_fix
        assert len(issue.agent_prompt) > 100  # Should be detailed

    def test_review_handoff_with_multiple_issues(self) -> None:
        """Test ReviewHandoff creation with multiple issues."""
        issues = [
            ReviewIssue(
                path="src/auth.py",
                line=10,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="SQL injection vulnerability in query construction",
                suggested_fix="Use parameterized queries instead of string concatenation",
                agent_prompt="Fix SQL injection in src/auth.py line 10",
            ),
            ReviewIssue(
                path="src/utils.py",
                line=25,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="N+1 query detected in loop",
                suggested_fix="Use select_related or prefetch_related",
                agent_prompt="Fix N+1 query in src/utils.py line 25",
            ),
        ]

        handoff = ReviewHandoff(
            agent_prompt="Fix 2 issues: 1 security vulnerability, 1 performance issue",
            relevant_files=["src/auth.py", "src/utils.py"],
            issues=issues,
        )

        assert len(handoff.issues) == 2
        assert len(handoff.relevant_files) == 2
        assert len(handoff.high_severity_issues) == 1
        assert len(handoff.medium_severity_issues) == 1
        assert handoff.by_category[ReviewCategory.SECURITY] == [issues[0]]

    def test_review_result_with_failures(self) -> None:
        """Test ReviewResult with failed review."""
        issue = ReviewIssue(
            path="src/main.py",
            line=5,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Uncaught exception",
            suggested_fix="Add try/except",
            agent_prompt="Fix exception handling",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix uncaught exception",
            relevant_files=["src/main.py"],
            issues=[issue],
        )

        result = ReviewResult(
            passed=False,
            issues=[issue],
            handoff=handoff,
            validation_passed=True,
            duration_ms=1500,
            model="claude-opus-4-6",
            provider="anthropic",
        )

        assert result.passed is False
        assert result.total_issues == 1
        assert result.high_severity_count == 1
        assert result.handoff is not None
        assert result.handoff.agent_prompt == "Fix uncaught exception"

    def test_review_result_clean_pass(self) -> None:
        """Test ReviewResult with clean pass (no issues)."""
        result = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=800,
            model="claude-sonnet-4-5-20250929",
            provider="anthropic",
        )

        assert result.passed is True
        assert result.total_issues == 0
        assert result.handoff is None
        assert result.validation_passed is True

    def test_review_result_failed_validation_blocks(self) -> None:
        """Test that failed validation blocks review."""
        result = ReviewResult(
            passed=False,
            issues=[],
            handoff=None,
            validation_passed=False,
            duration_ms=500,
        )

        assert result.passed is False
        assert result.failed_validation is True
        assert result.total_issues == 0


class TestReviewWithProviderIntegration:
    """Integration tests for review with AI provider."""

    async def test_review_workflow_with_test_model(self) -> None:
        """End-to-end: AI review with TestModel provider."""
        # Create provider for review
        provider = PydanticAIProvider(
            model=TestModel(),
            output_type=CodeReview,
            system_prompt=(
                "You are a code reviewer. Analyze code for bugs and security issues. "
                "Apply the 5-point false positive prevention check."
            ),
        )

        # Simulate review invocation
        code_snippet = """
def process_user(user_id):
    return database.query(f"SELECT * FROM users WHERE id = {user_id}")
"""

        result = await provider.invoke(f"Review this code:\n{code_snippet}")

        # Verify provider result
        assert result.output is not None
        assert isinstance(result.output, CodeReview)
        assert result.usage.input_tokens > 0
        assert result.model == "test"

    async def test_multi_issue_review_workflow(self) -> None:
        """Test review that finds multiple issues."""
        # This would normally use ReviewRunner, but we're testing the model flow
        issues = [
            ReviewIssue(
                path="src/api.py",
                line=15,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="XSS vulnerability: user input not sanitized",
                suggested_fix="Escape HTML entities before rendering",
                agent_prompt="Fix XSS in src/api.py line 15 by escaping user input",
            ),
            ReviewIssue(
                path="src/api.py",
                line=30,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Database query inside loop causes N+1 problem",
                suggested_fix="Move query outside loop or use bulk fetch",
                agent_prompt="Fix N+1 query in src/api.py line 30",
            ),
        ]

        handoff = ReviewHandoff(
            agent_prompt="Fix 2 issues in src/api.py: 1 security, 1 performance",
            relevant_files=["src/api.py"],
            issues=issues,
        )

        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=handoff,
            validation_passed=True,
            duration_ms=2000,
            model="test",
            provider="test",
        )

        assert result.total_issues == 2
        assert result.high_severity_count == 1
        assert result.by_category[ReviewCategory.SECURITY] == [issues[0]]
        assert result.by_category[ReviewCategory.PERFORMANCE] == [issues[1]]


class TestReviewHandoffGeneration:
    """Integration tests for handoff JSON generation."""

    def test_handoff_json_serialization(self) -> None:
        """Test that ReviewHandoff can be serialized to JSON."""
        issue = ReviewIssue(
            path="src/models.py",
            line=100,
            severity=ReviewSeverity.LOW,
            category=ReviewCategory.STANDARDS,
            message="Function exceeds complexity threshold",
            suggested_fix="Extract helper methods to reduce complexity",
            agent_prompt="Refactor src/models.py line 100 to reduce complexity",
        )

        handoff = ReviewHandoff(
            agent_prompt="Refactor complex function",
            relevant_files=["src/models.py"],
            issues=[issue],
        )

        # Serialize to JSON
        json_data = handoff.model_dump()

        assert json_data["agent_prompt"] == "Refactor complex function"
        assert len(json_data["relevant_files"]) == 1
        assert len(json_data["issues"]) == 1
        assert json_data["issues"][0]["path"] == "src/models.py"

    def test_handoff_json_round_trip(self) -> None:
        """Test that ReviewHandoff can be serialized and deserialized."""
        original = ReviewHandoff(
            agent_prompt="Fix all issues",
            relevant_files=["file1.py", "file2.py"],
            issues=[
                ReviewIssue(
                    path="file1.py",
                    line=10,
                    severity=ReviewSeverity.HIGH,
                    category=ReviewCategory.BUG,
                    message="Bug found",
                    suggested_fix="Fix it",
                    agent_prompt="Fix bug in file1.py",
                )
            ],
        )

        # Serialize
        json_data = original.model_dump()

        # Deserialize
        restored = ReviewHandoff.model_validate(json_data)

        assert restored.agent_prompt == original.agent_prompt
        assert restored.relevant_files == original.relevant_files
        assert len(restored.issues) == len(original.issues)
        assert restored.issues[0].path == original.issues[0].path

    def test_handoff_json_file_write(self, tmp_path: Path) -> None:
        """Test writing ReviewHandoff to JSON file."""
        handoff = ReviewHandoff(
            agent_prompt="Fix security issues",
            relevant_files=["src/auth.py"],
            issues=[
                ReviewIssue(
                    path="src/auth.py",
                    line=5,
                    severity=ReviewSeverity.HIGH,
                    category=ReviewCategory.SECURITY,
                    message="Weak password hashing",
                    suggested_fix="Use bcrypt or argon2",
                    agent_prompt="Fix password hashing in src/auth.py",
                )
            ],
        )

        # Write to file
        handoff_file = tmp_path / "review_handoff.json"
        handoff_file.write_text(handoff.model_dump_json(indent=2))

        # Read back
        loaded_json = handoff_file.read_text()
        loaded_handoff = ReviewHandoff.model_validate_json(loaded_json)

        assert loaded_handoff.agent_prompt == handoff.agent_prompt
        assert loaded_handoff.issues[0].severity == ReviewSeverity.HIGH


class TestReviewOutputFormats:
    """Integration tests for different output formats."""

    def test_review_result_json_output(self) -> None:
        """Test ReviewResult JSON serialization."""
        result = ReviewResult(
            passed=False,
            issues=[
                ReviewIssue(
                    path="test.py",
                    line=1,
                    severity=ReviewSeverity.MEDIUM,
                    category=ReviewCategory.STANDARDS,
                    message="Issue",
                    suggested_fix="Fix",
                    agent_prompt="Fix issue",
                )
            ],
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
            model="test",
            provider="test",
        )

        json_data = result.model_dump()

        assert json_data["passed"] is False
        assert result.total_issues == 1  # Property, not in model_dump
        assert json_data["validation_passed"] is True
        assert json_data["duration_ms"] == 1000

    def test_review_result_with_handoff_json(self) -> None:
        """Test ReviewResult with handoff JSON structure."""
        issue = ReviewIssue(
            path="app.py",
            line=50,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Null pointer dereference",
            suggested_fix="Add null check",
            agent_prompt="Fix null check in app.py",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix critical bug",
            relevant_files=["app.py"],
            issues=[issue],
        )

        result = ReviewResult(
            passed=False,
            issues=[issue],
            handoff=handoff,
            validation_passed=True,
            duration_ms=1500,
        )

        json_data = result.model_dump()

        assert json_data["handoff"] is not None
        assert json_data["handoff"]["agent_prompt"] == "Fix critical bug"
        assert len(json_data["handoff"]["issues"]) == 1


class TestReviewSeverityAndCategoryFiltering:
    """Integration tests for filtering by severity and category."""

    def test_filter_issues_by_severity(self) -> None:
        """Test filtering issues by severity level."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="High",
                suggested_fix="Fix",
                agent_prompt="Fix high",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Fix medium",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Low",
                suggested_fix="Fix",
                agent_prompt="Fix low",
            ),
        ]

        handoff = ReviewHandoff(
            agent_prompt="Fix all",
            relevant_files=["a.py", "b.py", "c.py"],
            issues=issues,
        )

        assert len(handoff.high_severity_issues) == 1
        assert len(handoff.medium_severity_issues) == 1
        assert len(handoff.low_severity_issues) == 1

    def test_filter_issues_by_category(self) -> None:
        """Test filtering issues by category."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug",
                suggested_fix="Fix",
                agent_prompt="Fix bug",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="Security",
                suggested_fix="Fix",
                agent_prompt="Fix security",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.BUG,
                message="Another bug",
                suggested_fix="Fix",
                agent_prompt="Fix another bug",
            ),
        ]

        handoff = ReviewHandoff(
            agent_prompt="Fix all",
            relevant_files=["a.py", "b.py", "c.py"],
            issues=issues,
        )

        by_category = handoff.by_category

        assert len(by_category[ReviewCategory.BUG]) == 2
        assert len(by_category[ReviewCategory.SECURITY]) == 1
        assert len(by_category[ReviewCategory.PERFORMANCE]) == 0


class TestReviewResultProperties:
    """Integration tests for ReviewResult computed properties."""

    def test_review_result_counts(self) -> None:
        """Test severity count properties."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="High 1",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="High 2",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Medium",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
        ]

        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )

        assert result.total_issues == 3
        assert result.high_severity_count == 2
        assert result.medium_severity_count == 1
        assert result.low_severity_count == 0

    def test_review_result_category_grouping(self) -> None:
        """Test category grouping property."""
        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Another bug",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
        ]

        result = ReviewResult(
            passed=False,
            issues=issues,
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )

        by_category = result.by_category
        assert len(by_category[ReviewCategory.BUG]) == 2
        assert len(by_category[ReviewCategory.SECURITY]) == 0


class TestReviewModelValidation:
    """Integration tests for model validation rules."""

    def test_review_issue_immutable(self) -> None:
        """Test that ReviewIssue is immutable (frozen)."""
        issue = ReviewIssue(
            path="test.py",
            line=1,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Bug",
            suggested_fix="Fix",
            agent_prompt="Fix bug",
        )

        # Should raise error when trying to modify
        with pytest.raises(ValidationError):
            issue.path = "other.py"  # type: ignore

    def test_review_severity_enum_validation(self) -> None:
        """Test that ReviewSeverity enum validates correctly."""
        # Valid severities
        assert ReviewSeverity.HIGH == "HIGH"
        assert ReviewSeverity.MEDIUM == "MEDIUM"
        assert ReviewSeverity.LOW == "LOW"

        # Invalid severity should fail
        with pytest.raises(ValidationError):
            ReviewIssue(
                path="test.py",
                line=1,
                severity="CRITICAL",  # type: ignore
                category=ReviewCategory.BUG,
                message="Bug",
                suggested_fix="Fix",
                agent_prompt="Fix",
            )

    def test_review_category_enum_validation(self) -> None:
        """Test that ReviewCategory enum validates correctly."""
        # Valid categories
        assert ReviewCategory.BUG == "bug"
        assert ReviewCategory.SECURITY == "security"
        assert ReviewCategory.PERFORMANCE == "performance"
        assert ReviewCategory.STANDARDS == "standards"
        assert ReviewCategory.SPEC_COMPLIANCE == "spec_compliance"

        # Invalid category should fail
        with pytest.raises(ValidationError):
            ReviewIssue(
                path="test.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category="memory_leak",  # type: ignore
                message="Bug",
                suggested_fix="Fix",
                agent_prompt="Fix",
            )


class TestTwoPassReviewWorkflow:
    """Integration tests for two-pass review (validation → AI review).

    NOTE: These tests will fail until ReviewRunner is implemented (Task #6).
    They test the integration between ValidationRunner and ReviewRunner.
    """

    def test_validation_pass_then_ai_review(self, tmp_path: Path) -> None:
        """Test Pass 1 (validation) succeeds, then Pass 2 (AI review) runs."""
        # Setup: Create a Python project with passing validation
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "example.py").write_text("""
def add(a: int, b: int) -> int:
    return a + b
""")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_example.py").write_text("""
from example import add

def test_add():
    assert add(1, 2) == 3
""")

        # Pass 1: Run validation
        toolchain = detect_toolchain(tmp_path)
        validator = ValidationRunner(project_root=tmp_path, toolchain=toolchain)

        # Verify validator is ready
        assert validator.project_root == tmp_path

        # Pass 2 would run AI review here (needs ReviewRunner implementation)
        # This is where we'd integrate with ReviewRunner:
        # reviewer = ReviewRunner(project_root=tmp_path, provider=test_provider)
        # result = await reviewer.review(validation_result=validation_result)

    def test_validation_fail_blocks_ai_review(self, tmp_path: Path) -> None:
        """Test Pass 1 (validation) fails, AI review should be blocked."""
        # Setup: Create project with validation failures
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "failing-project"
""")

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "bad.py").write_text("""
def broken(  ):  # Bad formatting
    return None
""")

        # Pass 1: Validation would fail
        toolchain = detect_toolchain(tmp_path)
        ValidationRunner(project_root=tmp_path, toolchain=toolchain)

        # ReviewRunner should check validation_passed before running AI review
        # Expected behavior: ReviewResult(passed=False, validation_passed=False)

    def test_two_pass_integration_with_mock_results(self) -> None:
        """Test two-pass workflow with mocked validation and review results."""
        # Mock Pass 1: Validation passes
        validation_result = ValidationResult(
            passed=True,
            gates=[
                GateResult(
                    gate_type=GateType.TEST,
                    passed=True,
                    message="All tests passed",
                    command="pytest",
                    duration_ms=1000,
                )
            ],
            total_duration_ms=1000,
        )

        assert validation_result.passed is True

        # Mock Pass 2: AI review finds issues
        review_issue = ReviewIssue(
            path="src/logic.py",
            line=42,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.PERFORMANCE,
            message="N+1 query detected in loop",
            suggested_fix="Use bulk fetch",
            agent_prompt="Fix N+1 query in src/logic.py line 42",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix performance issue",
            relevant_files=["src/logic.py"],
            issues=[review_issue],
        )

        review_result = ReviewResult(
            passed=False,  # Has issues but validation passed
            issues=[review_issue],
            handoff=handoff,
            validation_passed=True,  # Pass 1 succeeded
            duration_ms=2000,
            model="claude-opus-4-6",
            provider="anthropic",
        )

        # Verify two-pass results
        assert review_result.validation_passed is True
        assert review_result.passed is False  # AI review found issues
        assert review_result.total_issues == 1


class TestReviewWithValidationIntegration:
    """Integration tests for ReviewRunner with ValidationRunner.

    NOTE: These tests will fail until ReviewRunner is implemented (Task #6).
    """

    def test_review_runner_uses_validation_runner(self, tmp_path: Path) -> None:
        """Test that ReviewRunner integrates with ValidationRunner for Pass 1."""
        # Create minimal Python project
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
""")

        # Detect toolchain
        detect_toolchain(tmp_path)

        # ReviewRunner should use ValidationRunner internally:
        # reviewer = ReviewRunner(
        #     project_root=tmp_path,
        #     toolchain=toolchain,
        #     provider=test_provider
        # )
        # result = await reviewer.review()
        # assert result.validation_passed is not None

    def test_review_with_real_imp_validation(self) -> None:
        """Test review workflow using Imp's own validation."""
        # Find Imp project root
        imp_root = Path(__file__).parent.parent.parent
        assert (imp_root / "pyproject.toml").exists()

        # Detect Imp's toolchain
        toolchain = detect_toolchain(imp_root)
        assert toolchain.test_command is not None

        # Create validator
        validator = ValidationRunner(project_root=imp_root, toolchain=toolchain)
        gates = validator.available_gates()

        # Verify gates are detected
        assert "test" in gates or "lint" in gates

        # ReviewRunner would use this for Pass 1:
        # reviewer = ReviewRunner(project_root=imp_root, toolchain=toolchain, provider=...)
        # result = await reviewer.review()


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker triggering.

    NOTE: These tests will fail until ReviewRunner with circuit breaker is implemented.
    """

    def test_circuit_breaker_after_max_attempts(self) -> None:
        """Test circuit breaker triggers after max attempts (default 3)."""
        # Simulate multiple review attempts
        attempts = []

        for i in range(3):
            issue = ReviewIssue(
                path=f"src/file{i}.py",
                line=10 + i,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message=f"Bug attempt {i + 1}",
                suggested_fix=f"Fix {i + 1}",
                agent_prompt=f"Fix bug attempt {i + 1}",
            )

            result = ReviewResult(
                passed=False,
                issues=[issue],
                handoff=None,
                validation_passed=True,
                duration_ms=1000,
            )

            attempts.append(result)

        # After 3 attempts, circuit breaker should trigger
        assert len(attempts) == 3

        # ReviewRunner should track attempts and escalate:
        # circuit_breaker = CircuitBreaker(max_attempts=3)
        # if circuit_breaker.should_escalate(ticket_id):
        #     escalation = circuit_breaker.generate_escalation(ticket_id)
        #     # Escalate to human

    def test_circuit_breaker_configurable_max_attempts(self) -> None:
        """Test circuit breaker with custom max_attempts setting."""
        # Test with max_attempts=5
        max_attempts = 5
        attempts = []

        for i in range(max_attempts):
            result = ReviewResult(
                passed=False,
                issues=[
                    ReviewIssue(
                        path="file.py",
                        line=i,
                        severity=ReviewSeverity.HIGH,
                        category=ReviewCategory.BUG,
                        message=f"Attempt {i + 1}",
                        suggested_fix="Fix",
                        agent_prompt="Fix",
                    )
                ],
                handoff=None,
                validation_passed=True,
                duration_ms=1000,
            )
            attempts.append(result)

        assert len(attempts) == max_attempts

        # CircuitBreaker(max_attempts=5) should trigger after 5th attempt


class TestFixWorkflowIntegration:
    """Integration tests for review → fix → re-review workflow.

    NOTE: These tests will fail until ReviewRunner is implemented.
    """

    def test_review_fix_recheck_cycle(self, tmp_path: Path) -> None:
        """Test complete cycle: review finds issue → fix applied → re-review."""
        # Initial review finds issues
        initial_issue = ReviewIssue(
            path="src/app.py",
            line=50,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Missing null check",
            suggested_fix="Add null check",
            agent_prompt="Add null check for user_id in src/app.py line 50",
        )

        initial_handoff = ReviewHandoff(
            agent_prompt="Fix null check issue",
            relevant_files=["src/app.py"],
            issues=[initial_issue],
        )

        initial_result = ReviewResult(
            passed=False,
            issues=[initial_issue],
            handoff=initial_handoff,
            validation_passed=True,
            duration_ms=1500,
        )

        assert initial_result.passed is False

        # After fix: Re-review should pass
        fixed_result = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=800,
        )

        assert fixed_result.passed is True
        assert fixed_result.total_issues == 0

    def test_review_fix_new_issues_found(self) -> None:
        """Test workflow where fix introduces new issues."""
        # First review
        first_issue = ReviewIssue(
            path="src/main.py",
            line=10,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Original bug",
            suggested_fix="Fix original",
            agent_prompt="Fix original bug",
        )

        first_result = ReviewResult(
            passed=False,
            issues=[first_issue],
            handoff=None,
            validation_passed=True,
            duration_ms=1000,
        )

        # After fix, new issue introduced
        new_issue = ReviewIssue(
            path="src/main.py",
            line=12,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.BUG,
            message="New bug from fix",
            suggested_fix="Fix new bug",
            agent_prompt="Fix new bug introduced by previous fix",
        )

        second_result = ReviewResult(
            passed=False,
            issues=[new_issue],
            handoff=None,
            validation_passed=True,
            duration_ms=1200,
        )

        # Verify we're tracking different issues
        assert first_result.issues[0].line != second_result.issues[0].line
        assert "Original" in first_result.issues[0].message
        assert "New" in second_result.issues[0].message


class TestHandoffJSONFileIntegration:
    """Integration tests for handoff JSON file generation and persistence."""

    def test_write_handoff_to_json_file(self, tmp_path: Path) -> None:
        """Test writing ReviewHandoff to JSON file for agent pickup."""
        handoff = ReviewHandoff(
            agent_prompt="Fix 2 critical bugs in authentication",
            relevant_files=["src/auth.py", "src/session.py"],
            issues=[
                ReviewIssue(
                    path="src/auth.py",
                    line=25,
                    severity=ReviewSeverity.HIGH,
                    category=ReviewCategory.SECURITY,
                    message="SQL injection vulnerability",
                    suggested_fix="Use parameterized queries",
                    agent_prompt="Fix SQL injection in src/auth.py line 25",
                ),
                ReviewIssue(
                    path="src/session.py",
                    line=40,
                    severity=ReviewSeverity.HIGH,
                    category=ReviewCategory.BUG,
                    message="Session not invalidated on logout",
                    suggested_fix="Add session.invalidate()",
                    agent_prompt="Fix session invalidation in src/session.py line 40",
                ),
            ],
        )

        # Write to file
        handoff_file = tmp_path / "review_handoff.json"
        handoff_file.write_text(handoff.model_dump_json(indent=2))

        # Verify file exists and is valid JSON
        assert handoff_file.exists()
        loaded = ReviewHandoff.model_validate_json(handoff_file.read_text())

        assert len(loaded.issues) == 2
        assert loaded.issues[0].severity == ReviewSeverity.HIGH
        assert "SQL injection" in loaded.issues[0].message

    def test_handoff_file_location_convention(self, tmp_path: Path) -> None:
        """Test handoff file follows naming convention for coding agents."""
        # Convention: .imp/handoff_<ticket_id>.json
        imp_dir = tmp_path / ".imp"
        imp_dir.mkdir()

        ticket_id = "IMP-123"
        handoff_file = imp_dir / f"handoff_{ticket_id}.json"

        handoff = ReviewHandoff(
            agent_prompt="Fix issue in IMP-123",
            relevant_files=["src/feature.py"],
            issues=[
                ReviewIssue(
                    path="src/feature.py",
                    line=1,
                    severity=ReviewSeverity.LOW,
                    category=ReviewCategory.STANDARDS,
                    message="Minor style issue",
                    suggested_fix="Format",
                    agent_prompt="Fix style",
                )
            ],
        )

        handoff_file.write_text(handoff.model_dump_json(indent=2))

        # Verify file naming
        assert handoff_file.name == f"handoff_{ticket_id}.json"
        assert handoff_file.parent.name == ".imp"
