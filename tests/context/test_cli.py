"""Tests for context CLI commands."""

import json
from pathlib import Path

import pytest

# ===== CLI Tests =====


def test_init_command_human_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test init_command with human-readable output format."""
    from imp.context.cli import init_command

    # Create a minimal Python project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("def hello(): pass")

    # Run init_command
    exit_code = init_command(root=tmp_path, format="human")

    # Should succeed
    assert exit_code == 0

    # Should print output
    captured = capsys.readouterr()
    assert len(captured.out) > 0


def test_init_command_json_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test init_command with JSON output format."""
    from imp.context.cli import init_command

    # Create a minimal Python project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("def hello(): pass")

    # Run init_command
    exit_code = init_command(root=tmp_path, format="json")

    # Should succeed
    assert exit_code == 0

    # Should output valid JSON
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)


def test_init_command_jsonl_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test init_command with JSONL output format."""
    from imp.context.cli import init_command

    # Create a minimal Python project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("def hello(): pass")

    # Run init_command
    exit_code = init_command(root=tmp_path, format="jsonl")

    # Should succeed
    assert exit_code == 0

    # Should output JSONL (each line is valid JSON)
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(lines) > 0
    for line in lines:
        json.loads(line)  # Should not raise


def test_init_command_missing_root(capsys: pytest.CaptureFixture) -> None:
    """Test init_command with non-existent root directory."""
    from imp.context.cli import init_command

    # Use non-existent path
    nonexistent = Path("/nonexistent/path/that/does/not/exist")

    # Should fail
    exit_code = init_command(root=nonexistent, format="human")
    assert exit_code == 1

    # Should print error message
    captured = capsys.readouterr()
    assert "not exist" in captured.out.lower() or "error" in captured.out.lower()


def test_init_command_empty_project(tmp_path: Path) -> None:
    """Test init_command on an empty directory."""
    from imp.context.cli import init_command

    # Empty directory should still succeed (generates empty index)
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0


def test_init_command_creates_index_files(tmp_path: Path) -> None:
    """Test that init_command creates .index.md files."""
    from imp.context.cli import init_command

    # Create a simple Python project
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "module.py").write_text("def foo(): pass")

    # Run init
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0

    # Verify root .index.md exists
    root_index = tmp_path / ".index.md"
    assert root_index.exists()
    assert root_index.is_file()

    # Verify module .index.md exists
    module_index = src_dir / ".index.md"
    assert module_index.exists()
    assert module_index.is_file()


def test_init_command_creates_cache(tmp_path: Path) -> None:
    """Test that init_command creates .imp/scan.json cache file."""
    from imp.context.cli import init_command

    # Create a minimal Python project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("def hello(): pass")

    # Run init
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0

    # Verify .imp directory exists
    imp_dir = tmp_path / ".imp"
    assert imp_dir.exists()
    assert imp_dir.is_dir()

    # Verify scan.json cache exists
    cache_file = imp_dir / "scan.json"
    assert cache_file.exists()
    assert cache_file.is_file()

    # Verify cache is valid JSON
    cache_data = json.loads(cache_file.read_text())
    assert isinstance(cache_data, dict)


def test_init_command_missing_root_json_format(capsys: pytest.CaptureFixture) -> None:
    """Test init_command with non-existent root and JSON format."""
    from imp.context.cli import init_command

    nonexistent = Path("/nonexistent/path/that/does/not/exist")

    exit_code = init_command(root=nonexistent, format="json")
    assert exit_code == 1

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "error" in data
    assert "not exist" in data["error"].lower()


def test_init_command_exception_human_format(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test init_command error handling with human format when scan raises."""
    from unittest.mock import patch

    from imp.context.cli import init_command

    with patch("imp.context.cli.scan_and_parse", side_effect=RuntimeError("scan failed")):
        exit_code = init_command(root=tmp_path, format="human")

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "scan failed" in captured.out.lower()


def test_init_command_exception_json_format(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test init_command error handling with JSON format when scan raises."""
    from unittest.mock import patch

    from imp.context.cli import init_command

    with patch("imp.context.cli.scan_and_parse", side_effect=RuntimeError("scan failed")):
        exit_code = init_command(root=tmp_path, format="json")

    assert exit_code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "error" in data
    assert "scan failed" in data["error"]
