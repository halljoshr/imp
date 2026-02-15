"""Tests for context CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

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

    from imp.context.cli import init_command

    with patch("imp.context.cli.scan_and_parse", side_effect=RuntimeError("scan failed")):
        exit_code = init_command(root=tmp_path, format="human")

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "scan failed" in captured.out.lower()


def test_init_command_exception_json_format(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test init_command error handling with JSON format when scan raises."""

    from imp.context.cli import init_command

    with patch("imp.context.cli.scan_and_parse", side_effect=RuntimeError("scan failed")):
        exit_code = init_command(root=tmp_path, format="json")

    assert exit_code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "error" in data
    assert "scan failed" in data["error"]


# ===== Summarize Flag Tests =====


def test_init_command_summarize_flag(tmp_path: Path) -> None:
    """Test init_command with --summarize creates summaries."""
    from unittest.mock import AsyncMock

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    # Create a minimal project
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    # Mock the invoke function
    mock_invoke = AsyncMock(
        return_value=(
            "Source code module.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )
    )

    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0

    # Should have called AI for modules
    assert mock_invoke.call_count > 0

    # Should have saved summaries
    summaries_path = tmp_path / ".imp" / "summaries.json"
    assert summaries_path.exists()

    # Summaries should be valid JSON
    data = json.loads(summaries_path.read_text())
    assert isinstance(data, dict)
    assert len(data) > 0


def test_init_command_summarize_fills_purpose(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test init_command with --summarize fills purpose in indexes."""
    from unittest.mock import AsyncMock

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("class App: pass")

    mock_invoke = AsyncMock(
        return_value=(
            "Application entry point and core logic.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )
    )

    exit_code = init_command(
        root=tmp_path,
        format="json",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0

    # Root .index.md should contain the purpose
    root_index = (tmp_path / ".index.md").read_text()
    assert "Application entry point" in root_index


def test_init_command_summarize_uses_cache(tmp_path: Path) -> None:
    """Test init_command with --summarize uses cached summaries."""
    from unittest.mock import AsyncMock

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    mock_invoke = AsyncMock(
        return_value=(
            "First run summary.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )
    )

    # First run — should call AI
    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0
    first_call_count = mock_invoke.call_count

    # Second run — should use cached summaries (no new AI calls)
    mock_invoke.reset_mock()
    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0
    assert mock_invoke.call_count < first_call_count


def test_init_command_summarize_without_invoke_fn_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test init_command with --summarize but no invoke_fn returns error."""
    from imp.context.cli import init_command

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=None,
    )
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "provider" in captured.out.lower() or "invoke" in captured.out.lower()


def test_init_command_summarize_without_invoke_fn_json(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test init_command with --summarize but no invoke_fn returns JSON error."""
    from imp.context.cli import init_command

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    exit_code = init_command(
        root=tmp_path,
        format="json",
        summarize=True,
        model="test-model",
        invoke_fn=None,
    )
    assert exit_code == 1

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "error" in data


# ===== Staleness Detection Tests =====


def test_init_command_staleness_detection(tmp_path: Path) -> None:
    """Test that re-runs detect stale modules (file changes)."""
    from imp.context.cli import init_command

    # Create initial project
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    # First run — creates cache
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0
    assert (tmp_path / ".imp" / "scan.json").exists()

    # Second run — should succeed (incremental)
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0


def test_init_command_summarize_invalidates_stale_cache(tmp_path: Path) -> None:
    """Test that --summarize re-summarizes modules whose files changed."""

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    call_count = 0

    async def mock_invoke(prompt: str) -> tuple[str, TokenUsage]:
        nonlocal call_count
        call_count += 1
        return (
            f"Summary v{call_count}.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )

    # First run — should call AI
    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0
    first_call_count = call_count

    # Modify a file to trigger staleness (change content, not just mtime)
    (src_dir / "main.py").write_text("def hello(): pass\ndef world(): pass\n")

    # Second run — stale module should be re-summarized
    exit_code = init_command(
        root=tmp_path,
        format="human",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0
    # Should have made new AI calls for the stale module
    assert call_count > first_call_count


def test_init_command_jsonl_includes_summary_stats(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test JSONL output includes summary stats when --summarize is used."""
    from unittest.mock import AsyncMock

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    mock_invoke = AsyncMock(
        return_value=(
            "Source module.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )
    )

    exit_code = init_command(
        root=tmp_path,
        format="jsonl",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    lines = [json.loads(line) for line in captured.out.strip().split("\n") if line]
    summary_line = next(entry for entry in lines if entry.get("type") == "summary")
    assert "summarized_modules" in summary_line
    assert "summary_tokens" in summary_line


def test_init_command_json_includes_summary_stats(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test JSON output includes summary stats when --summarize is used."""
    from unittest.mock import AsyncMock

    from imp.context.cli import init_command
    from imp.types import TokenUsage

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello(): pass")

    mock_invoke = AsyncMock(
        return_value=(
            "Source module.",
            TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
        )
    )

    exit_code = init_command(
        root=tmp_path,
        format="json",
        summarize=True,
        model="test-model",
        invoke_fn=mock_invoke,
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "summarized_modules" in data
    assert "summary_tokens" in data
