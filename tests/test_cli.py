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


def test_check_not_implemented() -> None:
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "not implemented" in result.output.lower()


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
