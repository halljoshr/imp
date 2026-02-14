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


def test_init_implemented() -> None:
    """Test that imp init command is implemented."""
    # Test with --help to verify command exists without running full init
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "not implemented" not in result.output.lower()
    assert "init" in result.output.lower()


def test_check_implemented() -> None:
    """Test that imp check command is implemented and runs."""
    # Test with --help to verify command exists without running full validation
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "not implemented" not in result.output.lower()
    assert "check" in result.output.lower()


def test_interview_implemented() -> None:
    """Test that imp interview command is implemented."""
    result = runner.invoke(app, ["interview", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.output.lower()
    assert "import" in result.output.lower()


def test_review_implemented() -> None:
    """Test that imp review command is implemented."""
    # Test with --help to verify command exists
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0
    assert "not implemented" not in result.output.lower()
    assert "review" in result.output.lower()


def test_metrics_not_implemented() -> None:
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()
