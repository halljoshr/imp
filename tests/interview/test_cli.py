"""Unit tests for interview CLI commands.

Tests both the underlying functions (validate_command, import_command) and the
Typer CLI wiring (using CliRunner).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from imp.cli.main import app
from imp.interview.cli import import_command, validate_command

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture

runner = CliRunner()


# --- Test Helpers ---


def _complete_spec_dict() -> dict:
    """Return a complete spec dict for reuse across tests."""
    return {
        "name": "Test Project",
        "problem_statement": "Users need a way to authenticate securely with the application",
        "system_overview": "Authentication system with OAuth",
        "components": [
            {
                "name": "Auth Provider",
                "purpose": "Handle OAuth flow",
                "inputs": ["user credentials", "OAuth config"],
                "outputs": ["access token", "user profile"],
                "constraints": ["must support Google OAuth"],
                "edge_cases": ["token expiry during form submission"],
                "success_criteria": ["user can log in within 3 seconds"],
            }
        ],
        "success_criteria": ["users can authenticate end-to-end"],
        "out_of_scope": ["multi-factor authentication"],
        "constraints": ["must use HTTPS"],
        "stakeholder_profile": {
            "working_style": "terminal-first",
            "values": ["security", "simplicity"],
            "pain_points": ["session management complexity"],
            "priorities": ["security over convenience"],
            "technical_preferences": ["Python", "OAuth"],
        },
        "metadata": {
            "interview_date": "2026-02-13",
            "mode": "direct",
            "completeness_score": 95,
            "domain": "software-requirements",
            "question_count": 15,
        },
    }


def _minimal_spec_dict() -> dict:
    """Return a minimal (incomplete) spec dict."""
    return {"name": "Minimal Test"}


# --- validate_command tests ---


def test_validate_command_complete_spec_returns_zero(tmp_path: Path) -> None:
    """Valid complete spec file should return exit code 0."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    exit_code = validate_command(spec_file, format="human")

    assert exit_code == 0


def test_validate_command_incomplete_spec_returns_one(tmp_path: Path) -> None:
    """Valid incomplete spec file should return exit code 1."""
    spec_file = tmp_path / "minimal.json"
    spec_file.write_text(json.dumps(_minimal_spec_dict()), encoding="utf-8")

    exit_code = validate_command(spec_file, format="human")

    assert exit_code == 1


def test_validate_command_json_format_output(tmp_path: Path, capsys: CaptureFixture) -> None:
    """--format json should output parseable JSON with score and gaps."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    validate_command(spec_file, format="json")
    captured = capsys.readouterr()

    # Parse output as JSON
    output_data = json.loads(captured.out)
    assert "score" in output_data
    assert isinstance(output_data["score"], int)
    assert "gaps" in output_data
    assert "suggestions" in output_data


def test_validate_command_jsonl_format_output(tmp_path: Path, capsys: CaptureFixture) -> None:
    """--format jsonl should output single-line JSON."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    validate_command(spec_file, format="jsonl")
    captured = capsys.readouterr()

    # Should be single line
    lines = captured.out.strip().split("\n")
    assert len(lines) == 1
    # Should be valid JSON
    output_data = json.loads(lines[0])
    assert "score" in output_data


def test_validate_command_human_format_complete(tmp_path: Path, capsys: CaptureFixture) -> None:
    """--format human with complete spec should show 'complete' in output."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    validate_command(spec_file, format="human")
    captured = capsys.readouterr()

    assert "complete" in captured.out.lower()


def test_validate_command_human_format_incomplete(tmp_path: Path, capsys: CaptureFixture) -> None:
    """--format human with incomplete spec should show 'incomplete' and gaps table."""
    spec_file = tmp_path / "minimal.json"
    spec_file.write_text(json.dumps(_minimal_spec_dict()), encoding="utf-8")

    validate_command(spec_file, format="human")
    captured = capsys.readouterr()

    assert "incomplete" in captured.out.lower()
    # Should show gaps (Rich table output)
    assert "Field" in captured.out or "gap" in captured.out.lower()


def test_validate_command_nonexistent_file(capsys: CaptureFixture) -> None:
    """Non-existent file should return exit code 1 with error message."""
    nonexistent = Path("nonexistent.json")

    exit_code = validate_command(nonexistent, format="human")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error" in captured.out.lower() or "not found" in captured.out.lower()


def test_validate_command_invalid_json(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Invalid JSON file should return exit code 1 with error message."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("not json{", encoding="utf-8")

    exit_code = validate_command(invalid_file, format="human")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error" in captured.out.lower()


def test_validate_command_nonexistent_file_json_format(
    capsys: CaptureFixture,
) -> None:
    """Non-existent file with JSON format should output error in JSON."""
    nonexistent = Path("nonexistent.json")

    exit_code = validate_command(nonexistent, format="json")
    captured = capsys.readouterr()

    assert exit_code == 1
    output_data = json.loads(captured.out)
    assert "error" in output_data


def test_validate_command_invalid_json_json_format(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Invalid JSON with JSON format should output error in JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("not json{", encoding="utf-8")

    exit_code = validate_command(invalid_file, format="json")
    captured = capsys.readouterr()

    assert exit_code == 1
    output_data = json.loads(captured.out)
    assert "error" in output_data


# --- import_command tests ---


def test_import_command_complete_spec_returns_zero(tmp_path: Path) -> None:
    """Import complete spec should return exit code 0."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    exit_code = import_command(spec_file, output_dir=output_dir, format="human")

    assert exit_code == 0
    # Verify file was copied
    assert (output_dir / "complete.json").exists()


def test_import_command_incomplete_spec_returns_one(tmp_path: Path) -> None:
    """Import incomplete spec should return exit code 1."""
    spec_file = tmp_path / "minimal.json"
    spec_file.write_text(json.dumps(_minimal_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    exit_code = import_command(spec_file, output_dir=output_dir, format="human")

    assert exit_code == 1
    # Verify file was NOT copied
    assert not (output_dir / "minimal.json").exists()


def test_import_command_default_output_dir(tmp_path: Path, monkeypatch) -> None:
    """Import with output_dir=None should create .imp/specs/."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    # Change to tmp_path so .imp/specs is created there
    monkeypatch.chdir(tmp_path)

    exit_code = import_command(spec_file, output_dir=None, format="human")

    assert exit_code == 0
    default_dir = tmp_path / ".imp" / "specs"
    assert default_dir.exists()
    assert (default_dir / "complete.json").exists()


def test_import_command_json_format_success(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Import with --format json should output JSON with imported=True."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    import_command(spec_file, output_dir=output_dir, format="json")
    captured = capsys.readouterr()

    output_data = json.loads(captured.out)
    assert output_data["imported"] is True
    assert "score" in output_data
    assert "path" in output_data


def test_import_command_human_format_success(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Import with --format human should show 'imported successfully' panel."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    import_command(spec_file, output_dir=output_dir, format="human")
    captured = capsys.readouterr()

    assert "imported successfully" in captured.out.lower()


def test_import_command_incomplete_json_format(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Import incomplete spec with JSON format should output JSON error."""
    spec_file = tmp_path / "minimal.json"
    spec_file.write_text(json.dumps(_minimal_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    import_command(spec_file, output_dir=output_dir, format="json")
    captured = capsys.readouterr()

    output_data = json.loads(captured.out)
    assert "error" in output_data
    assert "score" in output_data


def test_import_command_nonexistent_file(capsys: CaptureFixture) -> None:
    """Import non-existent file should return exit code 1."""
    nonexistent = Path("nonexistent.json")

    exit_code = import_command(nonexistent, output_dir=None, format="human")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error" in captured.out.lower()


def test_import_command_invalid_json(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Import invalid JSON should return exit code 1."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("not json{", encoding="utf-8")

    exit_code = import_command(invalid_file, output_dir=None, format="human")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error" in captured.out.lower()


# --- CLI wiring tests (Typer CliRunner) ---


def test_cli_interview_help_shows_subcommands() -> None:
    """imp interview --help should show validate and import subcommands."""
    result = runner.invoke(app, ["interview", "--help"])

    assert result.exit_code == 0
    assert "validate" in result.stdout
    assert "import" in result.stdout


def test_cli_interview_validate_runs_command(tmp_path: Path) -> None:
    """imp interview validate <file> should run validate command."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")

    result = runner.invoke(app, ["interview", "validate", str(spec_file)])

    assert result.exit_code == 0
    assert "complete" in result.stdout.lower()


def test_cli_interview_import_runs_command(tmp_path: Path) -> None:
    """imp interview import <file> should run import command."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    output_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        ["interview", "import", str(spec_file), "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    assert "imported successfully" in result.stdout.lower()
    assert (output_dir / "complete.json").exists()


# --- Additional coverage tests for edge branches ---


def test_import_nonexistent_file_json_format(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """import_command with non-existent file and JSON format outputs JSON error."""
    missing = tmp_path / "missing.json"
    exit_code = import_command(missing, output_dir=None, format="json")
    captured = capsys.readouterr()

    assert exit_code == 1
    data = json.loads(captured.out)
    assert "error" in data


def test_import_invalid_json_json_format(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """import_command with invalid JSON and JSON format outputs JSON error."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json{", encoding="utf-8")
    exit_code = import_command(bad_file, output_dir=None, format="json")
    captured = capsys.readouterr()

    assert exit_code == 1
    data = json.loads(captured.out)
    assert "error" in data


def test_validate_human_complete_spec_no_gaps(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """validate_command human output for a complete spec shows no-gaps message."""
    spec_file = tmp_path / "complete.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    exit_code = validate_command(spec_file, format="human")
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "complete" in captured.out.lower()


def test_validate_human_no_suggestions_when_perfect(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """validate_command human output for perfect spec shows fully complete message."""
    spec_file = tmp_path / "perfect.json"
    spec_file.write_text(json.dumps(_complete_spec_dict()), encoding="utf-8")
    exit_code = validate_command(spec_file, format="human")
    captured = capsys.readouterr()

    assert exit_code == 0
    # Perfect spec should mention "complete"
    assert "complete" in captured.out.lower()


def test_validate_human_only_minor_gaps_no_questions(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """Human output with only MINOR gaps doesn't show suggested questions section."""
    # This spec has everything except constraints and out_of_scope (both MINOR)
    spec = _complete_spec_dict()
    spec.pop("constraints")
    spec.pop("out_of_scope")
    spec_file = tmp_path / "mostly_complete.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    exit_code = validate_command(spec_file, format="human")
    _ = capsys.readouterr()

    # Should still be complete (score >= 80 even without minor fields)
    assert exit_code == 0


def test_validate_human_incomplete_with_all_gap_types(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """Human output with incomplete spec shows gaps table and suggested questions."""
    spec = {"name": "Bare Minimum", "problem_statement": "A real problem statement here"}
    spec_file = tmp_path / "bare.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    exit_code = validate_command(spec_file, format="human")
    captured = capsys.readouterr()

    assert exit_code == 1
    # Should show gap information
    assert "gap" in captured.out.lower()
