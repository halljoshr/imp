#!/usr/bin/env python3
"""Smoke test for review module.

This is a standalone script that validates the review module works
in the wild, not just in test harnesses.

Run with: uv run python tests/smoke/smoke_test_review.py

Exit codes:
- 0: All smoke tests passed
- 1: At least one smoke test failed
"""

import sys


def test_imports() -> bool:
    """Test that all review modules can be imported."""
    print("Testing imports...")

    try:
        from imp.review import (  # noqa: F401
            ReviewCategory,
            ReviewHandoff,
            ReviewIssue,
            ReviewResult,
            ReviewSeverity,
        )

        print("✓ All review modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_models() -> bool:
    """Test that review models work correctly."""
    print("\nTesting models...")

    try:
        from imp.review.models import (
            ReviewCategory,
            ReviewHandoff,
            ReviewIssue,
            ReviewResult,
            ReviewSeverity,
        )

        # Test ReviewSeverity enum
        assert ReviewSeverity.HIGH == "HIGH"
        assert ReviewSeverity.MEDIUM == "MEDIUM"
        assert ReviewSeverity.LOW == "LOW"

        # Test ReviewCategory enum
        assert ReviewCategory.BUG == "bug"
        assert ReviewCategory.SECURITY == "security"
        assert ReviewCategory.PERFORMANCE == "performance"
        assert ReviewCategory.STANDARDS == "standards"
        assert ReviewCategory.SPEC_COMPLIANCE == "spec_compliance"

        # Test ReviewIssue creation
        issue = ReviewIssue(
            path="src/example.py",
            line=42,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Variable `user_id` is None without null check",
            suggested_fix="Add null check before using `user_id`",
            agent_prompt=(
                "In src/example.py at line 42, the code uses `user_id` without "
                "checking if it's None. Add a null check before line 42."
            ),
        )
        assert issue.path == "src/example.py"
        assert issue.line == 42
        assert issue.severity == ReviewSeverity.HIGH

        # Test ReviewHandoff creation
        handoff = ReviewHandoff(
            agent_prompt="Fix the null check issue in src/example.py",
            relevant_files=["src/example.py"],
            issues=[issue],
        )
        assert len(handoff.issues) == 1
        assert len(handoff.relevant_files) == 1
        assert len(handoff.high_severity_issues) == 1

        # Test ReviewResult creation
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

        # Test ReviewResult with clean pass
        clean_result = ReviewResult(
            passed=True,
            issues=[],
            handoff=None,
            validation_passed=True,
            duration_ms=800,
        )
        assert clean_result.passed is True
        assert clean_result.total_issues == 0

        # Test JSON serialization
        json_data = result.model_dump()
        assert json_data["passed"] is False
        assert len(json_data["issues"]) == 1

        print("✓ Models work correctly")
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_severity_filtering() -> bool:
    """Test severity-based filtering."""
    print("\nTesting severity filtering...")

    try:
        from imp.review.models import (
            ReviewCategory,
            ReviewHandoff,
            ReviewIssue,
            ReviewSeverity,
        )

        # Create issues with different severities
        high_issue = ReviewIssue(
            path="a.py",
            line=1,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Critical bug",
            suggested_fix="Fix it",
            agent_prompt="Fix critical bug",
        )

        medium_issue = ReviewIssue(
            path="b.py",
            line=2,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.PERFORMANCE,
            message="Slow query",
            suggested_fix="Optimize",
            agent_prompt="Fix slow query",
        )

        low_issue = ReviewIssue(
            path="c.py",
            line=3,
            severity=ReviewSeverity.LOW,
            category=ReviewCategory.STANDARDS,
            message="Style issue",
            suggested_fix="Format",
            agent_prompt="Fix style",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix all issues",
            relevant_files=["a.py", "b.py", "c.py"],
            issues=[high_issue, medium_issue, low_issue],
        )

        # Test severity filters
        assert len(handoff.high_severity_issues) == 1
        assert len(handoff.medium_severity_issues) == 1
        assert len(handoff.low_severity_issues) == 1
        assert handoff.high_severity_issues[0].path == "a.py"

        print("✓ Severity filtering works correctly")
        return True
    except Exception as e:
        print(f"✗ Severity filtering test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_category_filtering() -> bool:
    """Test category-based filtering."""
    print("\nTesting category filtering...")

    try:
        from imp.review.models import (
            ReviewCategory,
            ReviewHandoff,
            ReviewIssue,
            ReviewResult,
            ReviewSeverity,
        )

        # Create issues with different categories
        bug_issue = ReviewIssue(
            path="a.py",
            line=1,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Bug",
            suggested_fix="Fix",
            agent_prompt="Fix bug",
        )

        security_issue = ReviewIssue(
            path="b.py",
            line=2,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.SECURITY,
            message="Security flaw",
            suggested_fix="Fix",
            agent_prompt="Fix security",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix issues",
            relevant_files=["a.py", "b.py"],
            issues=[bug_issue, security_issue],
        )

        # Test category grouping
        by_category = handoff.by_category
        assert len(by_category[ReviewCategory.BUG]) == 1
        assert len(by_category[ReviewCategory.SECURITY]) == 1
        assert len(by_category[ReviewCategory.PERFORMANCE]) == 0

        # Test on ReviewResult
        result = ReviewResult(
            passed=False,
            issues=[bug_issue, security_issue],
            handoff=handoff,
            validation_passed=True,
            duration_ms=1000,
        )
        result_categories = result.by_category
        assert len(result_categories[ReviewCategory.BUG]) == 1

        print("✓ Category filtering works correctly")
        return True
    except Exception as e:
        print(f"✗ Category filtering test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_json_serialization() -> bool:
    """Test JSON serialization and deserialization."""
    print("\nTesting JSON serialization...")

    try:
        from imp.review.models import (
            ReviewCategory,
            ReviewHandoff,
            ReviewIssue,
            ReviewResult,
            ReviewSeverity,
        )

        # Create a complete review structure
        issue = ReviewIssue(
            path="test.py",
            line=10,
            severity=ReviewSeverity.MEDIUM,
            category=ReviewCategory.STANDARDS,
            message="Code style issue",
            suggested_fix="Reformat code",
            agent_prompt="Fix code style in test.py",
        )

        handoff = ReviewHandoff(
            agent_prompt="Fix style issues",
            relevant_files=["test.py"],
            issues=[issue],
        )

        result = ReviewResult(
            passed=False,
            issues=[issue],
            handoff=handoff,
            validation_passed=True,
            duration_ms=1200,
            model="test-model",
            provider="test-provider",
        )

        # Serialize to dict
        result_dict = result.model_dump()
        assert result_dict["passed"] is False
        assert len(result_dict["issues"]) == 1

        # Serialize to JSON string
        result_json = result.model_dump_json()
        assert "test.py" in result_json

        # Deserialize from JSON
        restored = ReviewResult.model_validate_json(result_json)
        assert restored.passed == result.passed
        assert len(restored.issues) == len(result.issues)
        assert restored.handoff is not None
        assert restored.handoff.agent_prompt == handoff.agent_prompt

        print("✓ JSON serialization works correctly")
        return True
    except Exception as e:
        print(f"✗ JSON serialization test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_model_immutability() -> bool:
    """Test that ReviewIssue is immutable."""
    print("\nTesting model immutability...")

    try:
        from imp.review.models import ReviewCategory, ReviewIssue, ReviewSeverity

        issue = ReviewIssue(
            path="test.py",
            line=1,
            severity=ReviewSeverity.HIGH,
            category=ReviewCategory.BUG,
            message="Bug",
            suggested_fix="Fix",
            agent_prompt="Fix bug",
        )

        # Attempt to modify should fail
        try:
            issue.path = "other.py"  # type: ignore
            # If we get here, immutability failed
            print("✗ ReviewIssue is not immutable")
            return False
        except Exception:
            # Expected to raise an error
            pass

        print("✓ Model immutability works correctly")
        return True
    except Exception as e:
        print(f"✗ Model immutability test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_review_result_properties() -> bool:
    """Test ReviewResult computed properties."""
    print("\nTesting ReviewResult properties...")

    try:
        from imp.review.models import (
            ReviewCategory,
            ReviewIssue,
            ReviewResult,
            ReviewSeverity,
        )

        issues = [
            ReviewIssue(
                path="a.py",
                line=1,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.BUG,
                message="Bug 1",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="b.py",
                line=2,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                message="Security issue",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="c.py",
                line=3,
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.PERFORMANCE,
                message="Performance issue",
                suggested_fix="Fix",
                agent_prompt="Fix",
            ),
            ReviewIssue(
                path="d.py",
                line=4,
                severity=ReviewSeverity.LOW,
                category=ReviewCategory.STANDARDS,
                message="Style issue",
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

        # Test counts
        assert result.total_issues == 4
        assert result.high_severity_count == 2
        assert result.medium_severity_count == 1
        assert result.low_severity_count == 1

        # Test validation property
        assert result.failed_validation is False

        # Test failed validation
        failed_validation = ReviewResult(
            passed=False,
            issues=[],
            handoff=None,
            validation_passed=False,
            duration_ms=100,
        )
        assert failed_validation.failed_validation is True

        print("✓ ReviewResult properties work correctly")
        return True
    except Exception as e:
        print(f"✗ ReviewResult properties test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main() -> int:
    """Run all smoke tests."""
    print("=" * 60)
    print("Review Module Smoke Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_models,
        test_severity_filtering,
        test_category_filtering,
        test_json_serialization,
        test_model_immutability,
        test_review_result_properties,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All smoke tests passed!")
        return 0
    else:
        print("\n❌ Some smoke tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
