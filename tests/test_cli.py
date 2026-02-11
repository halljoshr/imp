"""Smoke tests for the imp CLI."""

from typer.testing import CliRunner

from imp.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0-dev" in result.output


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "imp" in result.output.lower()


def test_subcommands_listed_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "check", "interview", "review", "metrics"):
        assert cmd in result.output


def test_init_not_implemented() -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()


def test_check_implemented() -> None:
    """Test that imp check command is implemented and runs."""
    result = runner.invoke(app, ["check"])
    # Exit code 1 means validation failed (which is expected - may have lint/type issues)
    # Exit code 0 means validation passed
    # Either is valid - what matters is that it ran
    assert result.exit_code in (0, 1)
    # Should show validation output, not "not implemented"
    assert "not implemented" not in result.output.lower()
    # Should show gate results or validation output
    assert "validation" in result.output.lower() or "gate" in result.output.lower()


def test_interview_not_implemented() -> None:
    result = runner.invoke(app, ["interview"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()


def test_review_not_implemented() -> None:
    result = runner.invoke(app, ["review"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()


def test_metrics_not_implemented() -> None:
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()
